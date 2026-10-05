from __future__ import annotations

from typing import Any, Mapping

from .connector_bindings import require_connector_fields


CPP_BOOST_RETIREMENT = (
    "The cppBoost runtime has been removed. Migrate explicitly to CppCoro and "
    "adapt the business functions to its coroutine API; automatic conversion "
    "would change the business-function contract."
)


def is_retired_language(value: Any) -> bool:
    return value in (5, "CppBoost", "cppBoost", "cpp-boost")


def require_supported_backends(document: Mapping[str, Any]) -> None:
    """Reject retired selectors before writing files or submitting a graph."""
    for collection in ("services", "dataConnectors"):
        entries = document.get(collection) or {}
        if isinstance(entries, Mapping):
            items = ((f"$.{collection}.{key}", value) for key, value in entries.items())
        elif isinstance(entries, list):
            items = ((f"$.{collection}[{index}]", value) for index, value in enumerate(entries))
        else:
            continue  # Structural diagnostics belong to the model validator.
        for path, entry in items:
            if not isinstance(entry, Mapping):
                continue
            if is_retired_language(entry.get("programmingLanguage")):
                raise ValueError(f"{path}.programmingLanguage: {CPP_BOOST_RETIREMENT}")
            if "cppBoostImplementation" in entry:
                raise ValueError(
                    f"{path}.cppBoostImplementation: {CPP_BOOST_RETIREMENT} "
                    "Remove the retired selector; configure implementations.cppCoro explicitly when needed."
                )
            if collection == "dataConnectors":
                require_connector_fields(entry, path)
