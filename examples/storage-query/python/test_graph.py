"""Generated SubStream -> Query -> return wiring, with substituted native I/O.

Uses the same PYTHONPATH and user-owned overlay as test_handlers.py. Does not
start listeners, provision resources or claim live PostgreSQL/S3 acceptance.
"""
import asyncio
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from storage_worker.internal.app.service import Service
from storage_worker.internal.config import Config
from storage_worker.models.storage_request import StorageRequest
from pyservicelib_gorundebug.runtime.context.context import Context
from pyservicelib_gorundebug.runtime.common import SubStreamCollectorFunc
from pyservicelib_gorundebug.runtime.environment.metrics.metrics import NoopMetricsEngine
from pyservicelib_gorundebug.dataquery.postgresqlsqlalchemy.connector import Connector as PGConnector
from pyservicelib_gorundebug.dataquery.s3aws.connector import Connector as S3Connector


class LocalService(Service):
    @property
    def tracing(self):
        return None


class GeneratedGraph(unittest.IsolatedAsyncioTestCase):
    async def test_all_generated_substream_routes(self):
        service = LocalService()
        service._config = Config.from_dict({"dataConnectors": {"database": {"connectionString": "postgresql://test@localhost/query_example"}}})
        service._serviceConfig = service._config.get_service_config_by_id(1)
        service._id = 1
        service._metrics_engine = NoopMetricsEngine()
        lifecycle = []
        class Rows:
            def __aiter__(self):
                async def iterate():
                    yield SimpleNamespace(_mapping={'value': b'one'})
                    yield SimpleNamespace(_mapping={'value': b'two'})
                return iterate()
        @asynccontextmanager
        async def row_stream(*args, **kwargs):
            try:
                yield Rows()
            finally:
                lifecycle.append('cursor-closed')
        async def execute(*args, **kwargs):
            return SimpleNamespace(rowcount=1, close=lambda: lifecycle.append('result-closed'))
        @asynccontextmanager
        async def connection():
            yield SimpleNamespace(stream=row_stream, execute=execute)
        engine = SimpleNamespace(begin=connection, connect=connection, dispose=AsyncMock())
        class Body:
            def __init__(self): self.chunks = iter([b'payload', b''])
            async def __aenter__(self): return self
            async def __aexit__(self, *args): lifecycle.append('body-closed')
            async def read(self, size):
                await asyncio.sleep(0)
                return next(self.chunks)
        async def pages(**kwargs):
            yield {'Contents': [{'Key': 'key', 'Size': 7}]}
            yield {}
        native = SimpleNamespace(
            meta=SimpleNamespace(config=SimpleNamespace(retries={'total_max_attempts': 1})),
            get_object=AsyncMock(side_effect=lambda **kwargs: {'Body': Body()}),
            head_object=AsyncMock(return_value={'ContentLength': 7}),
            put_object=AsyncMock(return_value={'ETag': 'tag'}),
            delete_object=AsyncMock(return_value={}),
            get_paginator=lambda operation: SimpleNamespace(paginate=pages))
        @asynccontextmanager
        async def client_context(ctx):
            try: yield native
            finally: lifecycle.append('client-closed')
        calls = []
        async def pg_maker(ctx, env, cfg):
            calls.append('pg')
            return PGConnector(cfg, engine=engine)
        async def s3_maker(ctx, env, cfg):
            calls.append('s3')
            return S3Connector(cfg, client_factory=client_context)
        service.makers.database_query_connector = pg_maker
        service.makers.objects_query_connector = s3_maker
        ctx = Context()
        await service.initialize_infrastructure(ctx)
        pg = service._connectors.database_query_connector
        s3 = service._connectors.objects_query_connector
        try:
            await pg.start(ctx)
            await s3.start(ctx)
            await service.build_runtime(ctx)
            self.assertEqual(['pg', 's3'], calls)
            self.assertEqual(8, len(service._endpoints.consumers))
            for operation in ('rows', 'returning', 'execute', 'get_object', 'head_object', 'list_objects', 'put_object', 'delete_object'):
                with self.subTest(operation=operation):
                    values = []
                    async def collect(value):
                        values.append(value)
                        if value.kind == 'completed':
                            required = {'rows': 'cursor-closed', 'returning': 'cursor-closed', 'execute': 'result-closed', 'get_object': 'body-closed'}.get(operation)
                            if required: self.assertIn(required, lifecycle)
                        return value.kind == 'completed'
                    entry = getattr(service, f'get_{operation}_request_substream')()
                    await asyncio.wait_for(entry.consume(
                        StorageRequest(operation, 'key', b'payload'), SubStreamCollectorFunc(collect)), 2)
                    self.assertEqual('completed', values[-1].kind)
                    self.assertTrue(all(value.request_id == operation for value in values))
                    self.assertEqual(3 if operation in ('rows', 'returning', 'list_objects') else 2, len(values))
            async def simultaneous(request_id):
                values = []
                async def collect(value):
                    values.append(value)
                    return value.kind == 'completed'
                await service.get_get_object_request_substream().consume(
                    StorageRequest(request_id, 'key'), SubStreamCollectorFunc(collect))
                self.assertEqual(['object', 'completed'], [value.kind for value in values])
                self.assertEqual([request_id, request_id], [value.request_id for value in values])
            await asyncio.wait_for(asyncio.gather(*(simultaneous(f'parallel-{i}') for i in range(4))), 2)
        finally:
            await s3.stop(ctx)
            await pg.stop(ctx)
        engine.dispose.assert_awaited_once()
        self.assertIn('client-closed', lifecycle)


if __name__ == '__main__':
    unittest.main()
