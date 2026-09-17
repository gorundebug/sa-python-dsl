"""Go emits declared type names verbatim, not their display-name normalization."""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .validation import Validator


GO_KEYWORDS = frozenset("break default func interface select case defer go map struct chan else goto package switch const fallthrough if range type continue for import return var".split())


def _go_identifier(name: str) -> bool:
    if not name or name == "_" or name in GO_KEYWORDS:
        return False
    return all(char == "_" or unicodedata.category(char).startswith("L")
               or (index > 0 and unicodedata.category(char) == "Nd")
               for index, char in enumerate(name))


def validate_type_identifiers(validator: Validator) -> None:
    if not any(service.programming_language == "GoLang" for service in validator.project.services.values()):
        return
    for key, definition in validator.project.types.items():
        named = definition.type in {"struct", "map", "array", "custom"} or definition.properties.get("useAlias") is True
        if named and not _go_identifier(definition.name):
            validator.add(
                "SG_SEMANTIC_INVALID_IDENTIFIER", "semantic",
                f"type name {definition.name!r} is not a valid Go identifier; named types are emitted verbatim",
                f"$.types.{key}.name", "type", definition.name,
                sourceName=definition.name, generatedName=definition.name, language="go",
            )
