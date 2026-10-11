from __future__ import annotations

import os
import glob
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .process_execution import MAX_CAPTURED_OUTPUT, run_bounded_process


VERIFICATIONS: Mapping[str, tuple[str, ...]] = {
    "build": ("make", "build"),
    "test": ("make", "test"),
    "lint": ("make", "lint"),
    "integration-test": ("make", "integration-test"),
    "merge-validate": ("make", "merge-validate"),
}
DEFAULT_VERIFICATION_TIMEOUT_SECONDS = 15 * 60
MAX_VERIFICATION_OUTPUT = MAX_CAPTURED_OUTPUT
_TASK_TITLE = re.compile(r"^# Task (\d+)/(\d+): `([^`]+)`$", re.MULTILINE)
_TABLE_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*`?([^|`]+?)`?\s*\|$", re.MULTILINE)
_TYPE_LINE = re.compile(r"^- (Input|Output|Key): `([^`]+)`(?:.*?`([^`]+)`)?.*$", re.MULTILINE)
_RUN_COMMAND = re.compile(r"^- \[ \] Run `([^`]+)`", re.MULTILINE)
_COMPLETED = re.compile(
    r"^- \[x\] ([^\s]+/task\d+\.md)[ \t]+[-\u2013\u2014][ \t]+"
    r"(.+?)[ \t]+[-\u2013\u2014][ \t]+(.+?)[ \t]+[-\u2013\u2014][ \t]+done(?:[ \t]+[^\r\n]*)?$",
    re.MULTILINE,
)


class BusinessTaskError(ValueError):
    def __init__(self, code: str, message: str, path: str = "$.verification") -> None:
        super().__init__(message)
        self.code = code
        self.path = path


def inspect_business_tasks(workspace: Path) -> dict[str, Any]:
    spec = workspace / "spec"
    progress_path = spec / "progress.md"
    progress = progress_path.read_text(encoding="utf-8") if progress_path.is_file() else ""
    # Task numbers change when generation adds/removes sorted functions.
    # Progress belongs to the function in its owner/runtime, not its old slot.
    completed = {
        (Path(path).parent.as_posix(), name, language)
        for path, name, language in _COMPLETED.findall(progress)
    }
    tasks: list[dict[str, Any]] = []
    if spec.is_dir():
        for path in sorted(spec.glob("*/task*.md")):
            task = _parse_task(workspace, path, completed)
            if task is not None:
                tasks.append(task)
    migrations = _migration_tasks(workspace)
    complete_count = sum(task["status"] == "complete" for task in tasks)
    return {
        "schemaVersion": "1.0",
        "status": "success",
        "summary": {
            "total": len(tasks),
            "complete": complete_count,
            "pending": len(tasks) - complete_count,
            "migrations": len(migrations),
        },
        "tasks": tasks,
        "migrations": migrations,
        "verifications": available_verifications(workspace),
    }


def available_verifications(workspace: Path) -> list[dict[str, Any]]:
    targets = _make_targets(workspace)
    result = []
    for identifier, command in VERIFICATIONS.items():
        target = command[-1]
        if target in targets:
            result.append({"id": identifier, "argv": list(command)})
    return result


def _make_targets(workspace: Path) -> set[str]:
    """Discover literal targets in local Make includes without evaluating Make.

    This is capability discovery, not a Make interpreter. Conditional execution
    and arbitrary variables are deliberately left to an explicit verification.
    """
    root = workspace.resolve()
    initial = next((root / name for name in ("GNUmakefile", "makefile", "Makefile")
                    if (root / name).is_file()), None)
    if initial is None:
        return set()
    pending = [initial]
    visited: set[Path] = set()
    targets: set[str] = set()
    total = 0
    while pending and len(visited) < 64:
        path = pending.pop().resolve()
        if path in visited or not path.is_relative_to(root) or not path.is_file():
            continue
        visited.add(path)
        if total + path.stat().st_size > 4 * 1024 * 1024:
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        total += len(content.encode("utf-8"))
        content = re.sub(r"\\\r?\n", " ", content)
        for line in content.splitlines():
            if line.startswith("\t"):
                continue
            rule = re.match(r"^ *([^#:=]+):(?!=)", line)
            if rule:
                targets.update(name for name in rule.group(1).split() if name in VERIFICATIONS)
            include = re.match(r"^ *(?:-?include|sinclude)\s+(.+)$", line)
            if not include:
                continue
            expression = include.group(1).strip()
            wildcard = re.fullmatch(r"\$\(wildcard\s+([^()]+)\)", expression)
            if wildcard:
                expression = wildcard.group(1)
            try:
                names = shlex.split(expression, comments=True)
            except ValueError:
                continue
            for name in names:
                name = name.replace("$(CURDIR)", str(root)).replace("${CURDIR}", str(root))
                if "$" in name:
                    continue
                for match in glob.iglob(str(root / name)):
                    if len(pending) >= 64:
                        break
                    pending.append(Path(match))
    return targets


def run_verification(
    workspace: Path,
    verification: str,
    *,
    timeout_seconds: int = DEFAULT_VERIFICATION_TIMEOUT_SECONDS,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    command = VERIFICATIONS.get(verification)
    if command is None:
        raise BusinessTaskError(
            "SA_VERIFICATION_NOT_ALLOWED",
            f"verification must be one of: {', '.join(sorted(VERIFICATIONS))}",
        )
    available = {item["id"] for item in available_verifications(workspace)}
    if verification not in available:
        raise BusinessTaskError(
            "SA_VERIFICATION_UNAVAILABLE",
            f"workspace does not provide the {verification!r} generated Make target",
        )
    environment = {
        key: os.environ[key]
        for key in ("HOME", "LANG", "LC_ALL", "PATH", "TMPDIR")
        if key in os.environ
    }
    started = monotonic()
    try:
        completed = (runner or run_bounded_process)(
            list(command),
            cwd=workspace,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise BusinessTaskError(
            "SA_VERIFICATION_TIMEOUT",
            f"verification exceeded the {timeout_seconds}-second timeout",
        ) from error
    duration_ms = max(0, round((monotonic() - started) * 1000))
    return {
        "schemaVersion": "1.0",
        "status": "success" if completed.returncode == 0 else "failed",
        "verification": verification,
        "argv": list(command),
        "exitCode": completed.returncode,
        "durationMs": duration_ms,
        "stdout": _bounded(completed.stdout),
        "stderr": _bounded(completed.stderr),
    }


def _parse_task(
    workspace: Path,
    path: Path,
    completed: set[tuple[str, str, str]],
) -> dict[str, Any] | None:
    content = path.read_text(encoding="utf-8", errors="replace")
    title = _TASK_TITLE.search(content)
    if title is None:
        return None
    fields = {
        key.strip().lower().replace(" ", "_"): value.strip()
        for key, value in _TABLE_ROW.findall(content)
        if key.strip() not in {"Field", "-------"}
    }
    types = {
        kind.lower(): {"name": name, **({"file": file_path} if file_path else {})}
        for kind, name, file_path in _TYPE_LINE.findall(content)
    }
    relative = path.relative_to(workspace).as_posix()
    commands = _RUN_COMMAND.findall(content)
    verification_ids = sorted(
        {
            identifier
            for command in commands
            for identifier in [_verification_id(command)]
            if identifier is not None
        }
    )
    return {
        "id": relative,
        "index": int(title.group(1)),
        "totalForOwner": int(title.group(2)),
        "name": title.group(3),
        "status": "complete" if (path.parent.name, title.group(3), fields.get("language")) in completed else "pending",
        "owner": path.parent.name,
        "language": fields.get("language"),
        "kind": fields.get("kind"),
        "file": fields.get("file"),
        "testFile": fields.get("test"),
        "types": types,
        "verificationIds": verification_ids,
    }


def _verification_id(command: str) -> str | None:
    normalized = command.strip()
    if normalized == "make build":
        return "build"
    if normalized == "make test" or normalized == "cargo test --workspace --all-targets":
        return "test"
    if normalized in {"make lint", "./scripts/python/typecheck.generated.sh"}:
        return "lint"
    if normalized == "make integration-test":
        return "integration-test"
    if normalized == "make merge-validate":
        return "merge-validate"
    if normalized.endswith("/test.generated.sh"):
        return "test"
    return None


def _migration_tasks(workspace: Path) -> list[dict[str, Any]]:
    directory = workspace / ".servicegen" / "migrations"
    if not directory.is_dir():
        return []
    result = []
    for path in sorted(directory.glob("*.md")):
        content = path.read_text(encoding="utf-8", errors="replace")
        items = [line[6:] for line in content.splitlines() if line.startswith("- [ ] ")]
        result.append(
            {
                "id": path.relative_to(workspace).as_posix(),
                "status": "pending" if items else "complete",
                "items": items,
            }
        )
    return result


def _bounded(value: str) -> str:
    if len(value) <= MAX_VERIFICATION_OUTPUT:
        return value
    return value[:MAX_VERIFICATION_OUTPUT] + "\n... output truncated ...\n"
