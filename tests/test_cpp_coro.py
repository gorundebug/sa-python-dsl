import unittest

import yaml

from sa_dsl import CppCoro, DataConnectorImplementation, Project, ServiceModule
from sa_dsl.browser import python_files_to_yaml
from sa_dsl.code_generation import to_api_document
from sa_dsl.importer import yaml_to_python_files
from sa_dsl.servicegen_capabilities import TARGET_BACKENDS


class CppCoroTest(unittest.TestCase):
    def test_language_and_connector_round_trip(self) -> None:
        project = Project("Coro Example")
        project.service(
            "Worker", language=CppCoro(),
            module=ServiceModule("example.com/coro/worker"),
        )
        project.http_connector("HTTP", host="0.0.0.0", port=9091)
        project.grpc_connector("RPC", address="localhost:9092")
        project.cron_connector("Schedules")
        document = project.to_document()
        implementations = {
            item["cppCoroImplementation"]
            for item in document["dataConnectors"].values()
        }
        self.assertEqual(
            {"boost/beast-http", "google/grpc", "cpp/libcron"}, implementations,
        )
        self.assertEqual("google/grpc", DataConnectorImplementation.GOOGLE_GRPC.value)
        rpc = next(item for item in document["dataConnectors"].values() if item["type"] == "gRPC")
        for backend in ("cppUserverImplementation", "cppCoroImplementation"):
            self.assertEqual("google/grpc", rpc[backend])
        self.assertEqual("cppCoro", TARGET_BACKENDS["cpp-coro"])
        restored = yaml_to_python_files(project.to_yaml(), "coro_example")
        self.assertEqual(
            document,
            yaml.safe_load(python_files_to_yaml(restored.files, restored.entrypoint)),
        )
        api_document = to_api_document(document)
        self.assertEqual(7, api_document["services"][0]["programmingLanguage"])

    def test_import_does_not_add_missing_implementation_selectors(self) -> None:
        project = Project("Existing Example")
        project.http_connector("HTTP", host="0.0.0.0", port=9091)
        project.grpc_connector("RPC", address="localhost:9092")
        project.cron_connector("Schedules")
        document = project.to_document()
        for connector in document["dataConnectors"].values():
            for field in list(connector):
                if field.endswith("Implementation"):
                    del connector[field]
        restored = yaml_to_python_files(document, "existing_example")
        self.assertEqual(
            document,
            yaml.safe_load(python_files_to_yaml(restored.files, restored.entrypoint)),
        )


if __name__ == "__main__":
    unittest.main()
