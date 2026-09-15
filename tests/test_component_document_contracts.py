"""Typed component boundaries reject malformed data, never guess its shape."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
import unittest

from component_fixture import component_project
from sa_dsl.component_document_validation import require_canonical_components, validate_canonical_components
from sa_dsl.visual_components import ComponentMetadata, normalize_components, without_visual_components


class ComponentDocumentContractTests(unittest.TestCase):
    def test_boundary_functions_have_annotations_and_no_dynamic_escape_hatches(self) -> None:
        for filename in ("visual_components.py", "component_document_validation.py"):
            source = Path(__file__).parents[1] / "src" / "sa_dsl" / filename
            tree = ast.parse(source.read_text(encoding="utf-8"))
            self.assertEqual(tree.type_ignores, [])
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.assertIsNotNone(node.returns, f"{filename}: {node.name}")
                    for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                        if arg.arg != "self":
                            self.assertIsNotNone(arg.annotation, f"{filename}: {node.name}.{arg.arg}")
                if isinstance(node, ast.Name):
                    self.assertNotIn(node.id, ("Any", "getattr", "cast"), filename)

    def test_rejects_nonstring_mapping_keys_at_the_document_boundary(self) -> None:
        with self.assertRaisesRegex(ValueError, "keys must be strings"):
            validate_canonical_components({"services": {42: {}}})
        with self.assertRaisesRegex(ValueError, "keys must be strings"):
            normalize_components({"version": 2, "groups": {42: {}}})

    def test_rejects_nonstring_topology_reference_instead_of_coercing_it(self) -> None:
        project, service, fragments = component_project()
        component = service.component("Pricing")
        for members in fragments:
            component.fragment(*members)
        document = project.to_document()
        document["services"][service.key]["pipelines"]["update"]["updatePrice"]["source"] = 7
        before = deepcopy(document)
        with self.assertRaisesRegex(ValueError, "source must be a string"):
            require_canonical_components(document)
        self.assertEqual(document, before)

    def test_preserves_optional_coordinates_and_returns_detached_metadata(self) -> None:
        source: ComponentMetadata = {"version": 2, "groups": {"pricing": {
            "name": "Pricing", "description": "Business processing",
            "fragments": [{"streams": [["p", "a"]], "position": {"x": 12}}],
        }}}
        normalized = normalize_components(source, [("p", "a")])
        self.assertEqual(normalized["groups"]["pricing"]["fragments"][0]["position"], {"x": 12})
        normalized["groups"]["pricing"]["fragments"][0]["streams"][0][1] = "different"
        self.assertEqual(source["groups"]["pricing"]["fragments"][0]["streams"], [["p", "a"]])

    def test_strips_only_visual_metadata_from_both_document_shapes(self) -> None:
        service: dict[str, object] = {"name": "Booking", "appearance": {
            "color": "blue", "components": {"version": 2, "groups": {}},
        }, "pipeline": "unchanged"}
        for services in ([service], {"booking": service}):
            document: dict[str, object] = {"services": services, "settings": {"name": "Project"}}
            before = deepcopy(document)
            clean = without_visual_components(document)
            self.assertEqual(document, before)
            self.assertNotIn("components", repr(clean))
            self.assertIn("unchanged", repr(clean))
            self.assertIn("blue", repr(clean))
