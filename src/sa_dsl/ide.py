"""Read-only IDE projection of a typed Python Service Architect project.

The Python project remains authoritative.  Neither operation writes canonical YAML
or adds source locations to the graph document.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import yaml

from .designer import make_snapshot
from .execution import execute_project
from .manifest import ProjectManifest


STREAM_METHODS = frozenset({
    "input", "substream", "map", "filter", "join", "multi_join", "process",
    "delay", "flat_map", "flat_map_iterable", "key_by", "merge", "split",
    "case", "sink", "cycle_link", "error", "when",
})
LINK_METHODS = frozenset({
    "function_call", "task_pool_call", "priority_task_pool_call", "parallel_call",
})
SKIP_DIRS = frozenset({
    ".git", ".venv", "venv", "__pycache__", "build", "dist", ".service-architect",
})


def _key(name: str) -> str:
    value = re.sub(
        r"[^A-Za-z0-9]+([A-Za-z0-9])?",
        lambda match: match.group(1).upper() if match.group(1) else "",
        name,
    )
    value = value[:1].lower() + value[1:] or "item"
    return "_" + value if value[0].isdigit() else value


def graph_snapshot(manifest: ProjectManifest) -> dict[str, Any]:
    """Evaluate Python in the bounded worker and return the shared Designer snapshot."""
    result = execute_project(manifest, "export")
    if not result.succeeded or result.rendered_yaml is None:
        diagnostics = list(result.diagnostics)
        return {
            "status": "failed", "diagnostics": diagnostics,
            "message": (str(diagnostics[0].get("message")) if diagnostics
                        else "Python graph could not be validated and exported"),
        }
    if not isinstance(yaml.safe_load(result.rendered_yaml), dict):
        return {"status": "failed", "message": "Exported graph is not a mapping"}
    return {"status": "success", "snapshot": make_snapshot(manifest.name, result.rendered_yaml)}


def _python_files(workspace: Path) -> list[Path]:
    return sorted(
        path for path in workspace.rglob("*.py")
        if not any(part in SKIP_DIRS for part in path.relative_to(workspace).parts)
        and not any((parent / '.service-architect/materialized.json').is_file()
                    for parent in path.parents if parent != workspace and workspace in parent.parents)
    )


def _name(node: ast.AST) -> str | None:
    return node.id if isinstance(node, ast.Name) else None


def _literal_key(call: ast.Call) -> str | None:
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return _key(call.args[0].value)
    return None


def _stream_definitions(workspace: Path) -> tuple[list[dict[str, Any]], list[tuple[Path, ast.AST, dict[str, str]]]]:
    definitions: list[dict[str, Any]] = []
    syntax: list[tuple[Path, ast.AST, dict[str, str]]] = []
    for path in _python_files(workspace):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeError):
            continue
        variables: dict[str, str] = {}
        for item in ast.walk(tree):
            if not isinstance(item, (ast.Assign, ast.AnnAssign)):
                continue
            call = item.value
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            if call.func.attr not in STREAM_METHODS:
                continue
            key = _literal_key(call)
            if key is None:
                continue
            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
            for target in targets:
                variable = _name(target)
                if variable:
                    variables[variable] = key
            definitions.append({
                "key": key, "name": call.args[0].value, "path": path,
                "line": call.lineno, "column": call.col_offset + 1,
            })
        syntax.append((path, tree, variables))
    return definitions, syntax


def _position(workspace: Path, path: Path, node: ast.AST) -> dict[str, Any]:
    return {
        "file": path.relative_to(workspace).as_posix(),
        "line": node.lineno, "column": node.col_offset + 1,
    }


def _service_score(path: Path, service: str) -> int:
    compact = re.sub(r"[^a-z0-9]", "", service.lower())
    return int(any(re.sub(r"[^a-z0-9]", "", part.lower()) == compact for part in path.parts))


def locate_source(workspace: Path, *, kind: str, service: str, key: str,
                  source: str = "", target: str = "") -> dict[str, Any]:
    """Find authoring expressions by existing textual keys; return no guessed location."""
    definitions, syntax = _stream_definitions(workspace)
    if kind == "node":
        matches = [item for item in definitions if item["key"] == key]
        if len(matches) > 1:
            best = max(_service_score(item["path"], service) for item in matches)
            matches = [item for item in matches if _service_score(item["path"], service) == best]
        if len(matches) == 1:
            item = matches[0]
            return {"status": "success", "location": {
                "file": item["path"].relative_to(workspace).as_posix(),
                "line": item["line"], "column": item["column"],
            }}
        return {"status": "not-found" if not matches else "ambiguous",
                "message": f"Could not uniquely locate stream {service}/{key}"}

    if kind != "link" or not source or not target:
        return {"status": "failed", "message": "Link lookup requires source and target keys"}
    # Variable declarations can live in separate imported files. Their names are
    # still ordinary Python identifiers in the connection expression.
    global_vars: dict[str, set[str]] = {}
    for _, _, local in syntax:
        for variable, stream_key in local.items():
            global_vars.setdefault(variable, set()).add(stream_key)
    matches: list[tuple[Path, ast.AST]] = []
    declarations: list[tuple[Path, ast.AST]] = []
    configured: list[tuple[Path, ast.AST]] = []
    error_links: list[tuple[Path, ast.AST]] = []
    for path, tree, local in syntax:
        def resolve(expr: ast.AST) -> str | None:
            if isinstance(expr, ast.BinOp):
                if isinstance(expr.op, ast.RShift):
                    return resolve(expr.right)
                if isinstance(expr.op, ast.LShift):
                    return resolve(expr.left)
            name = _name(expr)
            values = global_vars.get(name or "", set())
            return next(iter(values)) if len(values) == 1 else local.get(name or "")

        for item in ast.walk(tree):
            if isinstance(item, ast.BinOp) and isinstance(item.op, (ast.RShift, ast.LShift, ast.BitOr)):
                left, right = resolve(item.left), resolve(item.right)
                pair = (left, right) if isinstance(item.op, ast.RShift) else (right, left)
                if isinstance(item.op, ast.BitOr):
                    pair = (left, right)
                if pair == (source, target):
                    (error_links if isinstance(item.op, ast.BitOr) else matches).append((path, item))
            elif isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute):
                if item.func.attr in LINK_METHODS and item.args:
                    if (resolve(item.func.value), resolve(item.args[0])) == (source, target):
                        configured.append((path, item))
                elif item.func.attr == "on_error" and item.args:
                    if (resolve(item.func.value), resolve(item.args[0])) == (source, target):
                        error_links.append((path, item))
                elif item.func.attr == "from_sources":
                    if resolve(item.func.value) == target and any(resolve(arg) == source for arg in item.args):
                        matches.append((path, item))
                elif item.func.attr in STREAM_METHODS:
                    # A source= or sources= relationship may be declared directly
                    # in the target constructor, with no separate >> expression.
                    if _literal_key(item) != target:
                        continue
                    for keyword in item.keywords:
                        if keyword.arg == "source" and resolve(keyword.value) == source:
                            declarations.append((path, keyword.value))
                        elif keyword.arg == "sources" and isinstance(keyword.value, (ast.List, ast.Tuple)):
                            if any(resolve(element) == source for element in keyword.value.elts):
                                declarations.append((path, keyword.value))
    matches = configured or error_links or matches or declarations
    if len(matches) > 1:
        best = max(_service_score(path, service) for path, _ in matches)
        matches = [(path, item) for path, item in matches if _service_score(path, service) == best]
    if len(matches) == 1:
        path, item = matches[0]
        return {"status": "success", "location": _position(workspace, path, item)}
    return {"status": "not-found" if not matches else "ambiguous",
            "message": f"Could not uniquely locate link {service}/{source}->{target}"}
