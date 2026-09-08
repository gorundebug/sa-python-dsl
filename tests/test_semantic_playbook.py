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
        self.assertIn("Separate topology from invocation semantics", skill)
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

    def test_complex_patterns_are_machine_readable(self) -> None:
        intent = json.loads(catalog_resource("semantics", "intent-model"))
        fan_out = json.loads(catalog_resource("semantics", "fan-out"))
        temporal = json.loads(
            catalog_resource("semantics", "temporal-orchestration")
        )
        self.assertIn("correlation", intent["requiredAxes"])
        self.assertIn("Worker stream", fan_out["shape"])
        self.assertIn("stable Temporal schedule ID", temporal["scheduled"])


if __name__ == "__main__":
    unittest.main()
