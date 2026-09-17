"""Exact validation of visual repetitions; never replaces concrete runtime nodes.

Incoming execution policy belongs to the fragment; outgoing policy belongs to
its receiver. Only the document boundary accepts opaque input values.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from .model import Service, Stream
    from .validation import Validator


_JSONValue: TypeAlias = (
    str | int | float | bool | None
    | list["_JSONValue"] | tuple["_JSONValue", ...] | dict[str, "_JSONValue"]
)
_WireType: TypeAlias = tuple[bool, str, str]

_DISPLAY_TOPOLOGY = {
    "name", "description", "functionDescription", "source", "sources",
    "errorStream", "endpoint", "appearance", "pipeline", "component",
}


def _json_value(value: object) -> _JSONValue:
    """Validate the serialized-model boundary before semantic comparison."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_json_value(item) for item in value)
    if isinstance(value, dict):
        result: dict[str, _JSONValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("Component semantic documents require string keys")
            result[key] = _json_value(item)
        return result
    raise TypeError(f"Unsupported component semantic value: {type(value).__name__}")


def _json_object(value: object) -> dict[str, _JSONValue]:
    document = _json_value(value)
    if not isinstance(document, dict):
        raise TypeError("Component semantic documents must be objects")
    return document


def _stable(value: _JSONValue) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


@dataclass(slots=True)
class _Part:
    base: dict[int, str]
    adjacency: dict[tuple[int, int], tuple[str, ...]]


@dataclass(slots=True)
class _MatchBudget:
    remaining: int


@dataclass(frozen=True, slots=True)
class _Edge:
    source: int
    target: int
    signature: str
    output: str


class MatchLimit(ValueError):
    pass


def _equivalent(left: _Part, right: _Part, budget: _MatchBudget) -> bool:
    """Exact bijection, not fingerprint equality; bounded fail-closed search."""
    if Counter(left.base.values()) != Counter(right.base.values()):
        return False
    candidates = {
        node: [other for other, label in right.base.items() if label == signature]
        for node, signature in left.base.items()
    }
    order = sorted(left.base, key=lambda node: (len(candidates[node]), left.base[node]))
    mapping: dict[int, int] = {}
    used: set[int] = set()

    def edge(part: _Part, source: int, target: int) -> tuple[str, ...]:
        return part.adjacency.get((source, target), ())

    def visit(depth: int) -> bool:
        if depth == len(order):
            return True
        source = order[depth]
        for target in candidates[source]:
            budget.remaining -= 1
            if budget.remaining < 0:
                raise MatchLimit("Exact component matching exceeded its work limit")
            if target in used or edge(left, source, source) != edge(right, target, target):
                continue
            if any(
                edge(left, source, old) != edge(right, target, new)
                or edge(left, old, source) != edge(right, new, target)
                for old, new in mapping.items()
            ):
                continue
            mapping[source] = target
            used.add(target)
            if visit(depth + 1):
                return True
            used.remove(target)
            del mapping[source]
        return False

    return visit(0)


class _ServiceGraph:
    def __init__(self, service: Service, output_type: Callable[[Stream | None], _WireType | None]) -> None:
        streams = [stream for pipeline in service.pipelines.values()
                   for stream in pipeline.streams.values()]
        self.nodes: dict[int, Stream] = {id(stream): stream for stream in streams}
        self.incoming: defaultdict[int, list[_Edge]] = defaultdict(list)
        self.outgoing: defaultdict[int, list[_Edge]] = defaultdict(list)
        self.signatures: dict[int, str] = {}
        types = {id(stream): output_type(stream) for stream in streams}
        service_properties = _json_object(service.properties)
        for stream in streams:
            signature = {key: value for key, value in _json_object(stream.to_document()).items()
                         if key not in _DISPLAY_TOPOLOGY}
            signature["publicFunction"] = bool(signature.get("publicFunction"))
            if stream.function is not None or "functionName" in signature:
                for key in ("functionModule", "functionPackage", "functionInitializerGroup"):
                    signature[key] = signature.get(key) or ""
            signature["outputType"] = types[id(stream)]
            if stream.endpoint is not None:
                signature["endpoint"] = stream.endpoint.key
            self.signatures[id(stream)] = _stable(signature)

        edges: dict[tuple[int, int], tuple[Stream, Stream]] = {}
        for target in streams:
            for source in ([target.source] if target.source is not None else []) + target.sources:
                if id(source) in self.nodes:
                    edges[id(source), id(target)] = (source, target)
        for source in streams:
            if source.error_stream is not None and id(source.error_stream) in self.nodes:
                edges[id(source), id(source.error_stream)] = (source, source.error_stream)
        consumers: defaultdict[int, list[int]] = defaultdict(list)
        for source, target in edges.values():
            if target.type != "Error" and source.error_stream is not target:
                consumers[id(source)].append(id(target))
        links = {(id(link.source), id(link.target)): _json_object(link.to_document())
                 for link in service.links.values()}
        for pair, (source, target) in edges.items():
            props = links.get(pair, {})
            semantics = props.get("callSemantics")
            if semantics in (None, "", "Inherited"):
                semantics = service_properties.get("defaultCallSemantics")
            policy: dict[str, _JSONValue] = {"callSemantics": semantics}
            if semantics == "FunctionCall":
                policy["async"] = props.get("async", False)
            elif semantics in ("TaskPool", "PriorityTaskPool"):
                policy["poolName"] = props.get("poolName", "Default")
                if semantics == "PriorityTaskPool":
                    policy["priority"] = props.get("priority", 0)
            error = target.type == "Error" or source.error_stream is target
            source_role = "error" if error else (
                f"branch:{consumers[id(source)].index(id(target))}"
                if source.type in ("Split", "Case") else "output"
            )
            target_role = "source" if target.source is source else (
                f"sources:{next(i for i, item in enumerate(target.sources) if item is source)}"
                if target.type in ("Join", "MultiJoin") else "sources"
            )
            kind = "error" if error else "endpoint-result" if target.type == "Input" else "data"
            output: dict[str, _JSONValue] = {"kind": kind, "sourceRole": source_role, "valueType": types[id(source)]}
            full: dict[str, _JSONValue] = {**output, **policy, "targetRole": target_role}
            edge = _Edge(id(source), id(target), _stable(full), _stable(output))
            self.outgoing[id(source)].append(edge)
            self.incoming[id(target)].append(edge)

    def part(self, streams: Sequence[Stream]) -> _Part:
        ids = {id(stream) for stream in streams}
        if not ids or len(ids) != len(streams):
            raise ValueError("A component fragment must contain distinct streams and cannot be empty")
        if not ids <= self.nodes.keys():
            raise ValueError("A component fragment references an unknown or foreign stream")
        reached: set[int] = set()
        pending = [next(iter(ids))]
        while pending:
            node = pending.pop()
            if node in reached:
                continue
            reached.add(node)
            for edge in self.incoming[node] + self.outgoing[node]:
                neighbor = edge.source if edge.target == node else edge.target
                if neighbor in ids and neighbor not in reached:
                    pending.append(neighbor)
        if reached != ids:
            raise ValueError("A component fragment must be connected by execution links")
        base: dict[int, str] = {}
        adjacency: defaultdict[tuple[int, int], list[str]] = defaultdict(list)
        for node in ids:
            entry: list[str] = []
            exit_: list[str] = []
            ins: list[str] = []
            outs: list[str] = []
            for edge in self.incoming[node]:
                (ins if edge.source in ids else entry).append(edge.signature)
            for edge in self.outgoing[node]:
                if edge.target in ids:
                    outs.append(edge.signature)
                    adjacency[node, edge.target].append(edge.signature)
                else:
                    exit_.append(edge.output)
            base[node] = _stable((self.signatures[node], tuple(sorted(entry)), tuple(sorted(exit_)),
                                 tuple(sorted(ins)), tuple(sorted(outs))))
        return _Part(base, {pair: tuple(sorted(values)) for pair, values in adjacency.items()})


def validate_components(validator: Validator) -> None:
    """Add editor-semantic diagnostics after the ordinary topology diagnostics."""
    for service in validator.project.services.values():
        if not service.components:
            continue
        path = f"$.services.{service.key}.appearance.components"
        try:
            # Existing serialization checks identity, ownership, overlap and positions.
            service.to_document()
            graph = _ServiceGraph(service, validator.output_wire_type)
        except (ValueError, TypeError) as error:
            validator.add("SA_COMPONENT_INVALID_MEMBERSHIP", "semantic", str(error),
                          path, "component", service.name)
            continue
        for key, component in service.components.items():
            reference: _Part | None = None
            budget = _MatchBudget(500_000)
            for index, (members, _) in enumerate(component.fragments):
                fragment_path = f"{path}.groups.{key}.fragments[{index}]"
                try:
                    part = graph.part(members)
                    if reference is not None and not _equivalent(reference, part, budget):
                        validator.add(
                            "SA_COMPONENT_FRAGMENT_MISMATCH", "semantic",
                            "Component repetitions differ in node semantics, execution links or boundary ports; rebuild the component",
                            fragment_path, "component", component.name, referenceFragment=0,
                        )
                    if reference is None:
                        reference = part
                except (ValueError, TypeError) as error:
                    code = "SA_COMPONENT_MATCH_LIMIT" if isinstance(error, MatchLimit) else "SA_COMPONENT_INVALID_FRAGMENT"
                    validator.add(code, "semantic", str(error), fragment_path,
                                  "component", component.name)
                    if isinstance(error, MatchLimit):
                        break
