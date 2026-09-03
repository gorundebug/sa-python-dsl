import copy
import importlib
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from sa_dsl.importer import yaml_to_python_project


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_YAML = (
    REPOSITORY_ROOT / "servicegen/cmd/codegenerator/examples/example.yaml"
)


def normalized_document(document: dict) -> dict:
    result = copy.deepcopy(document)
    for service in (result.get("services") or {}).values():
        default_semantics = service.get("defaultCallSemantics", "FunctionCall")
        links = []
        for link in (service.get("links") or {}).values():
            semantics = link.get("callSemantics", "Inherited")
            if semantics in ("Inherited", default_semantics):
                continue
            normalized_link = dict(link)
            normalized_link.pop("key", None)
            links.append(normalized_link)
        service["links"] = sorted(
            links,
            key=lambda link: (
                link.get("source", ""),
                link.get("target", ""),
                link.get("callSemantics", ""),
            ),
        )
    return result


class YamlRoundTripTest(unittest.TestCase):
    def test_generated_python_project_serializes_to_equivalent_yaml(self) -> None:
        source_document = yaml.safe_load(CANONICAL_YAML.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory(prefix="sa-dsl-round-trip-") as temporary:
            package_name = "generated_processorder"
            package_root = Path(temporary) / package_name
            yaml_to_python_project(CANONICAL_YAML, package_root)

            sys.path.insert(0, temporary)
            try:
                generated_package = importlib.import_module(package_name)
                generated_document = yaml.safe_load(
                    generated_package.project.to_yaml()
                )
            finally:
                sys.path.pop(0)
                for module_name in list(sys.modules):
                    if module_name == package_name or module_name.startswith(
                        f"{package_name}."
                    ):
                        del sys.modules[module_name]

        self.assertEqual(
            normalized_document(source_document),
            normalized_document(generated_document),
        )


if __name__ == "__main__":
    unittest.main()
