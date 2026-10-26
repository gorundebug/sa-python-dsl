from __future__ import annotations

import importlib
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path, PurePosixPath
from typing import Mapping

from .model import Project
from .source_locations import capture_source_locations


def python_files_to_yaml(files: Mapping[str, str], entrypoint: str) -> str:
    """Execute a generated Python workspace and return its canonical YAML."""
    return _evaluate(files, entrypoint, False)["yaml"]


def python_files_to_snapshot(files: Mapping[str, str], entrypoint: str) -> dict:
    """Browser navigation metadata from evaluated objects; never added to YAML."""
    return _evaluate(files, entrypoint, True)


def _evaluate(files: Mapping[str, str], entrypoint: str, capture: bool) -> dict:
    module_name, separator, attribute_name = entrypoint.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError("Entrypoint must use module.path:attribute syntax")
    if not files:
        raise ValueError("Python project must contain at least one file")

    normalized: dict[PurePosixPath, str] = {}
    package_names: set[str] = set()
    for filename, content in files.items():
        path = PurePosixPath(filename)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ValueError(f"Python project path {filename!r} must be relative")
        if path.suffix != ".py":
            raise ValueError(f"Python project file {filename!r} must end in .py")
        if not isinstance(content, str):
            raise TypeError(f"Python project file {filename!r} must contain text")
        normalized[path] = content
        package_names.add(path.parts[0])

    with tempfile.TemporaryDirectory(prefix="sa-dsl-browser-") as temporary:
        workspace = Path(temporary)
        for relative, content in normalized.items():
            destination = workspace.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")

        sys.path.insert(0, str(workspace))
        importlib.invalidate_caches()
        try:
            with (capture_source_locations(workspace) if capture else nullcontext()) as locations:
                module = importlib.import_module(module_name)
                project = getattr(module, attribute_name)
                if callable(project) and not isinstance(project, Project):
                    project = project()
            if not isinstance(project, Project):
                raise TypeError(f"{entrypoint} must reference a Project")
            result = {"yaml": project.to_yaml()}
            if locations is not None:
                result["sourceLocations"] = locations.document(project)
            return result
        finally:
            sys.path.pop(0)
            for loaded_name in list(sys.modules):
                if any(
                    loaded_name == package
                    or loaded_name.startswith(f"{package}.")
                    for package in package_names
                ):
                    del sys.modules[loaded_name]
            importlib.invalidate_caches()
