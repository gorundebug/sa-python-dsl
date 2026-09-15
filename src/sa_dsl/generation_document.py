"""Flatten visual membership into observability labels on ordinary streams."""
from __future__ import annotations
from typing import Any
from .visual_components import normalize_components, without_visual_components


def generation_document(document: dict[str, Any]) -> dict[str, Any]:
    from .model import _key

    if not isinstance(document.get("services"), list) or not isinstance(document.get("streams"), list):
        raise ValueError("Code generation requires the flat API graph with services and streams arrays")
    assignments: dict[int, str | None] = {}
    for service in document["services"]:
        appearance = service.get("appearance") or {}
        if "components" not in appearance:
            continue
        streams = [(index, stream) for index, stream in enumerate(document["streams"])
                   if str(stream.get("idService")) == str(service.get("id"))]
        refs = {index: (stream.get("pipeline") or "default", _key(None, stream["name"]))
                for index, stream in streams}
        metadata = normalize_components(appearance["components"], refs.values())
        names = {tuple(ref): group["name"] for group in metadata["groups"].values()
                 for fragment in group["fragments"] for ref in fragment["streams"]}
        assignments.update({index: names.get(refs[index]) for index, _ in streams})
    result = without_visual_components(document)
    streams = []
    for index, stream in enumerate(document["streams"]):
        if index in assignments:
            stream = {key: value for key, value in stream.items() if key != "component"}
            if assignments[index]:
                stream["component"] = assignments[index]
        streams.append(stream)
    return {**result, "streams": streams}
