"""Implementation identities from the evaluated Python model, never generated paths."""

from __future__ import annotations

import re
from typing import Any


def implementation_targets(document: dict[str, Any]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    endpoints = {
        key: endpoint
        for connector in document.get("dataConnectors", {}).values()
        for key, endpoint in connector.get("endpoints", {}).items()
    }
    result: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for service_key, service in document.get("services", {}).items():
        nodes: dict[str, list[dict[str, Any]]] = {}
        for pipeline in service.get("pipelines", {}).values():
            for key, stream in pipeline.items():
                role = "function"
                function = stream
                suffix = ""
                if stream.get("type") in {"Input", "Sink"}:
                    function = endpoints.get(stream.get("endpoint"), {})
                    role = "source" if stream["type"] == "Input" else "sink"
                    suffix = role.title()
                name = function.get("functionName")
                if not isinstance(name, str) or not name.strip():
                    continue
                # Exported names are identifiers; preserve acronym spelling in the
                # primary candidate and provide the idiomatic snake-case spelling.
                symbol = name.strip() + suffix
                words = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", symbol)
                words = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", words)
                snake = re.sub(r"[^\w]+", "_", words).strip("_").lower()
                pascal = "".join(part[:1].upper() + part[1:] for part in re.split(r"[^\w]+|_", words) if part)
                nodes[key] = [{
                    "name": name.strip(), "role": role,
                    "symbols": list(dict.fromkeys([symbol, pascal, snake])),
                    "language": service.get("programmingLanguage", ""),
                    "service": service_key,
                    "owner": function.get("functionModule") or service_key,
                    "package": function.get("functionPackage", ""),
                }]
        result[service_key] = nodes
    return result
