from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable

import yaml

from .code_generation import CodeGenerationError, GeneratedProjectArchive, ServiceArchitectClient
from .execution import execute_project
from .manifest import ProjectManifest
from .semantic_diff import document_revision


PREVIEW_TTL_SECONDS = 15 * 60
MERGE_TIMEOUT_SECONDS = 5 * 60
MAX_ARCHIVE_FILES = 100_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
_PREVIEW_ID = re.compile(r"^[A-Za-z0-9_-]{20,128}$")
_IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "dist-test",
        "node_modules",
        "target",
        "tmp",
    }
)


class GenerationTransactionError(ValueError):
    def __init__(self, code: str, message: str, path: str = "$.generation") -> None:
        super().__init__(message)
        self.code = code
        self.path = path


class _CanonicalProject:
    def __init__(self, source: str) -> None:
        self._source = source

    def to_yaml(self) -> str:
        return self._source


def preview_generation_transaction(
    manifest: ProjectManifest,
    *,
    env_file: str = ".env",
    remove_stale: bool = False,
    client_factory: Callable[[Path], ServiceArchitectClient] = ServiceArchitectClient.from_env,
    now: Callable[[], float] = time.time,
) -> dict[str, Any]:
    exported = execute_project(manifest, "export")
    if not exported.succeeded:
        return _execution_payload("preview-generation", exported.to_payload())
    if exported.rendered_yaml is None:
        return _failure(
            manifest,
            "preview-generation",
            GenerationTransactionError(
                "SA_EXECUTION_PROTOCOL_ERROR",
                "Python authoring succeeded without returning canonical YAML",
                "$.authoring.entrypoint",
            ),
        )

    try:
        environment_path = _workspace_path(manifest.workspace, env_file)
        archive = client_factory(environment_path).generate_code(
            _CanonicalProject(exported.rendered_yaml)
        )
        workspace_revision = _workspace_revision(manifest.workspace)
        canonical_document = yaml.safe_load(exported.rendered_yaml)
        if not isinstance(canonical_document, dict):
            raise GenerationTransactionError(
                "SA_CANONICAL_INVALID", "canonical YAML must contain an object"
            )
        canonical_revision = document_revision(canonical_document)
        archive_revision = _bytes_revision(archive.content)
        created_at = int(now())
        preview_id = _new_preview_id()

        with tempfile.TemporaryDirectory(prefix="sa-generation-preview-") as temporary:
            staging = Path(temporary)
            archive_path = staging / "generated-project.zip"
            archive_path.write_bytes(archive.content)
            incoming = staging / "incoming"
            merge_script = _extract_merge_script(archive_path, incoming)
            report_path = staging / "merge-report.json"
            report = _run_merge(
                merge_script,
                archive_path,
                manifest.workspace,
                report_path,
                dry_run=True,
                remove_stale=remove_stale,
            )
            if _workspace_revision(manifest.workspace) != workspace_revision:
                raise GenerationTransactionError(
                    "SA_PREVIEW_MUTATED_WORKSPACE",
                    "merge preview changed the workspace; inspect local merge hooks",
                )

            metadata: dict[str, Any] = {
                "schemaVersion": "1.0",
                "previewId": preview_id,
                "project": manifest.name,
                "createdAt": created_at,
                "expiresAt": created_at + PREVIEW_TTL_SECONDS,
                "canonicalRevision": canonical_revision,
                "workspaceRevision": workspace_revision,
                "archiveRevision": archive_revision,
                "archiveFilename": archive.filename,
                "removeStale": remove_stale,
            }
            metadata["previewRevision"] = _json_revision(metadata)
            preview_directory = _preview_directory(manifest.workspace, preview_id)
            preview_directory.mkdir(parents=True, exist_ok=False)
            _atomic_write(preview_directory / "archive.zip", archive.content)
            _atomic_write(
                preview_directory / "metadata.json",
                _json_bytes(metadata),
            )
            _atomic_write(preview_directory / "report.json", _json_bytes(report))
    except (CodeGenerationError, GenerationTransactionError, OSError, ValueError) as error:
        transaction_error = error if isinstance(error, GenerationTransactionError) else GenerationTransactionError(
            "SA_GENERATION_PREVIEW_FAILED", str(error)
        )
        return _failure(manifest, "preview-generation", transaction_error)

    return {
        "schemaVersion": "1.0",
        "operation": "preview-generation",
        "status": "success",
        "project": {"name": manifest.name},
        "preview": {**metadata, "merge": report},
        "diagnostics": [],
    }


def apply_generation_transaction(
    manifest: ProjectManifest,
    *,
    preview_id: str,
    preview_revision: str,
    now: Callable[[], float] = time.time,
) -> dict[str, Any]:
    try:
        directory = _preview_directory(manifest.workspace, preview_id)
        metadata = _read_json(directory / "metadata.json")
        if metadata.get("previewId") != preview_id:
            raise GenerationTransactionError(
                "SA_PREVIEW_INVALID", "preview metadata does not match its identifier"
            )
        if metadata.get("previewRevision") != preview_revision:
            raise GenerationTransactionError(
                "SA_STALE_PREVIEW",
                "preview revision does not match; request a fresh generation preview",
                "$.preview_revision",
            )
        unsigned = dict(metadata)
        stored_revision = unsigned.pop("previewRevision", None)
        if stored_revision != _json_revision(unsigned):
            raise GenerationTransactionError(
                "SA_PREVIEW_INVALID", "preview metadata integrity check failed"
            )
        if (directory / "applied.json").exists():
            raise GenerationTransactionError(
                "SA_PREVIEW_ALREADY_APPLIED", "generation preview was already applied"
            )
        if int(metadata.get("expiresAt", 0)) <= int(now()):
            raise GenerationTransactionError(
                "SA_PREVIEW_EXPIRED", "generation preview expired; request a new preview"
            )
        if metadata.get("project") != manifest.name:
            raise GenerationTransactionError(
                "SA_PREVIEW_INVALID", "generation preview belongs to another project"
            )
        current_workspace_revision = _workspace_revision(manifest.workspace)
        if current_workspace_revision != metadata.get("workspaceRevision"):
            raise GenerationTransactionError(
                "SA_STALE_WORKSPACE",
                "workspace changed after preview; request a fresh generation preview",
            )
        archive_path = directory / "archive.zip"
        if _file_revision(archive_path) != metadata.get("archiveRevision"):
            raise GenerationTransactionError(
                "SA_PREVIEW_INVALID", "preview archive integrity check failed"
            )

        with tempfile.TemporaryDirectory(prefix="sa-generation-apply-") as temporary:
            staging = Path(temporary)
            merge_script = _extract_merge_script(archive_path, staging / "incoming")
            report = _run_merge(
                merge_script,
                archive_path,
                manifest.workspace,
                staging / "merge-report.json",
                dry_run=False,
                remove_stale=bool(metadata.get("removeStale")),
            )
        applied = {
            "schemaVersion": "1.0",
            "previewId": preview_id,
            "previewRevision": preview_revision,
            "appliedAt": int(now()),
            "workspaceRevision": _workspace_revision(manifest.workspace),
            "merge": report,
        }
        _atomic_write(directory / "applied.json", _json_bytes(applied))
    except (GenerationTransactionError, OSError, ValueError) as error:
        transaction_error = error if isinstance(error, GenerationTransactionError) else GenerationTransactionError(
            "SA_GENERATION_APPLY_FAILED", str(error)
        )
        return _failure(manifest, "apply-generation", transaction_error)

    return {
        "schemaVersion": "1.0",
        "operation": "apply-generation",
        "status": "success",
        "project": {"name": manifest.name},
        "application": applied,
        "diagnostics": [],
    }


def _extract_merge_script(archive_path: Path, destination: Path) -> Path:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_FILES:
                raise GenerationTransactionError(
                    "SA_ARCHIVE_LIMIT_EXCEEDED", "generated archive contains too many files"
                )
            if sum(member.file_size for member in members) > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise GenerationTransactionError(
                    "SA_ARCHIVE_LIMIT_EXCEEDED", "generated archive is too large when extracted"
                )
            for member in members:
                path = PurePosixPath(member.filename)
                mode = member.external_attr >> 16
                if (
                    not member.filename
                    or path.is_absolute()
                    or ".." in path.parts
                    or "\\" in member.filename
                    or stat.S_ISLNK(mode)
                ):
                    raise GenerationTransactionError(
                        "SA_ARCHIVE_INVALID_PATH",
                        f"generated archive contains unsafe path: {member.filename!r}",
                    )
            archive.extractall(destination)
            for member in members:
                mode = (member.external_attr >> 16) & 0o777
                extracted = destination.joinpath(*PurePosixPath(member.filename).parts)
                if mode and extracted.is_file():
                    extracted.chmod(mode)
    except zipfile.BadZipFile as error:
        raise GenerationTransactionError(
            "SA_ARCHIVE_INVALID", "generated artifact is not a valid ZIP archive"
        ) from error
    scripts = sorted(destination.glob("*/scripts/merge.generated.sh"))
    if not scripts:
        scripts = sorted(destination.glob("scripts/merge.generated.sh"))
    if len(scripts) != 1:
        raise GenerationTransactionError(
            "SA_MERGE_CONTRACT_UNSUPPORTED",
            "generated archive must contain exactly one scripts/merge.generated.sh",
        )
    return scripts[0]


def _run_merge(
    merge_script: Path,
    archive_path: Path,
    workspace: Path,
    report_path: Path,
    *,
    dry_run: bool,
    remove_stale: bool,
) -> dict[str, Any]:
    command = ["bash", str(merge_script)]
    if dry_run:
        command.append("--dry-run")
    if remove_stale:
        command.append("--remove-stale")
    command.extend(["--report-json", str(report_path), str(archive_path)])
    environment = {
        key: os.environ[key]
        for key in ("HOME", "LANG", "LC_ALL", "PATH", "TMPDIR")
        if key in os.environ
    }
    environment["SERVICEGEN_PROJECT_DIR_OVERRIDE"] = str(workspace.resolve())
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            env=environment,
            capture_output=True,
            text=True,
            timeout=MERGE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise GenerationTransactionError(
            "SA_MERGE_TIMEOUT", "ServiceGen merge operation timed out"
        ) from error
    if not report_path.is_file():
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise GenerationTransactionError(
            "SA_MERGE_CONTRACT_UNSUPPORTED",
            "ServiceGen merge did not produce its JSON report"
            + (f": {_bounded(detail)}" if detail else ""),
        )
    report = _read_json(report_path)
    expected_operation = "merge-preview" if dry_run else "merge-apply"
    if (
        report.get("schemaVersion") != "1.0"
        or report.get("operation") != expected_operation
        or report.get("status") not in {"success", "failed"}
        or not isinstance(report.get("summary"), dict)
        or not isinstance(report.get("files"), list)
    ):
        raise GenerationTransactionError(
            "SA_MERGE_PROTOCOL_ERROR", "ServiceGen merge returned an invalid JSON report"
        )
    if completed.returncode != 0 or report["status"] != "success":
        raise GenerationTransactionError(
            "SA_MERGE_FAILED",
            f"ServiceGen merge failed with exit code {completed.returncode}",
        )
    return report


def _workspace_revision(workspace: Path) -> str:
    digest = hashlib.sha256()
    root = workspace.resolve()
    for current, directories, files in os.walk(root, followlinks=False):
        relative_directory = Path(current).relative_to(root)
        directories[:] = sorted(
            directory
            for directory in directories
            if directory not in _IGNORED_DIRECTORIES
            and not (
                relative_directory == Path(".service-architect")
                and directory == "previews"
            )
        )
        for filename in sorted(files):
            relative = relative_directory / filename
            if relative == Path(".servicegen/merge.log"):
                continue
            if relative == Path(".service-architect/audit.jsonl"):
                continue
            path = root / relative
            digest.update(relative.as_posix().encode("utf-8") + b"\0")
            if path.is_symlink():
                digest.update(b"L\0" + os.readlink(path).encode("utf-8") + b"\0")
            else:
                digest.update(b"F\0")
                with path.open("rb") as source:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(block)
                digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _preview_directory(workspace: Path, preview_id: str) -> Path:
    if not _PREVIEW_ID.fullmatch(preview_id):
        raise GenerationTransactionError(
            "SA_PREVIEW_INVALID", "preview ID has an invalid format", "$.preview_id"
        )
    root = (workspace / ".service-architect" / "previews").resolve()
    directory = (root / preview_id).resolve(strict=False)
    if directory.parent != root:
        raise GenerationTransactionError(
            "SA_PREVIEW_INVALID", "preview ID resolves outside preview storage"
        )
    return directory


def _workspace_path(workspace: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts or "\\" in relative_path:
        raise GenerationTransactionError(
            "SA_WORKSPACE_BOUNDARY_VIOLATION",
            "path must be relative to the project workspace",
        )
    root = workspace.resolve()
    destination = (root / candidate).resolve(strict=False)
    if destination != root and root not in destination.parents:
        raise GenerationTransactionError(
            "SA_WORKSPACE_BOUNDARY_VIOLATION", "path resolves outside the project workspace"
        )
    return destination


def _new_preview_id() -> str:
    import secrets

    return secrets.token_urlsafe(24)


def _file_revision(path: Path) -> str:
    return _bytes_revision(path.read_bytes())


def _bytes_revision(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _json_revision(value: dict[str, Any]) -> str:
    return _bytes_revision(_json_bytes(value))


def _json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GenerationTransactionError(
            "SA_MERGE_PROTOCOL_ERROR", f"JSON document must be an object: {path.name}"
        )
    return value


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_bytes(content)
    temporary.replace(path)


def _execution_payload(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["operation"] = operation
    return result


def _failure(
    manifest: ProjectManifest,
    operation: str,
    error: GenerationTransactionError,
) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "operation": operation,
        "status": "failed",
        "project": {"name": manifest.name},
        "diagnostics": [
            {
                "code": error.code,
                "severity": "error",
                "path": error.path,
                "message": str(error),
            }
        ],
    }


def _bounded(value: str, limit: int = 1000) -> str:
    return value if len(value) <= limit else f"{value[:limit]}..."
