from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .manifest import ProjectManifest


Operation = Literal["validate", "export"]
DEFAULT_EXECUTION_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    operation: Operation
    status: Literal["success", "failed"]
    project_name: str
    diagnostics: tuple[dict[str, Any], ...] = ()
    rendered_yaml: str | None = None
    source_files: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        return self.status == "success"

    def to_payload(self, *, output: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schemaVersion": "1.0",
            "operation": self.operation,
            "status": self.status,
            "project": {"name": self.project_name},
            "diagnostics": list(self.diagnostics),
        }
        if output is not None:
            payload["artifact"] = {"kind": "canonical-yaml", "path": output}
        return payload


def execute_project(
    manifest: ProjectManifest,
    operation: Operation,
    *,
    timeout_seconds: int = DEFAULT_EXECUTION_TIMEOUT_SECONDS,
) -> ExecutionResult:
    """Execute a declared Python entrypoint in a bounded child process."""

    if manifest.authoring.mode != "python" or manifest.authoring.entrypoint is None:
        return ExecutionResult(
            operation=operation,
            status="failed",
            project_name=manifest.name,
            diagnostics=(
                {
                    "code": "SA_AUTHORING_MODE_UNSUPPORTED",
                    "severity": "error",
                    "path": "$.authoring.mode",
                    "message": (
                        f"{operation} requires Python authoring; "
                        f"found {manifest.authoring.mode}"
                    ),
                },
            ),
        )

    with tempfile.TemporaryDirectory(prefix="sa-dsl-") as temporary_directory:
        result_path = Path(temporary_directory) / "result.json"
        command = [
            sys.executable,
            "-I",
            "-m",
            "sa_dsl._worker",
            "--operation",
            operation,
            "--workspace",
            str(manifest.workspace.resolve()),
            "--entrypoint",
            manifest.authoring.entrypoint,
            "--project-name",
            manifest.name,
            "--result",
            str(result_path),
        ]
        try:
            process = subprocess.Popen(
                command,
                cwd=manifest.workspace,
                env=_worker_environment(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            stdout, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            _terminate_process_group(process)
            return _execution_failure(
                manifest,
                operation,
                "SA_EXECUTION_TIMEOUT",
                f"Python authoring exceeded the {timeout_seconds}-second timeout",
            )
        except OSError as error:
            return _execution_failure(
                manifest,
                operation,
                "SA_EXECUTION_FAILED",
                f"cannot start Python authoring process: {error}",
            )

        if not result_path.is_file():
            detail = stderr.strip() or stdout.strip()
            message = "Python authoring process did not produce a result"
            if detail:
                message = f"{message}: {_bounded_text(detail)}"
            return _execution_failure(
                manifest, operation, "SA_EXECUTION_FAILED", message
            )

        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            return _execution_failure(
                manifest,
                operation,
                "SA_EXECUTION_PROTOCOL_ERROR",
                f"cannot read Python authoring result: {error}",
            )

    diagnostics = payload.get("diagnostics", [])
    if not isinstance(diagnostics, list):
        return _execution_failure(
            manifest,
            operation,
            "SA_EXECUTION_PROTOCOL_ERROR",
            "Python authoring returned invalid diagnostics",
        )
    rendered_yaml = payload.get("yaml")
    if rendered_yaml is not None and not isinstance(rendered_yaml, str):
        return _execution_failure(
            manifest,
            operation,
            "SA_EXECUTION_PROTOCOL_ERROR",
            "Python authoring returned invalid YAML content",
        )
    source_files = payload.get("sourceFiles", [])
    if not isinstance(source_files, list) or any(not isinstance(path, str) for path in source_files):
        return _execution_failure(
            manifest, operation, "SA_EXECUTION_PROTOCOL_ERROR",
            "Python authoring returned invalid source file metadata",
        )
    status = payload.get("status")
    if status not in {"success", "failed"}:
        return _execution_failure(
            manifest,
            operation,
            "SA_EXECUTION_PROTOCOL_ERROR",
            "Python authoring returned an invalid status",
        )
    if process.returncode != 0 and status == "success":
        return _execution_failure(
            manifest,
            operation,
            "SA_EXECUTION_PROTOCOL_ERROR",
            "Python authoring exited unsuccessfully after reporting success",
        )
    return ExecutionResult(
        operation=operation,
        status=status,
        project_name=manifest.name,
        diagnostics=tuple(diagnostics),
        rendered_yaml=rendered_yaml,
        source_files=tuple(source_files),
    )


def write_canonical_yaml(
    manifest: ProjectManifest, rendered_yaml: str, output: str | None = None
) -> str:
    relative_output = output or manifest.canonical.output
    destination = _workspace_path(manifest.workspace, relative_output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    metadata = manifest.workspace / '.service-architect'
    if destination.is_relative_to((metadata / 'build').resolve()):
        ignore = manifest.workspace / '.gitignore'
        if ignore.is_symlink():
            raise ValueError('SA project .gitignore must not be a symlink')
        with ignore.open('a+', encoding='utf-8') as stream:
            stream.seek(0)
            content = stream.read()
            pattern = '.service-architect/build/'
            if pattern not in content.splitlines() and '/' + pattern not in content.splitlines():
                stream.write(('\n' if content and not content.endswith('\n') else '') + pattern + '\n')
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', dir=destination.parent,
            prefix=f'.{destination.name}.', suffix='.tmp', delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(rendered_yaml)
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return relative_output


def _workspace_path(workspace: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("output must be a relative path inside the project workspace")
    destination = (workspace / candidate).resolve()
    root = workspace.resolve()
    if destination != root and root not in destination.parents:
        raise ValueError("output resolves outside the project workspace")
    return destination


def _worker_environment() -> dict[str, str]:
    allowed = ("HOME", "LANG", "LC_ALL", "PATH", "TMPDIR", "VIRTUAL_ENV")
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass
    process.communicate()


def _execution_failure(
    manifest: ProjectManifest,
    operation: Operation,
    code: str,
    message: str,
) -> ExecutionResult:
    return ExecutionResult(
        operation=operation,
        status="failed",
        project_name=manifest.name,
        diagnostics=(
            {
                "code": code,
                "severity": "error",
                "path": "$.authoring.entrypoint",
                "message": message,
            },
        ),
    )


def _bounded_text(value: str, limit: int = 1000) -> str:
    return value if len(value) <= limit else f"{value[:limit]}..."
