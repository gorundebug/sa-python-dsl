import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from sa_dsl import Project
from sa_dsl.code_generation import GeneratedProjectArchive
from sa_dsl.execution import ExecutionResult, execute_project, write_canonical_yaml
from sa_dsl.generation import generate_project_archive
from sa_dsl.manifest import ManifestError, load_manifest
from sa_dsl.migration import import_yaml_project


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_YAML = REPOSITORY_ROOT / "servicegen/cmd/codegenerator/examples/example.yaml"


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


def write_manifest(
    workspace: Path,
    *,
    name: str = "Sample",
    entrypoint: str = "architecture:project",
) -> None:
    manifest = workspace / ".service-architect/project.yaml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": {"name": name},
                "authoring": {"mode": "python", "entrypoint": entrypoint},
                "canonical": {
                    "output": ".service-architect/build/architecture.yaml"
                },
                "generation": {"targets": ["go"]},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


class ManifestWorkflowTest(unittest.TestCase):
    def test_inspect_loads_manifest_without_executing_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-dsl-discovery-") as temporary:
            workspace = Path(temporary)
            marker = workspace / "executed.marker"
            (workspace / "architecture.py").write_text(
                "from pathlib import Path\n"
                "Path('executed.marker').write_text('executed')\n",
                encoding="utf-8",
            )
            write_manifest(workspace)

            manifest = load_manifest(workspace)

            self.assertEqual("architecture:project", manifest.authoring.entrypoint)
            self.assertFalse(marker.exists())

    def test_manifest_rejects_output_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-dsl-manifest-") as temporary:
            workspace = Path(temporary)
            write_manifest(workspace)
            manifest_path = workspace / ".service-architect/project.yaml"
            document = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            document["canonical"]["output"] = "../outside.yaml"
            manifest_path.write_text(
                yaml.safe_dump(document, sort_keys=False), encoding="utf-8"
            )

            with self.assertRaises(ManifestError) as raised:
                load_manifest(workspace)

            self.assertEqual("$.canonical.output", raised.exception.path)
            self.assertEqual(
                "SA_MANIFEST_INVALID",
                raised.exception.to_diagnostic()["code"],
            )

    def test_validate_and_export_execute_declared_project(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-dsl-execution-") as temporary:
            workspace = Path(temporary)
            (workspace / "architecture.py").write_text(
                "from sa_dsl import Project\nproject = Project('Sample')\n",
                encoding="utf-8",
            )
            write_manifest(workspace)
            manifest = load_manifest(workspace)

            validated = execute_project(manifest, "validate")
            exported = execute_project(manifest, "export")

            self.assertTrue(validated.succeeded, validated.diagnostics)
            self.assertTrue(exported.succeeded, exported.diagnostics)
            self.assertIsNotNone(exported.rendered_yaml)
            output = write_canonical_yaml(manifest, exported.rendered_yaml or "")
            self.assertEqual(".service-architect/build/architecture.yaml", output)
            self.assertTrue((workspace / output).is_file())

    def test_import_creates_immediately_valid_manifest_project(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-dsl-import-") as temporary:
            workspace = Path(temporary)
            source = workspace / "architecture.yaml"
            source.write_text(CANONICAL_YAML.read_text(encoding="utf-8"), encoding="utf-8")

            imported = import_yaml_project(workspace, "architecture.yaml", "processorder")

            self.assertTrue(imported.succeeded, imported.diagnostics)
            manifest = load_manifest(workspace / "processorder")
            self.assertEqual("main:project", manifest.authoring.entrypoint)
            self.assertEqual("Example", manifest.name)
            self.assertTrue(execute_project(manifest, "validate").succeeded)
            exported = execute_project(manifest, "export")
            self.assertTrue(exported.succeeded, exported.diagnostics)
            self.assertEqual(
                normalized_document(
                    yaml.safe_load(source.read_text(encoding="utf-8"))
                ),
                normalized_document(yaml.safe_load(exported.rendered_yaml or "")),
            )

    def test_generation_saves_backend_archive_inside_workspace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sa-dsl-generation-") as temporary:
            workspace = Path(temporary)
            write_manifest(workspace)
            manifest = load_manifest(workspace)
            exported = ExecutionResult(
                operation="export",
                status="success",
                project_name="Sample",
                rendered_yaml=Project("Sample").to_yaml(),
            )

            class Client:
                def generate_code(self, project):
                    self.rendered = project.to_yaml()
                    return GeneratedProjectArchive("sample.zip", b"zip-content")

            client = Client()
            with patch("sa_dsl.generation.execute_project", return_value=exported), patch(
                "sa_dsl.generation.ServiceArchitectClient.from_env",
                return_value=client,
            ):
                result = generate_project_archive(manifest)

            self.assertTrue(result.succeeded, result.diagnostics)
            self.assertEqual("dist/sample.zip", result.artifact)
            self.assertEqual(
                b"zip-content", (workspace / "dist/sample.zip").read_bytes()
            )
            self.assertEqual(exported.rendered_yaml, client.rendered)


if __name__ == "__main__":
    unittest.main()
