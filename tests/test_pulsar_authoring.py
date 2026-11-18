import pytest
import yaml
from sa_dsl import Project, Golang, Function, ServiceModule
from sa_dsl.browser import python_files_to_yaml
from sa_dsl.importer import yaml_to_python_files
from sa_dsl.code_generation import to_api_document


def fixture():
    p = Project('Pulsar Events')
    c = p.pulsar_connector('Events', servers=['pulsar://broker:6650'], admin_url='http://broker:8080')
    source = c.endpoint('Receive', function=Function('Receive'), topic='persistent://public/default/input', subscription_name='workers', subscription_type='Shared', create_topic=True, create_subscription=True, subscription_initial_position='Earliest', receiver_queue_size=32)
    sink = c.endpoint('Publish', function=Function('Publish'), topic='persistent://public/default/output', create_topic=True, publisher_max_in_flight=16)
    svc = p.service('Worker', language=Golang(), module=ServiceModule('example.com/worker'))
    flow = svc.pipeline('Events')
    text = p.string_type('Text')
    incoming = flow.input('Read', endpoint=source, value_type=text)
    flow.sink('Write', endpoint=sink, source=incoming, value_type=text)
    return p, c, source, sink


def test_round_trip_and_api():
    p, _, _, _ = fixture()
    assert not p.validate(), p.validate()
    doc = p.to_document()
    imported = yaml_to_python_files(doc, 'pulsar_roundtrip')
    assert yaml.safe_load(python_files_to_yaml(imported.files, imported.entrypoint)) == doc
    api = to_api_document(doc)
    assert api['dataConnectors'][0]['type'] == 11
    assert api['dataConnectors'][0]['adminUrl'] == 'http://broker:8080'
    assert api['endpoints'][0]['subscriptionName'] == 'workers'


@pytest.mark.parametrize('field,value', [('servers', []), ('servers', ['pulsar://user:secret@broker']), ('adminUrl', 'http://user:secret@admin'), ('token', 'secret'), ('operationTimeoutMs', True), ('connectTimeoutMs', 2147483648), ('tlsCertFile', 'cert')])
def test_connector_rejections(field, value):
    p, c, _, _ = fixture()
    c.properties[field] = value
    errors = p.validate()
    assert errors
    assert 'secret' not in str(errors)


@pytest.mark.parametrize('field,value', [('subscriptionName', ''), ('subscriptionType', 'KeyShared'), ('subscriptionType', []), ('receiverQueueSize', 0), ('receiverQueueSize', True), ('negativeAckRedeliveryDelayMs', -1), ('publisherMaxInFlight', 1), ('createSubscription', False), ('topic', 'non-persistent://public/default/input')])
def test_source_rejections(field, value):
    p, _, source, _ = fixture()
    source.properties[field] = value
    assert p.validate()


def test_sink_rejects_even_false_source_flag():
    p, _, _, sink = fixture()
    sink.properties['createSubscription'] = False
    assert p.validate()
