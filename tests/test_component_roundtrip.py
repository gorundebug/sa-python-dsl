import unittest
from unittest.mock import patch

import yaml

from sa_dsl import Golang, Project, ServiceModule, python_files_to_yaml, yaml_to_python_files
from sa_dsl.code_generation import to_api_document, ServiceArchitectClient
from sa_dsl.generation import _CanonicalProject


class ComponentRoundTripTests(unittest.TestCase):
    def model(self):
        project = Project("Components")
        service = project.service("Booking", language=Golang(), module=ServiceModule(path="example.com/booking"))
        component = service.component("Reservations", description="Two pipelines")
        component.pipeline("validate")
        component.pipeline("reserve")
        return project

    def test_yaml_python_yaml_preserves_entities_and_membership(self):
        document = self.model().to_document()
        workspace = yaml_to_python_files(document, "component_roundtrip")
        generated = "\n".join(workspace.files.values())
        self.assertIn(".component(", generated)
        self.assertIn("component=", generated)
        restored = yaml.safe_load(python_files_to_yaml(workspace.files, workspace.entrypoint))
        self.assertEqual(restored["services"]["booking"]["appearance"]["components"],
                         document["services"]["booking"]["appearance"]["components"])

    def test_editor_json_keeps_metadata(self):
        document = self.model().to_document()
        self.assertEqual(to_api_document(document)["services"][0]["appearance"]["components"],
                         document["services"]["booking"]["appearance"]["components"])

    def test_generation_does_not_send_editor_metadata(self):
        project = self.model()
        client = ServiceArchitectClient(api_key="test-key")
        with patch.object(client, "_generate_async", return_value="archive") as generate:
            self.assertEqual(client.generate_code(project), "archive")
        self.assertNotIn("components", generate.call_args.args[0]["services"][0].get("appearance", {}))
        self.assertIn("components", project.to_document()["services"]["booking"]["appearance"])

    def test_mcp_canonical_wrapper_strips_the_entire_editor_only_appearance(self):
        source = self.model().to_yaml()
        client = ServiceArchitectClient(api_key="test-key")
        with patch.object(client, "_generate_async", return_value="archive") as generate:
            client.generate_code(_CanonicalProject(source))
        self.assertNotIn("appearance", generate.call_args.args[0]["services"][0])


if __name__ == "__main__":
    unittest.main()
