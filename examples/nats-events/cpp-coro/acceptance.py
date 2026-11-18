"""Exercise the built generated Coro service with a disposable real NATS broker."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid
import nats

async def command(*args):
    process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError(stderr.decode())
    return stdout.decode().strip()

async def main():
    project = Path(sys.argv[1]).resolve()
    runtime = os.environ.get("NATS_ACCEPTANCE_RUNTIME", "coro")
    identity = runtime + '-nats-' + uuid.uuid4().hex[:10]
    broker, name = identity + '-broker', identity + '-service'
    client = service = None
    with tempfile.TemporaryDirectory(prefix=identity) as temporary:
        log_path = Path(temporary) / 'service.log'
        with log_path.open('w+') as log:
            try:
                await command('docker', 'run', '-d', '--name', broker, '-p', '127.0.0.1::4222', 'nats:2.15.3-alpine', '-js')
                port = (await command('docker', 'port', broker, '4222/tcp')).rsplit(':', 1)[1]
                client = await nats.connect('nats://127.0.0.1:' + port)
                received = []
                async def observe(message):
                    received.append(json.loads(message.data))
                await client.subscribe('example.core.processed', cb=observe)
                await client.flush()
                args = ['docker', 'run', '--rm', '--name', name, '--network', 'container:' + broker,
                    '-v', str(project) + ':/generated', '-v', os.environ.get('DEPENDENCY_CONAN_VOLUME', 'dependency-conan2') + ':/conan',
                    '-w', '/generated/eventprocessor']
                for key, value in {'CORE_EVENTS_SERVERS':'nats://127.0.0.1:4222', 'DURABLE_EVENTS_SERVERS':'nats://127.0.0.1:4222',
                    'SERVICELIB_NOOP_METRICS':'1', 'SERVICELIB_NOOP_LOGS':'1', 'SERVICELIB_NOOP_TRACING':'1'}.items():
                    args += ['-e', key + '=' + value]
                args += ['--entrypoint', '/generated/build/eventprocessor/nats_events_event_processor',
                    os.environ.get('NATS_ACCEPTANCE_IMAGE', os.environ.get('CPPCOROSERVICELIB_TEST_IMAGE', 'cppcoroservicelib-build:local'))]
                if runtime == 'userver':
                    args += ['--config', 'static_config.yaml', '--config_vars', 'config/config_vars.yaml']
                service = await asyncio.create_subprocess_exec(*args, stdout=log, stderr=log)
                js = client.jetstream()
                async def until(check):
                    async with asyncio.timeout(20):
                        while not await check():
                            if service.returncode is not None:
                                raise RuntimeError(log_path.read_text())
                            await asyncio.sleep(.025)
                async def ready():
                    try:
                        await js.consumer_info('EXAMPLE_IN', 'event_processor')
                        await js.stream_info('EXAMPLE_OUT')
                        return True
                    except nats.js.errors.NotFoundError:
                        return False
                await until(ready)
                await client.publish('example.core.incoming', json.dumps({'ID':'core-1','Value':' hello core '}).encode())
                await client.flush()
                await js.publish('example.durable.incoming', json.dumps({'ID':'durable-1','Value':' hello durable '}).encode())
                async def completed():
                    results = []
                    for line in log_path.read_text().splitlines():
                        try:
                            value = json.loads(line)
                            if isinstance(value, dict) and 'EventID' in value:
                                results.append(value)
                        except ValueError:
                            pass
                    return bool(received) and all(any(r.get('EventID') == key and r.get('Accepted') is True for r in results) for key in ['core-1','durable-1'])
                await until(completed)
                assert received == [{'ID':'core-1','Value':'HELLO CORE'}], received
                message = await js.get_msg('EXAMPLE_OUT', subject='example.durable.processed')
                assert json.loads(message.data) == {'ID':'durable-1','Value':'HELLO DURABLE'}
                async def acknowledged():
                    info = await js.consumer_info('EXAMPLE_IN', 'event_processor')
                    return info.num_ack_pending == 0 and info.ack_floor.stream_seq >= 1
                await until(acknowledged)
                await command('docker', 'stop', '-t', '10', name)
                await asyncio.wait_for(service.wait(), 15)
                assert service.returncode == 0, log_path.read_text()
                print(f'PASS: generated {runtime} Core/JetStream graph, normalized output, correlated results, explicit ACK and graceful stop')
            except BaseException:
                print(log_path.read_text(), file=sys.stderr)
                raise
            finally:
                if client:
                    await client.close()
                for container in [name, broker]:
                    try:
                        await command('docker', 'rm', '-f', container)
                    except RuntimeError:
                        pass
                if service and service.returncode is None:
                    await service.wait()

asyncio.run(main())
