"""Shared output-directory and Python-source protection for IDE and MCP merges."""
from __future__ import annotations

from pathlib import Path

from .manifest import ProjectManifest
from .mcp_workspace import WorkspaceBoundaryError


def generation_directory(
    manifest: ProjectManifest,
    *,
    output_dir: str | None = None,
    boundary_root: Path | None = None,
) -> Path:
    """Resolve outputDirectory; an MCP caller must supply its registered root.

    IDE callers can target a workspace containing the authoring project, but
    never a higher ancestor. Resolution alone does not create any directory.
    """
    value = output_dir if output_dir is not None else manifest.generation.output_directory
    if not value.strip() or "\\" in value or "\x00" in value:
        raise WorkspaceBoundaryError("generated project directory is invalid")
    authoring = manifest.workspace.resolve()
    candidate = Path(value).expanduser()
    target = (candidate if candidate.is_absolute() else authoring / candidate).resolve()
    if boundary_root is not None and not target.is_relative_to(boundary_root.resolve()):
        raise WorkspaceBoundaryError("generated project directory escapes the registered MCP workspace")
    if target in authoring.parents and target != authoring.parent:
        raise WorkspaceBoundaryError("generated project may target the immediate workspace parent, but not higher ancestors")
    if target.exists() and not target.is_dir():
        raise WorkspaceBoundaryError("generated project directory must be a directory")
    return target


def protect_authoring(
    manifest: ProjectManifest,
    destination: Path,
    incoming: Path,
    source_files: tuple[str, ...],
    env_file: str,
) -> None:
    """Reject incoming paths that would replace model source or project settings."""
    workspace = manifest.workspace.resolve()
    destination = destination.resolve()
    protected_files = {(workspace / name).resolve() for name in source_files}
    protected_files.add(manifest.manifest_path.resolve())
    protected_files.add((workspace / env_file).resolve())
    protected_files.add((workspace / ".gitignore").resolve())
    protected_directories = [(workspace / name).resolve() for name in
                             (".service-architect", ".git", ".venv", ".idea", ".vscode")]
    if destination != workspace and workspace.is_relative_to(destination):
        protected_directories.append(workspace)
    for source in incoming.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(incoming)
        target = (destination / relative).resolve()
        if not target.is_relative_to(destination):
            raise WorkspaceBoundaryError(f"generated path escapes its destination: {relative}")
        if target in protected_files or any(target.is_relative_to(folder) for folder in protected_directories):
            raise ValueError(f"generated file conflicts with Python authoring or project settings: {relative}")
