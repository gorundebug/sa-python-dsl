import json
import unittest

from sa_dsl.code_generation import to_api_document
from sa_dsl.mcp_resources import catalog_resource


class QueryExamplesTest(unittest.TestCase):
    def test_resource_examples_validate_and_export_real_query_models(self):
        for topic, connector, operation in (
            ("query-postgresql", 12, "Rows"), ("query-s3", 18, "GetObject"),
        ):
            with self.subTest(topic=topic):
                resource = json.loads(catalog_resource("examples", topic))
                namespace = {}
                # Execute our shipped, reviewed documentation, never a user workspace.
                exec(compile(resource["python"], topic, "exec"), namespace)
                project = namespace["project"]
                self.assertEqual([], project.validate())
                api = to_api_document(project.to_document())
                self.assertEqual(connector, api["dataConnectors"][0]["type"])
                self.assertEqual(operation, api["endpoints"][0]["queryOperation"])
                self.assertEqual([18, 19], [node["type"] for node in api["streams"]])
                self.assertNotIn("connectionString", api["dataConnectors"][0])
                self.assertEqual("servicegen://semantics/query", resource["semanticsResource"])

    def test_recipe_and_examples_are_discoverable(self):
        patterns = json.loads(catalog_resource("patterns", "index"))
        self.assertIn("storage-query", patterns["topics"])
        recipe = json.loads(catalog_resource("patterns", "storage-query"))
        examples = json.loads(catalog_resource("examples", "index"))
        for uri in recipe["exampleResources"]:
            self.assertIn(uri, examples["resources"])
