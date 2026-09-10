from __future__ import annotations

import json
import os
import secrets
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


AUDIT_RELATIVE_PATH = Path(".service-architect/audit.jsonl")
_LOCK = threading.Lock()


def record_operation(
    workspace: Path,
    operation: str,
    payload: dict[str, Any],
    started: float,
) -> None:
    event: dict[str, Any] = {
        "schemaVersion": "1.0",
        "eventId": secrets.token_urlsafe(12),
        "timestamp": datetime.now(UTC).isoformat(),
        "operation": operation,
        "status": payload.get("status", "unknown"),
        "durationMs": max(0, round((time.monotonic() - started) * 1000)),
        "diagnosticCodes": sorted(
            {
                diagnostic.get("code")
                for diagnostic in payload.get("diagnostics", [])
                if isinstance(diagnostic, dict) and isinstance(diagnostic.get("code"), str)
            }
        ),
    }
    project = payload.get("project")
    if isinstance(project, dict) and isinstance(project.get("name"), str):
        event["project"] = project["name"]
    for container_name in ("preview", "application"):
        container = payload.get(container_name)
        if not isinstance(container, dict):
            continue
        references = {
            key: container[key]
            for key in (
                "previewId", "previewRevision", "baselineRevision",
                "candidateRevision", "canonicalRevision", "workspaceRevision",
            )
            if isinstance(container.get(key), str)
        }
        if references:
            event["references"] = references

    root = workspace.resolve()
    destination = (root / AUDIT_RELATIVE_PATH).resolve(strict=False)
    if destination != root / AUDIT_RELATIVE_PATH or destination.is_symlink():
        raise OSError("audit path must not be a symlink or escape the workspace")
    line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
    with _LOCK:
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(destination, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, line.encode("utf-8"))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def read_audit(workspace: Path, *, limit: int = 100) -> dict[str, Any]:
    path = workspace / AUDIT_RELATIVE_PATH
    if not path.is_file():
        events: list[dict[str, Any]] = []
    else:
        lines = path.read_text(encoding="utf-8").splitlines()[-max(1, min(limit, 1000)):]
        events = [json.loads(line) for line in lines if line.strip()]
    return {"schemaVersion": "1.0", "events": events}


def record_operation_safely(workspace, operation, payload, started):
    """An audit failure must not obscure an already completed operation."""
    try:
        record_operation(workspace, operation, payload, started)
    except OSError as error:
        payload.setdefault("diagnostics", []).append({
            "code": "SA_AUDIT_WRITE_FAILED", "severity": "warning",
            "path": "$.audit", "message": f"Operation completed but audit could not be written: {error}",
        })
