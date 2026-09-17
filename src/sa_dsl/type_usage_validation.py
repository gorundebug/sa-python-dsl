"""Generation-time type ownership requirements, checked before export."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .validation import Validator


def common_type_users(validator: Validator) -> dict[str, list[str]]:
    project = validator.project
    usage: dict[str, dict[str, bool]] = {}
    for service in project.services.values():
        for pipeline in service.pipelines.values():
            for stream in pipeline.streams.values():
                pending = [value for field in ("valueType", "keyType")
                           if isinstance(value := stream.properties.get(field), str)]
                public = stream.properties.get("publicFunction") is True
                if public:
                    for source in ([stream.source] if stream.source is not None else []) + stream.sources:
                        wire = validator.output_wire_type(source)
                        if wire is not None:
                            pending.extend(value for value in (wire[1], wire[2]) if value)
                visited: set[str] = set()
                while pending:
                    key = pending.pop()
                    if key in visited or key not in project.types:
                        continue
                    visited.add(key)
                    definition = project.types[key]
                    owners = usage.setdefault(key, {})
                    owners[service.key] = owners.get(service.key, False) or public
                    for field in ("valueType", "keyType"):
                        child = definition.properties.get(field)
                        if isinstance(child, str):
                            pending.append(child)
    common: dict[str, list[str]] = {}
    for key, definition in project.types.items():
        owners = usage.get(key, {})
        languages = Counter(project.services[owner].programming_language for owner in owners)
        shared = any(count > 1 for count in languages.values())
        non_native = definition.type == "struct" and definition.properties.get("definitionFormat") not in (None, "Native", 1)
        if definition.properties.get("publicType") or any(owners.values()) or shared or (non_native and len(owners) > 1):
            common[key] = sorted(owners)
    return common


def validate_type_generation_contracts(validator: Validator) -> None:
    from .type_identifier_validation import validate_type_identifiers

    validate_type_identifiers(validator)
    for key, definition in validator.project.types.items():
        if definition.type == "struct" and not definition.properties.get("definitionFormat"):
            validator.add(
                "SG_SCHEMA_REQUIRED_FIELD", "schema",
                f"message type {definition.name!r} requires definitionFormat",
                f"$.types.{key}.definitionFormat", "type", definition.name,
                field="definitionFormat",
            )
    for key, services in common_type_users(validator).items():
        definition = validator.project.types[key]
        if not definition.properties.get("module"):
            validator.add(
                "SG_SCHEMA_REQUIRED_FIELD", "schema",
                f"common type {definition.name!r} requires a module",
                f"$.types.{key}.module", "type", definition.name,
                field="module", services=services,
            )
