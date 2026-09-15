from copy import deepcopy
import unittest
from unittest.mock import patch

import yaml

from component_fixture import component_project
from sa_dsl import yaml_to_python_files, python_files_to_yaml
from sa_dsl.code_generation import ServiceArchitectClient
from sa_dsl.component_document_validation import (
    ComponentValidationError, require_canonical_components, validate_canonical_components,
)
from sa_dsl.generation import _CanonicalProject


class CanonicalComponentValidationTests(unittest.TestCase):
    def model(self):
        project, service, fragments = component_project()
        component = service.component("Pricing")
        for members in fragments:
            component.fragment(*members)
        return project, fragments

    def invalid(self):
        project, fragments = self.model()
        fragments[1][0].properties["functionName"] = "DifferentBusinessFunction"
        return project

    def test_canonical_and_typed_paths_return_the_same_diagnostic(self):
        project = self.invalid()
        expected = [item.to_dict() for item in project.validate() if item.code.startswith("SA_COMPONENT_")]
        self.assertEqual([item.to_dict() for item in validate_canonical_components(project.to_document())], expected)

    def test_valid_document_is_unchanged_and_does_not_execute_code(self):
        project, _ = self.model()
        document = project.to_document()
        before = deepcopy(document)
        with patch("builtins.exec", side_effect=AssertionError("must not execute Python")), \
             patch("subprocess.Popen", side_effect=AssertionError("must not run a process")):
            self.assertEqual(validate_canonical_components(document), [])
        self.assertEqual(document, before)

    def test_yaml_import_rejects_mismatch_before_creating_workspace_files(self):
        source = self.invalid().to_yaml()
        with patch("sa_dsl.importer._Writer") as writer:
            with self.assertRaises(ComponentValidationError) as caught:
                yaml_to_python_files(source, "invalid_components")
            writer.assert_not_called()
        self.assertEqual(caught.exception.diagnostics[0]["code"], "SA_COMPONENT_FRAGMENT_MISMATCH")

    def test_canonical_wrapper_cannot_bypass_async_or_legacy_generation_checks(self):
        source = self.invalid().to_yaml()
        for authentication in ({"api_key": "test-key"}, {"id_token": "test-token"}):
            with self.subTest(authentication=list(authentication)):
                client = ServiceArchitectClient(**authentication)
                with patch.object(client, "_generate_async") as async_call, \
                     patch.object(client, "_generate_legacy") as legacy_call:
                    with self.assertRaises(ComponentValidationError):
                        client.generate_code(_CanonicalProject(source))
                    async_call.assert_not_called()
                    legacy_call.assert_not_called()

    def test_valid_yaml_python_yaml_still_preserves_membership(self):
        project, _ = self.model()
        original = project.to_document()
        files = yaml_to_python_files(original, "canonical_components")
        restored = yaml.safe_load(python_files_to_yaml(files.files, files.entrypoint))
        self.assertEqual(validate_canonical_components(restored), [])
        self.assertEqual(original["services"]["booking"]["appearance"]["components"],
                         restored["services"]["booking"]["appearance"]["components"])

    def test_unknown_member_is_rejected_without_mutating_source(self):
        project, _ = self.model()
        document = project.to_document()
        document["services"]["booking"]["appearance"]["components"]["groups"]["pricing"]["fragments"][1]["streams"][0][1] = "missing"
        original = deepcopy(document)
        with self.assertRaisesRegex(ValueError, "Unknown component stream"):
            require_canonical_components(document)
        self.assertEqual(document, original)

    def test_no_components_does_not_run_full_schema_validation(self):
        self.assertEqual(validate_canonical_components({"services": {"draft": {}}}), [])


if __name__ == "__main__":
    unittest.main()
