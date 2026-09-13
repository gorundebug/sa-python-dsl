import unittest

from sa_dsl import Function, Golang, Project, ServiceModule


class HTTPModuleValidationTests(unittest.TestCase):
    def fixture(self, direction="input"):
        project = Project("HTTP API")
        connector = project.http_connector("Baker API")
        endpoint = connector.post("Request", function=Function("Handle"), path="/baker")
        service = project.service(
            "Baker", language=Golang(version="1.25.4"),
            module=ServiceModule("example.com/baker"),
        )
        if direction:
            pipeline = service.pipeline("requests")
            getattr(pipeline, direction)("Request Stream", endpoint=endpoint)
        return project, connector, service

    def module_diagnostics(self, project, connector):
        return [
            diagnostic for diagnostic in project.validate()
            if diagnostic.path == f"$.dataConnectors.{connector.key}.module"
        ]

    def test_used_http_module_is_required_for_input_and_sink(self):
        for direction in ("input", "sink"):
            for value in (None, "", "   "):
                with self.subTest(direction=direction, value=value):
                    project, connector, _ = self.fixture(direction)
                    connector.properties["module"] = value
                    diagnostics = self.module_diagnostics(project, connector)
                    self.assertTrue(any(d.code == "SG_SCHEMA_REQUIRED_FIELD" for d in diagnostics))

    def test_unused_http_connector_is_a_valid_draft(self):
        project, connector, _ = self.fixture(None)
        self.assertEqual([], self.module_diagnostics(project, connector))

    def test_module_reference_must_exist(self):
        project, connector, _ = self.fixture()
        connector.properties["module"] = "missing"
        self.assertTrue(any(
            d.code == "SG_SEMANTIC_UNKNOWN_REFERENCE"
            for d in self.module_diagnostics(project, connector)
        ))

    def test_declared_module_object_is_accepted(self):
        project = Project("HTTP API")
        module = project.module("api", module_path="example.com/api", golang_version="1.25.4")
        connector = project.http_connector("Baker API", module=module)
        endpoint = connector.post("Request", function=Function("Handle"), path="/baker")
        service = project.service("Baker", language=Golang(), module=ServiceModule("example.com/baker"))
        service.pipeline("requests").input("Request Stream", endpoint=endpoint)
        self.assertEqual([], self.module_diagnostics(project, connector))

    def test_one_missing_module_diagnostic_per_connector(self):
        project, connector, service = self.fixture()
        endpoint = connector.get("Status", function=Function("Status"), path="/status")
        service.pipeline("status").input("Status Stream", endpoint=endpoint)
        self.assertEqual(1, len(self.module_diagnostics(project, connector)))


if __name__ == "__main__":
    unittest.main()
