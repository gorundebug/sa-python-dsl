from types import SimpleNamespace
from sa_dsl.source_locations import capture_source_locations


def test_factory_body_and_individual_calls_retain_all_instances(tmp_path):
    source = '''from sa_dsl.model import Service
service = Service("worker", "Worker", "golang", "example/worker")
pipeline = service.pipeline("Main")
def factory(name):
    return pipeline.merge(
        name
    )
one = factory("One")
two = factory("Two")
'''
    path = tmp_path / 'model.py'
    path.write_text(source)
    scope = {}
    with capture_source_locations(tmp_path) as index:
        exec(compile(source, str(path), 'exec'), scope)
    nodes = index.document(SimpleNamespace(services={'worker': scope['service']}))['nodes']['worker']
    assert nodes['one']['line'] == nodes['two']['line'] == 5
    assert nodes['one']['endLine'] == 7
    assert any(item['line'] == 8 for item in nodes['one']['related'])
    assert not any(item['line'] == 9 for item in nodes['one']['related'])
    assert any(item['line'] == 9 for item in nodes['two']['related'])


def test_calls_on_one_line_have_separate_ranges(tmp_path):
    source = '''from sa_dsl.model import Service
service = Service("worker", "Worker", "golang", "example/worker")
pipeline = service.pipeline("Main")
one = pipeline.merge("One"); two = pipeline.merge("Two")
'''
    path = tmp_path / 'model.py'; path.write_text(source)
    scope = {}
    with capture_source_locations(tmp_path) as index:
        exec(compile(source, str(path), 'exec'), scope)
    nodes = index.document(SimpleNamespace(services={'worker': scope['service']}))['nodes']['worker']
    assert nodes['one']['endColumn'] < nodes['two']['column']


def test_editor_columns_are_utf16_not_python_utf8_offsets(tmp_path):
    source = '''from sa_dsl.model import Service
service = Service("worker", "Worker", "golang", "example/worker")
pipeline = service.pipeline("Main")
label = "😀я"; one = pipeline.merge("One")
'''
    path = tmp_path / 'model.py'
    path.write_text(source)
    scope = {}
    with capture_source_locations(tmp_path) as index:
        exec(compile(source, str(path), 'exec'), scope)
    location = index.document(SimpleNamespace(services={'worker': scope['service']}))['nodes']['worker']['one']
    prefix = source.splitlines()[3].split('pipeline.merge')[0]
    assert location['column'] == len(prefix.encode('utf-16-le')) // 2 + 1
