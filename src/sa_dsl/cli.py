from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path
from typing import Any

from .model import Project
from .importer import yaml_to_python_project


def _load_project(path: Path) -> Project:
    namespace: dict[str, Any] = runpy.run_path(str(path))
    candidate = namespace.get("project")
    if candidate is None and callable(namespace.get("build")):
        candidate = namespace["build"]()
    if not isinstance(candidate, Project):
        raise TypeError(
            f"{path} must expose a Project as `project` or return one from `build()`"
        )
    return candidate


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sa-dsl",
        description="Build Service Architect YAML from a typed Python graph.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Validate a Python graph and emit YAML")
    build.add_argument("source", type=Path, help="Python graph file")
    build.add_argument(
        "--output", "-o", default="-", help="Output YAML path, or - for stdout"
    )

    check = subparsers.add_parser(
        "check", help="Validate a Python graph without writing YAML"
    )
    check.add_argument("source", type=Path, help="Python graph file")
    check.add_argument("--json", action="store_true", help="Print diagnostics as JSON")

    import_yaml = subparsers.add_parser(
        "import", help="Convert Service Architect YAML into a typed Python project"
    )
    import_yaml.add_argument("source", type=Path, help="Service Architect YAML file")
    import_yaml.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output Python package directory",
    )

    args = parser.parse_args()
    if args.command == "import":
        entrypoint = yaml_to_python_project(args.source, args.output)
        print(entrypoint)
        return
    project = _load_project(args.source)
    diagnostics = project.validate()
    if diagnostics:
        if getattr(args, "json", False):
            print(json.dumps([value.to_dict() for value in diagnostics], indent=2))
        else:
            for diagnostic in diagnostics:
                print(diagnostic, file=sys.stderr)
        raise SystemExit(1)
    if args.command == "check":
        print(f"Valid Service Architect project: {project.name}")
        return
    rendered = project.to_yaml()
    if args.output == "-":
        sys.stdout.write(rendered)
    else:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
