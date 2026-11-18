"""Run the generated service, not endpoint handlers, against an isolated NATS."""
import asyncio
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import nats


async def main():
    with tempfile.TemporaryDirectory(prefix='sa-nats-python-') as directory:
        root = Path(directory)
        broker_log = (root / 'broker.log').open('w+')
        service_log = (root / 'service.log').open('w+')
        broker = await asyncio.create_subprocess_exec(os.environ['NATS_SERVER_BINARY'],
            '-a', '127.0.0.1', '-p', '-1', '-js', '-sd', directory,
            stdout=broker_log, stderr=broker_log)
        service = client = None

        async def until(check):
            async with asyncio.timeout(15):
                while not await check():
                    if service and service.returncode is not None:
                        raise RuntimeError((root / 'service.log').read_text())
                    await asyncio.sleep(.025)

        async def stop(process):
            if process and process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 5)
                except TimeoutError:
                    process.kill()
                    await process.wait()

        try:
            async def broker_ready():
                return 'Server is ready' in (root / 'broker.log').read_text()
            await until(broker_ready)
            port = re.search(r'Listening for client connections on 127\.0\.0\.1:(\d+)', (root / 'broker.log').read_text())[1]
            address = f'nats://127.0.0.1:{port}'
            client = await nats.connect(address)
            received = []
            async def observe(message):
                received.append(json.loads(message.data))
            await client.subscribe('example.core.processed', cb=observe)
            await client.flush()
            env = dict(os.environ, CORE_EVENTS_SERVERS=address, DURABLE_EVENTS_SERVERS=address,
                       EVENT_PROCESSOR_HTTP_PORT='0',
                       SERVICELIB_NOOP_METRICS='1', SERVICELIB_NOOP_LOGS='1', SERVICELIB_NOOP_TRACING='1')
            service = await asyncio.create_subprocess_exec(sys.executable, '-m', 'event_processor.main',
                '--config', 'config/config.yaml', '--values', 'config/overrides.yaml',
                env=env, stdout=service_log, stderr=service_log)
            js = client.jetstream()
            async def resources_ready():
                try:
                    await js.consumer_info('EXAMPLE_IN', 'event_processor')
                    await js.stream_info('EXAMPLE_OUT')
                    return True
                except nats.js.errors.NotFoundError:
                    return False
            await until(resources_ready)
            await client.publish('example.core.incoming', json.dumps({'ID':'core-1','Value':' hello core '}).encode())
            await client.flush()
            await js.publish('example.durable.incoming', json.dumps({'ID':'durable-1','Value':' hello durable '}).encode())
            async def completed():
                output = (root / 'service.log').read_text()
                return received and all(f'"EventID": "{identity}", "Accepted": true' in output for identity in ['core-1','durable-1'])
            await until(completed)
            assert received == [{'ID':'core-1','Value':'HELLO CORE'}], received
            message = await js.get_msg('EXAMPLE_OUT', subject='example.durable.processed')
            assert json.loads(message.data) == {'ID':'durable-1','Value':'HELLO DURABLE'}
            async def acknowledged():
                info = await js.consumer_info('EXAMPLE_IN','event_processor')
                return info.num_ack_pending == 0 and info.ack_floor.stream_seq >= 1
            await until(acknowledged)
            await stop(service)
            assert service.returncode == 0, (root / 'service.log').read_text()
            print('PASS: generated Python Core/JetStream graph, output, result correlation, ACK and shutdown')
        except BaseException:
            print((root / 'service.log').read_text(), file=sys.stderr)
            raise
        finally:
            await stop(service)
            if client:
                await client.close()
            await stop(broker)
            broker_log.close()
            service_log.close()


asyncio.run(main())
