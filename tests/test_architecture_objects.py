import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sa_dsl.api_catalog import describe_typed_factory
from sa_dsl.architecture_objects import OBJECT_GUIDES, architecture_object_index, describe_architecture_object
from sa_dsl.execution import ExecutionResult
from sa_dsl.mcp_resources import catalog_resource
from sa_dsl.mcp_server import configure_workspace, designer_view
from sa_dsl.model import StreamType
from test_manifest_workflow import write_manifest


class ArchitectureObjectsTest(unittest.TestCase):
    def test_every_stream_operator_has_an_intent_guide(self):
        import re
        for operator in StreamType:
            kind = re.sub(r"(?<!^)(?=[A-Z])", "-", operator.value).lower()
            if operator is StreamType.SUBSTREAM:
                kind = "substream"
            self.assertIn(kind, OBJECT_GUIDES)

    def test_guides_are_bounded_and_signatures_and_links_resolve(self):
        index = architecture_object_index()
        self.assertEqual(len(OBJECT_GUIDES), len(index["objects"]))
        for item in index["objects"]:
            with self.subTest(kind=item["kind"]):
                encoded = catalog_resource("authoring", "object-" + item["kind"])
                self.assertLess(len(encoded.encode()), 20000)
                guide = json.loads(encoded)
                self.assertEqual("success", guide["status"])
                for key in ("purpose", "useWhen", "avoidWhen", "capabilityRule"):
                    self.assertTrue(guide[key])
                links = [guide["semanticsResource"], *guide["patternResources"]]
                for factory in guide["factories"]:
                    links.append(factory["resource"])
                    self.assertEqual(factory["signature"], describe_typed_factory(factory["owner"], factory["name"])["signature"])
                for uri in links:
                    category, topic = uri.removeprefix("servicegen://").split("/", 1)
                    self.assertNotEqual("not_found", json.loads(catalog_resource(category, topic)).get("status"), uri)

    def test_discovery_and_unknown_objects(self):
        index = json.loads(catalog_resource("authoring", "index"))
        self.assertIn("servicegen://authoring/object-index", index["resources"])
        self.assertIn("objects", json.loads(catalog_resource("authoring", "object-index")))
        self.assertEqual("not_found", describe_architecture_object("imaginary-node")["status"])
        self.assertEqual("flat-map", describe_architecture_object(" flat_map ")["kind"])

    def test_factories_reject_private_and_unknown_methods(self):
        for owner, method in (("Pipeline", "_stream"), ("Missing", "map"), ("Pipeline", "imaginary")):
            with self.assertRaises(ValueError):
                describe_typed_factory(owner, method)

    def test_lookup_does_not_execute_a_project_or_use_network(self):
        with patch("sa_dsl.mcp_server.execute_project", side_effect=AssertionError("execution")), patch(
            "urllib.request.urlopen", side_effect=AssertionError("network")
        ):
            from sa_dsl.mcp_server import describe_architecture_object as tool
            self.assertEqual("success", tool("http-endpoint")["status"])

    def test_designer_bind_failure_is_structured(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root)
            configure_workspace(root)
            try:
                with patch("sa_dsl.mcp_server.execute_project", return_value=ExecutionResult(
                    operation="export", status="success", project_name="Sample", rendered_yaml="settings:\n  name: Sample\n"
                )), patch("sa_dsl.mcp_server._designer_server", side_effect=PermissionError("loopback unavailable")):
                    result = designer_view()
                self.assertEqual("failed", result["status"])
                self.assertEqual("SA_DESIGNER_VIEW_FAILED", result["diagnostics"][0]["code"])
                self.assertIn("loopback unavailable", result["diagnostics"][0]["message"])
            finally:
                configure_workspace(Path.cwd())
