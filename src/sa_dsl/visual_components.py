"""Editor-only pipeline grouping metadata, excluded at generation boundaries."""
from __future__ import annotations

import math
from typing import Any, Iterable

COMPONENTS_VERSION = 1


def normalize_components(value: Any, pipeline_names: Iterable[str]) -> dict[str, Any]:
    if value is None:
        return {"version": COMPONENTS_VERSION, "groups": {}, "pipelines": {}}

    def object_(item: Any, path: str) -> None:
        if not isinstance(item, dict):
            raise ValueError(f"{path} must be an object")

    def fields(item: Any, allowed: set[str], path: str) -> None:
        object_(item, path)
        for key in item:
            if key not in allowed:
                raise ValueError(f"{path}.{key} is not supported")

    def text(item: Any, path: str) -> None:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{path} must be a non-empty string")

    fields(value, {"version", "groups", "pipelines"}, "components")
    if type(value.get("version")) is not int or value["version"] != COMPONENTS_VERSION:
        raise ValueError("Unsupported components version")
    object_(value.get("groups"), "components.groups")
    object_(value.get("pipelines"), "components.pipelines")
    groups: dict[str, Any] = {}
    pipelines: dict[str, str] = {}
    available = set(pipeline_names)
    for identity, group in value["groups"].items():
        text(identity, "Component identity")
        fields(group, {"name", "description", "position"}, f"components.groups.{identity}")
        text(group.get("name"), "Component name")
        copy = {"name": group["name"]}
        if group.get("description") is not None:
            if not isinstance(group["description"], str):
                raise ValueError("Component description must be a string")
            copy["description"] = group["description"]
        if group.get("position") is not None:
            fields(group["position"], {"x", "y"}, "Component position")
            position = {}
            for axis, coordinate in group["position"].items():
                if type(coordinate) not in (int, float) or not math.isfinite(coordinate):
                    raise ValueError(f"Component position {axis} must be finite")
                position[axis] = coordinate
            copy["position"] = position
        groups[identity] = copy
    for pipeline, component in value["pipelines"].items():
        if pipeline not in available:
            raise ValueError(f"Unknown component pipeline: {pipeline}")
        if not isinstance(component, str) or component not in groups:
            raise ValueError(f"Unknown component: {component}")
        pipelines[pipeline] = component
    return {"version": COMPONENTS_VERSION, "groups": groups, "pipelines": pipelines}


def without_visual_components(document: dict[str, Any]) -> dict[str, Any]:
    """Return a request copy without changing editor metadata in the source."""
    def clean_service(service: dict[str, Any]) -> dict[str, Any]:
        appearance = service.get("appearance") or {}
        if "components" not in appearance:
            return service
        remaining = {k: v for k, v in appearance.items() if k != "components"}
        clean = {k: v for k, v in service.items() if k != "appearance"}
        if remaining:
            clean["appearance"] = remaining
        return clean

    services = document.get("services")
    if services is None:
        return document
    return {**document, "services": (
        [clean_service(service) for service in services] if isinstance(services, list)
        else {key: clean_service(service) for key, service in services.items()}
    )}
