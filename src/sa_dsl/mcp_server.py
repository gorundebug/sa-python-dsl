from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any

import anyio
import yaml
from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from .business_tasks import BusinessTaskError, inspect_business_tasks as inspect_tasks, run_verification as execute_verification
from .designer import DEFAULT_ASSET_BASE, DesignerSnapshotServer, designer_document, make_snapshot, validate_asset_base
from .doctor import diagnose_project
from .execution import execute_project, write_canonical_yaml
from .generation import generate_project_archive
from .generation_transaction import apply_generation_transaction, preview_generation_transaction
from .manifest import ManifestError, load_manifest
from .migration import import_yaml_project as import_yaml_project_application
from .mcp_workspace import WorkspaceBoundary, WorkspaceBoundaryError
from .mcp_resources import catalog_resource, json_resource
from .operation_audit import read_audit, record_operation
from .semantic_diff import SemanticDiffError, preview_architecture_diff as build_architecture_diff
from .servicegen_capabilities import (
    CACHE_RELATIVE_PATH,
    CapabilityError,
    fetch_capabilities,
    language_capability,
    load_cached_capabilities,
    save_capabilities,
)
from .servicegen_validation import (
    ValidationContractError,
    attach_remediation,
    diagnostic_descriptor,
    fetch_validation_contract,
    load_validation_contract,
    save_validation_contract,
)


mcp = MCPServer("Service Architect")
UI_RESOURCE_URI = "ui://service-architect/designer"
_workspace = WorkspaceBoundary(Path.cwd())
_snapshot_server: DesignerSnapshotServer | None = None


def configure_workspace(path: str | Path) -> None:
    global _workspace
    _workspace = WorkspaceBoundary(path)


def _project_path(path: str) -> Path:
    return _workspace.resolve(path)


def _asset_base() -> str:
    return validate_asset_base(
        os.getenv("SERVICE_ARCHITECT_DESIGNER_ASSET_BASE", DEFAULT_ASSET_BASE)
    )


def _asset_origin() -> str:
    from urllib.parse import urlparse

    parsed = urlparse(_asset_base())
    return f"{parsed.scheme}://{parsed.netloc}"


def _designer_server() -> DesignerSnapshotServer:
    global _snapshot_server
    if _snapshot_server is None:
        _snapshot_server = DesignerSnapshotServer(asset_base=_asset_base())
    return _snapshot_server


@mcp.resource(
    UI_RESOURCE_URI,
    name="Service Architect Designer",
    description="Read-only visual Service Architect graph for an exact canonical revision.",
    mime_type="text/html;profile=mcp-app",
    meta={
        "ui": {
            "prefersBorder": False,
            "csp": {
                "resourceDomains": [_asset_origin()],
                "connectDomains": [],
            },
        },
        "openai/widgetDescription": "Read-only Service Architect graph and object inspector.",
        "openai/widgetCSP": {
            "resource_domains": [_asset_origin()],
            "connect_domains": [],
        },
    },
)
def designer_ui() -> str:
    return designer_document(_asset_base())


@mcp.resource("servicegen://semantics/{topic}")
def semantics_resource(topic: str) -> str:
    return catalog_resource("semantics", topic)


@mcp.resource("servicegen://authoring/{topic}")
def authoring_resource(topic: str) -> str:
    return catalog_resource("authoring", topic)


@mcp.resource("servicegen://schema/{topic}")
def schema_resource(topic: str) -> str:
    return catalog_resource("schema", topic)


@mcp.resource("servicegen://examples/{topic}")
def examples_resource(topic: str) -> str:
    return catalog_resource("examples", topic)


@mcp.resource("servicegen://patterns/{topic}")
def patterns_resource(topic: str) -> str:
    return catalog_resource("patterns", topic)


@mcp.resource("servicegen://workspace/current/capabilities")
def workspace_capabilities_resource() -> str:
    try:
        return json_resource(load_cached_capabilities(_workspace.root))
    except CapabilityError as error:
        return json_resource({
            "schemaVersion": "1.0",
            "status": "unavailable",
            "message": str(error),
            "refreshTool": "refresh_capabilities",
        })


@mcp.resource("servicegen://capabilities/{language}")
def language_capabilities_resource(language: str) -> str:
    try:
        return json_resource(
            language_capability(load_cached_capabilities(_workspace.root), language)
        )
    except CapabilityError as error:
        return json_resource({
            "schemaVersion": "1.0",
            "status": "unavailable",
            "message": str(error),
            "refreshTool": "refresh_capabilities",
            "workspaceResource": "servicegen://workspace/current/capabilities",
        })


@mcp.resource("servicegen://workspace/current/validation-contract")
def workspace_validation_contract_resource() -> str:
    try:
        return json_resource(load_validation_contract(_workspace.root))
    except ValidationContractError as error:
        return json_resource({
            "schemaVersion": "1.0",
            "status": "unavailable",
            "message": str(error),
            "refreshTool": "refresh_validation_contract",
        })


@mcp.resource("servicegen://validation/rules/{code}")
def validation_rule_resource(code: str) -> str:
    contract = load_validation_contract(_workspace.root)
    return json_resource({
        "schemaVersion": contract["schemaVersion"],
        "servicegenVersion": contract["servicegenVersion"],
        "contractRevision": contract["revision"],
        "capabilityRevision": contract["capabilityRevision"],
        "diagnostic": diagnostic_descriptor(contract, code),
    })


@mcp.resource("servicegen://workspace/current/source")
def workspace_source_resource() -> str:
    return json_resource(load_manifest(_workspace.root).inspect_payload())


@mcp.resource("servicegen://workspace/current/dsl")
def workspace_dsl_resource() -> str:
    manifest = load_manifest(_workspace.root)
    return _canonical_path(manifest.workspace, manifest.canonical.output).read_text(encoding="utf-8")


@mcp.resource("servicegen://workspace/current/graph")
def workspace_graph_resource() -> str:
    document = yaml.safe_load(workspace_dsl_resource())
    if not isinstance(document, dict):
        raise ValueError("canonical YAML must contain an object")
    return json_resource(document)


@mcp.resource("servicegen://workspace/current/tasks")
def workspace_tasks_resource() -> str:
    manifest = load_manifest(_workspace.root)
    return json_resource(inspect_tasks(manifest.workspace))


@mcp.resource("servicegen://workspace/current/audit")
def workspace_audit_resource() -> str:
    manifest = load_manifest(_workspace.root)
    return json_resource(read_audit(manifest.workspace))


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
        return load_manifest(_project_path(project_path)).inspect_payload()
    except (ManifestError, WorkspaceBoundaryError) as error:
        return _manifest_failure("inspect", error)


@mcp.tool(
    title="Check Service Architect project integration",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
def doctor(project_path: str = ".", env_file: str = ".env") -> dict[str, Any]:
    """Check package, manifest, credentials and merge compatibility without executing Python."""

    try:
        project = _project_path(project_path)
    except WorkspaceBoundaryError as error:
        return _manifest_failure("doctor", error)
    return {"operation": "doctor", **diagnose_project(project, env_file=env_file)}


@mcp.tool(
    title="Refresh ServiceGen capabilities",
    annotations=ToolAnnotations(
        open_world_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
    ),
)
def refresh_capabilities(
    project_path: str = ".",
    base_url: str | None = None,
) -> dict[str, Any]:
    """Fetch and atomically cache the public ServiceGen capability matrix."""

    try:
        manifest = load_manifest(_project_path(project_path))
        document = fetch_capabilities(base_url)
        output = save_capabilities(manifest.workspace, document)
    except (ManifestError, WorkspaceBoundaryError) as error:
        return _manifest_failure("refresh-capabilities", error)
    except (CapabilityError, OSError) as error:
        return _failure(
            "refresh-capabilities",
            "SA_CAPABILITY_REFRESH_FAILED",
            str(error),
            "$.servicegen.capabilities",
        )
    return {
        "schemaVersion": "1.0",
        "operation": "refresh-capabilities",
        "status": "success",
        "output": output.relative_to(manifest.workspace).as_posix(),
        "capabilities": {
            "schemaVersion": document["schemaVersion"],
            "servicegenVersion": document["servicegenVersion"],
            "apiRevision": document["apiRevision"],
            "revision": document["revision"],
            "languages": [item["name"] for item in document["languages"]],
        },
        "diagnostics": [],
    }


@mcp.tool(
    title="Refresh ServiceGen validation contract",
    annotations=ToolAnnotations(
        open_world_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
    ),
)
def refresh_validation_contract(
    project_path: str = ".",
    base_url: str | None = None,
) -> dict[str, Any]:
    """Fetch and atomically cache public ServiceGen diagnostic metadata."""

    try:
        manifest = load_manifest(_project_path(project_path))
        document = fetch_validation_contract(base_url)
        output = save_validation_contract(manifest.workspace, document)
    except (ManifestError, WorkspaceBoundaryError) as error:
        return _manifest_failure("refresh-validation-contract", error)
    except (ValidationContractError, OSError) as error:
        return _failure(
            "refresh-validation-contract",
            "SA_VALIDATION_CONTRACT_REFRESH_FAILED",
            str(error),
            "$.servicegen.validationContract",
        )
    return {
        "schemaVersion": "1.0",
        "operation": "refresh-validation-contract",
        "status": "success",
        "output": output.relative_to(manifest.workspace).as_posix(),
        "contract": {
            "schemaVersion": document["schemaVersion"],
            "servicegenVersion": document["servicegenVersion"],
            "diagnosticSchemaVersion": document["diagnosticSchemaVersion"],
            "capabilityRevision": document["capabilityRevision"],
            "revision": document["revision"],
            "diagnostics": len(document["diagnostics"]),
        },
        "diagnostics": [],
    }


@mcp.tool(
    title="Validate Service Architect project",
    annotations=ToolAnnotations(open_world_hint=False, destructive_hint=False),
)
def validate_project(project_path: str = ".") -> dict[str, Any]:
    """Execute the declared typed Python model and return validation diagnostics."""

    try:
        manifest = load_manifest(_project_path(project_path))
    except (ManifestError, WorkspaceBoundaryError) as error:
        return _manifest_failure("validate", error)
    return attach_remediation(
        execute_project(manifest, "validate").to_payload(), manifest.workspace
    )


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
        manifest = load_manifest(_project_path(project_path))
    except (ManifestError, WorkspaceBoundaryError) as error:
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
        manifest = load_manifest(_project_path(project_path))
    except (ManifestError, WorkspaceBoundaryError) as error:
        return _manifest_failure("generate", error)
    return generate_project_archive(
        manifest, output=output, env_file=env_file
    ).to_payload()


@mcp.tool(
    title="Preview ServiceGen project generation",
    annotations=ToolAnnotations(
        read_only_hint=True,
        open_world_hint=True,
    ),
)
async def preview_generation(
    ctx: Context,
    project_path: str = ".",
    env_file: str = ".env",
    remove_stale: bool = False,
) -> dict[str, Any]:
    """Generate an immutable archive and preview the exact ServiceGen merge."""

    try:
        manifest = load_manifest(_project_path(project_path))
    except (ManifestError, WorkspaceBoundaryError) as error:
        return _manifest_failure("preview-generation", error)
    started = time.monotonic()
    await ctx.report_progress(0, 3, "Exporting and validating architecture")
    result = await anyio.to_thread.run_sync(
        lambda: preview_generation_transaction(
            manifest, env_file=env_file, remove_stale=remove_stale
        )
    )
    await ctx.report_progress(3, 3, "Generation preview ready")
    record_operation(manifest.workspace, "preview-generation", result, started)
    return result


@mcp.tool(
    title="Apply an immutable ServiceGen generation preview",
    annotations=ToolAnnotations(
        open_world_hint=False,
        destructive_hint=True,
        idempotent_hint=False,
    ),
)
async def apply_generation(
    ctx: Context,
    preview_id: str,
    preview_revision: str,
    project_path: str = ".",
) -> dict[str, Any]:
    """Apply only an unexpired preview whose workspace revision is unchanged."""

    try:
        manifest = load_manifest(_project_path(project_path))
    except (ManifestError, WorkspaceBoundaryError) as error:
        return _manifest_failure("apply-generation", error)
    started = time.monotonic()
    await ctx.report_progress(0, 2, "Checking immutable preview and workspace revision")
    result = await anyio.to_thread.run_sync(
        lambda: apply_generation_transaction(
            manifest, preview_id=preview_id, preview_revision=preview_revision
        )
    )
    await ctx.report_progress(2, 2, "Generation apply finished")
    record_operation(manifest.workspace, "apply-generation", result, started)
    return result


@mcp.tool(
    title="Inspect generated business implementation tasks",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
def inspect_business_tasks(project_path: str = ".") -> dict[str, Any]:
    """Return generated function tasks, completion state, and safe verification IDs."""

    try:
        manifest = load_manifest(_project_path(project_path))
        result = inspect_tasks(manifest.workspace)
    except (ManifestError, WorkspaceBoundaryError) as error:
        return _manifest_failure("inspect-business-tasks", error)
    except OSError as error:
        return _failure(
            "inspect-business-tasks", "SA_TASK_INSPECTION_FAILED", str(error), "$.spec"
        )
    return {
        "schemaVersion": "1.0",
        "operation": "inspect-business-tasks",
        "status": "success",
        "project": {"name": manifest.name},
        "summary": result["summary"],
        "tasks": result["tasks"],
        "migrations": result["migrations"],
        "verifications": result["verifications"],
        "diagnostics": [],
    }


@mcp.tool(
    title="Run an allow-listed generated verification",
    annotations=ToolAnnotations(
        open_world_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
    ),
)
async def run_verification(
    ctx: Context,
    verification: str,
    project_path: str = ".",
) -> dict[str, Any]:
    """Run one generated verification target; arbitrary commands are not accepted."""

    try:
        manifest = load_manifest(_project_path(project_path))
        started = time.monotonic()
        await ctx.report_progress(0, 1, f"Running {verification}")
        result = await anyio.to_thread.run_sync(
            lambda: execute_verification(manifest.workspace, verification)
        )
    except (ManifestError, WorkspaceBoundaryError) as error:
        return _manifest_failure("run-verification", error)
    except BusinessTaskError as error:
        return _failure("run-verification", error.code, str(error), error.path)
    except OSError as error:
        return _failure(
            "run-verification", "SA_VERIFICATION_FAILED", str(error), "$.verification"
        )
    payload = {
        "schemaVersion": "1.0",
        "operation": "run-verification",
        "status": result["status"],
        "project": {"name": manifest.name},
        "result": result,
        "diagnostics": [] if result["status"] == "success" else [
            {
                "code": "SA_VERIFICATION_FAILED",
                "severity": "error",
                "path": "$.verification",
                "message": f"verification exited with code {result['exitCode']}",
            }
        ],
    }
    await ctx.report_progress(1, 1, f"{verification} finished")
    record_operation(manifest.workspace, "run-verification", payload, started)
    return payload


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

    try:
        workspace = _project_path(workspace_path)
    except WorkspaceBoundaryError as error:
        return _manifest_failure("import", error)
    return import_yaml_project_application(workspace, source, output).to_payload()


@mcp.tool(
    title="Preview semantic Service Architect changes",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False),
)
def preview_architecture_diff(
    project_path: str = ".",
    expected_baseline_revision: str | None = None,
) -> dict[str, Any]:
    """Compare current typed Python with the last exported canonical revision.

    The operation executes validation/export in an isolated child process but
    does not write canonical YAML or modify the workspace.
    """

    try:
        manifest = load_manifest(_project_path(project_path))
        baseline_path = _canonical_path(manifest.workspace, manifest.canonical.output)
        baseline_yaml = baseline_path.read_text(encoding="utf-8") if baseline_path.is_file() else None
    except (ManifestError, WorkspaceBoundaryError) as error:
        return _manifest_failure("preview-architecture-diff", error)
    except (OSError, ValueError) as error:
        return _failure(
            "preview-architecture-diff",
            "SA_CANONICAL_READ_FAILED",
            str(error),
            "$.canonical.output",
        )

    result = execute_project(manifest, "export")
    if not result.succeeded:
        payload = result.to_payload()
        payload["operation"] = "preview-architecture-diff"
        return payload
    if result.rendered_yaml is None:
        return _failure(
            "preview-architecture-diff",
            "SA_EXECUTION_PROTOCOL_ERROR",
            "Python authoring succeeded without returning canonical YAML",
            "$.authoring.entrypoint",
        )
    try:
        preview = build_architecture_diff(baseline_yaml, result.rendered_yaml)
    except SemanticDiffError as error:
        return _failure(
            "preview-architecture-diff",
            "SA_CANONICAL_INVALID",
            str(error),
            "$.canonical.output",
        )
    if (
        expected_baseline_revision is not None
        and preview["baselineRevision"] != expected_baseline_revision
    ):
        return _failure(
            "preview-architecture-diff",
            "SA_STALE_BASELINE_REVISION",
            "canonical baseline changed; request a new architecture preview",
            "$.expected_baseline_revision",
        )
    return {
        "schemaVersion": "1.0",
        "operation": "preview-architecture-diff",
        "status": "success",
        "project": {"name": manifest.name},
        "preview": preview,
        "diagnostics": [],
    }


@mcp.tool(
    title="Open Service Architect Designer",
    annotations=ToolAnnotations(
        read_only_hint=True,
        open_world_hint=False,
    ),
    meta={
        "ui": {"resourceUri": UI_RESOURCE_URI},
        "openai/outputTemplate": UI_RESOURCE_URI,
    },
)
def designer_view(project_path: str = ".") -> dict[str, Any]:
    """Return an immutable canonical snapshot and local read-only Designer URL."""

    try:
        manifest = load_manifest(_project_path(project_path))
    except (ManifestError, WorkspaceBoundaryError) as error:
        return _manifest_failure("designer-view", error)
    result = execute_project(manifest, "export")
    if not result.succeeded:
        payload = result.to_payload()
        payload["operation"] = "designer-view"
        return payload
    if result.rendered_yaml is None:
        return _failure(
            "designer-view",
            "SA_EXECUTION_PROTOCOL_ERROR",
            "Python authoring succeeded without returning canonical YAML",
            "$.authoring.entrypoint",
        )
    snapshot = make_snapshot(manifest.name, result.rendered_yaml)
    fallback_url = _designer_server().publish(snapshot)
    return {
        "schemaVersion": "1.0",
        "operation": "designer-view",
        "status": "success",
        "project": {"name": manifest.name},
        "snapshot": snapshot,
        "ui": {
            "resourceUri": UI_RESOURCE_URI,
            "fallbackUrl": fallback_url,
            "mode": "read-only",
        },
        "diagnostics": [],
    }


def _manifest_failure(operation: str, error: Exception) -> dict[str, Any]:
    diagnostic = error.to_diagnostic() if isinstance(error, ManifestError) else {
        "code": "SA_WORKSPACE_BOUNDARY_VIOLATION",
        "severity": "error",
        "path": "$",
        "message": str(error),
    }
    return {
        "schemaVersion": "1.0",
        "operation": operation,
        "status": "failed",
        "diagnostics": [diagnostic],
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


def _canonical_path(workspace: Path, relative_path: str) -> Path:
    root = workspace.resolve()
    candidate = (root / relative_path).resolve(strict=False)
    if candidate != root and root not in candidate.parents:
        raise ValueError("canonical output resolves outside the project workspace")
    return candidate


def main() -> None:
    parser = argparse.ArgumentParser(description="Service Architect MCP server")
    parser.add_argument(
        "--workspace",
        required=True,
        help="Only workspace root that MCP tools may access",
    )
    args = parser.parse_args()
    configure_workspace(args.workspace)
    try:
        mcp.run()
    finally:
        if _snapshot_server is not None:
            _snapshot_server.close()


if __name__ == "__main__":
    main()
