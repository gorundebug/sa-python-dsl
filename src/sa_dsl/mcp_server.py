from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from .execution import execute_project, write_canonical_yaml
from .generation import generate_project_archive
from .manifest import ManifestError, load_manifest
from .migration import import_yaml_project as import_yaml_project_application


mcp = MCPServer("Service Architect")


@mcp.tool(
    title="Inspect Service Architect project",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
def inspect_project(project_path: str = ".") -> dict[str, Any]:
    """Read project mode, entrypoint, canonical output, and generation targets.

    This operation reads only .service-architect/project.yaml. It never imports
    or executes the project's Python authoring code.
    """

    try:
        return load_manifest(Path(project_path)).inspect_payload()
    except ManifestError as error:
        return _manifest_failure("inspect", error)


@mcp.tool(
    title="Validate Service Architect project",
    annotations=ToolAnnotations(open_world_hint=False, destructive_hint=False),
)
def validate_project(project_path: str = ".") -> dict[str, Any]:
    """Execute the declared typed Python model and return validation diagnostics."""

    try:
        manifest = load_manifest(Path(project_path))
    except ManifestError as error:
        return _manifest_failure("validate", error)
    return execute_project(manifest, "validate").to_payload()


@mcp.tool(
    title="Export canonical Service Architect YAML",
    annotations=ToolAnnotations(
        open_world_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
    ),
)
def export_project(
    project_path: str = ".", output: str | None = None
) -> dict[str, Any]:
    """Validate typed Python and atomically write its canonical YAML artifact."""

    try:
        manifest = load_manifest(Path(project_path))
    except ManifestError as error:
        return _manifest_failure("export", error)
    result = execute_project(manifest, "export")
    if not result.succeeded:
        return result.to_payload()
    if result.rendered_yaml is None:
        return _failure(
            "export",
            "SA_EXECUTION_PROTOCOL_ERROR",
            "Python authoring succeeded without returning canonical YAML",
            "$.authoring.entrypoint",
        )
    try:
        artifact_path = write_canonical_yaml(manifest, result.rendered_yaml, output)
    except (OSError, ValueError) as error:
        return _failure(
            "export",
            "SA_CANONICAL_WRITE_FAILED",
            str(error),
            "$.canonical.output",
        )
    return result.to_payload(output=artifact_path)


@mcp.tool(
    title="Generate Service Architect project code",
    annotations=ToolAnnotations(
        open_world_hint=True,
        destructive_hint=False,
        idempotent_hint=False,
    ),
)
def generate_project(
    project_path: str = ".",
    output: str | None = None,
    env_file: str = ".env",
) -> dict[str, Any]:
    """Validate the Python model and download the generated project ZIP.

    The credentials file and output must be relative to the project workspace.
    The default output is dist/<filename supplied by the generation backend>.
    """

    try:
        manifest = load_manifest(Path(project_path))
    except ManifestError as error:
        return _manifest_failure("generate", error)
    return generate_project_archive(
        manifest, output=output, env_file=env_file
    ).to_payload()


@mcp.tool(
    title="Import Service Architect YAML as typed Python",
    annotations=ToolAnnotations(
        open_world_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
    ),
)
def import_yaml_project(
    workspace_path: str,
    source: str,
    output: str,
) -> dict[str, Any]:
    """Create a manifest-driven typed Python project from canonical YAML.

    Source and output are relative to workspace_path. The importer refuses to
    populate a non-empty output directory.
    """

    return import_yaml_project_application(
        workspace_path, source, output
    ).to_payload()


def _manifest_failure(operation: str, error: ManifestError) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "operation": operation,
        "status": "failed",
        "diagnostics": [error.to_diagnostic()],
    }


def _failure(
    operation: str, code: str, message: str, path: str
) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "operation": operation,
        "status": "failed",
        "diagnostics": [
            {
                "code": code,
                "severity": "error",
                "path": path,
                "message": message,
            }
        ],
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
