"""IDE command: generate with the existing archive and merge contracts."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from .generation import generate_project_archive
from .generation_transaction import _extract_merge_script, _run_merge
from .manifest import ProjectManifest
from .generation_progress import ProgressCallback, report_progress


def generate_and_merge(
    manifest: ProjectManifest,
    *,
    output_dir: str | None = None,
    env_file: str = '.env',
    cpp_graph: str | None = None,
    cpp_io_backend: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Use ServiceGen's own merge script against the explicitly chosen output directory."""
    try:
        destination = Path(output_dir if output_dir is not None else manifest.generation.output_directory).expanduser()
        if not destination.is_absolute():
            destination = manifest.workspace / destination
        destination = destination.resolve()
        if destination in manifest.workspace.resolve().parents and destination != manifest.workspace.resolve().parent:
            raise ValueError('generated project may target the immediate workspace parent, but not higher ancestors')
        with tempfile.TemporaryDirectory(prefix='.sa-ide-generation-', dir=manifest.workspace) as temporary:
            staging = Path(temporary)
            archive_path = staging / 'generated-project.zip'
            result = generate_project_archive(
                manifest,
                output=str(archive_path.relative_to(manifest.workspace)),
                env_file=env_file,
                cpp_graph=cpp_graph,
                cpp_io_backend=cpp_io_backend,
                on_progress=on_progress,
                job_timeout=30 * 60,
            )
            if not result.succeeded:
                detail = result.diagnostics[0].get('message') if result.diagnostics else 'Code generation failed'
                raise ValueError(str(detail))
            report_progress(on_progress, 'PREPARING', 'Preparing the archive and protecting authoring files')
            script = _extract_merge_script(archive_path, staging / 'incoming')
            _protect_authoring(manifest, destination, script.parent.parent, result.source_files, env_file)
            destination.mkdir(parents=True, exist_ok=True)
            report_progress(on_progress, 'MERGE_PREVIEW', 'Checking the merge before applying changes')
            _run_merge(script, archive_path, destination, staging / 'preview.json',
                       dry_run=True, remove_stale=False)
            report_progress(on_progress, 'MERGING', 'Applying generated files; preserving user-owned code')
            report = _run_merge(script, archive_path, destination, staging / 'applied.json',
                                dry_run=False, remove_stale=False)
        report_progress(on_progress, 'COMPLETED', 'Project generation and merge completed')
        return {'status': 'success', 'directory': str(destination), 'merge': report}
    except (OSError, ValueError) as error:
        report_progress(on_progress, 'FAILED', 'Generation or merge failed')
        return {'status': 'failed', 'message': str(error)}


def _protect_authoring(
    manifest: ProjectManifest, destination: Path, incoming: Path,
    source_files: tuple[str, ...], env_file: str,
) -> None:
    workspace = manifest.workspace.resolve()
    protected_files = {(workspace / name).resolve() for name in source_files}
    protected_files.add(manifest.manifest_path.resolve())
    protected_files.add((workspace / env_file).resolve())
    protected_files.add((workspace / '.gitignore').resolve())
    protected_directories = [(workspace / name).resolve() for name in
                             ('.service-architect', '.git', '.venv', '.idea', '.vscode')]
    if destination != workspace and workspace.is_relative_to(destination):
        protected_directories.append(workspace)
    # Check incoming paths, not all files in the workspace. A collision is an
    # error, never an implicit rename or a partial merge into the DSL sources.
    for source in incoming.rglob('*'):
        if not source.is_file():
            continue
        relative = source.relative_to(incoming)
        target = (destination / relative).resolve()
        if not target.is_relative_to(destination):
            raise ValueError(f'generated path escapes its destination: {relative}')
        if target in protected_files or any(target.is_relative_to(folder) for folder in protected_directories):
            raise ValueError(f'generated file conflicts with Python authoring or project settings: {relative}')
