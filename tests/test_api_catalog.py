from __future__ import annotations

import json
import unittest

from sa_dsl.mcp_resources import catalog_resource


class ApiCatalogTest(unittest.TestCase):
    def test_typed_api_is_generated_from_runtime_signatures(self) -> None:
        catalog = json.loads(catalog_resource("authoring", "typed-api"))
        self.assertTrue(catalog["generated"])
        stream = json.loads(catalog_resource("authoring", "typed-api-Stream"))["methods"]
        pipeline = json.loads(catalog_resource("authoring", "typed-api-Pipeline"))["methods"]
        self.assertIn("function_call", stream)
        function_call = json.loads(catalog_resource("authoring", "typed-api-Stream-function_call"))
        priority_call = json.loads(catalog_resource("authoring", "typed-api-Stream-priority_task_pool_call"))
        self.assertIn("async_", function_call["signature"])
        self.assertIn("priority", priority_call["signature"])
        self.assertIn("flat_map_iterable", pipeline)
        self.assertNotIn("_stream", pipeline)

    def test_api_resources_are_bounded_and_links_resolve(self) -> None:
        def read(uri):
            topic = uri.removeprefix("servicegen://authoring/")
            rendered = catalog_resource("authoring", topic)
            self.assertLess(len(rendered.encode()), 16000, uri)
            result = json.loads(rendered)
            self.assertNotIn("status", result)
            return result

        root = read("servicegen://authoring/typed-api")
        for class_ref in root["classes"].values():
            methods = read(class_ref["resource"])["methods"]
            for method_ref in methods.values():
                method = read(method_ref["resource"])
                self.assertIn("signature", method)
                self.assertIn("parameters", method)

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
