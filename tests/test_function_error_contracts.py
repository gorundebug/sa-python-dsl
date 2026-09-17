"""Regression coverage for shared generated function error contracts."""

import unittest

from sa_dsl import Function, Package, Project
from sa_dsl.model import Service, Stream
from sa_dsl.validation import TYPE_MISMATCH, Validator


class FunctionErrorContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = Project("Contracts")
        self.service = Service("service", "Service", "Go", "example.com/service")
        self.project.services[self.service.key] = self.service
        self.message = self.project.string_type("Message")
        self.error_a = self.project.string_type("FailureA", use_alias=True)
        self.error_b = self.project.string_type("FailureB", use_alias=True)
        self.native_error = self.project.error_type("NativeError", use_alias=False)

    def stream(self, key: str, error_type: str | None, kind: str = "Process") -> Stream:
        pipeline = self.service.pipeline(key)
        function = Function("SharedOperation", package=Package("business"))
        stream = Stream(
            key, key, kind, self.service, pipeline,
            function=function,
            properties={"valueType": self.message.key, **function.to_properties()},
        )
        pipeline.streams[key] = stream
        if error_type is not None:
            failure = Stream(
                key + "Error", key + " Error", "Error", self.service, pipeline,
                source=stream, properties={"valueType": error_type},
            )
            pipeline.streams[failure.key] = failure
            stream.on_error(failure)
        return stream

    def validator(self) -> Validator:
        validator = Validator(self.project)
        for stream in validator.streams.values():
            if stream.type == "Error" and stream.source is not None:
                validator.error_consumers[stream.source.key].append(stream)
        validator.validate_functions()
        return validator

    def test_different_error_types_report_both_declarations(self) -> None:
        self.stream("first", self.error_a.key)
        self.stream("second", self.error_b.key)
        diagnostics = self.validator().values
        self.assertEqual(len(diagnostics), 1)
        diagnostic = diagnostics[0]
        self.assertEqual(diagnostic.code, TYPE_MISMATCH)
        self.assertIn("pipelines.second", diagnostic.path)
        self.assertIn("pipelines.first", diagnostic.details["firstPath"])
        self.assertIn(self.error_a.key, diagnostic.details["expectedSignature"])
        self.assertIn(self.error_b.key, diagnostic.details["actualSignature"])

    def test_identical_error_contract_is_reusable(self) -> None:
        self.stream("first", self.error_a.key)
        self.stream("second", self.error_a.key)
        self.assertEqual(self.validator().values, [])

    def test_implicit_and_explicit_native_error_match(self) -> None:
        self.stream("first", None)
        self.stream("second", self.native_error.key)
        self.assertEqual(self.validator().values, [])

    def test_implicit_error_does_not_match_a_business_outcome(self) -> None:
        self.stream("first", None)
        self.stream("second", self.error_b.key)
        self.assertEqual(self.validator().values[0].code, TYPE_MISMATCH)

    def test_different_operator_contracts_do_not_match(self) -> None:
        self.stream("first", None)
        self.stream("second", None, "Map")
        self.assertEqual(self.validator().values[0].code, TYPE_MISMATCH)


if __name__ == "__main__":
    unittest.main()
