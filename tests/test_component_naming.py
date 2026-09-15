from component_fixture import component_project
import unittest
import yaml
from sa_dsl import Appearance, Project, Golang, ServiceModule, DslValidationError, yaml_to_python_files, python_files_to_yaml


class ComponentNamingTests(unittest.TestCase):
    def project(self):
        project = Project('Components')
        service = project.service('Analytics', language=Golang(), module=ServiceModule(path='example.com/analytics'))
        return project, service

    def test_readable_python_and_name_based_yaml_roundtrip(self):
        project, service, fragments = component_project()
        component = service.component('MyComponent', description='')
        for fragment in fragments:
            component.fragment(*fragment, appearance=Appearance(x=-284, y=-1501))
        service.component('Join')
        original = project.to_document()
        workspace = yaml_to_python_files(original, 'component_names')
        code = '\n'.join(workspace.files.values())
        self.assertIn('myComponentComponent = ', code)
        self.assertIn('joinComponent = ', code)
        self.assertNotIn('_component_1', code)
        self.assertNotIn('key=', code)
        self.assertNotIn("description=''", workspace.files["component_names/services/booking/service.py"])
        self.assertEqual(yaml.safe_load(python_files_to_yaml(workspace.files, workspace.entrypoint)), original)

    def test_rename_updates_exported_references(self):
        project, service = self.project()
        component = service.component('Before')
        service.pipeline('first')
        component.name = 'After'
        metadata = service.to_document()['appearance']['components']
        self.assertNotIn('pipelines', metadata)
        self.assertEqual(list(metadata['groups']), ['after'])

    def test_renamed_collision_is_rejected(self):
        project, service = self.project()
        service.component('First')
        other = service.component('Second')
        other.name = 'First'
        with self.assertRaises(DslValidationError):
            service.to_document()


if __name__ == '__main__':
    unittest.main()
