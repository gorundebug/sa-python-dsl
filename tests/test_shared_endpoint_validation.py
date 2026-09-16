import unittest

from sa_dsl import Function, Golang, Project, ServiceModule
from sa_dsl.model import Endpoint, Stream
from sa_dsl.validation import DUPLICATE, TYPE_MISMATCH, Validator


class SharedEndpointValidationTests(unittest.TestCase):
    def fixture(self) -> tuple[Project, Endpoint, list[Stream], list[Stream]]:
        project = Project("Shared API")
        connector = project.custom_connector("Remote")
        endpoint = connector.endpoint("Call", function=Function("Call"))
        service = project.service(
            "Client", language=Golang(), module=ServiceModule("example.com/client")
        )
        text = project.string_type("Text")
        requests: list[Stream] = []
        sinks: list[Stream] = []
        for index in range(3):
            pipeline = service.pipeline(f"Pipeline {index}")
            entry = connector.endpoint(f"Entry {index}", function=Function(f"Enter{index}"))
            request = pipeline.input(f"Request {index}", endpoint=entry, value_type=text)
            sink = pipeline.sink(
                f"Call {index}", endpoint=endpoint, source=request, value_type=text
            )
            requests.append(request)
            sinks.append(sink)
        return project, endpoint, requests, sinks

    def test_independent_pipelines_share_one_endpoint(self) -> None:
        project, endpoint, requests, sinks = self.fixture()
        validator = Validator(project)
        validator.validate_endpoint_usage()
        self.assertEqual([], validator.values)
        for request, sink in zip(requests, sinks):
            self.assertIs(sink.source, request)
            self.assertIs(sink.endpoint, endpoint)
        self.assertEqual([], [
            diagnostic for diagnostic in project.validate()
            if diagnostic.details.get("identity") == "endpointDirection"
        ])

    def test_callers_must_agree_without_a_remote_input(self) -> None:
        for direction in ("request", "response", "keyed request"):
            with self.subTest(direction=direction):
                project, _, requests, sinks = self.fixture()
                number = project.int_type("Number")
                if direction == "request":
                    requests[-1].properties["valueType"] = number.key
                elif direction == "response":
                    sinks[-1].properties["valueType"] = number.key
                else:
                    requests[-1].type = "KeyBy"
                    requests[-1].properties["keyType"] = number.key
                validator = Validator(project)
                validator.validate_endpoint_usage()
                self.assertEqual(1, len(validator.values))
                self.assertEqual(TYPE_MISMATCH, validator.values[0].code)
                self.assertEqual(sinks[-1].name, validator.values[0].object_name)

    def test_unknown_first_type_does_not_mask_later_mismatch(self) -> None:
        project, _, requests, _ = self.fixture()
        requests[0].properties.pop("valueType")
        requests[-1].properties["valueType"] = project.int_type("Number").key
        validator = Validator(project)
        validator.validate_endpoint_usage()
        self.assertEqual([TYPE_MISMATCH], [value.code for value in validator.values])

    def test_input_remains_unique_per_service(self) -> None:
        project, _, requests, _ = self.fixture()
        requests[1].endpoint = requests[0].endpoint
        validator = Validator(project)
        validator.validate_endpoint_usage()
        self.assertEqual([DUPLICATE], [value.code for value in validator.values])

    def test_remote_input_is_checked_against_all_callers(self) -> None:
        project, endpoint, _, sinks = self.fixture()
        server = project.service(
            "Server", language=Golang(), module=ServiceModule("example.com/server")
        )
        server.pipeline("Remote").input(
            "Remote input", endpoint=endpoint, value_type=project.int_type("Number")
        )
        validator = Validator(project)
        validator.validate_endpoint_usage()
        self.assertEqual([TYPE_MISMATCH] * 3, [value.code for value in validator.values])
        self.assertEqual({sink.name for sink in sinks}, {value.object_name for value in validator.values})


if __name__ == "__main__":
    unittest.main()
