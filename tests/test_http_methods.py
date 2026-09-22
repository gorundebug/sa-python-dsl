import copy
import unittest
from pathlib import Path

import yaml

from sa_dsl import HTTPMethodType
from sa_dsl.browser import python_files_to_yaml
from sa_dsl.importer import yaml_to_python_files
from sa_dsl.validation import HTTP_METHODS


METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", "CONNECT"}


class HttpMethodsTest(unittest.TestCase):
    def test_enum_matches_validation(self):
        self.assertEqual(METHODS, {method.value for method in HTTPMethodType})
        self.assertEqual(METHODS, HTTP_METHODS)

    def test_all_methods_round_trip(self):
        source = Path(__file__).resolve().parents[2] / "servicegen/cmd/codegenerator/examples/example.yaml"
        original = yaml.safe_load(source.read_text(encoding="utf-8"))
        connector_key = next(key for key, connector in original["dataConnectors"].items()
                             if connector["type"] == "HTTP" and connector.get("endpoints"))
        endpoint_key = next(iter(original["dataConnectors"][connector_key]["endpoints"]))
        for method in sorted(METHODS):
            with self.subTest(method=method):
                document = copy.deepcopy(original)
                endpoint = document["dataConnectors"][connector_key]["endpoints"][endpoint_key]
                endpoint["httpMethodType"] = method
                endpoint["path"] = "/http-method-round-trip/" + method.lower()
                generated = yaml_to_python_files(document, "http_method_" + method.lower())
                restored = yaml.safe_load(python_files_to_yaml(generated.files, generated.entrypoint))
                actual = restored["dataConnectors"][connector_key]["endpoints"][endpoint_key]
                self.assertEqual(method, actual["httpMethodType"])
                self.assertEqual(endpoint["path"], actual["path"])


if __name__ == "__main__":
    unittest.main()
