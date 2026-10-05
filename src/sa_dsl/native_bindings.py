from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class NativeTypeBinding:
    """Native spelling and import owned by one template target, not the DSL."""

    definition: str | None = None
    import_path: str | None = None
    package: str | None = None

    def to_document(self) -> dict[str, str]:
        result = {}
        for field, value in (
            ("definition", self.definition),
            ("import", self.import_path),
            ("package", self.package),
        ):
            if value is None:
                continue
            if not isinstance(value, str):
                raise NativeTypeBindingError(field, "SG_SCHEMA_WRONG_TYPE", f"{field} must be a string")
            result[field] = value
        return result


class NativeTypeBindingError(ValueError):
    def __init__(self, field: str, code: str, message: str):
        super().__init__(message)
        self.field = field
        self.code = code


_TYPE_FIELDS = frozenset({
    "name", "type", "description", "valueType", "keyType", "definitionFormat",
    "transferByValue", "useAlias", "package", "publicType", "module", "bindings",
})
_BINDING_FIELDS = frozenset({"definition", "import", "package"})


def normalize_native_type_bindings(bindings: Any) -> dict[str, dict[str, str]] | None:
    """Validate/copy authored bindings without interpreting or normalizing targets."""
    if bindings is None:
        return None
    if not isinstance(bindings, Mapping):
        raise NativeTypeBindingError("bindings", "SG_SCHEMA_WRONG_TYPE", "bindings must be a mapping")
    result = {}
    for target, value in bindings.items():
        if not isinstance(target, str) or not target or target.strip() != target:
            raise NativeTypeBindingError("bindings", "SG_SEMANTIC_INVALID_IDENTIFIER",
                                         f"Invalid native type binding target {target!r}")
        path = f"bindings[{target!r}]"
        if isinstance(value, NativeTypeBinding):
            try:
                value = value.to_document()
            except NativeTypeBindingError as error:
                raise NativeTypeBindingError(f"{path}.{error.field}", error.code, str(error)) from error
        if not isinstance(value, Mapping):
            raise NativeTypeBindingError(path, "SG_SCHEMA_WRONG_TYPE", f"{path} must be an object")
        entry = {}
        for field, item in value.items():
            if field not in _BINDING_FIELDS:
                raise NativeTypeBindingError(f"{path}.{field}", "SG_SCHEMA_UNKNOWN_FIELD",
                                             f"Unknown native type binding field {field!r}")
            if item is None:
                continue
            if not isinstance(item, str):
                raise NativeTypeBindingError(f"{path}.{field}", "SG_SCHEMA_WRONG_TYPE",
                                             f"{path}.{field} must be a string")
            entry[field] = item
        result[target] = entry
    return result


def require_type_fields(properties: Mapping[str, Any]) -> None:
    for field in properties:
        if field not in _TYPE_FIELDS:
            raise NativeTypeBindingError(str(field), "SG_SCHEMA_UNKNOWN_FIELD",
                                         f"Unknown type field {field!r}; use bindings for native definitions")
    normalize_native_type_bindings(properties.get("bindings"))
