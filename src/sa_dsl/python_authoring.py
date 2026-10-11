"""Conservative source-preserving edits of the real typed Python model.

This module inserts DSL statements, not serialized graph objects. The normal
Python worker remains the only evaluator and validator of their semantics.
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import inspect
import json
import keyword
import os
from pathlib import Path
import shutil
import stat
import tempfile
import time
from typing import Any
import uuid

import sa_dsl

from .execution import execute_project
from .manifest import load_manifest
from .semantic_diff import preview_architecture_diff


NODE_FACTORIES = frozenset((
    "input", "sink", "substream", "map", "filter", "flat_map",
    "flat_map_iterable", "key_by", "join", "multi_join", "merge", "split",
    "case", "when", "process", "delay", "cycle_link", "error",
))
ENDPOINT_FACTORIES = frozenset((
    "get", "post", "put", "patch", "delete", "head", "options", "trace",
    "connect", "unary_method", "client_streaming_method",
    "server_streaming_method", "bidirectional_streaming_method", "topic",
    "schedule", "activity", "workflow", "endpoint",
))
_SKIP_DIRECTORIES = frozenset((
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", "node_modules", "dist", ".idea", ".vscode",
    ".servicegen", "dependency-cache",
))
_MAX_FILES = 5000
_MAX_BYTES = 50 * 1024 * 1024
_MAX_SOURCE_BYTES = 1024 * 1024
_TTL = 15 * 60


class AuthoringError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str) -> None:
    raise AuthoringError(code, message)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _inside(root: Path, value: str) -> Path:
    candidate = root / value
    if not candidate.resolve().is_relative_to(root.resolve()):
        _fail("SA_WORKSPACE_BOUNDARY_VIOLATION", "path leaves the authoring workspace")
    relative = candidate.relative_to(root)
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            _fail("SA_WORKSPACE_BOUNDARY_VIOLATION", "symlinks are not supported for source edits")
    return candidate


def _source(root: Path, source_file: str) -> tuple[Path, bytes, str, ast.Module]:
    path = _inside(root, source_file)
    if path.suffix != ".py" or not path.is_file():
        _fail("SA_AUTHORING_SOURCE_INVALID", "source_file must name an existing Python file")
    data = path.read_bytes()
    if len(data) > _MAX_SOURCE_BYTES:
        _fail("SA_AUTHORING_LIMIT", "Python source exceeds the 1 MiB editing limit")
    try:
        text = data.decode("utf-8")
        tree = ast.parse(text)
    except (UnicodeError, SyntaxError) as error:
        _fail("SA_AUTHORING_SOURCE_INVALID", str(error))
    return path, data, text, tree


def _sites(tree: ast.Module, text: str) -> list[dict[str, Any]]:
    lines = text.splitlines(keepends=True)
    sites: list[dict[str, Any]] = []

    def visit(body: list[ast.stmt], scope: str, *, module: bool = False) -> None:
        for item in body:
            if item.col_offset == 0 or scope != "module":
                line = lines[item.lineno - 1]
                indent = line[:len(line) - len(line.lstrip(" \t"))]
                if "\t" not in indent:
                    sites.append({"beforeLine": item.lineno, "scope": scope,
                                  "indent": indent, "statement": line.strip()[:200]})
            if isinstance(item, ast.FunctionDef):
                if any(isinstance(node, (ast.Yield, ast.YieldFrom)) for node in ast.walk(item)):
                    continue
                visit(item.body, item.name if module else f"{scope}.{item.name}")
        if module:
            sites.append({"beforeLine": len(lines) + 1, "scope": "module",
                          "indent": "", "statement": "<end of module>"})

    visit(tree.body, "module", module=True)
    return sites


def inspect_python_authoring(project: Path, source_file: str | None = None) -> dict[str, Any]:
    """Read source structure without importing or evaluating project Python."""
    manifest = load_manifest(project)
    root = manifest.workspace
    if source_file is None:
        entries, _ = _inputs(root)
        return {"status": "success", "sourceFiles": [name for name, _ in entries if name.endswith(".py")],
                "sourceOfTruth": "typed Python", "nextStep": "Inspect a source file to select an insertion site."}
    _, data, text, tree = _source(root, source_file)
    declarations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    declarations.append({"symbol": target.id, "line": node.lineno,
                                         "factory": ast.unparse(node.value.func),
                                         "name": node.value.args[0].value if node.value.args and
                                         isinstance(node.value.args[0], ast.Constant) else None})
    return {"status": "success", "sourceFile": source_file, "sourceRevision": _digest(data),
            "declarations": declarations, "insertionSites": _sites(tree, text),
            "source": text,
            "limitations": ["Insertion only; existing expressions are not rewritten.",
                            "A factory edit can affect all its instances; review the semantic diff.",
                            "Choose a module or synchronous function body, not a control-flow block."]}


def _inputs(root: Path) -> tuple[list[tuple[str, bytes]], str]:
    entries: list[tuple[str, bytes]] = []
    total = 0
    for directory, directories, files in os.walk(root, followlinks=False):
        relative = Path(directory).relative_to(root)
        directories[:] = sorted(name for name in directories if name not in _SKIP_DIRECTORIES)
        if relative == Path(".service-architect"):
            directories[:] = [name for name in directories if name not in {"build", "previews", "edits"}]
        for name in directories:
            if (Path(directory) / name).is_symlink():
                _fail("SA_WORKSPACE_BOUNDARY_VIOLATION", "authoring input contains a symlink directory")
        for name in sorted(files):
            if name == ".env" or name.startswith(".env.") or name.endswith((".pyc", ".pyo")):
                continue
            if relative == Path(".service-architect") and name == "audit.jsonl":
                continue
            path = Path(directory) / name
            if path.is_symlink() or not path.is_file():
                _fail("SA_WORKSPACE_BOUNDARY_VIOLATION", "authoring input must be a regular file")
            size = path.stat().st_size
            if len(entries) >= _MAX_FILES or total + size > _MAX_BYTES:
                _fail("SA_AUTHORING_LIMIT", "authoring inputs exceed 5000 files or 50 MiB; use a dedicated architecture directory")
            data = path.read_bytes()
            total += len(data)
            if total > _MAX_BYTES:
                _fail("SA_AUTHORING_LIMIT", "authoring inputs exceed 50 MiB")
            entries.append((path.relative_to(root).as_posix(), data))
    digest = hashlib.sha256()
    for name, data in entries:
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return entries, digest.hexdigest()


def _reference(value: str) -> str:
    if not isinstance(value, str):
        _fail("SA_AUTHORING_EXPRESSION_INVALID", "references must be Python expressions")
    try:
        expression = ast.parse(value, mode="eval").body
    except SyntaxError as error:
        _fail("SA_AUTHORING_EXPRESSION_INVALID", str(error))

    def allowed(node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return not node.id.startswith("__")
        if isinstance(node, ast.Attribute):
            return not node.attr.startswith("_") and allowed(node.value)
        if isinstance(node, ast.Subscript):
            return allowed(node.value) and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, (str, int))
        return False

    if not allowed(expression):
        _fail("SA_AUTHORING_EXPRESSION_INVALID", "use a name, public attribute or literal-indexed object reference")
    return ast.unparse(expression)


def _expression(value: str, constructors: set[str]) -> str:
    if not isinstance(value, str):
        _fail("SA_AUTHORING_EXPRESSION_INVALID", "argument values must be Python expressions, including quoted string literals")
    try:
        expression = ast.parse(value, mode="eval").body
    except SyntaxError as error:
        _fail("SA_AUTHORING_EXPRESSION_INVALID", str(error))

    def check(node: ast.AST) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool, type(None))):
            return
        if isinstance(node, (ast.Name, ast.Attribute, ast.Subscript)):
            _reference(ast.unparse(node))
            return
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            for child in node.elts:
                check(child)
            return
        if isinstance(node, ast.Dict) and all(key is not None for key in node.keys):
            for key, child in zip(node.keys, node.values):
                check(key)
                check(child)
            return
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)) and isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, (int, float)):
            return
        if isinstance(node, ast.Call) and ast.unparse(node.func) in constructors:
            for child in node.args:
                check(child)
            for arg in node.keywords:
                if arg.arg is None:
                    _fail("SA_AUTHORING_EXPRESSION_INVALID", "argument expansion is not supported")
                check(arg.value)
            return
        _fail("SA_AUTHORING_EXPRESSION_INVALID", "only literals, references and imported typed DSL constructors are supported")

    check(expression)
    return ast.unparse(expression)


def _statements(tree: ast.Module, operations: list[dict[str, Any]], imports: list[str]) -> list[str]:
    if not operations or len(operations) > 100:
        _fail("SA_AUTHORING_REQUEST_INVALID", "provide between 1 and 100 operations")
    public = {name for name in sa_dsl.__all__ if inspect.isclass(getattr(sa_dsl, name, None))
              and getattr(sa_dsl, name).__module__ == "sa_dsl.model"}
    if any(name not in public for name in imports) or len(imports) != len(set(imports)):
        _fail("SA_AUTHORING_REQUEST_INVALID", "imports must be unique public typed DSL classes")
    constructors = set(imports)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "sa_dsl":
            constructors.update(alias.asname or alias.name for alias in node.names if alias.name in public)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sa_dsl":
                    constructors.update(f"{alias.asname or alias.name}.{name}" for name in public)
    statements = [f"from sa_dsl import {', '.join(imports)}"] if imports else []
    names: set[str] = set()
    for operation in operations:
        kind = operation.get("kind")
        if kind in {"add_node", "add_endpoint"}:
            fields = {"kind", "receiver", "factory", "symbol", "name", "arguments"}
            if set(operation) - fields:
                _fail("SA_AUTHORING_REQUEST_INVALID", "unknown operation fields")
            factory = operation.get("factory")
            if factory not in (NODE_FACTORIES if kind == "add_node" else ENDPOINT_FACTORIES):
                _fail("SA_AUTHORING_REQUEST_INVALID", "unknown typed DSL factory for this operation")
            symbol = operation.get("symbol", "")
            if not isinstance(symbol, str) or not symbol.isidentifier() or keyword.iskeyword(symbol) or symbol.startswith("__") or symbol in names:
                _fail("SA_AUTHORING_REQUEST_INVALID", "new symbols must be unique Python identifiers")
            names.add(symbol)
            name = operation.get("name")
            if not isinstance(name, str) or not name.strip():
                _fail("SA_AUTHORING_REQUEST_INVALID", "the architecture object needs a nonempty name")
            arguments = operation.get("arguments", {})
            if not isinstance(arguments, dict) or any(not isinstance(key, str) or not key.isidentifier() or keyword.iskeyword(key) or key == "name" for key in arguments):
                _fail("SA_AUTHORING_REQUEST_INVALID", "arguments must map keyword names to Python expressions")
            args = [repr(name)] + [f"{key}={_expression(value, constructors)}" for key, value in arguments.items()]
            statements.append(f"{symbol} = {_reference(operation.get('receiver'))}.{factory}({', '.join(args)})")
        elif kind == "connect_ports":
            if set(operation) - {"kind", "source", "target", "role"}:
                _fail("SA_AUTHORING_REQUEST_INVALID", "unknown connection fields; call semantics are not inferred")
            source = _reference(operation.get("source"))
            target = _reference(operation.get("target"))
            role = operation.get("role", "data")
            if role == "data":
                statements.append(f"{source} >> {target}")
            elif role == "additional":
                statements.append(f"{target} << {source}")
            elif role == "error":
                statements.append(f"{source} >> {target}")
                statements.append(f"{source}.on_error({target})")
            else:
                _fail("SA_AUTHORING_REQUEST_INVALID", "role must be data, additional or error; use actual DSL stream references, not invented port IDs")
        else:
            _fail("SA_AUTHORING_REQUEST_INVALID", "unknown Python authoring operation")
    return statements


def _insert(text: str, tree: ast.Module, before_line: int, statements: list[str]) -> str:
    sites = [site for site in _sites(tree, text) if site["beforeLine"] == before_line]
    if len(sites) != 1:
        _fail("SA_AUTHORING_SITE_UNSUPPORTED", "select an insertion site returned by inspect_python_authoring")
    site = sites[0]
    lines = text.splitlines(keepends=True)
    ending = "\r\n" if "\r\n" in text else "\n"
    prefix = "".join(lines[:before_line - 1])
    suffix = "".join(lines[before_line - 1:])
    if prefix and not prefix.endswith(("\n", "\r")):
        prefix += ending
    inserted = "".join(site["indent"] + statement + ending for statement in statements)
    candidate = prefix + inserted + suffix
    try:
        ast.parse(candidate)
    except SyntaxError as error:
        _fail("SA_AUTHORING_SITE_UNSUPPORTED", str(error))
    return candidate


def _copy_inputs(entries: list[tuple[str, bytes]], root: Path) -> None:
    for name, data in entries:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def _validated(root: Path) -> Any:
    result = execute_project(load_manifest(root), "export")
    if not result.succeeded:
        return result
    if result.rendered_yaml is None:
        _fail("SA_AUTHORING_VALIDATION_FAILED", "Python worker returned no canonical model")
    return result


def preview_python_changes(project: Path, *, source_file: str, source_revision: str,
                           before_line: int, operations: list[dict[str, Any]],
                           imports: list[str] | None = None) -> dict[str, Any]:
    manifest = load_manifest(project)
    root = manifest.workspace
    path, data, text, tree = _source(root, source_file)
    if _digest(data) != source_revision:
        _fail("SA_STALE_WORKSPACE", "source file changed; inspect it again")
    statements = _statements(tree, operations, imports or [])
    candidate = _insert(text, tree, before_line, statements)
    entries, workspace_revision = _inputs(root)
    relative = path.relative_to(root).as_posix()
    if dict(entries).get(relative) != data:
        _fail("SA_STALE_WORKSPACE", "source changed while preparing the edit")
    with tempfile.TemporaryDirectory(prefix="sa-python-edit-") as temporary:
        shadow = Path(temporary) / root.name
        shadow.mkdir()
        _copy_inputs(entries, shadow)
        baseline = _validated(shadow)
        if not baseline.succeeded:
            return {**baseline.to_payload(), "operation": "preview_python_changes", "phase": "baseline"}
        (shadow / relative).write_bytes(candidate.encode("utf-8"))
        result = _validated(shadow)
        if not result.succeeded:
            return {**result.to_payload(), "operation": "preview_python_changes", "phase": "candidate"}
    diff = preview_architecture_diff(baseline.rendered_yaml, result.rendered_yaml)
    if baseline.rendered_yaml == result.rendered_yaml:
        _fail("SA_AUTHORING_NO_EFFECT", "statements did not change the exported model; the selected scope may not execute")
    if _inputs(root)[1] != workspace_revision:
        _fail("SA_STALE_WORKSPACE", "authoring inputs changed during validation")
    preview_id = uuid.uuid4().hex
    storage = _inside(root, f".service-architect/edits/{preview_id}")
    storage.mkdir(parents=True, mode=0o700)
    metadata = {"schemaVersion": 1, "previewId": preview_id, "sourceFile": relative,
                "workspaceRevision": workspace_revision, "candidateHash": _digest(candidate.encode("utf-8")),
                "expiresAt": time.time() + _TTL, "mode": stat.S_IMODE(path.stat().st_mode)}
    encoded = json.dumps(metadata, sort_keys=True).encode("utf-8")
    _private_write(storage / "metadata.json", encoded)
    _private_write(storage / "candidate.py", candidate.encode("utf-8"))
    return {"status": "success", "operation": "preview_python_changes", "previewId": preview_id,
            "previewRevision": _digest(encoded), "expiresAt": metadata["expiresAt"],
            "sourceFile": relative, "sourceDiff": "".join(difflib.unified_diff(text.splitlines(keepends=True),
                      candidate.splitlines(keepends=True), fromfile=relative, tofile=relative)),
            "architectureDiff": diff, "validation": result.to_payload(),
            "nextStep": "Review the source and architecture diffs, then call apply_python_changes."}


def _private_write(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)


def apply_python_changes(project: Path, *, preview_id: str, preview_revision: str) -> dict[str, Any]:
    root = load_manifest(project).workspace
    if len(preview_id) != 32 or any(char not in "0123456789abcdef" for char in preview_id):
        _fail("SA_AUTHORING_PREVIEW_INVALID", "invalid preview identifier")
    storage = _inside(root, f".service-architect/edits/{preview_id}")
    encoded = _inside(root, str((storage / "metadata.json").relative_to(root))).read_bytes()
    if _digest(encoded) != preview_revision:
        _fail("SA_AUTHORING_PREVIEW_INVALID", "preview revision does not match")
    metadata = json.loads(encoded)
    if metadata.get("previewId") != preview_id or metadata.get("schemaVersion") != 1:
        _fail("SA_AUTHORING_PREVIEW_INVALID", "invalid preview metadata")
    if time.time() > metadata["expiresAt"]:
        _fail("SA_AUTHORING_PREVIEW_EXPIRED", "preview expired; prepare a new edit")
    if (storage / "applied").exists():
        _fail("SA_AUTHORING_PREVIEW_APPLIED", "preview has already been applied")
    lock = _inside(root, ".service-architect/edits/applying.lock")
    try:
        _private_write(lock, b"")
    except FileExistsError:
        _fail("SA_AUTHORING_EDIT_BUSY", "another edit is already being applied in this workspace")
    try:
        entries, revision = _inputs(root)
        if revision != metadata["workspaceRevision"]:
            _fail("SA_STALE_WORKSPACE", "authoring inputs changed; prepare a new preview")
        candidate = _inside(root, str((storage / "candidate.py").relative_to(root))).read_bytes()
        if _digest(candidate) != metadata["candidateHash"]:
            _fail("SA_AUTHORING_PREVIEW_INVALID", "candidate content changed")
        path = _inside(root, metadata["sourceFile"])
        with tempfile.TemporaryDirectory(prefix="sa-python-apply-") as temporary:
            shadow = Path(temporary) / root.name
            shadow.mkdir()
            _copy_inputs(entries, shadow)
            (shadow / metadata["sourceFile"]).write_bytes(candidate)
            result = _validated(shadow)
            if not result.succeeded:
                return {**result.to_payload(), "operation": "apply_python_changes"}
        if _inputs(root)[1] != revision:
            _fail("SA_STALE_WORKSPACE", "authoring inputs changed during validation")
        descriptor, name = tempfile.mkstemp(prefix=".sa-edit-", dir=path.parent)
        temporary_file = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(candidate)
                handle.flush()
                os.fsync(handle.fileno())
            temporary_file.chmod(metadata["mode"])
            os.replace(temporary_file, path)
        finally:
            temporary_file.unlink(missing_ok=True)
        _private_write(storage / "applied", b"applied\n")
        return {"status": "success", "operation": "apply_python_changes", "sourceFile": metadata["sourceFile"],
                "sourceRevision": _digest(candidate), "validation": result.to_payload(),
                "nextStep": "Export the validated Python model when a canonical artifact is needed."}
    finally:
        lock.unlink(missing_ok=True)
