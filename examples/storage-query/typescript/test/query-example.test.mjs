import assert from 'node:assert/strict';
import { test } from 'node:test';
import { Readable } from 'node:stream';
import { Kysely, PostgresAdapter, PostgresQueryCompiler } from 'kysely';
import { S3Client } from '@aws-sdk/client-s3';
import { MessageContext } from '@gorundebug/tsservicelib/runtime/graph';
import * as pg from '@gorundebug/tsservicelib/dataquery/postgresqlkysely';
import * as s3 from '@gorundebug/tsservicelib/dataquery/s3aws';

function stream() {
  const results = [], errors = [];
  return { results, errors, runtimeEnvironment: () => ({ metrics: () => ({ enabled: () => false }) }), setQueryConsumer() {},
    consumeResult(_context, value) { results.push(value); },
    errorStream() { return { emit(_context, error) { errors.push(error); } }; } };
}
async function handler(name) {
  const module = await import(`../dist/internal/functions/${name}-query.js`);
  const symbol = name.split('-').map(x => x[0].toUpperCase() + x.slice(1)).join('') + 'Query';
  return new module[symbol]();
}
const request = { requestId: 'request', key: "key'; --", value: Buffer.from('payload') };

await test('PostgreSQL read, returning and command consumers use compiled Kysely queries and release before completion', async () => {
  for (const operation of ['rows', 'returning', 'execute']) {
    let released = 0;
    const queries = [];
    const connection = {
      async executeQuery(query) { queries.push(query); return { rows: [], numAffectedRows: 1n }; },
      async *streamQuery(query) {
        queries.push(query);
        yield { rows: [{ value: Buffer.from('one') }, { value: Buffer.from('two') }] };
      }
    };
    const db = new Kysely({ dialect: {
      createAdapter: () => new PostgresAdapter(),
      createQueryCompiler: () => new PostgresQueryCompiler(),
      createIntrospector() { throw new Error('No schema introspection in handlers'); },
      createDriver: () => ({ async init() {}, async acquireConnection() { return connection; },
        async releaseConnection() { released++; }, async destroy() {} })
    } });
    try {
      const output = stream();
      const save = output.consumeResult;
      output.consumeResult = (ctx, value) => {
        if (value.kind === 'completed') assert.equal(released, 1);
        save(ctx, value);
      };
      const factory = operation !== 'execute' ? pg.makeRowsEndpointConsumer : pg.makeExecuteEndpointConsumer;
      await factory(output, db, await handler(operation)).consume(new MessageContext(), request);
      assert.deepEqual(output.errors, []);
      assert.equal(output.results.at(-1).kind, 'completed');
      assert.ok(output.results.every(x => x.requestId === request.requestId));
      assert.ok(!queries[0].sql.includes(request.key));
      assert.equal(queries[0].parameters[0], request.key);
      assert.deepEqual(output.results.slice(0, -1).map(x => Buffer.from(x.value).toString()), operation !== 'execute' ? ['one', 'two'] : ['1']);
    } finally { await db.destroy(); }
  }
});

await test('all five S3 consumers use native AWS request/response mapping', async () => {
  const client = new S3Client({ region: 'eu-west-1', endpoint: 'https://s3.example.invalid',
    forcePathStyle: true, maxAttempts: 1, credentials: { accessKeyId: 'test', secretAccessKey: 'test' },
    requestHandler: { async handle(request) {
      let body = 'payload', headers = {}, statusCode = 200;
      if (request.query['list-type'] === '2') {
        headers['content-type'] = 'application/xml';
        body = request.query['continuation-token'] === 'next'
          ? '<ListBucketResult><IsTruncated>false</IsTruncated></ListBucketResult>'
          : '<ListBucketResult><IsTruncated>true</IsTruncated><NextContinuationToken>next</NextContinuationToken><Contents><Key>first</Key><Size>7</Size></Contents></ListBucketResult>';
      } else if (request.method === 'HEAD') { body = ''; headers['content-length'] = '7'; }
      else if (request.method === 'PUT') { body = ''; headers.etag = 'tag'; }
      else if (request.method === 'DELETE') { body = ''; statusCode = 204; }
      return { response: { statusCode, headers, body: Readable.from([Buffer.from(body)]) } };
    } }
  });
  try {
    for (const name of ['get-object', 'head-object', 'list-objects', 'put-object', 'delete-object']) {
      const output = stream();
      const method = 'make' + name.split('-').map(x => x[0].toUpperCase() + x.slice(1)).join('') + 'EndpointConsumer';
      await s3[method](output, client, await handler(name)).consume(new MessageContext(), request);
      assert.deepEqual(output.errors, [], name);
      assert.equal(output.results.at(-1).kind, 'completed', name);
      assert.ok(output.results.every(x => x.requestId === request.requestId));
      assert.equal(output.results.length, name === 'list-objects' ? 3 : 2);
      if (name === 'get-object') assert.equal(Buffer.from(output.results[0].value).toString(), 'payload');
      if (name === 'list-objects') assert.equal(Buffer.from(output.results[1].value).toString(), '[]');
    }
  } finally { client.destroy(); }
});
