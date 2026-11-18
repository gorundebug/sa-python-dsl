import pytest
import yaml
from sa_dsl import Project, Golang, Function, ServiceModule
from sa_dsl.browser import python_files_to_yaml
from sa_dsl.importer import yaml_to_python_files
from sa_dsl.code_generation import to_api_document


def fixture():
    p=Project('Redis Streams')
    c=p.redis_streams_connector('Events',servers=['redis://broker:6379'],redis_database=0)
    source=c.endpoint('Receive',function=Function('Receive'),stream_key='events.in',consumer_group='workers',create_consumer_group=True,group_start_id='0-0')
    sink=c.endpoint('Publish',function=Function('Publish'),stream_key='events.out',create_stream=True,publisher_max_in_flight=16)
    svc=p.service('Worker',language=Golang(),module=ServiceModule('example.com/worker'))
    flow=svc.pipeline('Events'); text=p.string_type('Text')
    incoming=flow.input('Read',endpoint=source,value_type=text)
    flow.sink('Write',endpoint=sink,source=incoming,value_type=text)
    return p,c,source,sink


def test_round_trip_and_api():
    p,_,_,_=fixture()
    assert not p.validate(),p.validate()
    doc=p.to_document()
    imported=yaml_to_python_files(doc,'redis_roundtrip')
    assert yaml.safe_load(python_files_to_yaml(imported.files,imported.entrypoint))==doc
    api=to_api_document(doc)
    assert api['dataConnectors'][0]['type']==10
    assert api['dataConnectors'][0]['redisDatabase']==0
    assert api['endpoints'][0]['streamKey']=='events.in'


@pytest.mark.parametrize('field,value', [('servers',[]),('servers',['redis://one','redis://two']),('servers',['redis://user:secret@host']),('servers',['redis://host/1']),('servers',['redis://host:0']),('redisDatabase',True),('redisDatabase',-1),('password','secret'),('tlsCertFile','/cert')])
def test_connection_validation(field,value):
    p,c,_,_=fixture();c.properties[field]=value
    errors=p.validate()
    assert errors
    assert 'secret' not in str(errors)


@pytest.mark.parametrize('field,value',[('readCount',0),('readBlockMs',60001),('claimIdleMs',False),('claimIntervalMs',0),('groupStartId','bad'),('createConsumerGroup','yes'),('publisherMaxInFlight',4),('createStream',True)])
def test_source_validation(field,value):
    p,_,source,_=fixture();source.properties[field]=value
    assert p.validate()


def test_sink_rejects_source_fields():
    p,_,_,sink=fixture();sink.properties['consumerGroup']='workers'
    assert p.validate()


@pytest.mark.parametrize('field', ['connectTimeoutMs', 'operationTimeoutMs', 'redisDatabase'])
def test_typescript_rejects_native_integer_overflow(field):
    p,c,_,_=fixture()
    c.properties[field]=2147483648
    assert not p.validate(), p.validate()
    svc=next(iter(p.services.values()))
    svc.programming_language='TypeScript'
    errors=p.validate()
    assert any(field in str(error) for error in errors), errors
    c.properties[field]=2147483647
    assert not p.validate(), p.validate()
