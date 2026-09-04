from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path
from typing import Any

from .execution import execute_project, write_canonical_yaml
from .generation import generate_project_archive
from .manifest import ManifestError, load_manifest
from .migration import import_yaml_project
from .model import Project


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

    inspect = subparsers.add_parser(
        "inspect", help="Read project metadata without executing authoring code"
    )
    inspect.add_argument(
        "--project",
        type=Path,
        default=Path("."),
        help="Project directory or project.yaml path",
    )
    inspect.add_argument(
        "--format",
        choices=("human", "json"),
        default="human",
        help="Output format",
    )

    validate = subparsers.add_parser(
        "validate", help="Execute and validate the manifest Python entrypoint"
    )
    validate.add_argument("--project", type=Path, default=Path("."))
    validate.add_argument(
        "--format", choices=("human", "json"), default="human"
    )

    export = subparsers.add_parser(
        "export", help="Validate Python authoring and write canonical YAML"
    )
    export.add_argument("--project", type=Path, default=Path("."))
    export.add_argument(
        "--output",
        "-o",
        help="Workspace-relative output path; defaults to canonical.output",
    )
    export.add_argument("--format", choices=("human", "json"), default="human")

    generate = subparsers.add_parser(
        "generate", help="Request and save a generated project ZIP"
    )
    generate.add_argument("--project", type=Path, default=Path("."))
    generate.add_argument(
        "--output",
        "-o",
        help="Workspace-relative ZIP path; defaults to dist/<server filename>",
    )
    generate.add_argument(
        "--env-file",
        default=".env",
        help="Workspace-relative credentials file",
    )
    generate.add_argument("--format", choices=("human", "json"), default="human")

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
    import_yaml.add_argument(
        "--format", choices=("human", "json"), default="human"
    )

    args = parser.parse_args()
    if args.command == "inspect":
        try:
            manifest = load_manifest(args.project)
        except ManifestError as error:
            if args.format == "json":
                print(
                    json.dumps(
                        {
                            "schemaVersion": "1.0",
                            "operation": "inspect",
                            "status": "failed",
                            "diagnostics": [error.to_diagnostic()],
                        },
                        indent=2,
                    )
                )
            else:
                print(f"Invalid Service Architect project: {error}", file=sys.stderr)
                print(f"Location: {error.path}", file=sys.stderr)
            raise SystemExit(2)

        if args.format == "json":
            print(json.dumps(manifest.inspect_payload(), indent=2))
        else:
            print(f"Service Architect project: {manifest.name}")
            print(f"Authoring mode: {manifest.authoring.mode}")
            if manifest.authoring.entrypoint is not None:
                print(f"Entrypoint: {manifest.authoring.entrypoint}")
            if manifest.authoring.source is not None:
                print(f"YAML source: {manifest.authoring.source}")
            print(f"Canonical YAML: {manifest.canonical.output}")
            print(f"Generation targets: {', '.join(manifest.generation.targets)}")
        return

    if args.command in {"validate", "export"}:
        try:
            manifest = load_manifest(args.project)
        except ManifestError as error:
            _print_operation_failure(args.command, error, args.format)
            raise SystemExit(2)

        result = execute_project(manifest, args.command)
        output_path = None
        if result.succeeded and args.command == "export":
            if result.rendered_yaml is None:
                _print_protocol_failure(args.command, args.format)
                raise SystemExit(2)
            try:
                output_path = write_canonical_yaml(
                    manifest, result.rendered_yaml, args.output
                )
            except (OSError, ValueError) as error:
                _print_write_failure(args.command, str(error), args.format)
                raise SystemExit(2)

        if args.format == "json":
            print(json.dumps(result.to_payload(output=output_path), indent=2))
        elif result.succeeded:
            if args.command == "validate":
                print(f"Valid Service Architect project: {manifest.name}")
            else:
                print(f"Canonical YAML written to {output_path}")
        else:
            for diagnostic in result.diagnostics:
                print(
                    f"{diagnostic.get('code', 'SA_ERROR')}: "
                    f"{diagnostic.get('message', 'unknown error')}",
                    file=sys.stderr,
                )
        if not result.succeeded:
            raise SystemExit(1)
        return

    if args.command == "generate":
        try:
            manifest = load_manifest(args.project)
        except ManifestError as error:
            _print_operation_failure("generate", error, args.format)
            raise SystemExit(2)
        result = generate_project_archive(
            manifest, output=args.output, env_file=args.env_file
        )
        if args.format == "json":
            print(json.dumps(result.to_payload(), indent=2))
        elif result.succeeded:
            print(f"Generated project archive written to {result.artifact}")
        else:
            for diagnostic in result.diagnostics:
                print(
                    f"{diagnostic.get('code', 'SA_ERROR')}: "
                    f"{diagnostic.get('message', 'unknown error')}",
                    file=sys.stderr,
                )
        if not result.succeeded:
            raise SystemExit(1)
        return

    if args.command == "import":
        result = import_yaml_project(
            Path.cwd(), str(args.source), str(args.output)
        )
        if args.format == "json":
            print(json.dumps(result.to_payload(), indent=2))
        elif result.succeeded:
            print(f"Imported Service Architect project: {result.project_path}")
            print(f"Entrypoint: {result.entrypoint}")
        else:
            for diagnostic in result.diagnostics:
                print(
                    f"{diagnostic.get('code', 'SA_ERROR')}: "
                    f"{diagnostic.get('message', 'unknown error')}",
                    file=sys.stderr,
                )
        if not result.succeeded:
            raise SystemExit(1)
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


def _print_operation_failure(
    operation: str, error: ManifestError, output_format: str
) -> None:
    if output_format == "json":
        print(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "operation": operation,
                    "status": "failed",
                    "diagnostics": [error.to_diagnostic()],
                },
                indent=2,
            )
        )
    else:
        print(f"Invalid Service Architect project: {error}", file=sys.stderr)
        print(f"Location: {error.path}", file=sys.stderr)


def _print_protocol_failure(operation: str, output_format: str) -> None:
    _print_simple_failure(
        operation,
        "SA_EXECUTION_PROTOCOL_ERROR",
        "Python authoring succeeded without returning canonical YAML",
        output_format,
    )


def _print_write_failure(operation: str, message: str, output_format: str) -> None:
    _print_simple_failure(
        operation, "SA_CANONICAL_WRITE_FAILED", message, output_format
    )


def _print_simple_failure(
    operation: str, code: str, message: str, output_format: str
) -> None:
    diagnostic = {
        "code": code,
        "severity": "error",
        "path": "$.canonical.output",
        "message": message,
    }
    if output_format == "json":
        print(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "operation": operation,
                    "status": "failed",
                    "diagnostics": [diagnostic],
                },
                indent=2,
            )
        )
    else:
        print(f"{code}: {message}", file=sys.stderr)


if __name__ == "__main__":
    main()
