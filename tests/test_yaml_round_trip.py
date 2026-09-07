import copy
import importlib
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from sa_dsl.browser import python_files_to_yaml
from sa_dsl.importer import yaml_to_python_files, yaml_to_python_project


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
            if semantics == "TaskPool" and "priority" in normalized_link:
                normalized_link["callSemantics"] = "PriorityTaskPool"
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
    def test_in_memory_project_contains_importable_entrypoint(self) -> None:
        generated = yaml_to_python_files(CANONICAL_YAML, "generated_processorder")

        self.assertEqual("generated_processorder.main:project", generated.entrypoint)
        self.assertIn("generated_processorder/main.py", generated.files)
        self.assertIn("generated_processorder/__init__.py", generated.files)
        self.assertTrue(
            any(path.endswith("/pipelines/automation.py") for path in generated.files)
        )

    def test_filesystem_project_uses_the_in_memory_output(self) -> None:
        generated = yaml_to_python_files(CANONICAL_YAML, "generated_processorder")

        with tempfile.TemporaryDirectory(prefix="sa-dsl-files-") as temporary:
            package_root = Path(temporary) / generated.package_name
            entrypoint = yaml_to_python_project(CANONICAL_YAML, package_root)

            self.assertEqual(package_root / "main.py", entrypoint)
            for filename, expected in generated.files.items():
                relative = Path(filename).relative_to(generated.package_name)
                self.assertEqual(
                    expected,
                    (package_root / relative).read_text(encoding="utf-8"),
                )

    def test_in_memory_python_project_serializes_to_equivalent_yaml(self) -> None:
        source_document = yaml.safe_load(CANONICAL_YAML.read_text(encoding="utf-8"))
        generated = yaml_to_python_files(CANONICAL_YAML, "generated_processorder")

        rendered_document = yaml.safe_load(
            python_files_to_yaml(generated.files, generated.entrypoint)
        )

        self.assertEqual(
            normalized_document(source_document),
            normalized_document(rendered_document),
        )

    def test_in_memory_python_project_rejects_parent_traversal(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be relative"):
            python_files_to_yaml({"../project.py": ""}, "project:project")

    def test_legacy_task_pool_priority_uses_typed_priority_call(self) -> None:
        document = yaml.safe_load(CANONICAL_YAML.read_text(encoding="utf-8"))
        link = document["services"]["orderService"]["links"][
            "processOrder_splitPipeline"
        ]
        link["callSemantics"] = "TaskPool"

        generated = yaml_to_python_files(document, "generated_processorder")

        self.assertIn(
            ".priority_task_pool_call(",
            generated.files[
                "generated_processorder/services/order_service/pipelines/order.py"
            ],
        )

    def test_join_sources_keep_primary_and_additional_slots(self) -> None:
        generated = yaml_to_python_files(CANONICAL_YAML, "generated_processorder")

        join_pipeline = generated.files[
            "generated_processorder/services/analytics_service/pipelines/join_analytics.py"
        ]
        self.assertIn(
            "key_orders_for_join >> join_order_payment_analytics",
            join_pipeline,
        )
        self.assertIn(
            "join_order_payment_analytics << key_payments_for_join",
            join_pipeline,
        )

        multi_join_pipeline = generated.files[
            "generated_processorder/services/analytics_service/pipelines/multi_join_analytics.py"
        ]
        self.assertIn(
            "key_orders_for_multi_join >> multi_join_analytics_events",
            multi_join_pipeline,
        )
        self.assertIn(
            "multi_join_analytics_events << key_payments_for_multi_join",
            multi_join_pipeline,
        )
        self.assertIn(
            "multi_join_analytics_events << key_shipments_for_multi_join",
            multi_join_pipeline,
        )

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
