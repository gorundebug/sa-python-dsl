from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .code_generation import CodeGenerationError, ServiceArchitectClient
from .execution import execute_project
from .manifest import ProjectManifest


@dataclass(frozen=True, slots=True)
class GenerationResult:
    status: Literal["success", "failed"]
    project_name: str
    diagnostics: tuple[dict[str, Any], ...] = ()
    artifact: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == "success"

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schemaVersion": "1.0",
            "operation": "generate",
            "status": self.status,
            "project": {"name": self.project_name},
            "diagnostics": list(self.diagnostics),
        }
        if self.artifact is not None:
            payload["artifact"] = {"kind": "generated-project-zip", "path": self.artifact}
        return payload


class _CanonicalProject:
    def __init__(self, source: str) -> None:
        self._source = source

    def to_yaml(self) -> str:
        return self._source


def generate_project_archive(
    manifest: ProjectManifest,
    *,
    output: str | None = None,
    env_file: str = ".env",
) -> GenerationResult:
    exported = execute_project(manifest, "export")
    if not exported.succeeded:
        return GenerationResult(
            status="failed",
            project_name=manifest.name,
            diagnostics=exported.diagnostics,
        )
    if exported.rendered_yaml is None:
        return _failure(
            manifest,
            "SA_EXECUTION_PROTOCOL_ERROR",
            "Python authoring succeeded without returning canonical YAML",
            "$.authoring.entrypoint",
        )

    try:
        environment_path = _workspace_path(manifest.workspace, env_file)
        client = ServiceArchitectClient.from_env(environment_path)
        archive = client.generate_code(_CanonicalProject(exported.rendered_yaml))
        relative_output = output or f"dist/{archive.filename}"
        destination = _workspace_path(manifest.workspace, relative_output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.tmp")
        temporary.write_bytes(archive.content)
        temporary.replace(destination)
    except (CodeGenerationError, OSError, ValueError) as error:
        return _failure(
            manifest,
            "SA_CODE_GENERATION_FAILED",
            str(error),
            "$.generation",
        )

    return GenerationResult(
        status="success",
        project_name=manifest.name,
        artifact=relative_output,
    )


def _workspace_path(workspace: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("path must be relative to the project workspace")
    destination = (workspace / candidate).resolve()
    root = workspace.resolve()
    if destination != root and root not in destination.parents:
        raise ValueError("path resolves outside the project workspace")
    return destination


def _failure(
    manifest: ProjectManifest, code: str, message: str, path: str
) -> GenerationResult:
    return GenerationResult(
        status="failed",
        project_name=manifest.name,
        diagnostics=(
            {
                "code": code,
                "severity": "error",
                "path": path,
                "message": message,
            },
        ),
    )
