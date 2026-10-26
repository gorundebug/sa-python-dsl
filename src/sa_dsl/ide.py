"""IDE projection of a typed Python Service Architect project.

Python remains authoritative. Snapshot refresh saves the canonical YAML artifact;
source navigation is read-only. Neither operation adds locations to the graph.
"""

from __future__ import annotations

import ast
import copy
import re
from pathlib import Path
from typing import Any

import yaml

from .designer import make_snapshot
from .execution import execute_project, write_canonical_yaml
from .manifest import ProjectManifest
from .source_locations import source_fingerprint, write_source_locations, lookup_source_location
from .ide_implementations import implementation_targets


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
    """Evaluate Python, save canonical YAML and display that same model."""
    fingerprint = source_fingerprint(manifest.workspace)
    result = execute_project(manifest, "export", capture_locations=True)
    if not result.succeeded or result.rendered_yaml is None:
        diagnostics = list(result.diagnostics)
        return {
            "status": "failed", "diagnostics": diagnostics,
            "message": (str(diagnostics[0].get("message")) if diagnostics
                        else "Python graph could not be validated and exported"),
        }
    if not isinstance(yaml.safe_load(result.rendered_yaml), dict):
        return {"status": "failed", "message": "Exported graph is not a mapping"}
    try:
        if fingerprint != source_fingerprint(manifest.workspace):
            raise ValueError("Python sources changed during refresh; refresh the graph again")
        write_canonical_yaml(manifest, result.rendered_yaml)
        locations = getattr(result, "source_locations", None)
        if locations is not None:
            write_source_locations(manifest.workspace, locations, fingerprint,
                                   manifest.canonical.output, result.rendered_yaml)
    except (OSError, ValueError) as error:
        return {'status': 'failed', 'message': f'Cannot save canonical YAML: {error}'}
    snapshot = make_snapshot(manifest.name, result.rendered_yaml)
    snapshot["implementations"] = implementation_targets(yaml.safe_load(result.rendered_yaml))
    snapshot["generationOutputDirectory"] = manifest.generation.output_directory or "."
    if locations is not None:
        used = {position["file"] for service in locations["nodes"].values() for position in service.values()}
        used.update(item["file"] for service in locations["nodes"].values()
                    for position in service.values() for item in position.get("related", []))
        snapshot["sourceLocations"] = {"nodes": locations["nodes"],
                                       "files": {name: fingerprint[name] for name in used if name in fingerprint}}
    return {"status": "success", "snapshot": snapshot}


def _python_files(workspace: Path) -> list[Path]:
    return sorted(
        path for path in workspace.rglob("*.py")
        if not any(part in SKIP_DIRS for part in path.relative_to(workspace).parts)
        and not any((parent / '.service-architect/materialized.json').is_file()
                    for parent in path.parents if parent != workspace and workspace in parent.parents)
    )


def _name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
            and isinstance(node.slice, ast.Constant)
            and type(node.slice.value) in (str, int)):
        return f"{node.value.id}[{node.slice.value!r}]"
    return None


def _literal_loop_bindings(target: ast.AST, value: Any) -> dict[str, Any] | None:
    if isinstance(target, ast.Name) and type(value) in (str, int, float, bool, type(None)):
        return {target.id: value}
    if isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (tuple, list)):
        if len(target.elts) != len(value):
            return None
        bindings: dict[str, Any] = {}
        for element, item in zip(target.elts, value):
            part = _literal_loop_bindings(element, item)
            if part is None or bindings.keys() & part.keys():
                return None
            bindings.update(part)
        return bindings
    return None


def _expand_literal_loops(tree: ast.AST) -> ast.AST:
    """Index small literal route tables without importing or executing user code.

    Cloned nodes retain source positions. Dynamic iterators and mutable loop
    bindings are deliberately left unresolved rather than guessed.
    """
    enumerate_shadowed = any(
        isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store) and item.id == "enumerate"
        or isinstance(item, ast.arg) and item.arg == "enumerate"
        or isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and item.name == "enumerate"
        or isinstance(item, ast.alias) and (item.asname or item.name.split(".")[0]) == "enumerate"
        for item in ast.walk(tree)
    )

    class Substitute(ast.NodeTransformer):
        def __init__(self, bindings: dict[str, Any]) -> None:
            self.bindings = bindings

        def visit_Name(self, node: ast.Name) -> ast.AST:
            if isinstance(node.ctx, ast.Load) and node.id in self.bindings:
                return ast.copy_location(ast.Constant(value=self.bindings[node.id]), node)
            return node

    class Expand(ast.NodeTransformer):
        remaining = 20000

        def visit_For(self, node: ast.For) -> ast.AST | list[ast.stmt]:
            iterator = node.iter
            enumerated = (
                isinstance(iterator, ast.Call) and isinstance(iterator.func, ast.Name)
                and iterator.func.id == "enumerate" and not enumerate_shadowed
                and len(iterator.args) == 1 and not iterator.keywords
            )
            literal = iterator.args[0] if enumerated else iterator
            if not isinstance(literal, (ast.Tuple, ast.List)) or len(literal.elts) > 256:
                return node
            try:
                values = ast.literal_eval(literal)
            except (ValueError, TypeError, SyntaxError, RecursionError):
                return node
            items = list(enumerate(values)) if enumerated else values
            bindings = [_literal_loop_bindings(node.target, value) for value in items]
            if any(binding is None for binding in bindings):
                return node
            body_nodes = [item for statement in node.body for item in ast.walk(statement)]
            # Do not substitute through another lexical scope or control-flow
            # that can stop the loop or change its bindings before a declaration.
            if any(isinstance(item, (
                ast.For, ast.AsyncFor, ast.While, ast.If, ast.Try, ast.With,
                ast.AsyncWith, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
                ast.Break, ast.Continue, ast.Return, ast.Raise, ast.Import, ast.ImportFrom,
                ast.Match,
            )) for item in body_nodes):
                return node
            bound_names = {name for binding in bindings if binding for name in binding}
            if any(isinstance(item, ast.Name) and isinstance(item.ctx, (ast.Store, ast.Del))
                   and item.id in bound_names for item in body_nodes):
                return node
            cost = len(body_nodes) * len(items)
            if cost > self.remaining or node.orelse:
                return node
            self.remaining -= cost
            expanded: list[ast.stmt] = []
            for binding in bindings:
                substitute = Substitute(binding or {})
                expanded.extend(substitute.visit(copy.deepcopy(statement)) for statement in node.body)
            return expanded

    return Expand().visit(tree)


def _literal_key(call: ast.Call) -> str | None:
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return _key(call.args[0].value)
    return None


def _stream_definitions(workspace: Path) -> tuple[list[dict[str, Any]], list[tuple[Path, ast.AST, dict[str, str]]]]:
    definitions: list[dict[str, Any]] = []
    syntax: list[tuple[Path, ast.AST, dict[str, str]]] = []
    for path in _python_files(workspace):
        try:
            tree = _expand_literal_loops(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
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


def _module_key(workspace: Path, path: Path) -> tuple[str, ...]:
    parts = path.relative_to(workspace).with_suffix("").parts
    return parts[:-1] if parts[-1] == "__init__" else parts


def _module_imports(workspace: Path, path: Path, tree: ast.AST) -> dict[str, tuple[str, ...] | None]:
    """Index explicit imports, rejecting aliases with ambiguous or mutable bindings."""
    package = path.relative_to(workspace).parts[:-1]
    aliases: dict[str, tuple[str, ...] | None] = {}
    for statement in getattr(tree, "body", ()):
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                name = alias.asname or alias.name.split(".")[0]
                module = tuple(alias.name.split(".")) if alias.asname else (name,)
                aliases[name] = None if name in aliases else module
        elif isinstance(statement, ast.ImportFrom):
            if statement.level > len(package):
                continue
            base = package[:len(package) - statement.level + 1] if statement.level else ()
            base += tuple(statement.module.split(".")) if statement.module else ()
            for alias in statement.names:
                if alias.name == "*":
                    continue
                name = alias.asname or alias.name
                aliases[name] = None if name in aliases else base + (alias.name,)
    import_counts: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.alias):
            name = node.asname or node.name.split(".")[0]
            import_counts[name] = import_counts.get(name, 0) + 1
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            if node.id in aliases:
                aliases[node.id] = None
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in aliases:
                aliases[node.name] = None
        elif isinstance(node, ast.arg) and node.arg in aliases:
            aliases[node.arg] = None
    for name in aliases:
        if import_counts.get(name) != 1:
            aliases[name] = None
    return aliases


def _imported_stream(expr: ast.AST, aliases: dict[str, tuple[str, ...] | None],
                     modules: dict[tuple[str, ...], dict[str, str] | None]) -> tuple[bool, str | None]:
    """Resolve imported module attributes and literal route keys without execution."""
    suffix = ""
    if isinstance(expr, ast.Subscript):
        if not isinstance(expr.slice, ast.Constant) or type(expr.slice.value) not in (str, int):
            return False, None
        suffix = f"[{expr.slice.value!r}]"
        expr = expr.value
    attributes: list[str] = []
    while isinstance(expr, ast.Attribute):
        attributes.append(expr.attr)
        expr = expr.value
    if not isinstance(expr, ast.Name) or expr.id not in aliases:
        return False, None
    module = aliases[expr.id]
    if module is None:
        return True, None
    qualified = module + tuple(reversed(attributes))
    variables = modules.get(qualified[:-1])
    return True, variables.get(qualified[-1] + suffix) if variables is not None else None


def locate_source(workspace: Path, *, kind: str, service: str, key: str,
                  source: str = "", target: str = "") -> dict[str, Any]:
    """Find authoring expressions by existing textual keys; return no guessed location."""
    if kind not in {"node", "link"} or kind == "link" and (not source or not target):
        return {"status": "failed", "message": "Link lookup requires source and target keys"}
    recorded = lookup_source_location(workspace, kind, service, key, source, target)
    if recorded is not None:
        return recorded
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
    modules: dict[tuple[str, ...], dict[str, str] | None] = {}
    for path, _, local in syntax:
        module = _module_key(workspace, path)
        modules[module] = None if module in modules else local
        for variable, stream_key in local.items():
            global_vars.setdefault(variable, set()).add(stream_key)
    matches: list[tuple[Path, ast.AST]] = []
    declarations: list[tuple[Path, ast.AST]] = []
    configured: list[tuple[Path, ast.AST]] = []
    error_links: list[tuple[Path, ast.AST]] = []
    for path, tree, local in syntax:
        aliases = _module_imports(workspace, path, tree)

        def resolve(expr: ast.AST) -> str | None:
            if isinstance(expr, ast.BinOp):
                if isinstance(expr.op, ast.RShift):
                    return resolve(expr.right)
                if isinstance(expr.op, ast.LShift):
                    return resolve(expr.left)
            handled, imported = _imported_stream(expr, aliases, modules)
            if handled:
                return imported
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
