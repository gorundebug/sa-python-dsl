from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

import yaml

from .importer import yaml_to_python_project
from .manifest import MANIFEST_RELATIVE_PATH


_LANGUAGE_TARGETS = {
    "GoLang": "go",
    "CppUserver": "cpp-userver",
    "CppBoost": "cpp-boost",
    "Python": "python",
    "Rust": "rust",
    "TypeScript": "typescript",
    1: "go",
    2: "cpp-userver",
    3: "python",
    4: "rust",
    5: "cpp-boost",
    6: "typescript",
}


@dataclass(frozen=True, slots=True)
class ImportResult:
    status: Literal["success", "failed"]
    project_name: str | None = None
    project_path: str | None = None
    entrypoint: str | None = None
    targets: tuple[str, ...] = ()
    diagnostics: tuple[dict[str, Any], ...] = ()

    @property
    def succeeded(self) -> bool:
        return self.status == "success"

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schemaVersion": "1.0",
            "operation": "import",
            "status": self.status,
            "diagnostics": list(self.diagnostics),
        }
        if self.succeeded:
            payload["project"] = {
                "name": self.project_name,
                "path": self.project_path,
                "manifest": MANIFEST_RELATIVE_PATH.as_posix(),
                "entrypoint": self.entrypoint,
                "targets": list(self.targets),
            }
        return payload


def import_yaml_project(
    workspace: str | Path,
    source: str,
    output: str,
) -> ImportResult:
    root = Path(workspace).expanduser().resolve()
    try:
        source_path = _workspace_path(root, source)
        output_path = _workspace_path(root, output)
        document = yaml.safe_load(source_path.read_text(encoding="utf-8"))
        if not isinstance(document, Mapping):
            raise ValueError("Service Architect YAML root must be a mapping")

        settings = document.get("settings") or {}
        if not isinstance(settings, Mapping):
            raise ValueError("settings must be an object")
        project_name = settings.get("name") or output_path.name
        if not isinstance(project_name, str) or not project_name.strip():
            raise ValueError("settings.name must be a non-empty string")

        targets = _generation_targets(document)
        entrypoint_path = yaml_to_python_project(document, output_path)
        entrypoint_module = ".".join(
            entrypoint_path.relative_to(output_path).with_suffix("").parts
        )
        entrypoint = f"{entrypoint_module}:project"
        canonical_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", project_name).strip("-")
        canonical_name = canonical_name or "architecture"
        manifest = {
            "version": 1,
            "project": {"name": project_name},
            "authoring": {"mode": "python", "entrypoint": entrypoint},
            "canonical": {
                "output": f".service-architect/build/{canonical_name}.yaml"
            },
            "generation": {"targets": list(targets)},
        }
        manifest_path = output_path / MANIFEST_RELATIVE_PATH
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
    except (OSError, ValueError, yaml.YAMLError) as error:
        return ImportResult(
            status="failed",
            diagnostics=(
                {
                    "code": "SA_IMPORT_FAILED",
                    "severity": "error",
                    "path": "$",
                    "message": str(error),
                },
            ),
        )

    return ImportResult(
        status="success",
        project_name=project_name,
        project_path=_relative_display(root, output_path),
        entrypoint=entrypoint,
        targets=targets,
    )


def _generation_targets(document: Mapping[str, Any]) -> tuple[str, ...]:
    targets: list[str] = []
    services = document.get("services") or {}
    if not isinstance(services, Mapping):
        raise ValueError("services must be an object")
    for service in services.values():
        if not isinstance(service, Mapping):
            raise ValueError("each service must be an object")
        language = service.get("programmingLanguage")
        target = _LANGUAGE_TARGETS.get(language)
        if target is None:
            raise ValueError(f"unsupported programming language: {language!r}")
        if target not in targets:
            targets.append(target)
    if not targets:
        raise ValueError("at least one service programming language is required")
    return tuple(targets)


def _workspace_path(workspace: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("source and output must be workspace-relative paths")
    resolved = (workspace / candidate).resolve()
    if resolved != workspace and workspace not in resolved.parents:
        raise ValueError("source or output resolves outside the workspace")
    return resolved


def _relative_display(workspace: Path, path: Path) -> str:
    return path.relative_to(workspace).as_posix()
