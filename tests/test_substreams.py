import unittest

import yaml

from sa_dsl import CppBoost, CppUserver, Function, Golang, Project, Python, Rust, ServiceModule, TypeScript
from sa_dsl.browser import python_files_to_yaml
from sa_dsl.importer import yaml_to_python_files


def fixture():
    project = Project("SubStream Example")
    service = project.service("Worker", language=Golang(), module=ServiceModule("example.com/substreams/worker"))
    text = project.string_type("Text")
    pipeline = service.pipeline("lookup")
    entry = pipeline.substream("Lookup", value_type=text)
    result = pipeline.map("Normalize", source=entry, value_type=text, function=Function("Normalize"))
    result >> entry
    return project, pipeline, entry, result, text


class SubStreamTest(unittest.TestCase):
    def test_all_languages_validate_and_round_trip(self) -> None:
        for language in (Golang(), Python(), TypeScript(), Rust(), CppBoost(), CppUserver()):
            with self.subTest(language=language.programming_language):
                project = Project("Portable SubStream")
                service = project.service(
                    "Worker", language=language,
                    module=ServiceModule("example.com/substreams/worker"),
                )
                text = project.string_type("Text")
                pipeline = service.pipeline("lookup")
                entry = pipeline.substream("Lookup", value_type=text)
                result = pipeline.map(
                    "Normalize", source=entry, value_type=text, function=Function("Normalize"),
                )
                result >> entry
                self.assertEqual([], project.validate())
                generated = yaml_to_python_files(project.to_yaml(), "portable_substream")
                restored = yaml.safe_load(python_files_to_yaml(generated.files, generated.entrypoint))
                self.assertEqual(project.to_document(), restored)
                entry.source = None
                self.assertTrue(any("result source" in item.message for item in project.validate()))

    def test_valid_entry_and_return_round_trip(self):
        project, _, entry, result, _ = fixture()
        self.assertEqual([], project.validate())
        generated = yaml_to_python_files(project.to_yaml(), "substream_example")
        restored = yaml.safe_load(python_files_to_yaml(generated.files, generated.entrypoint))
        self.assertEqual(project.to_document(), restored)
        self.assertIs(result, entry.source)

    def test_missing_return_is_reported(self):
        project, _, entry, _, _ = fixture()
        entry.source = None
        self.assertTrue(any("result source" in item.message for item in project.validate()))

    def test_result_outside_body_is_reported(self):
        project, pipeline, entry, _, text = fixture()
        other = pipeline.substream("Other", value_type=text)
        result = pipeline.map("Other Result", source=other, value_type=text, function=Function("Normalize"))
        result >> other
        result >> entry
        self.assertTrue(any("reachable" in item.message for item in project.validate()))

    def test_entry_function_is_rejected(self):
        project, _, entry, _, _ = fixture()
        entry.function = Function("NotAnInputHandler")
        self.assertTrue(any("not an input business function" in item.message for item in project.validate()))

    def test_multiple_body_consumers_require_split(self):
        project, pipeline, entry, _, text = fixture()
        pipeline.map("Extra", source=entry, value_type=text, function=Function("Normalize"))
        self.assertTrue(any("one body consumer" in item.message for item in project.validate()))


if __name__ == "__main__":
    unittest.main()
