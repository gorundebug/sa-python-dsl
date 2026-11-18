from __future__ import annotations

import pytest
import yaml
from sa_dsl import Function, Golang, Project, RabbitMQConnector, ServiceModule
from sa_dsl.browser import python_files_to_yaml
from sa_dsl.code_generation import to_api_document
from sa_dsl.importer import yaml_to_python_files
from sa_dsl.api_catalog import build_connector_capabilities


def fixture():
    p = Project('Rabbit authoring')
    c = p.rabbitmq_connector('Broker', servers=['amqp://broker:5672'], virtual_host='/')
    receive = c.endpoint('Receive', function=Function('Receive'), queue_name='incoming')
    publish = c.endpoint('Publish', function=Function('Publish'), exchange_name='events', routing_key='processed')
    service = p.service('Worker', language=Golang(), module=ServiceModule('example.com/worker'))
    pipeline = service.pipeline('Events')
    text = p.string_type('Text')
    source = pipeline.input('Read', endpoint=receive, value_type=text)
    pipeline.sink('Write', endpoint=publish, source=source, value_type=text)
    return p, c, receive, publish


def test_existing_resources_and_opt_in_creation_roundtrip():
    p,c,receive,publish=fixture()
    assert isinstance(c, RabbitMQConnector)
    assert p.validate() == []
    assert not {'createQueue','createExchange','createBinding'} & receive.properties.keys()
    receive.properties.update(createQueue=True, queueType='quorum', consumerCredits=128)
    publish.properties.update(createExchange=True,exchangeType='topic',createQueue=True,queueName='processed',createBinding=True,publisherMaxInFlight=64)
    assert p.validate() == []
    document=p.to_document()
    imported=yaml_to_python_files(document,'rabbit_roundtrip')
    assert 'rabbitmq_connector(' in '\n'.join(imported.files.values())
    assert yaml.safe_load(python_files_to_yaml(imported.files,imported.entrypoint)) == document
    api=to_api_document(document)
    assert api['dataConnectors'][0]['type'] == 9
    assert api['dataConnectors'][0]['virtualHost'] == '/'
    assert api['endpoints'][0]['queueName'] == 'incoming'
    assert 'rabbitmq_connector' in build_connector_capabilities()['connectors']


@pytest.mark.parametrize('field,value',[
    ('servers',[]),('servers','amqp://broker'),('servers',['amqp://user:secret@broker']),
    ('servers',['amqp://broker/vhost']),('servers',['http://broker']),('servers',['amqp://broker:0']),
    ('servers',['amqp://broker:']),('servers',['amqp://broker?']),('servers',['amqp://broker#']),
    ('servers',['amqp://broker','amqps://broker']),('connectTimeoutMs',True),('operationTimeoutMs',0),
    ('tlsEnabled','yes'),('tlsCertFile','/tls/client.pem'),('password','secret'),('token','secret'),
    ('virtualHost','bad\n'),('brokers','broker:9092'),
])
def test_connection_rejects_invalid_fields_without_exposing_secrets(field,value):
    p,c,_,_=fixture();c.properties[field]=value
    errors=p.validate()
    assert errors
    assert 'secret' not in str(errors)


@pytest.mark.parametrize('field,value',[
    ('createQueue','false'),('consumerCredits',0),('consumerCredits',True),('consumerCredits',4097),
    ('queueType','stream'),('queueType',[]),('exchangeType',{}),('exchangeType','headers'),('queueName','bad\n'),('publisherMaxInFlight',2),
    ('createBinding',True),('subject','events'),('topic','events'),
])
def test_invalid_source_settings(field,value):
    p,_,receive,_=fixture();receive.properties[field]=value
    assert p.validate()


def test_direction_and_creation_semantics():
    p,_,receive,publish=fixture()
    receive.properties.pop('queueName')
    publish.properties.update(consumerCredits=10,exchangeType='direct')
    fields={e.path.rsplit('.',1)[-1] for e in p.validate()}
    assert {'queueName','consumerCredits','exchangeType'} <= fields


def test_native_fields_do_not_leak_into_custom():
    p=Project('Other');c=p.custom_connector('Local');c.properties['virtualHost']='/'
    e=c.endpoint('Run',function=Function('Run'));e.properties['createQueue']=False
    assert {e.path.rsplit('.',1)[-1] for e in p.validate()} == {'virtualHost','createQueue'}


@pytest.mark.parametrize('field,value', [
    ('virtualHost', '/tenant'), ('connectTimeoutMs', 2147483648),
    ('operationTimeoutMs', 2147483648), ('tlsServerName', 'different'),
    ('queueName', 'tenant/events'), ('exchangeName', 'events?tenant'),
    ('routingKey', 'tenant%2F'),
])
def test_typescript_native_limits_are_target_specific(field, value):
    p, c, receive, publish = fixture()
    if field == 'tlsServerName':
        c.properties['tlsEnabled'] = True
    target = receive if field == 'queueName' else publish if field in {'exchangeName', 'routingKey'} else c
    target.properties[field] = value
    assert not p.validate(), 'supported Go options must remain valid'
    next(iter(p.services.values())).programming_language = 'TypeScript'
    errors = p.validate()
    assert any(error.path.endswith('.' + field) for error in errors)


def test_typescript_supported_native_boundaries():
    p, c, _, _ = fixture()
    next(iter(p.services.values())).programming_language = 'TypeScript'
    c.properties.update(tlsEnabled=True, tlsServerName='broker', operationTimeoutMs=2147483647)
    service = next(iter(p.services.values()))
    source = next(s for pipeline in service.pipelines.values() for s in pipeline.streams.values() if s.type == 'Input')
    source.endpoint = p.custom_connector('Local').endpoint('Start', function=Function('Start'))
    assert not p.validate()


def test_typescript_rabbit_source_and_mixed_graph_rejected_sink_preserved():
    p, _, receive, _ = fixture()
    service = next(iter(p.services.values()))
    service.programming_language = 'TypeScript'
    errors = p.validate()
    assert len(errors) == 1
    assert 'native receive credit' in errors[0].message
    assert errors[0].details['direction'] == 'source'
    pipeline = next(iter(service.pipelines.values()))
    source = next(s for s in pipeline.streams.values() if s.type == 'Input')
    local = p.custom_connector('Local').endpoint('Start', function=Function('Start'))
    source.endpoint = local
    assert p.validate() == []
    assert 'RabbitMQ' in p.to_yaml()
    capabilities = build_connector_capabilities()['directionCapabilities']
    target = next(t for t in capabilities['languages'] if t['backend'] == 'typescript')
    assert target['connectors']['RabbitMQ']['source']['supported'] is False
    assert target['connectors']['RabbitMQ']['sink']['supported'] is True


@pytest.mark.parametrize('operation', ['validate', 'export'])
def test_cli_worker_rejects_unsupported_source_before_export(tmp_path, operation):
    import inspect
    import json
    import subprocess
    import sys
    imports = 'from sa_dsl import Function, Golang, Project, RabbitMQConnector, ServiceModule\n'
    model = imports + inspect.getsource(fixture) + "\nproject=fixture()[0]\nnext(iter(project.services.values())).programming_language='TypeScript'\n"
    (tmp_path / 'project.py').write_text(model)
    output = tmp_path / 'result.json'
    result = subprocess.run([sys.executable, '-m', 'sa_dsl._worker', '--operation', operation,
        '--workspace', str(tmp_path), '--entrypoint', 'project:project', '--project-name', 'Rabbit authoring',
        '--result', str(output)], capture_output=True, timeout=15)
    assert result.returncode == 1, result.stderr
    payload = json.loads(output.read_text())
    assert payload['status'] == 'failed'
    assert 'yaml' not in payload
    assert any('native receive credit' in d['message'] for d in payload['diagnostics'])
