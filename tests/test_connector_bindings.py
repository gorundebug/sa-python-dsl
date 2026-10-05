from __future__ import annotations

import inspect
import unittest

import yaml

from sa_dsl import DataConnectorImplementation, KafkaCluster, Project
from sa_dsl.api_catalog import build_typed_api_catalog
from sa_dsl.browser import python_files_to_yaml
from sa_dsl.code_generation import to_api_document
from sa_dsl.importer import yaml_to_python_files
from sa_dsl.model import DslValidationError


class ConnectorBindingsTest(unittest.TestCase):
    def factories(self):
        return (
            ("http_connector", {}),
            ("grpc_connector", {}),
            ("kafka_connector", {"cluster": KafkaCluster(brokers="localhost:9092")}),
            ("cron_connector", {}),
            ("temporal_connector", {"address": "localhost:7233", "namespace": "default"}),
            ("custom_connector", {}),
        )

    def test_every_public_factory_accepts_open_targets_without_changing_defaults(self):
        catalog = build_typed_api_catalog()["classes"]["Project"]["methods"]
        for name, arguments in self.factories():
            with self.subTest(factory=name):
                before = getattr(Project("Example"), name)("Transport", **arguments).to_document()
                self.assertNotIn("implementations", before)
                self.assertFalse(any(field.endswith("Implementation") for field in before))
                bindings = {"external": "vendor/transport"}
                connector = getattr(Project("Example"), name)("Transport", **arguments, implementations=bindings)
                bindings["external"] = "mutated"
                after = connector.to_document()
                self.assertEqual({"external": "vendor/transport"}, after.pop("implementations"))
                self.assertEqual(before, after)
                self.assertIn("implementations", catalog[name]["signature"])

    def test_yaml_python_yaml_and_api_keep_bindings_for_every_connector(self):
        project = Project("Bindings")
        for index, (name, arguments) in enumerate(self.factories()):
            getattr(project, name)(f"Transport {index}", **arguments,
                                   implementations={"external": f"vendor/transport-{index}"})
        document = project.to_document()
        restored = yaml_to_python_files(project.to_yaml(), "bindings_example")
        self.assertEqual(document, yaml.safe_load(python_files_to_yaml(restored.files, restored.entrypoint)))
        api_document = to_api_document(document)
        self.assertEqual(
            [item["implementations"] for item in document["dataConnectors"].values()],
            [item["implementations"] for item in api_document["dataConnectors"]],
        )

    def test_dictionary_only_import_does_not_reintroduce_legacy_defaults(self):
        project = Project("Dictionary Only")
        project.http_connector("HTTP", implementations={"external": "vendor/http"})
        document = project.to_document()
        connector = document["dataConnectors"]["hTTP"] if "hTTP" in document["dataConnectors"] else next(iter(document["dataConnectors"].values()))
        self.assertFalse(any(field.endswith("Implementation") for field in connector))
        connector["implementations"]["golang"] = "custom/http"
        restored = yaml_to_python_files(document, "dictionary_only")
        self.assertEqual(document, yaml.safe_load(python_files_to_yaml(restored.files, restored.entrypoint)))

    def test_explicit_selection_is_not_overridden_by_dsl_defaults(self):
        connector = Project("Custom").http_connector(
            "HTTP", implementations={"golang": "custom/http"}
        )
        self.assertNotIn("goImplementation", connector.to_document())
        self.assertEqual("custom/http", connector.to_document()["implementations"]["golang"])

    def test_aliases_and_enum_values(self):
        connector = Project("Aliases").http_connector("HTTP", implementations={
            "go": DataConnectorImplementation.NET_HTTP, "golang": "net/http",
        })
        self.assertEqual({"go": "net/http", "golang": "net/http"}, connector.to_document()["implementations"])
        with self.assertRaisesRegex(DslValidationError, "Conflicting"):
            Project("Conflict").http_connector("HTTP",
                implementations={"go": "one", "golang": "two"})

    def test_removed_selectors_fail_import_projection_and_mutation(self):
        fields = ("goImplementation", "cppUserverImplementation", "cppCoroImplementation",
                  "pythonImplementation", "rustImplementation", "typeScriptImplementation")
        for field in fields:
            for value in (None, "old/transport"):
                with self.subTest(field=field, value=value):
                    document = {"settings": {"name": "Invalid"}, "dataConnectors": {
                        "http": {"name": "HTTP", "type": "HTTP", field: value}}}
                    with self.assertRaisesRegex(ValueError, field):
                        yaml_to_python_files(document, "invalid")
                    with self.assertRaisesRegex(ValueError, field):
                        to_api_document(document)
                    project = Project("Mutation")
                    connector = project.http_connector("HTTP")
                    connector.properties[field] = value
                    self.assertTrue(any(item.code == "SG_SCHEMA_UNKNOWN_FIELD" and item.path.endswith(field)
                                        for item in project.validate()))
                    with self.assertRaisesRegex(DslValidationError, field):
                        connector.to_document()

    def test_factories_do_not_accept_language_specific_parameters(self):
        removed = ("go_implementation", "cpp_userver_implementation", "cpp_coro_implementation",
                   "python_implementation", "rust_implementation", "type_script_implementation")
        for name, arguments in self.factories():
            factory = getattr(Project("Invalid"), name)
            for parameter in removed:
                with self.subTest(factory=name, parameter=parameter):
                    self.assertNotIn(parameter, inspect.signature(factory).parameters)
                    with self.assertRaises(TypeError):
                        factory("HTTP", **arguments, **{parameter: None})

    def test_invalid_mappings_and_values_are_not_coerced(self):
        for value in ([], "http", {"": "http"}, {"../target": "http"}, {"*": "http"},
                      {1: "http"}, {"external": None}, {"external": 1},
                      {"external": ""}, {"external": " http"}):
            with self.subTest(value=value), self.assertRaises(DslValidationError):
                Project("Invalid").http_connector("HTTP", implementations=value)

    def test_mutation_is_validated_before_export(self):
        project = Project("Mutable")
        connector = project.http_connector("HTTP", implementations={"external": "vendor/http"})
        saved = connector.to_document()
        saved["implementations"]["external"] = "mutated-export"
        self.assertEqual("vendor/http", connector.properties["implementations"]["external"])
        connector.properties["implementations"]["external"] = None
        self.assertTrue(any("implementations" in diagnostic.path for diagnostic in project.validate()))
        with self.assertRaises(DslValidationError):
            connector.to_document()

    def test_empty_dictionary_stays_an_object(self):
        connector = Project("Empty").http_connector("HTTP", implementations={})
        self.assertEqual({}, connector.to_document()["implementations"])


if __name__ == "__main__":
    unittest.main()
