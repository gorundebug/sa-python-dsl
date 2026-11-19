"""Live generated graph acceptance. Run only against disposable local resources.

Requires SA_QUERY_DISPOSABLE=1, SA_QUERY_PG_PORT and SA_QUERY_S3_PORT. Creates a
new table/bucket; no drop/truncate and no connection to arbitrary remote hosts.
"""
import asyncio
from pyservicelib_gorundebug.runtime.context.request import request_cancelled
import json
import os
import unittest
from pathlib import Path

from sqlalchemy import text
from storage_worker.internal.config import Config
from storage_worker.models.storage_request import StorageRequest
from pyservicelib_gorundebug.runtime.common import SubStreamCollectorFunc
from pyservicelib_gorundebug.runtime.context.context import Context
from pyservicelib_gorundebug.runtime.environment.metrics.metrics import NoopMetricsEngine
from test_graph import LocalService


@unittest.skipUnless(os.environ.get('SA_QUERY_DISPOSABLE') == '1', 'requires disposable local resources')
class LiveGraph(unittest.IsolatedAsyncioTestCase):
    async def test_all_operations_through_generated_graph(self):
        pg_port = int(os.environ['SA_QUERY_PG_PORT'])
        s3_port = int(os.environ['SA_QUERY_S3_PORT'])
        service = LocalService()
        service._config = Config.from_dict({'dataConnectors': {
            'database': {'connectionString': f'postgresql://postgres@127.0.0.1:{pg_port}/query_example'},
            'objects': {'address': f'http://127.0.0.1:{s3_port}', 'forcePathStyle': True}}})
        service._id = 1
        service._serviceConfig = service._config.get_service_config_by_id(1)
        service._metrics_engine = NoopMetricsEngine()
        ctx = Context()
        await service.initialize_infrastructure(ctx)
        pg = service._connectors.database_query_connector
        s3 = service._connectors.objects_query_connector
        try:
            await pg.start(ctx)
            await s3.start(ctx)
            # Explicit test provisioning, outside service handlers/startup.
            async with pg.engine.begin() as connection:
                await connection.execute(text(Path(__file__).with_name('schema.sql').read_text()))
            await s3.client.create_bucket(Bucket='query-example', CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'})
            await service.build_runtime(ctx)

            async def call(operation, key='object', value=b'', request_id=None):
                request_id = request_id or operation
                received = []
                async def collect(result):
                    received.append(result)
                    return result.kind == 'completed'
                entry = getattr(service, f'get_{operation}_request_substream')()
                await asyncio.wait_for(entry.consume(StorageRequest(request_id, key, value), SubStreamCollectorFunc(collect)), 5)
                self.assertEqual('completed', received[-1].kind)
                self.assertTrue(all(result.request_id == request_id for result in received))
                return received[:-1]

            payload = bytes(range(256)) * 1025
            key = "quoted'; key"
            self.assertEqual(payload, (await call('returning', "returning-'key", payload))[0].value)
            self.assertEqual(payload, (await call('rows', "returning-'key"))[0].value)
            self.assertEqual([], await call('rows', key))
            self.assertEqual(b'1', (await call('execute', key, payload))[0].value)
            self.assertEqual(payload, (await call('rows', key))[0].value)
            await call('execute', key, b'updated\x00')
            self.assertEqual(b'updated\x00', (await call('rows', key))[0].value)
            await call('put_object', 'object', payload)
            self.assertEqual(len(payload), json.loads((await call('head_object'))[0].value)['size'])
            self.assertEqual(payload, b''.join(result.value for result in await call('get_object')))
            listing = [item for page in await call('list_objects') for item in json.loads(page.value)]
            self.assertEqual([{'key': 'object', 'size': len(payload)}], listing)
            results = await asyncio.gather(*(call('get_object', request_id=f'parallel-{i}') for i in range(4)))
            self.assertTrue(all(b''.join(item.value for item in values) == payload for values in results))
            await call('put_object', 'empty')
            self.assertEqual([], await call('get_object', 'empty'))
            # Observe business finalization without changing endpoint execution or
            # error/completion policy. The sample Error branch has no reply; an
            # unsuccessful SubStream invocation is bounded/cancelled by its caller.
            async def failed_call(operation, request, *, cancel_signal=None):
                function = getattr(service.functions, operation + '_query')
                original_end = function.end_request
                ended = asyncio.Event()
                outcomes, received = [], []
                async def observe_end(stream, state, error, out, errors):
                    outcomes.append(error)
                    try:
                        await original_end(stream, state, error, out, errors)
                    finally:
                        ended.set()
                async def collect(result):
                    received.append(result)
                    return result.kind == 'completed'
                function.end_request = observe_end
                token = request_cancelled.set(cancel_signal) if cancel_signal else None
                task = asyncio.create_task(getattr(service, f'get_{operation}_request_substream')().consume(request, SubStreamCollectorFunc(collect)))
                try:
                    if cancel_signal:
                        # SQL blocks on the fixture's table lock. Cancel while it
                        # is in flight, not before invoking the graph.
                        async def wait_for_lock():
                            while not ended.is_set():
                                async with pg.engine.connect() as probe:
                                    waiting = await probe.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND wait_event_type = 'Lock' AND state = 'active'"))
                                if waiting:
                                    return
                                await asyncio.sleep(0.01)
                            self.fail('SQL completed before reaching the lock')
                        await asyncio.wait_for(wait_for_lock(), 1)
                        self.assertFalse(ended.is_set())
                        cancel_signal.set()
                    await asyncio.wait_for(ended.wait(), 3)
                    self.assertEqual(1, len(outcomes))
                    self.assertIsNotNone(outcomes[0])
                    self.assertFalse(any(result.kind == 'completed' for result in received))
                    return outcomes[0]
                finally:
                    if not task.done(): task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    function.end_request = original_end
                    if token is not None: request_cancelled.reset(token)

            missing = await failed_call('get_object', StorageRequest('missing', 'not-present'))
            self.assertEqual('NoSuchKey', missing.response['Error']['Code'])
            async with pg.engine.begin() as connection:
                await connection.execute(text('ALTER TABLE query_example_items RENAME TO query_example_hidden'))
            try:
                sql_error = await failed_call('rows', StorageRequest('sql-error', key))
                self.assertEqual('42P01', sql_error.orig.sqlstate)
            finally:
                async with pg.engine.begin() as connection:
                    await connection.execute(text('ALTER TABLE query_example_hidden RENAME TO query_example_items'))
            async with pg.engine.begin() as connection:
                await connection.execute(text('LOCK TABLE query_example_items IN ACCESS EXCLUSIVE MODE'))
                cancelled = await failed_call('rows', StorageRequest('cancelled', key), cancel_signal=asyncio.Event())
                self.assertIsInstance(cancelled, asyncio.CancelledError)
            # A cancelled SQL query must release its cursor/connection: the next
            # normal query through the same connector must still succeed.
            self.assertEqual(b'updated\x00', (await call('rows', key))[0].value)
            self.assertEqual(payload, b''.join(result.value for result in await call('get_object')))
            await call('delete_object')
            self.assertEqual([], [item for page in await call('list_objects') for item in json.loads(page.value)])
        finally:
            await s3.stop(ctx)
            await pg.stop(ctx)


if __name__ == '__main__':
    unittest.main()
