"""Optional, read-only code overlay. No relationships are added to the model.

The first implementation uses Go's SSA/VTA analysis, shared by both IDE hosts.
It resolves possible interface callees across makers/helpers, not executions.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any

import yaml

from .designer import make_snapshot
from .execution import execute_project
from .ide_implementations import implementation_targets
from .manifest import ProjectManifest


def _pascal_identifier(name: str) -> str:
    """Default templates title-case words, including acronyms (DSP -> Dsp)."""
    words = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", words)
    return "".join(part[:1].upper() + part[1:].lower()
                   for part in re.split(r"[^\w]+|_", words) if part)


def _directory(root: Path, name: str) -> Path:
    name = re.sub(r"\s", "", name).lower()
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError("Invalid generated owner name")
    result = (root / name).resolve()
    if not result.is_relative_to(root):
        raise ValueError("Generated owner escapes the project directory")
    return result


def analysis_request(document: dict[str, Any], root: Path, service_key: str) -> dict[str, Any]:
    service = document.get("services", {}).get(service_key)
    if not service:
        raise ValueError("Service is not present in the Python model")
    if service.get("programmingLanguage") != "GoLang":
        raise ValueError("SubStream code analysis currently supports Go services only")
    root = root.resolve(strict=True)
    service_dir = _directory(root, service.get("name") or service_key)
    business = []
    owners = {service_dir}
    for key, targets in implementation_targets(document).get(service_key, {}).items():
        for target in targets:
            owner = _directory(root, target["owner"])
            # Shared Go modules may have a language suffix, as in IDE navigation.
            if not owner.is_dir() and target["owner"] != service_key:
                matches = [p.resolve() for p in root.glob(owner.name + "_*")
                           if (p / "go.mod").is_file() and p.resolve().is_relative_to(root)]
                if len(matches) != 1:
                    raise ValueError(f"Cannot uniquely locate Go owner {target['owner']}")
                owner = matches[0]
            location = owner / ("internal" if target["owner"] == service_key else "pkg") / "functions"
            location = (location / target["package"]).resolve()
            if not location.is_relative_to(owner):
                raise ValueError("Function package escapes its owner")
            owners.add(owner)
            symbols = list(dict.fromkeys([*target["symbols"], *map(_pascal_identifier, target["symbols"])]))
            business.append({"key": key, "directory": str(location), "symbols": symbols})
    substreams = []
    for pipeline in service.get("pipelines", {}).values():
        for key, node in pipeline.items():
            if node.get("type") != "SubStream":
                continue
            name = node.get("name") or key
            # The ordinary generated Go accessor uses the public PascalCase name.
            symbol = "".join(word[:1].upper() + word[1:] for word in re.split(r"[^\w]+|_", name) if word)
            substreams.append({"key": key, "symbols": list(dict.fromkeys([
                symbol, key[:1].upper() + key[1:], _pascal_identifier(name), _pascal_identifier(key),
            ]))})
    return {"root": str(root), "serviceDirectory": str(service_dir),
            "patterns": ["./" + p.relative_to(root).as_posix() + "/..." for p in sorted(owners)],
            "business": business, "substreams": substreams}


def _analyzer() -> tuple[Path, dict[str, str]]:
    go = shutil.which("go")
    if not go:
        raise ValueError("Install Go 1.25+ and make go available on PATH to analyze SubStream calls")
    source = Path(__file__).parent / "_go_calls"
    digest = hashlib.sha256()
    for path in sorted(source.iterdir()):
        if path.name in {"main.go", "go.mod", "go.sum"}:
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    digest.update(subprocess.check_output([go, "version"], timeout=10))
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "service-architect" / "go-calls" / digest.hexdigest()
    binary = cache / ("analyze.exe" if os.name == "nt" else "analyze")
    env = {**os.environ, "GOTOOLCHAIN": "local"}
    if not binary.is_file():
        cache.mkdir(parents=True, exist_ok=True)
        # Build our bundled analyzer, never source or hooks from the user project.
        # A private staging directory also keeps an installed wheel read-only.
        with tempfile.TemporaryDirectory(dir=cache) as temporary:
            work = Path(temporary)
            for name in ("main.go", "go.mod", "go.sum"):
                shutil.copyfile(source / name, work / name)
            built = work / binary.name
            build = subprocess.run([go, "build", "-mod=readonly", "-o", str(built), "."], cwd=work,
                                   env={**env, "GOWORK": "off", "GOFLAGS": ""}, capture_output=True, text=True, timeout=120)
            if build.returncode:
                raise ValueError("Cannot prepare Go call analysis: " + build.stderr[-4000:])
            os.replace(built, binary)
    return binary, env


def substream_calls(manifest: ProjectManifest, *, service: str | None = None, revision: str,
                    output_dir: str | None = None) -> dict[str, Any]:
    try:
        exported = execute_project(manifest, "export")
        if not exported.succeeded or exported.rendered_yaml is None:
            raise ValueError("Python model must validate before code analysis")
        actual = make_snapshot(manifest.name, exported.rendered_yaml)["revision"]
        if actual != revision:
            raise ValueError("Python model changed; refresh the graph before analyzing calls")
        root = (manifest.workspace / (output_dir or manifest.generation.output_directory or ".")).resolve()
        document = yaml.safe_load(exported.rendered_yaml)
        selected = [service] if service else [key for key, value in document.get("services", {}).items()
            if value.get("programmingLanguage") == "GoLang" and any(
                node.get("type") == "SubStream" for pipeline in value.get("pipelines", {}).values()
                for node in pipeline.values())]
        result: dict[str, Any] = {"links": [], "unresolved": [], "errors": []}
        analyzer = None
        for key in selected:
            try:
                request = analysis_request(document, root, key)
                if not request["substreams"]:
                    continue
                if analyzer is None:
                    analyzer = _analyzer()
                binary, env = analyzer
                run = subprocess.run([str(binary)], input=json.dumps(request), cwd=root, env=env,
                                     capture_output=True, text=True, timeout=120)
                if run.returncode:
                    raise ValueError(run.stderr[-4000:] or "Go call analysis failed")
                found = json.loads(run.stdout)
                result["links"].extend({**link, "service": key} for link in found["links"])
                result["unresolved"].extend({"service": key, "key": name} for name in found["unresolved"])
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                if service:
                    raise
                result["errors"].append({"service": key, "message": str(error)})
        return {"status": "success", "revision": actual, "service": service,
                "semantics": "possible-static-calls", **result}
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return {"status": "failed", "revision": revision, "service": service, "message": str(error)}
