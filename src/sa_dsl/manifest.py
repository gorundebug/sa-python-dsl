from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import yaml


MANIFEST_RELATIVE_PATH = Path(".service-architect/project.yaml")
SUPPORTED_AUTHORING_MODES = frozenset({"python", "yaml"})
SUPPORTED_GENERATION_TARGETS = frozenset(
    {
        "go",
        "cpp-userver",
        "cpp-boost",
        "python",
        "rust",
        "typescript",
    }
)

_ENTRYPOINT_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"
    r":[A-Za-z_][A-Za-z0-9_]*$"
)


class ManifestError(ValueError):
    """A stable, location-aware manifest validation error."""

    def __init__(self, message: str, *, path: str = "$") -> None:
        super().__init__(message)
        self.path = path

    def to_diagnostic(self) -> dict[str, str]:
        return {
            "code": "SA_MANIFEST_INVALID",
            "severity": "error",
            "path": self.path,
            "message": str(self),
        }


@dataclass(frozen=True, slots=True)
class AuthoringConfig:
    mode: str
    entrypoint: str | None = None
    source: str | None = None


@dataclass(frozen=True, slots=True)
class CanonicalConfig:
    output: str


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    targets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProjectManifest:
    version: int
    name: str
    authoring: AuthoringConfig
    canonical: CanonicalConfig
    generation: GenerationConfig
    workspace: Path
    manifest_path: Path

    def inspect_payload(self) -> dict[str, Any]:
        return {
            "schemaVersion": "1.0",
            "operation": "inspect",
            "status": "success",
            "project": {
                "name": self.name,
                "manifest": MANIFEST_RELATIVE_PATH.as_posix(),
                "authoringMode": self.authoring.mode,
                "entrypoint": self.authoring.entrypoint,
                "source": self.authoring.source,
                "canonicalOutput": self.canonical.output,
                "targets": list(self.generation.targets),
            },
        }


def find_manifest(project: str | Path) -> tuple[Path, Path]:
    """Return the workspace and manifest path without searching parent folders."""

    candidate = Path(project).expanduser()
    if candidate.is_file():
        manifest_path = candidate
        if candidate.parent.name == ".service-architect":
            workspace = candidate.parent.parent
        else:
            workspace = candidate.parent
        return workspace, manifest_path

    manifest_path = candidate / MANIFEST_RELATIVE_PATH
    if not manifest_path.is_file():
        raise ManifestError(
            f"manifest not found: {manifest_path}",
            path=MANIFEST_RELATIVE_PATH.as_posix(),
        )
    return candidate, manifest_path


def load_manifest(project: str | Path) -> ProjectManifest:
    workspace, manifest_path = find_manifest(project)
    try:
        document = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ManifestError(
            f"cannot read manifest: {error}", path=MANIFEST_RELATIVE_PATH.as_posix()
        ) from error
    except yaml.YAMLError as error:
        raise ManifestError(
            f"invalid YAML: {error}", path=MANIFEST_RELATIVE_PATH.as_posix()
        ) from error

    root = _mapping(document, "$")
    _reject_unknown(root, {"version", "project", "authoring", "canonical", "generation"}, "$")

    version = root.get("version")
    if version != 1:
        raise ManifestError("version must be 1", path="$.version")

    project_config = _mapping(root.get("project"), "$.project")
    _reject_unknown(project_config, {"name"}, "$.project")
    name = _required_string(project_config, "name", "$.project.name")

    authoring_config = _mapping(root.get("authoring"), "$.authoring")
    _reject_unknown(authoring_config, {"mode", "entrypoint", "source"}, "$.authoring")
    mode = _required_string(authoring_config, "mode", "$.authoring.mode")
    if mode not in SUPPORTED_AUTHORING_MODES:
        allowed = ", ".join(sorted(SUPPORTED_AUTHORING_MODES))
        raise ManifestError(f"mode must be one of: {allowed}", path="$.authoring.mode")

    entrypoint = _optional_string(authoring_config, "entrypoint", "$.authoring.entrypoint")
    source = _optional_string(authoring_config, "source", "$.authoring.source")
    if mode == "python":
        if entrypoint is None:
            raise ManifestError(
                "entrypoint is required for Python authoring",
                path="$.authoring.entrypoint",
            )
        if not _ENTRYPOINT_PATTERN.fullmatch(entrypoint):
            raise ManifestError(
                "entrypoint must use module.path:attribute syntax",
                path="$.authoring.entrypoint",
            )
        if source is not None:
            raise ManifestError(
                "source is only valid for YAML authoring", path="$.authoring.source"
            )
    else:
        if source is None:
            raise ManifestError(
                "source is required for YAML authoring", path="$.authoring.source"
            )
        _validate_relative_path(source, "$.authoring.source")
        if entrypoint is not None:
            raise ManifestError(
                "entrypoint is only valid for Python authoring",
                path="$.authoring.entrypoint",
            )

    canonical_config = _mapping(root.get("canonical"), "$.canonical")
    _reject_unknown(canonical_config, {"output"}, "$.canonical")
    canonical_output = _required_string(
        canonical_config, "output", "$.canonical.output"
    )
    _validate_relative_path(canonical_output, "$.canonical.output")

    generation_config = _mapping(root.get("generation"), "$.generation")
    _reject_unknown(generation_config, {"targets"}, "$.generation")
    targets_value = generation_config.get("targets")
    if not isinstance(targets_value, list) or not targets_value:
        raise ManifestError(
            "targets must be a non-empty list", path="$.generation.targets"
        )

    targets: list[str] = []
    for index, target in enumerate(targets_value):
        target_path = f"$.generation.targets[{index}]"
        if not isinstance(target, str) or not target.strip():
            raise ManifestError("target must be a non-empty string", path=target_path)
        if target not in SUPPORTED_GENERATION_TARGETS:
            allowed = ", ".join(sorted(SUPPORTED_GENERATION_TARGETS))
            raise ManifestError(f"target must be one of: {allowed}", path=target_path)
        if target in targets:
            raise ManifestError(f"duplicate target: {target}", path=target_path)
        targets.append(target)

    return ProjectManifest(
        version=version,
        name=name,
        authoring=AuthoringConfig(mode=mode, entrypoint=entrypoint, source=source),
        canonical=CanonicalConfig(output=canonical_output),
        generation=GenerationConfig(targets=tuple(targets)),
        workspace=workspace,
        manifest_path=manifest_path,
    )


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError("must be an object", path=path)
    return value


def _reject_unknown(
    value: Mapping[str, Any], allowed: set[str], path: str
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ManifestError(
            f"unknown field: {unknown[0]}", path=f"{path}.{unknown[0]}"
        )


def _required_string(value: Mapping[str, Any], key: str, path: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise ManifestError("must be a non-empty string", path=path)
    return result


def _optional_string(
    value: Mapping[str, Any], key: str, path: str
) -> str | None:
    result = value.get(key)
    if result is None:
        return None
    if not isinstance(result, str) or not result.strip():
        raise ManifestError("must be a non-empty string when provided", path=path)
    return result


def _validate_relative_path(value: str, path: str) -> None:
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or ".." in parsed.parts or "\\" in value:
        raise ManifestError(
            "must be a forward-slash relative path without parent traversal",
            path=path,
        )
