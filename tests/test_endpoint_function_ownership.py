import unittest

from sa_dsl import Function, Package, Project
from sa_dsl.model import Connector, Endpoint, Service
from sa_dsl.validation import Validator


class EndpointFunctionOwnershipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = Project("Endpoint adapters")
        self.service = Service("service", "Service", "GoLang", "example.com/service")
        self.project.services[self.service.key] = self.service
        self.connector = Connector("api", "API", "HTTP")
        self.project.connectors[self.connector.key] = self.connector
        self.value = self.project.string_type("Message", public_type=False)

    def endpoint(self, key: str, function: str = "HandleRequest") -> Endpoint:
        endpoint = Endpoint(key, key, self.connector, Function(function))
        self.connector.endpoints[key] = endpoint
        return endpoint

    def test_distinct_endpoint_handlers_collide_even_with_equal_message_types(self) -> None:
        for key in ("first", "second"):
            self.service.pipeline(key).input(key, endpoint=self.endpoint(key), value_type=self.value)
        validator = Validator(self.project)
        validator.validate_functions()
        diagnostic, = validator.values
        self.assertEqual(diagnostic.code, "SG_SEMANTIC_DUPLICATE_IDENTITY")
        self.assertEqual(diagnostic.details["firstEndpoint"], "first")
        self.assertEqual(diagnostic.details["secondEndpoint"], "second")
        self.assertEqual(diagnostic.details["identity"], "endpointHandler")

    def test_multiple_sinks_for_one_endpoint_are_supported(self) -> None:
        endpoint = self.endpoint("shared")
        for key in ("first", "second"):
            self.service.pipeline(key).sink(key, endpoint=endpoint, value_type=self.value)
        validator = Validator(self.project)
        validator.validate_functions()
        self.assertEqual(validator.values, [])

    def test_input_and_sink_handlers_have_separate_roles(self) -> None:
        self.service.pipeline("incoming").input("Input", endpoint=self.endpoint("incoming"), value_type=self.value)
        self.service.pipeline("outgoing").sink("Sink", endpoint=self.endpoint("outgoing"), value_type=self.value)
        validator = Validator(self.project)
        validator.validate_functions()
        self.assertEqual(validator.values, [])

    def test_distinct_adapters_can_share_business_functions(self) -> None:
        for key in ("first", "second"):
            pipeline = self.service.pipeline(key)
            request = pipeline.input(key, endpoint=self.endpoint(key, key + "HTTP"), value_type=self.value)
            pipeline.map(key + "Business", source=request, value_type=self.value, function=Function("SharedBusiness"))
        validator = Validator(self.project)
        validator.validate_functions()
        self.assertEqual(validator.values, [])

    def test_same_handler_name_in_distinct_packages_does_not_collide(self) -> None:
        for key in ("first", "second"):
            endpoint = self.endpoint(key)
            endpoint.function = Function("HandleRequest", package=Package("functions/" + key))
            stream = self.service.pipeline(key).input(key, endpoint=endpoint, value_type=self.value)
            self.assertEqual(Validator(self.project).function(stream),
                             ("HandleRequest", "functions/" + key, False, ""))
        validator = Validator(self.project)
        validator.validate_functions()
        self.assertEqual(validator.values, [])


if __name__ == "__main__":
    unittest.main()
