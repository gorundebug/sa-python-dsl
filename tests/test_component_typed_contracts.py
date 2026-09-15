"""The component matcher validates documents once and compares typed values."""
import ast
from pathlib import Path
import unittest

from component_fixture import component_project
from sa_dsl.component_validation import _json_object
from sa_dsl.validation import Validator


class ComponentTypedContractTests(unittest.TestCase):
    def test_document_boundary_rejects_unknown_values_and_nonstring_keys(self) -> None:
        for value in (object(), {"invalid": object()}, {123: "not a string key"}):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(TypeError):
                    _json_object(value)

    def test_document_boundary_retains_json_values_and_detaches_containers(self) -> None:
        value = {"items": ["text", 3, 1.5, True, None], "nested": {"key": "value"}}
        result = _json_object(value)
        self.assertEqual(result, value)
        self.assertIsNot(result, value)
        self.assertIsNot(result["items"], value["items"])
        self.assertIsNot(result["nested"], value["nested"])

    def test_invalid_serialized_metadata_becomes_a_diagnostic_not_a_crash(self) -> None:
        project, service, fragments = component_project()
        component = service.component("Pricing")
        for fragment in fragments:
            component.fragment(*fragment)
        # The public model stores user properties at its document boundary.
        fragments[0][0].properties["invalid"] = object()
        validator = Validator(project)
        from sa_dsl.component_validation import validate_components
        validate_components(validator)
        self.assertEqual(len(validator.values), 1)
        self.assertEqual(validator.values[0].code, "SA_COMPONENT_INVALID_MEMBERSHIP")
        self.assertIn("Unsupported component semantic value", validator.values[0].message)

    def test_matcher_functions_have_explicit_contracts_without_any_or_getattr(self) -> None:
        path = Path(__file__).parents[1] / "src" / "sa_dsl" / "component_validation.py"
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.assertIsNotNone(node.returns, node.name)
                for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                    if argument.arg != "self":
                        self.assertIsNotNone(argument.annotation, f"{node.name}.{argument.arg}")
            if isinstance(node, ast.Name):
                self.assertNotIn(node.id, ("Any", "getattr"))
