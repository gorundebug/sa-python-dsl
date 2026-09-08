from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from .code_generation import DEFAULT_API_KEY_URL


CAPABILITIES_PATH = "/v1/capabilities"
CACHE_RELATIVE_PATH = Path(".service-architect/capabilities.json")
SUPPORTED_SCHEMA_VERSION = "1.0"

TARGET_BACKENDS = {
    "go": "golang",
    "cpp-userver": "cppUserver",
    "cpp-boost": "cppBoost",
    "python": "python",
    "rust": "rust",
    "typescript": "typescript",
}


class CapabilityError(RuntimeError):
    """Capability discovery returned an unusable contract."""


class _Response(Protocol):
    status: int

    def read(self) -> bytes: ...

    def __enter__(self) -> _Response: ...

    def __exit__(self, *args: object) -> None: ...


def capability_url(base_url: str | None = None) -> str:
    root = (
        base_url
        or os.getenv("SERVICE_ARCHITECT_API_URL")
        or DEFAULT_API_KEY_URL
    ).rstrip("/")
    parsed = urllib.parse.urlparse(root)
    local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
        raise CapabilityError("capability API URL must use HTTPS (HTTP is allowed only for localhost)")
    if not parsed.netloc:
        raise CapabilityError("capability API URL must be absolute")
    return root + CAPABILITIES_PATH


def fetch_capabilities(
    base_url: str | None = None,
    *,
    timeout: float = 30,
    opener: Callable[..., _Response] | None = None,
) -> dict[str, Any]:
    request = urllib.request.Request(
        capability_url(base_url),
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with (opener or urllib.request.urlopen)(request, timeout=timeout) as response:
            content = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        raise CapabilityError(f"capability API returned HTTP {error.code}") from error
    except (urllib.error.URLError, OSError) as error:
        raise CapabilityError(f"cannot reach capability API: {error}") from error
    if status != 200:
        raise CapabilityError(f"capability API returned HTTP {status}")
    try:
        document = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CapabilityError("capability API did not return valid JSON") from error
    return validate_capability_matrix(document)


def validate_capability_matrix(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise CapabilityError("capability document root must be an object")
    schema = document.get("schemaVersion")
    if schema != SUPPORTED_SCHEMA_VERSION:
        raise CapabilityError(
            f"unsupported capability schema {schema!r}; expected {SUPPORTED_SCHEMA_VERSION!r}"
        )
    for field in ("servicegenVersion", "apiRevision", "revision"):
        value = document.get(field)
        if not isinstance(value, str) or not value.strip():
            raise CapabilityError(f"capability field {field!r} must be a non-empty string")
    if not document["revision"].startswith("sha256:"):
        raise CapabilityError("capability revision must use the sha256: format")
    languages = document.get("languages")
    if not isinstance(languages, list) or not languages:
        raise CapabilityError("capability languages must be a non-empty array")
    seen: set[str] = set()
    for index, language in enumerate(languages):
        if not isinstance(language, dict):
            raise CapabilityError(f"capability languages[{index}] must be an object")
        backend = language.get("backend")
        if not isinstance(backend, str) or not backend:
            raise CapabilityError(f"capability languages[{index}].backend must be a string")
        if backend in seen:
            raise CapabilityError(f"duplicate capability backend {backend!r}")
        seen.add(backend)
    return document


def save_capabilities(workspace: Path, document: Mapping[str, Any]) -> Path:
    validated = validate_capability_matrix(dict(document))
    destination = workspace.resolve() / CACHE_RELATIVE_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(validated, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def load_cached_capabilities(workspace: Path) -> dict[str, Any]:
    source = workspace.resolve() / CACHE_RELATIVE_PATH
    if not source.is_file():
        raise CapabilityError(
            f"capability cache is missing: {CACHE_RELATIVE_PATH.as_posix()}; run refresh_capabilities"
        )
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CapabilityError(f"cannot read capability cache: {error}") from error
    return validate_capability_matrix(document)


def language_capability(document: Mapping[str, Any], value: str) -> dict[str, Any]:
    normalized = value.casefold()
    for language in document["languages"]:
        aliases = {
            str(language.get("id", "")).casefold(),
            str(language.get("name", "")).casefold(),
            str(language.get("backend", "")).casefold(),
        }
        if normalized in aliases:
            return language
    raise CapabilityError(f"language {value!r} is not present in the cached capability matrix")


def compatibility_diagnostics(
    document: Mapping[str, Any], targets: tuple[str, ...]
) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    backends = {language["backend"] for language in document["languages"]}
    for index, target in enumerate(targets):
        backend = TARGET_BACKENDS[target]
        if backend not in backends:
            diagnostics.append(
                {
                    "code": "SA_CAPABILITY_TARGET_UNAVAILABLE",
                    "severity": "error",
                    "path": f"$.generation.targets[{index}]",
                    "message": (
                        f"target {target!r} requires backend {backend!r}, which is not "
                        "declared by the cached ServiceGen capability revision"
                    ),
                }
            )
    return diagnostics
