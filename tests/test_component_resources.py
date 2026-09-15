import json
import unittest

from sa_dsl.api_catalog import build_typed_api_catalog
from sa_dsl.mcp_resources import catalog_resource


def object_fields(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AssertionError("Expected a JSON object")
    fields: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise AssertionError("Expected string object keys")
        fields[key] = item
    return fields


def array_values(value: object) -> list[object]:
    if not isinstance(value, list):
        raise AssertionError("Expected a JSON array")
    return list(value)


def string_value(value: object) -> str:
    if not isinstance(value, str):
        raise AssertionError("Expected a string")
    return value


class ComponentResourcesTests(unittest.TestCase):
    def test_service_and_component_are_discoverable(self) -> None:
        catalog = object_fields(build_typed_api_catalog())
        classes = object_fields(catalog["classes"])
        service_methods = object_fields(object_fields(classes["Service"])["methods"])
        component_methods = object_fields(object_fields(classes["Component"])["methods"])
        self.assertIn("component", service_methods)
        self.assertIn("fragment", component_methods)
        pipeline = object_fields(service_methods["pipeline"])
        parameters = array_values(pipeline["parameters"])
        self.assertNotIn("component", [string_value(object_fields(parameter)["name"]) for parameter in parameters])
        self.assertNotIn("pipeline", component_methods)


    def test_semantics_links_resolve_to_reflected_signatures(self) -> None:
        semantics = object_fields(json.loads(catalog_resource("semantics", "visual-components")))
        index = object_fields(json.loads(catalog_resource("semantics", "index")))
        self.assertIn("visual-components", array_values(index["topics"]))
        for value in array_values(semantics["apiResources"]):
            uri = string_value(value)
            self.assertTrue(uri.startswith("servicegen://"))
            category, topic = uri.removeprefix("servicegen://").split("/", 1)
            resource = object_fields(json.loads(catalog_resource(category, topic)))
            self.assertNotEqual(resource.get("status"), "not_found")
            self.assertIs(resource["generated"], True)
            self.assertTrue(string_value(resource["signature"]))


if __name__ == "__main__":
    unittest.main()
