"""IDE command: generate with the existing archive and merge contracts."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from .generation import generate_project_archive
from .generation_transaction import _extract_merge_script, _run_merge
from .manifest import ProjectManifest


def generate_and_merge(
    manifest: ProjectManifest,
    *,
    output_dir: str,
    env_file: str = '.env',
    cpp_graph: str | None = None,
    cpp_io_backend: str | None = None,
) -> dict[str, Any]:
    """Use ServiceGen's own merge script against the explicitly chosen output directory."""
    try:
        destination = Path(output_dir).expanduser()
        if not destination.is_absolute():
            destination = manifest.workspace / destination
        destination = destination.resolve()
        if destination == manifest.workspace.resolve() or destination in manifest.workspace.resolve().parents:
            raise ValueError('generated project must not overwrite the Python DSL project')
        with tempfile.TemporaryDirectory(prefix='.sa-ide-generation-', dir=manifest.workspace) as temporary:
            staging = Path(temporary)
            archive_path = staging / 'generated-project.zip'
            result = generate_project_archive(
                manifest,
                output=str(archive_path.relative_to(manifest.workspace)),
                env_file=env_file,
                cpp_graph=cpp_graph,
                cpp_io_backend=cpp_io_backend,
            )
            if not result.succeeded:
                detail = result.diagnostics[0].get('message') if result.diagnostics else 'Code generation failed'
                raise ValueError(str(detail))
            script = _extract_merge_script(archive_path, staging / 'incoming')
            destination.mkdir(parents=True, exist_ok=True)
            _run_merge(script, archive_path, destination, staging / 'preview.json',
                       dry_run=True, remove_stale=False)
            report = _run_merge(script, archive_path, destination, staging / 'applied.json',
                                dry_run=False, remove_stale=False)
        return {'status': 'success', 'directory': str(destination), 'merge': report}
    except (OSError, ValueError) as error:
        return {'status': 'failed', 'message': str(error)}
