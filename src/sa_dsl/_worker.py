from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

from .model import Project


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--operation", choices=("validate", "export"), required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--entrypoint", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()

    payload: dict[str, Any]
    exit_code = 0
    try:
        project = _load_entrypoint(args.workspace, args.entrypoint)
        if project.name != args.project_name:
            raise ValueError(
                "manifest project name does not match the Python Project name: "
                f"{args.project_name!r} != {project.name!r}"
            )
        diagnostics = [diagnostic.to_dict() for diagnostic in project.validate()]
        payload = {
            "status": "failed" if diagnostics else "success",
            "diagnostics": diagnostics,
        }
        if not diagnostics and args.operation == "export":
            payload["yaml"] = project.to_yaml()
        if diagnostics:
            exit_code = 1
    except Exception as error:
        payload = {
            "status": "failed",
            "diagnostics": [
                {
                    "code": "SA_AUTHORING_EXCEPTION",
                    "severity": "error",
                    "path": "$.authoring.entrypoint",
                    "message": f"{type(error).__name__}: {error}",
                }
            ],
        }
        exit_code = 1

    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(payload), encoding="utf-8")
    raise SystemExit(exit_code)


def _load_entrypoint(workspace: Path, entrypoint: str) -> Project:
    module_name, attribute_name = entrypoint.split(":", 1)
    sys.path.insert(0, str(workspace.resolve()))
    module = importlib.import_module(module_name)
    candidate = getattr(module, attribute_name)
    if callable(candidate) and not isinstance(candidate, Project):
        candidate = candidate()
    if not isinstance(candidate, Project):
        raise TypeError(
            f"{entrypoint} must reference a Project or a callable returning Project"
        )
    return candidate


if __name__ == "__main__":
    main()
