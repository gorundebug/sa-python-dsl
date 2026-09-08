from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from .servicegen_capabilities import public_api_url


CONTRACT_PATH = "/v1/validation-contract"
CACHE_RELATIVE_PATH = Path(".service-architect/validation-contract.json")
SUPPORTED_SCHEMA_VERSION = "1.0"


class ValidationContractError(RuntimeError):
    """The ServiceGen validation metadata cannot be used safely."""


class _Response(Protocol):
    status: int

    def read(self) -> bytes: ...

    def __enter__(self) -> _Response: ...

    def __exit__(self, *args: object) -> None: ...


def fetch_validation_contract(
    base_url: str | None = None,
    *,
    timeout: float = 30,
    opener: Callable[..., _Response] | None = None,
) -> dict[str, Any]:
    request = urllib.request.Request(
        public_api_url(base_url) + CONTRACT_PATH,
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with (opener or urllib.request.urlopen)(request, timeout=timeout) as response:
            content = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        raise ValidationContractError(
            f"validation contract API returned HTTP {error.code}"
        ) from error
    except (urllib.error.URLError, OSError) as error:
        raise ValidationContractError(
            f"cannot reach validation contract API: {error}"
        ) from error
    if status != 200:
        raise ValidationContractError(
            f"validation contract API returned HTTP {status}"
        )
    try:
        document = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationContractError(
            "validation contract API did not return valid JSON"
        ) from error
    return validate_contract(document)


def validate_contract(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValidationContractError("validation contract root must be an object")
    if document.get("schemaVersion") != SUPPORTED_SCHEMA_VERSION:
        raise ValidationContractError(
            f"unsupported validation contract schema {document.get('schemaVersion')!r}; "
            f"expected {SUPPORTED_SCHEMA_VERSION!r}"
        )
    for field in (
        "servicegenVersion",
        "diagnosticSchemaVersion",
        "capabilityRevision",
        "revision",
    ):
        value = document.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValidationContractError(
                f"validation contract field {field!r} must be a non-empty string"
            )
    for field in ("capabilityRevision", "revision"):
        if not document[field].startswith("sha256:"):
            raise ValidationContractError(
                f"validation contract field {field!r} must use sha256: format"
            )
    diagnostics = document.get("diagnostics")
    if not isinstance(diagnostics, list) or not diagnostics:
        raise ValidationContractError(
            "validation contract diagnostics must be a non-empty array"
        )
    seen: set[str] = set()
    for index, descriptor in enumerate(diagnostics):
        if not isinstance(descriptor, dict):
            raise ValidationContractError(
                f"validation contract diagnostics[{index}] must be an object"
            )
        code = descriptor.get("code")
        if not isinstance(code, str) or not code.startswith("SG_"):
            raise ValidationContractError(
                f"validation contract diagnostics[{index}].code must be SG_*"
            )
        if code in seen:
            raise ValidationContractError(f"duplicate validation diagnostic {code!r}")
        seen.add(code)
        for field in ("stage", "condition", "meaning", "remediation", "evaluation"):
            value = descriptor.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValidationContractError(
                    f"validation diagnostic {code!r} field {field!r} must be a string"
                )
        if descriptor["evaluation"] != "servicegen":
            raise ValidationContractError(
                f"validation diagnostic {code!r} must be evaluated by servicegen"
            )
        if not isinstance(descriptor.get("scopes"), list) or not descriptor["scopes"]:
            raise ValidationContractError(
                f"validation diagnostic {code!r} scopes must be a non-empty array"
            )
        if not isinstance(descriptor.get("userCorrectable"), bool):
            raise ValidationContractError(
                f"validation diagnostic {code!r} userCorrectable must be boolean"
            )
    return document


def save_validation_contract(
    workspace: Path, document: Mapping[str, Any]
) -> Path:
    validated = validate_contract(dict(document))
    destination = workspace.resolve() / CACHE_RELATIVE_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(validated, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def load_validation_contract(workspace: Path) -> dict[str, Any]:
    source = workspace.resolve() / CACHE_RELATIVE_PATH
    if not source.is_file():
        raise ValidationContractError(
            f"validation contract cache is missing: {CACHE_RELATIVE_PATH.as_posix()}; "
            "run refresh_validation_contract"
        )
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationContractError(
            f"cannot read validation contract cache: {error}"
        ) from error
    return validate_contract(document)


def diagnostic_descriptor(
    document: Mapping[str, Any], code: str
) -> dict[str, Any]:
    for descriptor in document["diagnostics"]:
        if descriptor["code"] == code:
            return descriptor
    raise ValidationContractError(
        f"diagnostic code {code!r} is not present in the cached validation contract"
    )


def attach_remediation(
    payload: dict[str, Any], workspace: Path
) -> dict[str, Any]:
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list):
        return payload
    try:
        contract = load_validation_contract(workspace)
    except ValidationContractError:
        contract = None
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        code = diagnostic.get("code")
        if not isinstance(code, str) or not code.startswith("SG_"):
            continue
        diagnostic["validationRuleUri"] = f"servicegen://validation/rules/{code}"
        if contract is None:
            continue
        try:
            descriptor = diagnostic_descriptor(contract, code)
        except ValidationContractError:
            continue
        diagnostic["validationRule"] = {
            "contractRevision": contract["revision"],
            "condition": descriptor["condition"],
            "remediation": descriptor["remediation"],
            "userCorrectable": descriptor["userCorrectable"],
            "evaluation": descriptor["evaluation"],
        }
    return payload
