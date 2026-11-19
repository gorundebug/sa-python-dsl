from sa_dsl import python_files_to_snapshot, python_files_to_yaml
import pytest
import sys
from types import ModuleType
from tests.test_query_authoring import PROFILES


def test_browser_snapshot_preserves_yaml_and_factory_locations():
    files = {'graph.py': '''from sa_dsl import Project, Golang, ServiceModule
project = Project("Navigation")
service = project.service("Worker", language=Golang(), module=ServiceModule("example/worker"))
pipeline = service.pipeline("Main")
def factory(name):
    return pipeline.merge(name)
one = factory("One")
two = factory("Two")
'''}
    snapshot = python_files_to_snapshot(files, 'graph:project')
    assert snapshot['yaml'] == python_files_to_yaml(files, 'graph:project')
    nodes = snapshot['sourceLocations']['nodes']['worker']
    assert nodes['one']['file'] == 'graph.py'
    assert nodes['one']['line'] == nodes['two']['line'] == 6
    assert any(item['line'] == 7 for item in nodes['one']['related'])
    assert any(item['line'] == 8 for item in nodes['two']['related'])


@pytest.mark.parametrize('profile,language,_connector_id', PROFILES)
def test_query_factory_navigation_keeps_each_request_result_and_error_link(profile, language, _connector_id):
    operation = 'Rows' if profile.startswith('postgresql_') else 'GetObject'
    source = f'''from sa_dsl import Project, {language.__name__}, ServiceModule, Function
project = Project("Navigation")
request = project.string_type("Request")
result = project.string_type("Result")
failure = project.error_type("Failure")
storage = project.{profile}_connector("Storage")
endpoint = storage.endpoint("Read", function=Function("Read"), query_operation="{operation}")
service = project.service("Worker", language={language.__name__}(), module=ServiceModule("example/worker"))
pipeline = service.pipeline("Main")
def factory(name, entry):
    return pipeline.query(name, endpoint=endpoint, value_type=result, source=entry)
first = pipeline.substream("First", value_type=request)
second = pipeline.substream("Second", value_type=request)
one = factory("One", first)
two = factory("Two", second)
one >> first
two >> second
first_error = pipeline.error("First error", value_type=failure)
second_error = pipeline.error("Second error", value_type=failure)
one.on_error(first_error)
two.on_error(second_error)
'''
    snapshot = python_files_to_snapshot({'graph.py': source}, 'graph:project')
    assert snapshot['yaml'] == python_files_to_yaml({'graph.py': source}, 'graph:project')
    nodes = snapshot['sourceLocations']['nodes']['worker']
    links = snapshot['sourceLocations']['links']['worker']

    def line(text):
        return source.splitlines().index(text) + 1

    factory_line = line('    return pipeline.query(name, endpoint=endpoint, value_type=result, source=entry)')
    for query, entry, error in [('one', 'first', 'firstError'), ('two', 'second', 'secondError')]:
        assert nodes[query]['line'] == factory_line
        assert links[entry][query]['line'] == factory_line
        assert links[query][entry]['line'] == line(f'{query} >> {entry}')
        assert links[query][error]['line'] == line(f'{query}.on_error({entry}_error)')
        call_line = line(f'{query} = factory("{query.title()}", {entry})')
        assert any(location['line'] == call_line for location in nodes[query]['related'])
        assert any(location['line'] == call_line for location in links[entry][query]['related'])
        assert nodes[query]['file'] == 'graph.py'


@pytest.mark.parametrize('fail', [False, True])
def test_snapshot_restores_host_module_even_after_evaluation_failure(monkeypatch, fail):
    host_module = ModuleType('graph')
    monkeypatch.setitem(sys.modules, 'graph', host_module)
    source = 'from sa_dsl import Project\nproject = Project("Fresh workspace")\n'
    if fail:
        source += 'raise RuntimeError("fixture failure")\n'
        with pytest.raises(RuntimeError, match='fixture failure'):
            python_files_to_snapshot({'graph.py': source}, 'graph:project')
    else:
        snapshot = python_files_to_snapshot({'graph.py': source}, 'graph:project')
        assert 'Fresh workspace' in snapshot['yaml']
    assert sys.modules['graph'] is host_module
