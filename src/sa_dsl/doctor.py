from __future__ import annotations

import importlib.metadata
import sys
from pathlib import Path
from typing import Any

from .auth import load_env
from .manifest import ManifestError, load_manifest
from .servicegen_capabilities import (
    CapabilityError,
    compatibility_diagnostics,
    load_cached_capabilities,
)
from .servicegen_validation import (
    ValidationContractError,
    load_validation_contract,
)


def diagnose_project(project: Path, *, env_file: str = ".env") -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    _check(
        checks,
        "python",
        "pass" if sys.version_info >= (3, 11) else "error",
        f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )
    try:
        version = importlib.metadata.version("sa-python-dsl")
        _check(checks, "package", "pass", f"sa-python-dsl {version}")
    except importlib.metadata.PackageNotFoundError:
        _check(checks, "package", "error", "sa-python-dsl distribution is not installed")

    try:
        manifest = load_manifest(project)
    except ManifestError as error:
        _check(checks, "manifest", "error", f"{error.path}: {error}")
        return _payload(checks)
    _check(checks, "manifest", "pass", f"manifest v{manifest.version}: {manifest.name}")

    capability_revision: str | None = None
    try:
        capabilities = load_cached_capabilities(manifest.workspace)
        capability_revision = capabilities["revision"]
        compatibility = compatibility_diagnostics(
            capabilities, manifest.generation.targets
        )
        if compatibility:
            for diagnostic in compatibility:
                _check(checks, "capabilities", "error", diagnostic["message"])
        else:
            _check(
                checks,
                "capabilities",
                "pass",
                (
                    f"schema {capabilities['schemaVersion']}; ServiceGen "
                    f"{capabilities['servicegenVersion']}; API {capabilities['apiRevision']}; "
                    f"revision {capabilities['revision']}"
                ),
            )
    except CapabilityError as error:
        status = "warning" if "cache is missing" in str(error) else "error"
        _check(checks, "capabilities", status, str(error))

    try:
        validation_contract = load_validation_contract(manifest.workspace)
        if (
            capability_revision is not None
            and validation_contract["capabilityRevision"] != capability_revision
        ):
            _check(
                checks,
                "validationContract",
                "error",
                "validation contract and capability cache describe different ServiceGen revisions",
            )
        else:
            _check(
                checks,
                "validationContract",
                "pass",
                (
                    f"schema {validation_contract['schemaVersion']}; ServiceGen "
                    f"{validation_contract['servicegenVersion']}; revision "
                    f"{validation_contract['revision']}"
                ),
            )
    except ValidationContractError as error:
        status = "warning" if "cache is missing" in str(error) else "error"
        _check(checks, "validationContract", status, str(error))

    canonical = manifest.workspace / manifest.canonical.output
    _check(
        checks,
        "canonical",
        "pass" if canonical.is_file() else "warning",
        manifest.canonical.output if canonical.is_file() else "canonical export is not present yet",
    )

    credentials_path = manifest.workspace / env_file
    try:
        values = load_env(credentials_path) if credentials_path.is_file() else {}
        configured = bool(
            values.get("SERVICE_ARCHITECT_API_KEY")
            or values.get("SERVICE_ARCHITECT_ID_TOKEN")
            or (
                values.get("SERVICE_ARCHITECT_USERNAME")
                and values.get("SERVICE_ARCHITECT_PASSWORD")
            )
        )
        _check(
            checks,
            "credentials",
            "pass" if configured else "warning",
            "generation credentials configured" if configured else "generation credentials are not configured",
        )
    except (OSError, ValueError) as error:
        _check(checks, "credentials", "error", f"cannot read credential configuration: {error}")

    merge_script = manifest.workspace / "scripts/merge.generated.sh"
    if merge_script.is_file():
        content = merge_script.read_text(encoding="utf-8", errors="replace")
        compatible = "--report-json" in content and "SERVICEGEN_PROJECT_DIR_OVERRIDE" in content
        _check(
            checks,
            "mergeContract",
            "pass" if compatible else "warning",
            "transactional merge contract available" if compatible else "regenerate project to update merge contract",
        )
    else:
        _check(checks, "mergeContract", "warning", "generated merge script is not present yet")
    return _payload(checks)


def _check(checks: list[dict[str, str]], identifier: str, status: str, message: str) -> None:
    checks.append({"id": identifier, "status": status, "message": message})


def _payload(checks: list[dict[str, str]]) -> dict[str, Any]:
    errors = sum(check["status"] == "error" for check in checks)
    warnings = sum(check["status"] == "warning" for check in checks)
    return {
        "schemaVersion": "1.0",
        "status": "failed" if errors else "success",
        "summary": {"errors": errors, "warnings": warnings, "checks": len(checks)},
        "checks": checks,
    }
