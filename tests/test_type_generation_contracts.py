import unittest

from sa_dsl import Project, TypeDefinitionFormat
from sa_dsl.model import Service, Stream
from sa_dsl.type_usage_validation import validate_type_generation_contracts
from sa_dsl.validation import Diagnostic, Validator


class TypeGenerationContractTests(unittest.TestCase):
    def use(self, project: Project, key: str, name: str, language: str = "GoLang") -> None:
        service = Service(name, name, language, "example.com/" + name)
        project.services[name] = service
        pipeline = service.pipeline("Business")
        stream = Stream(name, name, "Map", service, pipeline, properties={"valueType": key})
        pipeline.streams[name] = stream

    def diagnostics(self, project: Project) -> list[Diagnostic]:
        validator = Validator(project)
        validate_type_generation_contracts(validator)
        return validator.values

    def test_shared_private_native_type_requires_module(self) -> None:
        project = Project("Shared")
        value = project.struct_type("Work", public_type=False, definition_format=TypeDefinitionFormat.NATIVE)
        self.use(project, value.key, "first")
        self.use(project, value.key, "second")
        errors = self.diagnostics(project)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].path, "$.types.work.module")
        self.assertEqual(errors[0].details["services"], ["first", "second"])
        module = project.module("Internal Types", module_path="example.com/types", golang_version="1.25.4")
        value.properties["module"] = module.name
        self.assertEqual(self.diagnostics(project), [])

    def test_single_service_private_type_does_not_need_module(self) -> None:
        project = Project("Private")
        value = project.struct_type("Work", public_type=False, definition_format=TypeDefinitionFormat.NATIVE)
        self.use(project, value.key, "first")
        self.assertEqual(self.diagnostics(project), [])

    def test_public_type_requires_module_even_if_unused(self) -> None:
        project = Project("Public")
        project.struct_type("Request", public_type=True, definition_format=TypeDefinitionFormat.PROTOBUF)
        self.assertEqual(self.diagnostics(project)[0].path, "$.types.request.module")

    def test_structure_requires_definition_format(self) -> None:
        project = Project("Format")
        project.struct_type("Work", public_type=False)
        self.assertEqual(self.diagnostics(project)[0].path, "$.types.work.definitionFormat")

    def test_native_types_in_different_languages_are_not_shared(self) -> None:
        project = Project("Languages")
        value = project.struct_type("Work", public_type=False, definition_format=TypeDefinitionFormat.NATIVE)
        self.use(project, value.key, "first")
        self.use(project, value.key, "second", "Python")
        self.assertEqual(self.diagnostics(project), [])

    def test_wire_types_are_shared_across_languages(self) -> None:
        project = Project("Languages")
        value = project.struct_type("Work", public_type=False, definition_format=TypeDefinitionFormat.PROTOBUF)
        self.use(project, value.key, "first")
        self.use(project, value.key, "second", "Python")
        self.assertEqual(self.diagnostics(project)[0].path, "$.types.work.module")


if __name__ == "__main__":
    unittest.main()
