from __future__ import annotations

import re
from enum import Enum
from typing import Any, Mapping


# Rejection only: these fields are not aliases for the open mapping.
_REMOVED_WIRE_FIELDS = (
    "goImplementation", "cppUserverImplementation", "cppCoroImplementation",
    "pythonImplementation", "rustImplementation", "typeScriptImplementation",
)
REMOVED_CONNECTOR_FIELDS = frozenset(_REMOVED_WIRE_FIELDS) | frozenset(
    re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower() for name in _REMOVED_WIRE_FIELDS
)
_TARGET = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def require_connector_fields(properties: Mapping[str, Any], path: str = "connector") -> None:
    for field in sorted(REMOVED_CONNECTOR_FIELDS.intersection(properties)):
        raise ValueError(
            f"{path}.{field} has been removed; use implementations or omit the "
            "selection to use the template pack default"
        )


def normalize_connector_implementations(
    bindings: Mapping[str, str] | None,
) -> dict[str, str] | None:
    """Copy open target selections, rejecting malformed or conflicting input."""
    if bindings is None:
        return None
    if not isinstance(bindings, Mapping):
        raise ValueError("Connector implementations must be a mapping of target names to strings")
    selected: dict[str, tuple[str, str]] = {}
    result: dict[str, str] = {}
    for name, value in bindings.items():
        if not isinstance(name, str) or not _TARGET.fullmatch(name):
            raise ValueError(f"Invalid connector implementation target {name!r}")
        if isinstance(value, Enum):
            value = value.value
        if not isinstance(value, str) or not value or value.strip() != value:
            raise ValueError(
                f"Connector implementations.{name} must be a nonempty string without surrounding whitespace"
            )
        target = "golang" if name == "go" else name
        previous = selected.get(target)
        if previous is not None and previous[1] != value:
            raise ValueError(
                f"Conflicting connector implementations for {target!r}: "
                f"{previous[0]}={previous[1]!r} and implementations.{name}={value!r}"
            )
        selected[target] = (f"implementations.{name}", value)
        result[name] = value
    return result
