import unittest
import yaml
from sa_dsl import Appearance, Project, Golang, ServiceModule, DslValidationError, yaml_to_python_files, python_files_to_yaml


class ComponentNamingTests(unittest.TestCase):
    def project(self):
        project = Project('Components')
        service = project.service('Analytics', language=Golang(), module=ServiceModule(path='example.com/analytics'))
        return project, service

    def test_readable_python_and_name_based_yaml_roundtrip(self):
        project, service = self.project()
        component = service.component('MyComponent', description='')
        component.pipeline('first')
        service.component('Join', appearance=Appearance(x=-284, y=-1501)).pipeline('second')
        original = project.to_document()
        workspace = yaml_to_python_files(original, 'component_names')
        code = '\n'.join(workspace.files.values())
        self.assertIn('myComponentComponent = ', code)
        self.assertIn('joinComponent = ', code)
        self.assertNotIn('_component_1', code)
        self.assertNotIn('key=', code)
        self.assertNotIn("description=''", code)
        self.assertEqual(yaml.safe_load(python_files_to_yaml(workspace.files, workspace.entrypoint)), original)

    def test_rename_updates_exported_references(self):
        project, service = self.project()
        component = service.component('Before')
        component.pipeline('first')
        component.name = 'After'
        metadata = service.to_document()['appearance']['components']
        self.assertEqual(metadata['pipelines'], {'first': 'after'})
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
