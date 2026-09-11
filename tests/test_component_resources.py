import json
import unittest

from sa_dsl.api_catalog import build_typed_api_catalog
from sa_dsl.mcp_resources import catalog_resource


class ComponentResourcesTests(unittest.TestCase):
    def test_service_and_component_are_discoverable(self):
        classes = build_typed_api_catalog()["classes"]
        self.assertIn("component", classes["Service"]["methods"])
        self.assertIn("pipeline", classes["Component"]["methods"])
        pipeline = classes["Service"]["methods"]["pipeline"]
        component = next(p for p in pipeline["parameters"] if p["name"] == "component")
        self.assertFalse(component["required"])
        self.assertIn("Component", component["annotation"])

    def test_semantics_links_resolve_to_reflected_signatures(self):
        semantics = json.loads(catalog_resource("semantics", "visual-components"))
        index = json.loads(catalog_resource("semantics", "index"))
        self.assertIn("visual-components", index["topics"])
        for uri in semantics["apiResources"]:
            category, topic = uri.removeprefix("servicegen://").split("/", 1)
            resource = json.loads(catalog_resource(category, topic))
            self.assertNotEqual(resource.get("status"), "not_found")
            self.assertTrue(resource["generated"])
            self.assertIn("signature", resource)


if __name__ == "__main__":
    unittest.main()
