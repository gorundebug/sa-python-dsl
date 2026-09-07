from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

import yaml


SCHEMA_VERSION = "1.0"
COLLECTION_KINDS = {
    "dataConnectors": "dataConnector",
    "modules": "module",
    "pools": "pool",
    "types": "type",
}
SERVICE_CHILD_KINDS = {
    "streams": "stream",
    "links": "link",
}


class SemanticDiffError(ValueError):
    pass


def document_revision(document: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        document,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def preview_architecture_diff(
    baseline_yaml: str | None,
    candidate_yaml: str,
) -> dict[str, Any]:
    baseline = _document(baseline_yaml, "baseline") if baseline_yaml is not None else {}
    candidate = _document(candidate_yaml, "candidate")
    changes: list[dict[str, Any]] = []

    for collection, kind in COLLECTION_KINDS.items():
        _compare_collection(
            changes,
            _mapping(baseline.get(collection), f"$.{collection}"),
            _mapping(candidate.get(collection), f"$.{collection}"),
            collection,
            kind,
        )

    _compare_services(changes, baseline, candidate)

    known = set(COLLECTION_KINDS) | {"services"}
    for section in sorted((set(baseline) | set(candidate)) - known):
        before = baseline.get(section, _MISSING)
        after = candidate.get(section, _MISSING)
        if before != after:
            changes.append(_change("section", section, f"$.{section}", before, after))

    changes.sort(key=lambda item: (item["path"], item["change"]))
    summary = {"added": 0, "changed": 0, "removed": 0, "total": len(changes)}
    for change in changes:
        summary[change["change"]] += 1

    return {
        "schemaVersion": SCHEMA_VERSION,
        "baselineRevision": document_revision(baseline) if baseline_yaml is not None else None,
        "candidateRevision": document_revision(candidate),
        "hasBaseline": baseline_yaml is not None,
        "summary": summary,
        "changes": changes,
    }


def _compare_services(
    changes: list[dict[str, Any]],
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> None:
    before_services = _mapping(baseline.get("services"), "$.services")
    after_services = _mapping(candidate.get("services"), "$.services")
    for identity in sorted(set(before_services) | set(after_services), key=str):
        path = _path("services", identity)
        before = before_services.get(identity, _MISSING)
        after = after_services.get(identity, _MISSING)
        if before is _MISSING or after is _MISSING:
            changes.append(_change("service", str(identity), path, before, after))
            continue
        before_service = _mapping(before, path)
        after_service = _mapping(after, path)
        before_properties = {
            key: value for key, value in before_service.items() if key not in SERVICE_CHILD_KINDS
        }
        after_properties = {
            key: value for key, value in after_service.items() if key not in SERVICE_CHILD_KINDS
        }
        if before_properties != after_properties:
            changes.append(
                _change("service", str(identity), path, before_properties, after_properties)
            )
        for collection, kind in SERVICE_CHILD_KINDS.items():
            _compare_collection(
                changes,
                _mapping(before_service.get(collection), f"{path}.{collection}"),
                _mapping(after_service.get(collection), f"{path}.{collection}"),
                collection,
                kind,
                parent_path=path,
                parent_identity=str(identity),
            )


def _compare_collection(
    changes: list[dict[str, Any]],
    before: Mapping[Any, Any],
    after: Mapping[Any, Any],
    collection: str,
    kind: str,
    *,
    parent_path: str = "$",
    parent_identity: str | None = None,
) -> None:
    for identity in sorted(set(before) | set(after), key=str):
        old = before.get(identity, _MISSING)
        new = after.get(identity, _MISSING)
        if old == new:
            continue
        path = _path(collection, identity, parent_path=parent_path)
        change = _change(kind, str(identity), path, old, new)
        if parent_identity is not None:
            change["service"] = parent_identity
        changes.append(change)


def _change(
    kind: str,
    identity: str,
    path: str,
    before: Any,
    after: Any,
) -> dict[str, Any]:
    if before is _MISSING:
        change = "added"
    elif after is _MISSING:
        change = "removed"
    else:
        change = "changed"
    result: dict[str, Any] = {
        "change": change,
        "kind": kind,
        "identity": identity,
        "path": path,
    }
    if change == "changed":
        result["changedFields"] = _changed_fields(before, after)
    if before is not _MISSING:
        result["beforeHash"] = document_revision({"value": before})
    if after is not _MISSING:
        result["afterHash"] = document_revision({"value": after})
    return result


def _changed_fields(before: Any, after: Any) -> list[str]:
    if not isinstance(before, dict) or not isinstance(after, dict):
        return ["value"]
    return sorted(
        str(key)
        for key in set(before) | set(after)
        if before.get(key, _MISSING) != after.get(key, _MISSING)
    )


def _document(value: str, label: str) -> dict[str, Any]:
    try:
        document = yaml.safe_load(value)
    except yaml.YAMLError as error:
        raise SemanticDiffError(f"invalid {label} canonical YAML: {error}") from error
    if not isinstance(document, dict):
        raise SemanticDiffError(f"{label} canonical YAML must contain an object")
    return document


def _mapping(value: Any, path: str) -> Mapping[Any, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SemanticDiffError(f"{path} must be an object")
    return value


def _path(collection: str, identity: Any, *, parent_path: str = "$") -> str:
    encoded = json.dumps(str(identity), ensure_ascii=True)
    separator = "" if parent_path == "$" else "."
    return f"{parent_path}{separator}{collection}[{encoded}]"


_MISSING = object()
