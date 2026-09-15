"""Typed visual repeated-subgraph metadata; runtime streams remain concrete."""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import NotRequired, TypedDict

COMPONENTS_VERSION = 2
StreamReference = tuple[str, str]


class ComponentPosition(TypedDict, total=False):
    x: int | float
    y: int | float


class ComponentFragment(TypedDict):
    streams: list[list[str]]
    position: NotRequired[ComponentPosition]


class ComponentDefinition(TypedDict):
    name: str
    fragments: list[ComponentFragment]
    description: NotRequired[str]


class ComponentMetadata(TypedDict):
    version: int
    groups: dict[str, ComponentDefinition]


def _mapping(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be a mapping")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{path} keys must be strings")
        result[key] = item
    return result


def _fields(value: object, allowed: set[str], path: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    result = _mapping(value, path)
    extra = set(result) - allowed
    if extra:
        raise ValueError(f"Unsupported {path} fields: {sorted(extra)}")
    return result


def _text(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value


def _position(value: object) -> ComponentPosition:
    raw = _fields(value, {"x", "y"}, "fragment.position")
    result: ComponentPosition = {}
    for key, coordinate in raw.items():
        if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)) or not math.isfinite(coordinate):
            raise ValueError("Fragment coordinates must be finite numbers")
        if key == "x":
            result["x"] = coordinate
        else:
            result["y"] = coordinate
    return result


def normalize_components(
    value: object,
    stream_refs: Iterable[Sequence[str]] | Mapping[str, Iterable[str]] | None = None,
) -> ComponentMetadata:
    from .model import _key

    if value is None:
        return {"version": COMPONENTS_VERSION, "groups": {}}
    if isinstance(value, dict) and value.get("version") == 1:
        raise ValueError("Pipeline-group components are no longer supported. Remove old appearance.components and recreate components from repeated fragments.")
    raw = _fields(value, {"version", "groups"}, "components")
    version = raw.get("version")
    if type(version) is not int or version != COMPONENTS_VERSION:
        raise ValueError("Unsupported components version")
    if not isinstance(raw.get("groups"), dict):
        raise ValueError("components.groups must be an object")
    raw_groups = _mapping(raw["groups"], "components.groups")
    available: set[StreamReference] | None = None
    if stream_refs is not None:
        references: Iterable[Sequence[str]]
        if isinstance(stream_refs, Mapping):
            references = ((pipeline, stream) for pipeline, streams in stream_refs.items() for stream in streams)
        else:
            references = stream_refs
        available = set()
        for reference in references:
            if len(reference) != 2:
                raise ValueError("A component stream reference must be [pipeline, stream]")
            available.add((_text(reference[0], "pipeline"), _text(reference[1], "stream")))
    used: set[StreamReference] = set()
    groups: dict[str, ComponentDefinition] = {}
    for identity, value_group in raw_groups.items():
        _text(identity, "component key")
        group = _fields(value_group, {"name", "description", "fragments"}, "component")
        name = _text(group.get("name"), "component.name")
        key = _key(None, name)
        if key in groups:
            raise ValueError(f"Duplicate component: {key}")
        raw_fragments = group.get("fragments")
        if not isinstance(raw_fragments, list):
            raise ValueError("component.fragments must be an array")
        fragments: list[ComponentFragment] = []
        for value_fragment in raw_fragments:
            fragment = _fields(value_fragment, {"streams", "position"}, "fragment")
            refs = fragment.get("streams")
            if not isinstance(refs, list) or not refs:
                raise ValueError("fragment.streams must be a non-empty array")
            members: list[list[str]] = []
            for ref in refs:
                if not isinstance(ref, (list, tuple)) or len(ref) != 2:
                    raise ValueError("A component stream reference must be [pipeline, stream]")
                member = (_text(ref[0], "pipeline"), _text(ref[1], "stream"))
                if available is not None and member not in available:
                    raise ValueError(f"Unknown component stream: {member}")
                if member in used:
                    raise ValueError(f"Component fragments must not overlap: {member}")
                used.add(member)
                members.append(list(member))
            normalized: ComponentFragment = {"streams": sorted(members)}
            if "position" in fragment:
                position = _position(fragment["position"])
                if position:
                    normalized["position"] = position
            fragments.append(normalized)
        normalized_group: ComponentDefinition = {"name": name, "fragments": fragments}
        description = group.get("description")
        if description is not None:
            if not isinstance(description, str):
                raise ValueError("component.description must be a string")
            if description:
                normalized_group["description"] = description
        groups[key] = normalized_group
    return {"version": COMPONENTS_VERSION, "groups": groups}


def without_visual_components(document: dict[str, object]) -> dict[str, object]:
    """Return a request copy without changing metadata in the input document."""
    def clean_service(value: object) -> dict[str, object]:
        service = _mapping(value, "service")
        appearance = _mapping(service.get("appearance") or {}, "service.appearance")
        if "components" not in appearance:
            return service
        remaining = {key: item for key, item in appearance.items() if key != "components"}
        clean = {key: item for key, item in service.items() if key != "appearance"}
        if remaining:
            clean["appearance"] = remaining
        return clean

    services = document.get("services")
    if services is None:
        return document
    if isinstance(services, list):
        return {**document, "services": [clean_service(service) for service in services]}
    return {**document, "services": {
        key: clean_service(service) for key, service in _mapping(services, "services").items()
    }}
