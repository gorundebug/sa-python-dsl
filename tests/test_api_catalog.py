from __future__ import annotations

import json
import unittest

from sa_dsl.mcp_resources import catalog_resource


class ApiCatalogTest(unittest.TestCase):
    def test_typed_api_is_generated_from_runtime_signatures(self) -> None:
        catalog = json.loads(catalog_resource("authoring", "typed-api"))
        self.assertTrue(catalog["generated"])
        stream = catalog["classes"]["Stream"]["methods"]
        pipeline = catalog["classes"]["Pipeline"]["methods"]
        self.assertIn("async_", stream["function_call"]["signature"])
        self.assertIn("priority", stream["priority_task_pool_call"]["signature"])
        self.assertIn("flat_map_iterable", pipeline)
        self.assertNotIn("_stream", pipeline)

    def test_connector_capabilities_follow_factory_parameters(self) -> None:
        catalog = json.loads(
            catalog_resource("authoring", "connector-capabilities")
        )
        temporal = catalog["connectors"]["temporal_connector"]
        self.assertEqual(
            {"Go", "Python", "TypeScript"},
            set(temporal["languageAdapters"]),
        )
        self.assertNotIn("Rust", temporal["languageAdapters"])
        self.assertIn("address", temporal["requiredParameters"])
        self.assertIn("namespace", temporal["requiredParameters"])

    def test_recipes_include_decisions_and_anti_patterns(self) -> None:
        index = json.loads(catalog_resource("patterns", "index"))
        recipe = json.loads(
            catalog_resource("patterns", "iterable-worker-aggregation")
        )
        review = json.loads(
            catalog_resource("authoring", "review-checklist")
        )
        self.assertIn("temporal-parallel", index["topics"])
        self.assertIn("correlation key", recipe["decisions"])
        self.assertIn("using Split to expand an iterable", recipe["antiPatterns"])
        self.assertIn("state", review)
        self.assertIn("proof", review)


if __name__ == "__main__":
    unittest.main()
