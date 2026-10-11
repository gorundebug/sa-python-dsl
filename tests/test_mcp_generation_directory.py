"""MCP must honor the same generated-project location as IDE integrations."""
import asyncio
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
import zipfile

import yaml

from sa_dsl.code_generation import GeneratedProjectArchive
from sa_dsl.doctor import diagnose_project
from sa_dsl.generation_transaction import apply_generation_transaction, preview_generation_transaction
from sa_dsl.manifest import load_manifest
from sa_dsl import mcp_server
from sa_dsl.operation_audit import record_operation
from tests.test_business_tasks import TASK
from tests.test_generation_transaction import Client, MERGE_SCRIPT, generated_archive, project_workspace


def authoring_project(root: Path, output=".."):
    authoring = root / "example-architecture"
    authoring.mkdir()
    manifest = project_workspace(authoring)
    document = yaml.safe_load(manifest.manifest_path.read_text())
    document["generation"]["outputDirectory"] = output
    manifest.manifest_path.write_text(yaml.safe_dump(document))
    return load_manifest(authoring)


def preview(manifest, root, **options):
    return preview_generation_transaction(
        manifest, boundary_root=root, client_factory=lambda _: Client(generated_archive()), **options
    )


def apply(manifest, root, result, **options):
    token = result["preview"]
    return apply_generation_transaction(manifest, boundary_root=root,
        preview_id=token["previewId"], preview_revision=token["previewRevision"], **options)


def test_parent_output_preview_audit_and_apply(tmp_path):
    manifest = authoring_project(tmp_path)
    source = (manifest.workspace / "architecture.py").read_bytes()
    (tmp_path / "user.txt").write_text("keep business code\n")
    result = preview(manifest, tmp_path)
    assert result["status"] == "success", result
    assert not (tmp_path / "generated.txt").exists()
    record_operation(manifest.workspace, "preview-generation", result, time.monotonic())
    applied = apply(manifest, tmp_path, result)
    assert applied["status"] == "success", applied
    assert (tmp_path / "generated.txt").read_text() == "generated v2\n"
    assert (manifest.workspace / "generated.txt").read_text() == "generated v1\n"
    assert (manifest.workspace / "architecture.py").read_bytes() == source
    assert (tmp_path / "user.txt").read_text() == "keep business code\n"


def test_output_only_change_invalidates_preview(tmp_path):
    manifest = authoring_project(tmp_path)
    result = preview(manifest, tmp_path)
    (tmp_path / "user.txt").write_text("changed after preview\n")
    applied = apply(manifest, tmp_path, result)
    assert applied["diagnostics"][0]["code"] == "SA_STALE_WORKSPACE"
    assert not (tmp_path / "generated.txt").exists()


def test_new_output_is_created_only_on_apply(tmp_path):
    manifest = authoring_project(tmp_path, "../generated")
    result = preview(manifest, tmp_path)
    assert result["status"] == "success", result
    assert not (tmp_path / "generated").exists()
    applied = apply(manifest, tmp_path, result)
    assert applied["status"] == "success", applied
    assert (tmp_path / "generated/generated.txt").is_file()


def test_outside_registered_workspace_fails_before_execution(tmp_path):
    manifest = authoring_project(tmp_path)
    with patch("sa_dsl.generation_transaction.execute_project") as execute:
        result = preview(manifest, manifest.workspace)
    assert result["diagnostics"][0]["code"] == "SA_WORKSPACE_BOUNDARY_VIOLATION"
    execute.assert_not_called()


def test_source_change_during_generation_is_rejected(tmp_path):
    manifest = authoring_project(tmp_path)
    class ChangingClient:
        def generate_code(self, project):
            (manifest.workspace / "architecture.py").write_text("# concurrent edit\n")
            return generated_archive()
    result = preview_generation_transaction(manifest, boundary_root=tmp_path,
        client_factory=lambda _: ChangingClient())
    assert result["diagnostics"][0]["code"] == "SA_STALE_WORKSPACE"
    assert not (tmp_path / "generated.txt").exists()


def test_mcp_protects_nested_authoring_project(tmp_path):
    manifest = authoring_project(tmp_path)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("example/example-architecture/architecture.py", "replace authoring")
        archive.writestr("example/scripts/merge.generated.sh", MERGE_SCRIPT)
    with patch("sa_dsl.generation_transaction._run_merge") as merge:
        result = preview_generation_transaction(manifest, boundary_root=tmp_path,
            client_factory=lambda _: Client(GeneratedProjectArchive("example.zip", output.getvalue())))
    assert result["status"] == "failed", result
    assert "conflicts with Python authoring" in result["diagnostics"][0]["message"]
    merge.assert_not_called()


def test_preview_storage_symlink_escape_is_rejected(tmp_path):
    manifest = authoring_project(tmp_path)
    with tempfile.TemporaryDirectory() as outside:
        (manifest.workspace / ".service-architect/previews").symlink_to(outside, target_is_directory=True)
        result = preview(manifest, tmp_path)
        assert result["status"] == "failed"
        assert not list(Path(outside).iterdir())


def test_expired_preview_and_changed_archive_are_rejected(tmp_path):
    manifest = authoring_project(tmp_path)
    expired = preview(manifest, tmp_path, now=lambda: 1000)
    assert apply(manifest, tmp_path, expired, now=lambda: 2000)["diagnostics"][0]["code"] == "SA_PREVIEW_EXPIRED"
    result = preview(manifest, tmp_path)
    path = manifest.workspace / ".service-architect/previews" / result["preview"]["previewId"] / "archive.zip"
    path.write_bytes(b"modified")
    assert apply(manifest, tmp_path, result)["diagnostics"][0]["code"] == "SA_PREVIEW_INVALID"


def test_tasks_verification_and_doctor_use_generated_directory(tmp_path):
    manifest = authoring_project(tmp_path)
    spec = tmp_path / "spec/orders"
    spec.mkdir(parents=True)
    (spec / "task1.md").write_text(TASK)
    (tmp_path / "Makefile").write_text("test:\n\t@printf 'verified parent directory\\n'\n")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "merge.generated.sh").write_text(MERGE_SCRIPT)
    mcp_server.configure_workspace(tmp_path)
    class Context:
        async def report_progress(self, *args):
            pass
    try:
        tasks = mcp_server.inspect_business_tasks("example-architecture")
        assert tasks["summary"]["total"] == 1, tasks
        assert tasks["verifications"][0]["id"] == "test"
        verified = asyncio.run(mcp_server.run_verification(Context(), "test", "example-architecture"))
        assert verified["status"] == "success", verified
        assert "verified parent directory" in verified["result"]["stdout"]
        diagnosed = mcp_server.doctor("example-architecture")
        assert next(item for item in diagnosed["checks"] if item["id"] == "mergeContract")["status"] == "pass"
    finally:
        mcp_server.configure_workspace(Path.cwd())


def test_doctor_rejects_credentials_path_outside_authoring_project(tmp_path):
    manifest = authoring_project(tmp_path)
    (tmp_path / ".env").write_text("SERVICE_ARCHITECT_API_KEY=sa-test-secret-must-not-leak-9173\n")
    result = diagnose_project(manifest.workspace, env_file="../.env")
    assert next(item for item in result["checks"] if item["id"] == "credentials")["status"] == "error"
    assert "sa-test-secret-must-not-leak-9173" not in json.dumps(result)
