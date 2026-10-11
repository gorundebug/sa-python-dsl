import json
from pathlib import Path

import yaml

from sa_dsl import mcp_server
from tests.test_generation_transaction import project_workspace


def _output_directory(root: Path, destination: str) -> None:
    manifest = project_workspace(root)
    document = yaml.safe_load(manifest.manifest_path.read_text(encoding="utf-8"))
    document["generation"]["outputDirectory"] = destination
    manifest.manifest_path.write_text(yaml.safe_dump(document), encoding="utf-8")


def test_task_resource_uses_generated_project_directory(tmp_path, monkeypatch):
    _output_directory(tmp_path, "generated")
    destination = tmp_path / "generated"
    spec = destination / "spec" / "quotes"
    spec.mkdir(parents=True)
    (spec / "task1.md").write_text(
        "# Task 1/1: `CalculateQuote`\n\n"
        "| Language | `Go` |\n| Kind | `Map` |\n"
        "| File | `quotes/internal/functions/calculate_quote.go` |\n",
        encoding="utf-8",
    )
    (destination / "Makefile").write_text("test:\n\ttrue\n", encoding="utf-8")
    (tmp_path / "Makefile").write_text("lint:\n\tfalse\n", encoding="utf-8")
    monkeypatch.setattr(mcp_server, "_workspace", type(mcp_server._workspace)(tmp_path))
    result = json.loads(mcp_server.workspace_tasks_resource())
    assert result["summary"]["total"] == 1
    assert result["tasks"][0]["name"] == "CalculateQuote"
    assert [item["id"] for item in result["verifications"]] == ["test"]


def test_task_resource_rejects_output_outside_mcp_boundary(tmp_path, monkeypatch):
    _output_directory(tmp_path, "../outside")
    monkeypatch.setattr(mcp_server, "_workspace", type(mcp_server._workspace)(tmp_path))
    result = json.loads(mcp_server.workspace_tasks_resource())
    assert result["status"] == "failed", result
    assert result["diagnostics"]
