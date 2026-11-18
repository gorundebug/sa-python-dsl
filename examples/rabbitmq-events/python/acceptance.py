"""Exercise the regenerated graph against an explicitly supplied disposable broker."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.parse import urlsplit
import rabbitmq_amqp_python_client as sdk
from proton.utils import BlockingConnection


def main():
    prefix = 'generated-python-' + uuid.uuid4().hex
    image = os.environ.get('RABBITMQ_ACCEPTANCE_IMAGE')
    container = prefix + '-service'
    incoming, outgoing, exchange = (prefix + suffix for suffix in ('-in', '-out', '-exchange'))
    values = Path('config/overrides.yaml')
    if not image and os.environ.get("RABBITMQ_ACCEPTANCE_RUNTIME") != "typescript":
        values.write_text(values.read_text().replace('example.incoming', incoming).replace('example.processed', outgoing).replace('example.events', exchange))
    address = urlsplit(os.environ['RABBITMQ_TEST_URL'])
    uri = f'amqp://adapter:adapter-test@{address.hostname}:{address.port}/'
    admin = sdk.Connection(uri=uri, recovery_configuration=sdk.RecoveryConfiguration(active_recovery=False))
    admin.dial()
    service = native = None
    with tempfile.TemporaryFile(mode='w+') as log:
        def logs():
            log.seek(0)
            return log.read()
        try:
            env = dict(os.environ, EVENTS_SERVERS=os.environ['RABBITMQ_TEST_URL'], EVENTS_USERNAME='adapter', EVENTS_PASSWORD='adapter-test', RECEIVE_EVENT_QUEUE_NAME=incoming, PUBLISH_EVENT_QUEUE_NAME=outgoing, PUBLISH_EVENT_EXCHANGE_NAME=exchange, EVENT_PROCESSOR_HTTP_PORT='0', SERVICELIB_NOOP_METRICS='1', SERVICELIB_NOOP_LOGS='1', SERVICELIB_NOOP_TRACING='1')
            command = [sys.executable, '-m', 'event_processor.main', '--config', 'config/config.yaml', '--values', str(values)]
            if os.environ.get("RABBITMQ_ACCEPTANCE_RUNTIME") == "typescript":
                command = ["node", "dist/main.generated.js"]
            if image:
                env['EVENTS_SERVERS'] = os.environ.get('RABBITMQ_CONTAINER_URL',
                    env['EVENTS_SERVERS'].replace('127.0.0.1', 'host.docker.internal').replace('localhost', 'host.docker.internal'))
                command = ['docker', 'run', '--rm', '--name', container]
                for key in ('EVENTS_SERVERS', 'EVENTS_USERNAME', 'EVENTS_PASSWORD',
                            'RECEIVE_EVENT_QUEUE_NAME', 'PUBLISH_EVENT_QUEUE_NAME',
                            'PUBLISH_EVENT_EXCHANGE_NAME', 'EVENT_PROCESSOR_HTTP_PORT',
                            'SERVICELIB_NOOP_METRICS', 'SERVICELIB_NOOP_LOGS', 'SERVICELIB_NOOP_TRACING'):
                    command.extend(['-e', key])
                command.extend([image, '--config', 'config/config.yaml',
                                '--values', 'config/overrides.yaml'])
            service = subprocess.Popen(command, env=env, stdout=log, stderr=log)
            deadline = time.monotonic() + 25
            while True:
                assert service.poll() is None, logs()
                if all(int(admin.management().request(None, sdk.AddressHelper.queue_address(q), 'GET', [200,404]).subject) == 200 for q in (incoming,outgoing)):
                    break
                assert time.monotonic() < deadline, logs()
                time.sleep(.05)
            native = BlockingConnection(uri, timeout=10)
            receiver = native.create_receiver(sdk.AddressHelper.queue_address(outgoing), credit=1)
            publisher = admin.publisher(sdk.AddressHelper.queue_address(incoming))
            publisher.publish(sdk.Message(body=json.dumps({'ID':'rabbit-1','Value':' hello rabbit '}).encode(), inferred=True))
            publisher.close()
            result = receiver.receive(timeout=15)
            assert json.loads(bytes(result.body)) == {'ID':'rabbit-1','Value':'HELLO RABBIT'}
            receiver.accept()
            while '"EventID":"rabbit-1","Accepted":true' not in logs().replace(' ', ''):
                assert service.poll() is None and time.monotonic() < deadline, logs()
                time.sleep(.05)
            # The source prints its result only after explicit settlement completes.
            if image:
                subprocess.run(['docker', 'stop', '--time', '8', container], check=True,
                               capture_output=True, timeout=12)
            else:
                service.terminate()
            assert service.wait(timeout=10) == 0, logs()
            print('PASS: generated RabbitMQ graph, transformed payload, correlated publication outcome, explicit accept and shutdown')
        except BaseException:
            print(logs(), file=sys.stderr)
            for q in (incoming, outgoing):
                print(admin.management().request(None, sdk.AddressHelper.queue_address(q), "GET", [200,404]).body, file=sys.stderr)
            raise
        finally:
            if image:
                subprocess.run(['docker', 'rm', '--force', container],
                               capture_output=True, timeout=12)
            if service and service.poll() is None:
                service.kill()
                service.wait()
            if native:
                native.close()
            for queue in (incoming,outgoing):
                admin.management().request(None, sdk.AddressHelper.queue_address(queue), 'DELETE', [200,204,404])
            admin.management().delete_exchange(exchange)
            admin.close()


if __name__ == '__main__':
    main()
