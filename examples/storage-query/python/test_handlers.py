"""Lightweight native-boundary checks; not a PostgreSQL/S3 server acceptance test.

Run with the generated and overlaid service src plus pyservicelib/src on PYTHONPATH.
"""
import importlib
import json
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy.dialects import postgresql
from storage_worker.models.storage_request import StorageRequest
from pyservicelib_gorundebug.dataquery import postgresqlsqlalchemy as pg, s3aws as s3


class Stream:
    from pyservicelib_gorundebug.runtime.environment.metrics import NoopMetrics
    environment = SimpleNamespace(metrics=NoopMetrics())
    def __init__(self):
        self.results = []
        self.errors = []
        self.error_stream = SimpleNamespace(consume=AsyncMock(side_effect=self.errors.append))
    async def consume_result(self, value):
        self.results.append(value)
    def set_query_consumer(self, consumer):
        self.consumer = consumer


def handler(name):
    module = importlib.import_module(f"storage_worker.internal.functions.{name}_query")
    return getattr(module, ''.join(word.title() for word in name.split('_')) + 'Query')()


class Handlers(unittest.IsolatedAsyncioTestCase):
    async def test_generated_function_makers(self):
        from storage_worker.internal.app.makers_generated import ServiceMakers
        from storage_worker.internal.app.functions_generated import ServiceFunctions
        from pyservicelib_gorundebug.runtime.context.context import Context
        functions = await ServiceFunctions.init_functions(Context(), SimpleNamespace(), ServiceMakers())
        for name in ('rows', 'returning', 'execute', 'get_object', 'head_object', 'list_objects', 'put_object', 'delete_object'):
            implementation = getattr(functions, name + '_query')
            self.assertIs(type(implementation), type(handler(name)))
            first = await implementation.begin_request(None)
            second = await implementation.begin_request(None)
            self.assertIsNot(first.state, second.state)

    async def test_postgres_builders_and_lifecycle(self):
        for name in ('rows', 'returning', 'execute'):
            with self.subTest(name=name):
                closed = []
                statements = []
                class Rows:
                    def __aiter__(self):
                        async def iterate():
                            for value in (b'one', b'two'):
                                yield SimpleNamespace(_mapping={'value': value})
                        return iterate()
                @asynccontextmanager
                async def stream(statement, parameters, **kwargs):
                    statements.append((statement, parameters))
                    try:
                        yield Rows()
                    finally:
                        closed.append('cursor')
                async def execute(statement, parameters):
                    statements.append((statement, parameters))
                    return SimpleNamespace(rowcount=1, close=lambda: closed.append('result'))
                @asynccontextmanager
                async def begin():
                    yield SimpleNamespace(stream=stream, execute=execute)
                    closed.append('transaction')
                output = Stream()
                consumer = getattr(pg, f'make_{"rows" if name == "returning" else name}_endpoint_consumer')(
                    output, SimpleNamespace(begin=begin), handler(name))
                await consumer.consume(StorageRequest('request', "x'; DROP TABLE x;--", b'value'))
                self.assertEqual([], output.errors)
                self.assertEqual('completed', output.results[-1].kind)
                self.assertTrue(all(item.request_id == 'request' for item in output.results))
                sql = str(statements[0][0].compile(dialect=postgresql.dialect()))
                self.assertNotIn('DROP TABLE', sql)
                self.assertEqual("x'; DROP TABLE x;--", statements[0][1]['key'])
                self.assertIn('transaction', closed)
                self.assertIn('cursor' if name in ('rows', 'returning') else 'result', closed)
                self.assertEqual([b'one', b'two'] if name in ('rows', 'returning') else [b'1'],
                                 [item.value for item in output.results[:-1]])

    async def test_all_s3_operations(self):
        for name in ('get_object', 'head_object', 'list_objects', 'put_object', 'delete_object'):
            with self.subTest(name=name):
                closed = []
                class Body:
                    def __init__(self):
                        self.parts = iter([b'one', b'two', b''])
                    async def __aenter__(self): return self
                    async def __aexit__(self, *args): closed.append('body')
                    async def read(self, size): return next(self.parts)
                async def pages(**kwargs):
                    self.assertEqual('key', kwargs['Prefix'])
                    yield {'Contents': [{'Key': 'key1', 'Size': 3}]}
                    yield {}
                native = SimpleNamespace(
                    meta=SimpleNamespace(config=SimpleNamespace(retries={'total_max_attempts': 1})),
                    get_object=AsyncMock(return_value={'Body': Body()}),
                    head_object=AsyncMock(return_value={'ContentLength': 6, 'ETag': 'tag'}),
                    put_object=AsyncMock(return_value={'ETag': 'tag'}),
                    delete_object=AsyncMock(return_value={}),
                    get_paginator=lambda op: SimpleNamespace(paginate=pages))
                output = Stream()
                consumer = getattr(s3, f'make_{name}_endpoint_consumer')(output, native, handler(name))
                await consumer.consume(StorageRequest('request', 'key', b'payload'))
                self.assertEqual([], output.errors)
                self.assertEqual('completed', output.results[-1].kind)
                self.assertTrue(all(item.request_id == 'request' for item in output.results))
                if name == 'get_object':
                    self.assertEqual(['body'], closed)
                    self.assertEqual([b'one', b'two'], [item.value for item in output.results[:-1]])
                elif name == 'list_objects':
                    self.assertEqual([[{'key': 'key1', 'size': 3}], []],
                                     [json.loads(item.value) for item in output.results[:-1]])
                elif name == 'put_object':
                    native.put_object.assert_awaited_once_with(Bucket='query-example', Key='key', Body=b'payload')

    async def test_empty_object_and_missing_object_are_distinct(self):
        class EmptyBody:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def read(self, size): return b''
        for error in (None, RuntimeError('NoSuchKey')):
            output = Stream()
            native = SimpleNamespace(
                meta=SimpleNamespace(config=SimpleNamespace(retries={'total_max_attempts': 1})),
                get_object=AsyncMock(return_value={'Body': EmptyBody()}, side_effect=error))
            consumer = s3.make_get_object_endpoint_consumer(output, native, handler('get_object'))
            await consumer.consume(StorageRequest('request', 'key'))
            self.assertEqual([] if error else ['completed'], [x.kind for x in output.results])
            self.assertEqual([error] if error else [], output.errors)


if __name__ == '__main__':
    unittest.main()
