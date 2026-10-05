from __future__ import annotations

import inspect
import unittest

import yaml

from sa_dsl import DataType, DslValidationError, NativeTypeBinding, Project
from sa_dsl.api_catalog import build_typed_api_catalog
from sa_dsl.browser import python_files_to_yaml
from sa_dsl.code_generation import to_api_document
from sa_dsl.importer import yaml_to_python_files


class NativeTypeBindingsTest(unittest.TestCase):
    def factories(self):
        for name, factory in inspect.getmembers(Project, inspect.isfunction):
            if name.startswith("_") or not name.endswith("_type"):
                continue
            arguments = {}
            if name in {"array_type", "map_type"}:
                arguments["value_type"] = DataType.STRING
            if name == "map_type":
                arguments["key_type"] = DataType.STRING
            yield name, arguments

    def test_all_type_factories_accept_bindings_without_inventing_defaults(self):
        catalog = build_typed_api_catalog()["classes"]["Project"]["methods"]
        factories = list(self.factories())
        self.assertGreater(len(factories), 20)
        for name, arguments in factories:
            with self.subTest(factory=name):
                before = getattr(Project("Before"), name)("Record", **arguments).to_document()
                self.assertNotIn("bindings", before)
                bindings = {"external.runtime": NativeTypeBinding("NativeRecord", "vendor.records", "records")}
                value = getattr(Project("After"), name)("Record", **arguments, bindings=bindings)
                bindings["external.runtime"] = NativeTypeBinding("Changed")
                after = value.to_document()
                self.assertEqual({"external.runtime": {
                    "definition": "NativeRecord", "import": "vendor.records", "package": "records",
                }}, after.pop("bindings"))
                self.assertEqual(before, after)
                self.assertIn("bindings", catalog[name]["signature"])

    def test_yaml_python_yaml_and_api_preserve_every_type_and_target(self):
        project = Project("Native Bindings")
        for index, (name, arguments) in enumerate(self.factories()):
            getattr(project, name)(f"Record {index}", **arguments, bindings={
                "external.runtime": NativeTypeBinding(definition="ExternalRecord", import_path="records"),
                "cppUserver": NativeTypeBinding(definition="UserverRecord"),
                "cppCoro": NativeTypeBinding(definition="CoroRecord"),
                "empty": NativeTypeBinding(definition=""),
                "absent": NativeTypeBinding(),
            })
        document = project.to_document()
        generated = yaml_to_python_files(project.to_yaml(), "native_bindings_example")
        self.assertTrue(any("NativeTypeBinding(" in body for body in generated.files.values()))
        restored = yaml.safe_load(python_files_to_yaml(generated.files, generated.entrypoint))
        self.assertEqual(document, restored)
        api = to_api_document(document)
        self.assertEqual([value["bindings"] for value in document["types"].values()],
                         [value["bindings"] for value in api["types"]])
        for value in restored["types"].values():
            self.assertEqual({"definition": ""}, value["bindings"]["empty"])
            self.assertEqual({}, value["bindings"]["absent"])

    def test_removed_fields_rejected_at_import_export_validation_and_api(self):
        fields = ("typeDefinitionLang1", "typeDefinitionLang2", "typeImportLang1", "typeImportLang2",
                  "typeDefinition", "typeImport")
        for field in fields:
            for old_value in (None, "old"):
                with self.subTest(field=field, value=old_value):
                    document = {"settings": {"name": "Removed"}, "types": {
                        "record": {"name": "Record", "type": "custom", field: old_value},
                    }}
                    with self.assertRaisesRegex(ValueError, field):
                        yaml_to_python_files(document, "removed_native_binding")
                    with self.assertRaisesRegex(ValueError, field):
                        to_api_document(document)
                    project = Project("Mutation")
                    value = project.custom_type("Record")
                    value.properties[field] = old_value
                    self.assertTrue(any(item.code == "SG_SCHEMA_UNKNOWN_FIELD" and item.path.endswith(field)
                                        for item in project.validate()))
                    with self.assertRaisesRegex(DslValidationError, field):
                        value.to_document()

    def test_removed_constructor_arguments_are_not_accepted(self):
        for method in ("custom_type", "struct_type"):
            for field in ("type_definition", "type_import", "type_definition_lang1", "type_definition_lang2"):
                with self.subTest(method=method, field=field), self.assertRaises(TypeError):
                    getattr(Project("Removed"), method)("Record", **{field: None})

    def test_malformed_bindings_are_not_coerced(self):
        for bindings in ([], "native", {"": NativeTypeBinding()}, {" external": NativeTypeBinding()},
                         {1: NativeTypeBinding()}, {"external": []},
                         {"external": {"definition": 3}}, {"external": {"import": False}},
                         {"external": {"package": []}}, {"external": {"definiton": None}},
                         {"external": NativeTypeBinding(definition=5)}):
            with self.subTest(bindings=bindings), self.assertRaises(DslValidationError):
                Project("Invalid").custom_type("Record", bindings=bindings)

    def test_export_is_detached_and_mutation_is_validated(self):
        project = Project("Mutable")
        value = project.custom_type("Record", bindings={"external": NativeTypeBinding("Original")})
        exported = value.to_document()
        exported["bindings"]["external"]["definition"] = "Changed"
        self.assertEqual("Original", value.properties["bindings"]["external"]["definition"])
        value.properties["bindings"]["external"]["definition"] = 123
        self.assertTrue(any(item.code == "SG_SCHEMA_WRONG_TYPE" for item in project.validate()))
        with self.assertRaises(DslValidationError):
            value.to_document()

    def test_explicit_empty_dictionary_is_preserved(self):
        project = Project("Empty")
        project.custom_type("Record", bindings={})
        document = project.to_document()
        generated = yaml_to_python_files(document, "empty_native_bindings")
        self.assertEqual(document, yaml.safe_load(python_files_to_yaml(generated.files, generated.entrypoint)))


if __name__ == "__main__":
    unittest.main()
