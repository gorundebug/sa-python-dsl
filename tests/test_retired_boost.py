import copy
import inspect
import runpy
import tempfile
import unittest
from pathlib import Path

import sa_dsl
from sa_dsl import CppCoro, CppUserver, DataConnectorImplementation, Project, ServiceModule
from sa_dsl.code_generation import to_api_document
from sa_dsl.importer import yaml_to_python_files, yaml_to_python_project
from sa_dsl.manifest import SUPPORTED_GENERATION_TARGETS
from sa_dsl.model import ProgrammingLanguage
from sa_dsl.retired_backends import require_supported_backends
from sa_dsl.servicegen_capabilities import TARGET_BACKENDS
from sa_dsl.validation import validate_project


class RetiredBoostTest(unittest.TestCase):
    def test_public_api_and_generated_defaults_do_not_expose_retired_runtime(self):
        self.assertFalse(hasattr(sa_dsl, "CppBoost"))
        self.assertNotIn("CppBoost", {member.value for member in ProgrammingLanguage})
        self.assertNotIn("cpp-boost", SUPPORTED_GENERATION_TARGETS)
        self.assertNotIn("cpp-boost", TARGET_BACKENDS)
        project = Project("Coro")
        project.http_connector("HTTP")
        project.grpc_connector("RPC")
        project.cron_connector("Cron")
        for connector in project.to_document()["dataConnectors"].values():
            self.assertNotIn("cppBoostImplementation", connector)
            self.assertIn("cppCoroImplementation", connector)
        for name in ("http_connector", "grpc_connector", "kafka_connector", "cron_connector"):
            self.assertNotIn("cpp_boost_implementation", inspect.signature(getattr(Project, name)).parameters)
        self.assertEqual(DataConnectorImplementation.BOOST_BEAST_HTTP.value, "boost/beast-http")

    def test_checked_in_example_uses_current_connector_options(self):
        example = Path(__file__).resolve().parents[1] / "examples/processorder/main.py"
        project = runpy.run_path(str(example))["project"]
        connectors = project.to_document()["dataConnectors"]
        self.assertGreaterEqual(len(connectors), 4)
        for connector in connectors.values():
            self.assertNotIn("cppBoostImplementation", connector)
        grpc = [connector for connector in connectors.values() if connector.get("type") == "gRPC"]
        self.assertTrue(grpc)
        for connector in grpc:
            self.assertEqual(connector["cppCoroImplementation"], "google/grpc")
        from sa_dsl.api_catalog import LANGUAGE_PARAMETERS
        self.assertNotIn("cpp_boost_implementation", LANGUAGE_PARAMETERS)
        self.assertEqual(validate_project(project), [])
        document = project.to_document()
        pipeline = document["services"]["inventoryService"]["pipelines"]["inventoryItem"]
        failure = pipeline["getInventoryItemError"]
        self.assertEqual(failure["type"], "Error")
        self.assertEqual(failure["valueType"], "inventoryFailure")
        self.assertFalse(failure.get("functionName"))
        conversion = pipeline["mapInventoryItemError"]
        self.assertEqual(conversion["type"], "Map")
        self.assertEqual(conversion["source"], "getInventoryItemError")
        self.assertEqual(conversion["functionName"], "GetInventoryItemError")
        self.assertEqual(conversion["valueType"], "orderItemResult")
        self.assertEqual(
            set(pipeline["mergeInventoryResult"]["sources"]),
            {"getInventoryItemData", "mapInventoryItemError"},
        )

    def test_numeric_ids_do_not_shift_when_boost_is_removed(self):
        project = Project("Languages")
        for name, language in (("Coro", CppCoro()), ("Userver", CppUserver()), ("TS", sa_dsl.TypeScript())):
            project.service(name, language=language, module=ServiceModule("example/"+name.lower()))
        self.assertEqual([7, 2, 6], [service["programmingLanguage"] for service in to_api_document(project.to_document())["services"]])

    def test_import_and_generation_reject_old_language_without_mutating_input(self):
        for language in ("CppBoost", "cppBoost", "cpp-boost", 5):
            document = {"settings": {"name": "Legacy"}, "services": {
                "worker": {"name": "Worker", "modulePath": "example/worker", "programmingLanguage": language},
            }}
            before = copy.deepcopy(document)
            for operation in (lambda: yaml_to_python_files(document, "legacy"), lambda: to_api_document(document)):
                with self.assertRaisesRegex(ValueError, r"\$\.services\.worker\.programmingLanguage:.*removed.*coroutine API"):
                    operation()
            self.assertEqual(before, document)
            with tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / "imported"
                with self.assertRaises(ValueError):
                    yaml_to_python_project(document, destination)
                self.assertFalse(destination.exists())

    def test_old_selector_is_not_silently_discarded_even_without_boost_services(self):
        document = {"dataConnectors": {"http": {"type": "HTTP", "cppBoostImplementation": "boost/beast-http"}}}
        with self.assertRaisesRegex(ValueError, r"dataConnectors.http.cppBoostImplementation"):
            yaml_to_python_files(document, "legacy")
        with self.assertRaisesRegex(ValueError, r"dataConnectors\[0\].cppBoostImplementation"):
            require_supported_backends({"dataConnectors": list(document["dataConnectors"].values())})

    def test_mutated_typed_model_also_reports_retired_language(self):
        project = Project("Legacy")
        service = project.service("Worker", language=CppCoro(), module=ServiceModule("example/worker"))
        service.programming_language = "CppBoost"
        diagnostics = validate_project(project)
        self.assertTrue(any(item.code == "SG_CAPABILITY_UNSUPPORTED_FEATURE" and "coroutine API" in item.message for item in diagnostics))


if __name__ == "__main__":
    unittest.main()
