import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { sql } from 'kysely';
import { CreateBucketCommand } from '@aws-sdk/client-s3';
import { MessageContext, RuntimeConfigStore, ServiceApp, makeDefaultSerdeRegistry, SubStreamCollectorFunc } from '@gorundebug/tsservicelib/runtime';
import { Config } from '../dist/internal/config/config.js';
import { defaultMakers, initFunctionsParallel, initStreams, registerGeneratedSerdes, ServiceSubStreams } from '../dist/internal/app/graph.generated.js';
import { defaultInfrastructureMakers, initInfrastructure } from '../dist/internal/app/infrastructure-makers.generated.js';
import { ServiceClients } from '../dist/internal/app/clients.generated.js';
import { ServiceServers } from '../dist/internal/app/servers.generated.js';
import { ServiceConnectors } from '../dist/internal/app/connectors.generated.js';
import { ServiceEndpoints } from '../dist/internal/app/endpoints.generated.js';

await test('all eight generated SubStreams with disposable PostgreSQL and S3', {
  skip: process.env.SA_QUERY_DISPOSABLE !== '1', timeout: 15000,
}, async () => {
  const directory = await mkdtemp(join(tmpdir(), 'sa-query-ts-live-'));
  const context = new MessageContext();
  const connectors = new ServiceConnectors();
  try {
    const pgPort = Number(process.env.SA_QUERY_PG_PORT), s3Port = Number(process.env.SA_QUERY_S3_PORT);
    assert.ok(Number.isInteger(pgPort) && pgPort > 0 && pgPort < 65536);
    assert.ok(Number.isInteger(s3Port) && s3Port > 0 && s3Port < 65536);
    const cfgPath = join(directory, 'config.json'), empty = join(directory, 'values.json');
    await writeFile(cfgPath, JSON.stringify({ dataConnectors: {
      database: { connectionString: `postgresql://postgres@127.0.0.1:${pgPort}/query_example` },
      objects: { address: `http://127.0.0.1:${s3Port}`, forcePathStyle: true }
    } }));
    await writeFile(empty, '{}');
    const config = await Config.load(['--config', cfgPath, '--values', empty]);
    const serdeRegistry = makeDefaultSerdeRegistry();
    registerGeneratedSerdes(serdeRegistry);
    const app = new ServiceApp(new RuntimeConfigStore(config.runtime), 1, { serdeRegistry });
    const env = app.environment();
    const makers = defaultMakers(), clients = new ServiceClients();
    await initInfrastructure(context, config, env, defaultInfrastructureMakers(), new ServiceServers(), clients, connectors);
    const pg = connectors.databaseQueryConnector, s3 = connectors.objectsQueryConnector;
    await pg.start(context);
    await s3.start(context);
    // Explicit disposable fixture provisioning; never run by business handlers.
    await sql`CREATE TABLE query_example_items (key text PRIMARY KEY, value bytea NOT NULL)`.execute(pg.db);
    await s3.client().send(new CreateBucketCommand({ Bucket: 'query-example', CreateBucketConfiguration: { LocationConstraint: 'eu-west-1' } }));
    const functions = await initFunctionsParallel(context, config, env, makers);
    const streams = initStreams(config, env, functions);
    const accessors = new ServiceSubStreams();
    accessors.bindSubStreams(streams);
    new ServiceEndpoints().bind(streams, functions, clients, makers);
    async function call(operation, key = 'object', value = Buffer.alloc(0), requestId = operation) {
      const results = [];
      await accessors[`get${operation}RequestSubStream`]().consume(context.bounded(5000), { requestId, key, value }, new SubStreamCollectorFunc((_ctx, result) => {
        results.push(result);
        return result.kind === 'completed';
      }));
      assert.equal(results.at(-1).kind, 'completed');
      assert.ok(results.every(result => result.requestId === requestId));
      return results.slice(0, -1);
    }
    const bytes = Buffer.alloc(262400);
    for (let i = 0; i < bytes.length; i++) bytes[i] = i % 256;
    const key = "key'; quoted";
    assert.deepEqual(Buffer.from((await call('Returning', "returning-'key", bytes))[0].value), bytes);
    assert.deepEqual(Buffer.from((await call('Rows', "returning-'key"))[0].value), bytes);
    assert.deepEqual(await call('Rows', key), []);
    assert.equal(Buffer.from((await call('Execute', key, bytes))[0].value).toString(), '1');
    assert.deepEqual(Buffer.from((await call('Rows', key))[0].value), bytes);
    await call('Execute', key, Buffer.from('updated\0'));
    assert.deepEqual(Buffer.from((await call('Rows', key))[0].value), Buffer.from('updated\0'));
    await call('PutObject', 'object', bytes);
    assert.equal(JSON.parse(Buffer.from((await call('HeadObject'))[0].value).toString()).size, bytes.length);
    assert.deepEqual(Buffer.concat((await call('GetObject')).map(result => result.value)), bytes);
    const pages = await call('ListObjects');
    assert.deepEqual(pages.flatMap(page => JSON.parse(Buffer.from(page.value).toString())), [{ key: 'object', size: bytes.length }]);
    const concurrent = await Promise.all(Array.from({length: 4}, (_, i) => call('GetObject', 'object', Buffer.alloc(0), `parallel-${i}`)));
    for (const results of concurrent) assert.deepEqual(Buffer.concat(results.map(result => result.value)), bytes);
    await call('PutObject', 'empty');
    assert.deepEqual(await call('GetObject', 'empty'), []);
    async function failure(operation, key, cancelLockedSQL = false) {
      const name = operation[0].toLowerCase() + operation.slice(1) + 'Query';
      const handler = functions[name], original = handler.endRequest.bind(handler);
      const received = [], outcomes = [];
      let finish;
      const ended = new Promise(resolve => { finish = resolve; });
      handler.endRequest = async (...args) => {
        outcomes.push(args[3]);
        try { await original(...args); } finally { finish(); }
      };
      const abort = new AbortController();
      const task = accessors[`get${operation}RequestSubStream`]().consume(
        context.withExternalCancellation(abort.signal).bounded(5000),
        { requestId: 'failure', key, value: Buffer.alloc(0) },
        new SubStreamCollectorFunc((_ctx, result) => { received.push(result); return result.kind === 'completed'; })
      ).then(() => undefined, error => error);
      try {
        if (cancelLockedSQL) {
          const deadline = Date.now() + 1000;
          let waiting = false;
          while (Date.now() < deadline && outcomes.length === 0) {
            const probe = await sql`SELECT count(*) AS count FROM pg_stat_activity WHERE datname = current_database() AND wait_event_type = 'Lock' AND state = 'active'`.execute(pg.db);
            if (Number(probe.rows[0].count) > 0) { waiting = true; break; }
            await new Promise(resolve => setTimeout(resolve, 10));
          }
          assert.ok(waiting, 'SQL must be in flight before cancellation');
          abort.abort(new Error('cancel live query'));
        }
        await ended;
        assert.equal(outcomes.length, 1);
        assert.ok(outcomes[0] instanceof Error);
        assert.ok(!received.some(result => result.kind === 'completed'));
        return outcomes[0];
      } finally {
        abort.abort();
        await task;
        handler.endRequest = original;
      }
    }
    assert.equal((await failure('GetObject', 'not-present')).name, 'NoSuchKey');
    await sql`ALTER TABLE query_example_items RENAME TO query_example_hidden`.execute(pg.db);
    try { assert.equal((await failure('Rows', key)).code, '42P01'); }
    finally { await sql`ALTER TABLE query_example_hidden RENAME TO query_example_items`.execute(pg.db); }
    await pg.db.transaction().execute(async transaction => {
      await sql`LOCK TABLE query_example_items IN ACCESS EXCLUSIVE MODE`.execute(transaction);
      assert.equal((await failure('Rows', key, true)).message, 'cancel live query');
    });
    assert.deepEqual(Buffer.from((await call('Rows', key))[0].value), Buffer.from('updated\0'));
    assert.deepEqual(Buffer.concat((await call('GetObject')).map(result => result.value)), bytes);
    await call('DeleteObject');
    assert.deepEqual((await call('ListObjects')).flatMap(page => JSON.parse(Buffer.from(page.value).toString())), []);
  } finally {
    await connectors.objectsQueryConnector?.stop(context);
    await connectors.databaseQueryConnector?.stop(context);
    await rm(directory, { recursive: true, force: true });
  }
});
