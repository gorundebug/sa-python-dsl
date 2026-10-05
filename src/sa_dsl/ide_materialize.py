"""Materialize the evaluated graph as reviewable Python DSL without changing authoring."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from .execution import execute_project
from .generation import _workspace_path
from .manifest import ProjectManifest
from .migration import import_yaml_project


MARKER = Path('.service-architect/materialized.json')


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def materialize_project(manifest: ProjectManifest, output: str = 'python-dsl') -> dict[str, Any]:
    """Export -> import, then update only files owned by the prior materialization."""
    try:
        target = _workspace_path(manifest.workspace, output)
        if target == manifest.workspace.resolve():
            raise ValueError('materialized DSL must use a separate directory')
        exported = execute_project(manifest, 'export')
        if not exported.succeeded or exported.rendered_yaml is None:
            detail = exported.diagnostics[0].get('message') if exported.diagnostics else 'Cannot export Python graph'
            raise ValueError(str(detail))
        with tempfile.TemporaryDirectory(prefix='.sa-materialize-', dir=manifest.workspace) as temporary:
            staging = Path(temporary)
            source = staging / 'canonical.yaml'
            source.write_text(exported.rendered_yaml, encoding='utf-8')
            generated = staging / 'model'
            result = import_yaml_project(
                manifest.workspace,
                str(source.relative_to(manifest.workspace)),
                str(generated.relative_to(manifest.workspace)),
            )
            if not result.succeeded:
                detail = result.diagnostics[0].get('message') if result.diagnostics else 'Cannot import canonical YAML'
                raise ValueError(str(detail))
            generated_manifest = yaml.safe_load((generated / '.service-architect/project.yaml').read_text(encoding='utf-8'))
            generated_manifest['authoring']['entrypoint'] = 'model.main:project'
            incoming = {
                f'model/{file.relative_to(generated).as_posix()}': file.read_bytes()
                for file in generated.rglob('*') if file.is_file()
                and file.relative_to(generated).as_posix() != '.service-architect/project.yaml'
            }
            incoming['.service-architect/project.yaml'] = yaml.safe_dump(
                generated_manifest, sort_keys=False).encode('utf-8')
            marker = target / MARKER
            if marker.is_symlink() or marker.parent.is_symlink():
                raise ValueError('materialized DSL metadata must not be a symlink')
            if target.exists() and any(target.iterdir()) and not marker.is_file():
                raise ValueError('destination is not a materialized DSL directory; choose an empty directory')
            previous: dict[str, str] = {}
            if marker.is_file():
                metadata = json.loads(marker.read_text(encoding='utf-8'))
                if metadata.get('schemaVersion') != '1.0' or metadata.get('sourceProject') != manifest.name:
                    raise ValueError('materialized DSL belongs to another project')
                previous = metadata.get('files') or {}
                if not isinstance(previous, dict):
                    raise ValueError('materialized DSL manifest is invalid')
            # Preflight every destination before writing anything. User edits are never discarded.
            for name in set(previous) | set(incoming):
                relative = Path(name)
                if relative.is_absolute() or '..' in relative.parts or name == MARKER.as_posix():
                    raise ValueError('materialized DSL manifest contains an unsafe path')
                file = target / relative
                if file.is_symlink() or any(parent.is_symlink() for parent in file.parents if parent != target):
                    raise ValueError(f'materialized DSL contains a symlink: {name}')
                if file.exists():
                    if not file.is_file() or name not in previous or _digest(file.read_bytes()) != previous[name]:
                        raise ValueError(f'materialized DSL has user changes: {name}')
            target.mkdir(parents=True, exist_ok=True)
            for name, content in incoming.items():
                destination = target / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary_file = destination.with_name(f'.{destination.name}.tmp')
                temporary_file.write_bytes(content)
                os.replace(temporary_file, destination)
            for name in set(previous) - set(incoming):
                (target / name).unlink()
            marker.parent.mkdir(parents=True, exist_ok=True)
            metadata = {
                'schemaVersion': '1.0', 'sourceProject': manifest.name,
                'canonicalRevision': _digest(exported.rendered_yaml.encode('utf-8')),
                'files': {name: _digest(content) for name, content in sorted(incoming.items())},
            }
            temporary_marker = marker.with_name(f'.{marker.name}.tmp')
            temporary_marker.write_text(json.dumps(metadata, indent=2, sort_keys=True) + '\n', encoding='utf-8')
            os.replace(temporary_marker, marker)
        return {'status': 'success', 'directory': str(target),
                'canonicalRevision': metadata['canonicalRevision'], 'files': len(incoming)}
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {'status': 'failed', 'message': str(error)}
