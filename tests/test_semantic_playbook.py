from __future__ import annotations

import json
from pathlib import Path
import unittest

from sa_dsl.mcp_resources import catalog_resource


ROOT = Path(__file__).resolve().parents[1]


class SemanticPlaybookContractTest(unittest.TestCase):
    def test_authoring_skill_requires_semantic_classification(self) -> None:
        skill = (
            ROOT
            / "plugins/service-architect/skills/service-architect-authoring/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("references/semantic-playbook.md", skill)
        self.assertIn(
            "Separate cardinality, topology, and invocation semantics",
            skill,
        )
        self.assertIn("preview_architecture_diff", skill)

    def test_call_semantics_explain_intent_and_exclusions(self) -> None:
        resource = json.loads(catalog_resource("semantics", "call-semantics"))
        values = resource["values"]
        self.assertEqual(
            "source.priority_task_pool_call(target, pool=pool, priority=priority)",
            values["PriorityTaskPool"]["api"],
        )
        self.assertIn(
            "collection fan-out",
            values["PriorityTaskPool"]["doesNotMean"],
        )
        self.assertIn(
            "Do not infer a method from the word parallel alone.",
            resource["selectionRules"],
        )
        self.assertIn(
            "Declare the graph edge before calling a typed call-semantics method.",
            resource["selectionRules"],
        )
        self.assertEqual([0, 255], values["PriorityTaskPool"]["priorityRange"])

    def test_complex_patterns_are_machine_readable(self) -> None:
        intent = json.loads(catalog_resource("semantics", "intent-model"))
        fan_out = json.loads(catalog_resource("semantics", "fan-out"))
        temporal = json.loads(
            catalog_resource("semantics", "temporal-orchestration")
        )
        self.assertIn("correlation", intent["requiredAxes"])
        self.assertIn("FlatMapIterable or FlatMap", fan_out["shape"])
        self.assertIn("Optional Split broadcast", fan_out["shape"])
        self.assertIn("stable Temporal schedule ID", temporal["scheduled"])

    def test_operator_and_boundary_rules_match_typed_api(self) -> None:
        operators = json.loads(
            catalog_resource("semantics", "operator-selection")
        )
        api = json.loads(catalog_resource("semantics", "authoring-api"))
        boundaries = json.loads(catalog_resource("semantics", "boundaries"))
        self.assertIn("iterable input", operators["FlatMapIterable"])
        self.assertIn("Broadcast", operators["Split"])
        self.assertIn("does not create", api["wiring"]["typed call method"])
        self.assertIn("consumer group", boundaries["Kafka"])


if __name__ == "__main__":
    unittest.main()
