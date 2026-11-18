"""Run the freshly generated service; provision only a uniquely named fixture."""
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import pulsar


def main():
    admin_url = os.environ['PULSAR_TEST_ADMIN_URL']
    address = os.environ.get('PULSAR_TEST_URL', 'pulsar://127.0.0.1:16650')
    namespace = 'public/sa-python-canonical-' + uuid.uuid4().hex
    incoming, outgoing = [f'persistent://{namespace}/{name}' for name in ('incoming', 'processed')]

    def admin(method, path, body=None):
        request = Request(admin_url + path, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json'}, method=method)
        try:
            with urlopen(request, timeout=5) as response:
                data = response.read()
                return json.loads(data) if data else None
        except HTTPError as error:
            if method == 'DELETE' and error.code == 404:
                return None
            raise

    admin('PUT', '/admin/v2/namespaces/' + namespace, {})
    service = client = producer = reader = None
    with tempfile.TemporaryFile(mode='w+') as log:
        def logs():
            log.seek(0)
            return log.read()

        try:
            admin('POST', f'/admin/v2/namespaces/{namespace}/autoTopicCreation', {'allowAutoTopicCreation': False})
            admin('POST', f'/admin/v2/namespaces/{namespace}/autoSubscriptionCreation', {'allowAutoSubscriptionCreation': False})
            env = dict(os.environ, EVENTS_SERVERS=address, EVENTS_ADMIN_URL=admin_url,
                       RECEIVE_EVENT_TOPIC=incoming, PUBLISH_EVENT_TOPIC=outgoing,
                       EVENT_PROCESSOR_HTTP_PORT='0', SERVICELIB_NOOP_METRICS='1',
                       SERVICELIB_NOOP_LOGS='1', SERVICELIB_NOOP_TRACING='1')
            probe = subprocess.run([sys.executable, '-c', '''
import os
from event_processor.internal.config import Config
from pyservicelib_gorundebug.runtime.config.pulsar import PulsarDataConnectorConfig, PulsarEndpointConfig
c = Config.from_dict({})
dc = c.named.data_connectors.events
source, sink = c.named.endpoints.receive_event, c.named.endpoints.publish_event
assert isinstance(dc, PulsarDataConnectorConfig) and dc.type.value == 11
assert dc.admin_url == os.environ['EVENTS_ADMIN_URL'] and dc.servers == [os.environ['EVENTS_SERVERS']]
assert isinstance(source, PulsarEndpointConfig) and isinstance(sink, PulsarEndpointConfig)
assert source.topic == os.environ['RECEIVE_EVENT_TOPIC'] and sink.topic == os.environ['PUBLISH_EVENT_TOPIC']
assert source.create_subscription is True and source.subscription_initial_position == 'Earliest'
assert sink.subscription_initial_position is None and sink.create_subscription is None
source.validate_role(True)
sink.validate_role(False)
'''], env=env, capture_output=True, text=True, timeout=10)
            assert probe.returncode == 0, probe.stdout + probe.stderr
            service = subprocess.Popen([sys.executable, '-m', 'event_processor.main', '--config', 'config/config.yaml', '--values', 'config/overrides.yaml'], env=env, stdout=log, stderr=log)
            deadline = time.monotonic() + 25

            def wait(predicate):
                while not predicate():
                    assert service.poll() is None, logs()
                    assert time.monotonic() < deadline, logs()
                    time.sleep(.025)

            def source_ready():
                try:
                    return 'event_processors' in admin('GET', f'/admin/v2/persistent/{namespace}/incoming/subscriptions')
                except HTTPError as error:
                    if error.code == 404:
                        return False
                    raise

            wait(source_ready)
            client = pulsar.Client(address, operation_timeout_seconds=3)
            producer = client.create_producer(incoming, batching_enabled=False)
            reader = client.create_reader(outgoing, pulsar.MessageId.earliest)
            for i in range(3):
                producer.send(json.dumps({'ID':f'event-{i}', 'Value':' hello '}).encode())
            records = {}
            for _ in range(3):
                message = reader.read_next(timeout_millis=5000)
                value = json.loads(message.data())
                assert value['Value'] == 'HELLO' and message.partition_key() == value['ID']
                assert value['ID'] not in records
                records[value['ID']] = base64.b64encode(message.message_id().serialize()).decode()

            def settled():
                stats = admin('GET', f'/admin/v2/persistent/{namespace}/incoming/stats')['subscriptions']['event_processors']
                return stats['msgBacklog'] == 0 and stats['unackedMessages'] == 0

            wait(settled)
            def outcomes():
                return [json.loads(line) for line in logs().splitlines() if line.startswith('{') and '"Accepted"' in line]
            wait(lambda: len(outcomes()) == 3)
            assert {v['EventID'] for v in outcomes()} == {f'event-{i}' for i in range(3)}
            for value in outcomes():
                assert value == {'EventID':value['EventID'], 'MessageID':records[value['EventID']], 'Accepted':True, 'Reason':''}
            service.terminate()
            assert service.wait(timeout=8) == 0, logs()
            print('PASS: generated Pulsar Python: three normalized outputs, native MessageId correlation, explicit ACK and clean shutdown')
        except BaseException:
            print(logs(), file=sys.stderr)
            raise
        finally:
            if service and service.poll() is None:
                service.kill()
                service.wait(timeout=5)
            if reader:
                reader.close()
            if producer:
                producer.close()
            if client:
                client.close()
            for topic in ('incoming', 'processed'):
                admin('DELETE', f'/admin/v2/persistent/{namespace}/{topic}?force=true')
            admin('DELETE', '/admin/v2/namespaces/' + namespace)


if __name__ == '__main__':
    main()
