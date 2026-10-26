from sa_dsl import python_files_to_snapshot, python_files_to_yaml


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
