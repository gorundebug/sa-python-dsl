"""Create a separate architecture project beside generated workspace code."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

import yaml

from .manifest import MANIFEST_RELATIVE_PATH, SUPPORTED_GENERATION_TARGETS
from .migration import import_yaml_project


def initialize_project(
    workspace: Path, *, name: str | None = None, source_yaml: Path | None = None,
) -> dict[str, Any]:
    created: list[Path] = []
    created_metadata = False
    created_root = False
    root: Path | None = None
    metadata: Path | None = None
    try:
        workspace = workspace.expanduser().resolve()
        if not workspace.is_dir():
            raise ValueError('Open an existing workspace folder before creating a project')
        if not workspace.name:
            raise ValueError('Choose a named workspace folder, not the filesystem root')
        root = workspace / f'{workspace.name}-architecture'
        if root.exists() or root.is_symlink():
            raise ValueError(f'Cannot create project: {root.name} already exists; no files were changed')
        project_name = workspace.name if name is None else name.strip()
        if not project_name or '\x00' in project_name or '\n' in project_name or '\r' in project_name:
            raise ValueError('Project name must be a non-empty single line')
        manifest = root / MANIFEST_RELATIVE_PATH
        metadata = manifest.parent
        source = root / 'project.py'
        if metadata.is_symlink() or (metadata.exists() and not metadata.is_dir()):
            raise ValueError('.service-architect must be a regular directory')
        for path in (manifest, source, root / 'project'):
            if path.exists() or path.is_symlink():
                raise ValueError(f'Cannot create project: {path.relative_to(root)} already exists; no files were changed')
        entrypoint = 'project:project'
        source_name = 'project.py'
        targets = tuple(sorted(SUPPORTED_GENERATION_TARGETS))
        sources = {'project.py': ('from sa_dsl import Project\n\n\n'
                                 + f'project = Project(name={project_name!r})\n').encode('utf-8')}
        if source_yaml is not None:
            source_yaml = source_yaml.expanduser()
            if not source_yaml.is_absolute():
                source_yaml = workspace / source_yaml
            sources, entrypoint, targets = _import_sources(source_yaml, project_name)
            source_name = entrypoint.split(':', 1)[0].replace('.', '/') + '.py'
        document = {
            'version': 1,
            'project': {'name': project_name},
            'authoring': {'mode': 'python', 'entrypoint': entrypoint},
            'canonical': {'output': f'.service-architect/build/{workspace.name}.yaml'},
            # Empty projects allow all targets; imports retain their service targets.
            'generation': {
                'targets': list(targets),
                'outputDirectory': '..',
            },
        }
        files = dict(sources)
        files['.env'] = (
            '# Service Architect remote code generation credentials. Do not commit this file.\n'
            '# Set your Service Architect API key below, then run Generate and merge.\n'
            '# Importing YAML and viewing the graph do not require a key.\n'
            '# The API URL is configured by default; no AWS credentials are needed.\n'
            'SERVICE_ARCHITECT_API_KEY=\n'
        ).encode('utf-8')
        files[MANIFEST_RELATIVE_PATH.as_posix()] = yaml.safe_dump(
            document, sort_keys=False, allow_unicode=True).encode('utf-8')
        files['.gitignore'] = ('.venv/\n__pycache__/\n*.py[cod]\n.env\n.env.*\n!.env.example\n'
                              '.service-architect/build/\n.sa-ide-generation-*/\n').encode('utf-8')
        root.mkdir()
        created_root = True
        if not metadata.exists():
            metadata.mkdir()
            created_metadata = True
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation protects files that appeared after the preflight.
            with path.open('xb') as stream:
                created.append(path)
                stream.write(content)
        return {
            'status': 'success', 'operation': 'init', 'name': project_name,
            'directory': str(root), 'source': source_name,
            'manifest': MANIFEST_RELATIVE_PATH.as_posix(),
            'generationDirectory': str(workspace),
        }
    except (OSError, ValueError, yaml.YAMLError) as error:
        cleanup_errors = []
        for path in reversed(created):
            try:
                path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                cleanup_errors.append(str(cleanup_error))
        if created_metadata and metadata is not None:
            try:
                metadata.rmdir()
            except OSError:
                pass  # Never remove unrelated files added to the directory.
        if created_root and root is not None:
            for directory in sorted((path for path in root.rglob('*') if path.is_dir()),
                                    key=lambda path: len(path.parts), reverse=True):
                try:
                    directory.rmdir()
                except OSError:
                    pass
            try:
                root.rmdir()
            except OSError:
                pass
        detail = str(error)
        if cleanup_errors:
            detail += '; cleanup incomplete: ' + '; '.join(cleanup_errors)
        return {'status': 'failed', 'operation': 'init', 'message': detail}


def _import_sources(source: Path, name: str) -> tuple[dict[str, bytes], str, tuple[str, ...]]:
    document = yaml.safe_load(source.read_text(encoding='utf-8'))
    if not isinstance(document, dict):
        raise ValueError('Select an architecture YAML containing settings and services, not a project manifest')
    settings = document.get('settings') or {}
    if not isinstance(settings, dict):
        raise ValueError('Architecture YAML settings must be an object')
    # Apply the name chosen in the same creation dialog; never edit the input file.
    document['settings'] = {**settings, 'name': name}
    with tempfile.TemporaryDirectory(prefix='sa-init-import-') as temporary:
        staging = Path(temporary)
        (staging / 'architecture.yaml').write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding='utf-8')
        result = import_yaml_project(staging, 'architecture.yaml', 'model')
        if not result.succeeded or result.entrypoint is None:
            message = result.diagnostics[0].get('message') if result.diagnostics else 'Cannot import architecture YAML'
            raise ValueError(str(message))
        generated = staging / 'model'
        files = {
            (Path('model') / path.relative_to(generated)).as_posix(): path.read_bytes()
            for path in generated.rglob('*')
            if path.is_file() and path.relative_to(generated) != MANIFEST_RELATIVE_PATH
        }
        # Generated imports refer to the package by name. Keep that package
        # directory when relocating it from staging into the architecture root.
        return files, f'model.{result.entrypoint}', result.targets
