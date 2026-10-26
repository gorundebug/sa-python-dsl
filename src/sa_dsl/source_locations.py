"""IDE-only provenance captured while evaluating the actual typed model.

No locations enter canonical YAML. Navigation reads a freshness-checked sidecar
and never evaluates Python. Hooks exist only in the isolated snapshot worker.
"""
from __future__ import annotations

from contextlib import contextmanager
import ast
from functools import wraps
import hashlib
import json
from pathlib import Path
import sys
import tempfile

from .model import Pipeline, Service, Stream


INDEX_PATH = ".service-architect/build/source-locations.json"
SKIP_DIRS = frozenset({".git", ".venv", "venv", "__pycache__", "build", "dist", ".service-architect"})


def source_fingerprint(workspace: Path) -> dict[str, str]:
    root = workspace.resolve()
    paths = [p for p in root.rglob("*.py")
             if not any(part in SKIP_DIRS for part in p.relative_to(root).parts)
             and not any((parent / ".service-architect/materialized.json").is_file()
                         for parent in p.parents if parent != root and root in parent.parents)
             and p.resolve().is_relative_to(root)]
    paths.append(root / ".service-architect/project.yaml")
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if p.is_file()}


class SourceLocations:
    def __init__(self, workspace: Path):
        self.root = workspace.resolve()
        self.nodes = {}
        self.edges = {}
        self.trees = {}

    def position(self):
        frame = sys._getframe(1)
        positions = []
        try:
            while frame is not None:
                path = Path(frame.f_code.co_filename).resolve()
                if (path.is_relative_to(self.root) and path.suffix == ".py"
                        and not any(part in SKIP_DIRS for part in path.relative_to(self.root).parts)
                        and not str(frame.f_globals.get("__name__", "")).startswith("sa_dsl.")):
                    try:
                        if path not in self.trees:
                            text = path.read_text(encoding="utf-8")
                            self.trees[path] = (text.splitlines(), [n for n in ast.walk(ast.parse(text)) if isinstance(n, (ast.Call, ast.BinOp))])
                        lines, calls = self.trees[path]
                        instruction = list(frame.f_code.co_positions())[frame.f_lasti // 2]
                        line, end, column, end_column = instruction
                        matches = [n for n in calls if n.lineno <= frame.f_lineno <= n.end_lineno
                                   and (line is None or (n.lineno, n.col_offset) <= (line, column or 0)
                                        and (n.end_lineno, n.end_col_offset) >= (end or line, end_column or 0))]
                        if matches:
                            node = min(matches, key=lambda n: (n.end_lineno - n.lineno, n.end_col_offset - n.col_offset))
                            def editor_column(line_number, byte_offset):
                                prefix = lines[line_number - 1].encode("utf-8")[:byte_offset].decode("utf-8")
                                return len(prefix.encode("utf-16-le")) // 2 + 1
                            location = {"file": path.relative_to(self.root).as_posix(),
                                        "line": node.lineno, "column": editor_column(node.lineno, node.col_offset),
                                        "endLine": node.end_lineno, "endColumn": editor_column(node.end_lineno, node.end_col_offset)}
                            if location not in positions:
                                positions.append(location)
                    except (OSError, SyntaxError, IndexError, UnicodeError):
                        pass  # Provenance must never alter model construction.
                frame = frame.f_back
        finally:
            del frame
        if not positions:
            return None
        return {**positions[0], "related": positions}

    def record(self, method, args, result):
        position = self.position()
        if position is None:
            return
        if method == "_stream" and isinstance(result, Stream):
            # Keep references until export: object IDs must not be recycled.
            self.nodes[id(result)] = (result, position)
            if result.source is not None:
                self.edges[id(result.source), id(result), "source"] = position
            for source in result.sources:
                self.edges[id(source), id(result), "sources"] = position
        elif method == "__rshift__" and isinstance(result, Stream):
            self.edges[id(args[0]), id(args[1]), "source"] = position
        elif method == "__lshift__" and isinstance(result, Stream):
            self.edges[id(args[1]), id(args[0]), "sources"] = position
        elif method == "from_sources":
            for source in args[1:]:
                self.edges[id(source), id(args[0]), "sources"] = position
        elif method == "on_error":
            self.edges[id(result), id(result.error_stream), "error"] = position
        elif method == "_link":
            self.edges[id(result.source), id(result.target), "configured"] = position

    def document(self, project):
        nodes, links = {}, {}
        for service in project.services.values():
            nodes[service.key], links[service.key] = {}, {}
            streams = [s for p in service.pipelines.values() for s in p.streams.values()]

            def edge(source, target, role):
                position = self.edges.get((id(source), id(target), role))
                if position is not None:
                    links[service.key].setdefault(source.key, {})[target.key] = position

            for stream in streams:
                item = self.nodes.get(id(stream))
                if item is not None:
                    nodes[service.key][stream.key] = item[1]
                if stream.source is not None:
                    edge(stream.source, stream, "source")
                for source in stream.sources:
                    edge(source, stream, "sources")
            for stream in streams:
                if stream.error_stream is not None:
                    edge(stream, stream.error_stream, "error")
            for link in service.links.values():
                edge(link.source, link.target, "configured")
        return {"nodes": nodes, "links": links}


@contextmanager
def capture_source_locations(workspace: Path):
    index = SourceLocations(workspace)
    originals = []
    try:
        for owner, methods in ((Pipeline, ("_stream",)),
                               (Stream, ("__rshift__", "__lshift__", "from_sources", "on_error")),
                               (Service, ("_link",))):
            for method in methods:
                original = getattr(owner, method)
                originals.append((owner, method, original))

                def wrap(original, method):
                    @wraps(original)
                    def tracked(*args, **kwargs):
                        result = original(*args, **kwargs)
                        index.record(method, args, result)
                        return result
                    return tracked

                setattr(owner, method, wrap(original, method))
        yield index
    finally:
        for owner, method, original in originals:
            setattr(owner, method, original)


def _inside(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Source location escapes the project")
    path = (root / path).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Source location escapes the project")
    return path


def write_source_locations(workspace: Path, locations: dict, fingerprint: dict,
                           canonical: str, rendered: str) -> None:
    root = workspace.resolve()
    destination = _inside(root, INDEX_PATH)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "files": fingerprint,
               "canonical": {"file": canonical, "sha256": hashlib.sha256(rendered.encode()).hexdigest()},
               **locations}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                         prefix=".source-locations-", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream)
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def lookup_source_location(workspace: Path, kind: str, service: str, key: str,
                           source: str, target: str):
    root = workspace.resolve()
    try:
        path = _inside(root, INDEX_PATH)
        if not path.exists():
            return None
        if path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("Source index exceeds size limit")
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["version"] != 1 or data["files"] != source_fingerprint(root):
            raise ValueError("Python sources changed")
        canonical = data["canonical"]
        if hashlib.sha256(_inside(root, canonical["file"]).read_bytes()).hexdigest() != canonical["sha256"]:
            raise ValueError("Canonical graph changed")
        position = (data["nodes"].get(service, {}).get(key) if kind == "node"
                    else data["links"].get(service, {}).get(source, {}).get(target))
        if position is None:
            return None
        file = _inside(root, position["file"])
        if (not file.is_file() or file.suffix != ".py"
                or any(type(position[k]) is not int or position[k] < 1 for k in ("line", "column"))):
            raise ValueError("Invalid source position")
        return {"status": "success", "location": position}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        return {"status": "stale", "message": f"Refresh the Service Architect graph before navigating: {error}"}
