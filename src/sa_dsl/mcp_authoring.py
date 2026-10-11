"""MCP entry points for conservative, validated typed-Python edits."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from mcp.types import ToolAnnotations

from . import python_authoring
from .mcp_workspace import WorkspaceBoundary


def register_authoring_tools(mcp: Any, workspace_root: Callable[[], Path]) -> None:
    async def call(name: str, project: str, **arguments: Any) -> dict[str, Any]:
        try:
            path = WorkspaceBoundary(workspace_root()).resolve(project)
            return await asyncio.to_thread(getattr(python_authoring, name), path, **arguments)
        except (ValueError, OSError) as error:
            return {"status": "failed", "operation": name, "diagnostics": [{
                "code": getattr(error, "code", "SA_AUTHORING_FAILED"), "path": "$.authoring", "message": str(error)}]}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
    async def inspect_python_authoring(project: str = ".", source_file: str | None = None) -> dict[str, Any]:
        """Find Python files, declarations and insertion sites without executing the model.

        Inspect a source_file to get its revision and beforeLine anchors. Read
        describe_architecture_object for semantics and exact typed DSL factories.
        """
        return await call("inspect_python_authoring", project, source_file=source_file)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False))
    async def preview_python_changes(source_file: str, source_revision: str, before_line: int,
                                     operations: list[dict[str, Any]], imports: list[str] | None = None,
                                     project: str = ".") -> dict[str, Any]:
        """Preview a batch of typed Python additions, validating the complete candidate.

        Operations: add_node/add_endpoint use receiver, factory, symbol, name,
        arguments; connect_ports uses source, target, role (data, additional or error).
        Arguments are Python expressions: existing references, quoted literals,
        or typed DSL constructors. Imports are optional public sa_dsl class names.
        A batch can add an endpoint, nodes and links without invalid intermediate
        graphs. No source is changed until apply_python_changes. Existing source
        is not reformatted or regenerated. Review effects on every factory instance.
        """
        return await call("preview_python_changes", project, source_file=source_file,
                          source_revision=source_revision, before_line=before_line,
                          operations=operations, imports=imports)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False))
    async def add_node(source_file: str, source_revision: str, before_line: int, receiver: str,
                       factory: str, symbol: str, name: str, arguments: dict[str, str] | None = None,
                       imports: list[str] | None = None, project: str = ".") -> dict[str, Any]:
        """Prepare a validated add-node preview using an existing Pipeline reference.

        Select a meaningful business stage, not one node per code statement.
        factory is a typed method such as map/filter/split/join; arguments are
        Python expressions. Use a batch when associated links are also needed.
        """
        return await preview_python_changes(source_file, source_revision, before_line, [{
            "kind": "add_node", "receiver": receiver, "factory": factory, "symbol": symbol,
            "name": name, "arguments": arguments or {}}], imports, project)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False))
    async def add_endpoint(source_file: str, source_revision: str, before_line: int, receiver: str,
                           factory: str, symbol: str, name: str, arguments: dict[str, str] | None = None,
                           imports: list[str] | None = None, project: str = ".") -> dict[str, Any]:
        """Prepare a validated endpoint preview on an existing typed Connector.

        Use the connector's exact factory (post, unary_method, topic, activity,
        etc.) and read its capability contract first. This does not invent a
        transport implementation, business function or stream binding.
        """
        return await preview_python_changes(source_file, source_revision, before_line, [{
            "kind": "add_endpoint", "receiver": receiver, "factory": factory, "symbol": symbol,
            "name": name, "arguments": arguments or {}}], imports, project)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False))
    async def connect_ports(source_file: str, source_revision: str, before_line: int,
                            source: str, target: str, role: str = "data", project: str = ".") -> dict[str, Any]:
        """Preview a typed DSL connection between existing stream references.

        data inserts source >> target; additional inserts target << source.
        error inserts source >> target followed by source.on_error(target).
        Use real Python references, not numerical Designer port IDs. The DSL
        validates stream roles and cardinality; no task pool, retry or scheduling
        semantics is inferred. Existing duplicate links are not silently removed.
        """
        return await preview_python_changes(source_file, source_revision, before_line, [{
            "kind": "connect_ports", "source": source, "target": target, "role": role}], None, project)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False))
    async def apply_python_changes(preview_id: str, preview_revision: str, project: str = ".") -> dict[str, Any]:
        """Apply a reviewed Python-source preview with revision and validation checks.

        One source file is replaced atomically. Expired, changed, reused and
        concurrent previews are rejected. Canonical YAML remains a derived
        artifact and is not edited by this operation.
        """
        return await call("apply_python_changes", project, preview_id=preview_id,
                          preview_revision=preview_revision)
