"""Run exactly the same canonical documents as Designer and ServiceGen."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import unittest

import yaml

from sa_dsl.component_document_validation import validate_canonical_components
from build_component_semantic_corpus import json_value, mapping


@dataclass(frozen=True)
class Case:
    name: str
    valid: bool
    yaml: str


def cases() -> list[Case]:
    path = Path(__file__).parent / "fixtures" / "component-semantics.json"
    corpus = mapping(json_value(json.loads(path.read_text(encoding="utf-8"))))
    if corpus["version"] != 1 or not isinstance(corpus["cases"], list):
        raise ValueError("Unsupported component corpus")
    result: list[Case] = []
    for item in corpus["cases"]:
        entry = mapping(item)
        name, valid, source = entry["name"], entry["valid"], entry["yaml"]
        if not isinstance(name, str) or not isinstance(valid, bool) or not isinstance(source, str):
            raise TypeError("Invalid component corpus entry")
        result.append(Case(name, valid, source))
    return result


class SharedComponentCorpusTests(unittest.TestCase):
    def test_canonical_component_contract(self) -> None:
        scenarios = cases()
        self.assertEqual(len(scenarios), 24)
        for case in scenarios:
            with self.subTest(case=case.name):
                document = mapping(json_value(yaml.safe_load(case.yaml)))
                before = json.dumps(document, sort_keys=True)
                if case.name == "overlapping-fragments":
                    with self.assertRaisesRegex(ValueError, "Component fragments must not overlap"):
                        validate_canonical_components(document)
                    self.assertEqual(json.dumps(document, sort_keys=True), before)
                    continue
                diagnostics = validate_canonical_components(document)
                self.assertEqual(not diagnostics, case.valid, [item.to_dict() for item in diagnostics])
                self.assertEqual(json.dumps(document, sort_keys=True), before)
                for diagnostic in diagnostics:
                    self.assertTrue(diagnostic.code.startswith("SA_COMPONENT_"), diagnostic)
