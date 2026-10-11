"""IDE command: generate with the existing archive and merge contracts."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from .generation import generate_project_archive
from .generation_transaction import _extract_merge_script, _run_merge
from .manifest import ProjectManifest
from .generation_progress import ProgressCallback, report_progress
from .generation_workspace import generation_directory, protect_authoring


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
        destination = generation_directory(manifest, output_dir=output_dir)
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
            protect_authoring(manifest, destination, script.parent.parent, result.source_files, env_file)
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
