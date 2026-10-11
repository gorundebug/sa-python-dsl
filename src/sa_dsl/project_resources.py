"""Explicit, read-only project resources without a mutable current-project slot."""

from __future__ import annotations

import json
from typing import Any, Callable
from urllib.parse import quote

import yaml

from .business_tasks import inspect_business_tasks as inspect_tasks
from .generation_workspace import generation_directory
from .manifest import ManifestError, load_manifest
from .mcp_workspace import WorkspaceBoundary, WorkspaceBoundaryError
from .operation_audit import read_audit
from .servicegen_capabilities import CapabilityError, language_capability, load_cached_capabilities
from .servicegen_validation import ValidationContractError, diagnostic_descriptor, load_validation_contract


_KINDS = ("source", "dsl", "graph", "tasks", "audit", "capabilities", "validation-contract")


class ProjectResources:
    def __init__(self, workspace: Callable[[], WorkspaceBoundary], manifest_failure: Callable[..., dict[str, Any]]) -> None:
        self._workspace = workspace
        self._manifest_failure = manifest_failure

    def references(self, project: str) -> dict[str, str]:
        boundary = self._workspace()
        relative = boundary.resolve(project).relative_to(boundary.root).as_posix()
        if relative == ".":
            return {
                **{kind: f"servicegen://workspace/current/{kind}" for kind in _KINDS},
                "languageCapabilities": "servicegen://capabilities/{language}",
                "validationRule": "servicegen://validation/rules/{code}",
            }
        base = "servicegen://project/" + quote(relative, safe="")
        return {
            **{kind: f"{base}/{kind}" for kind in _KINDS},
            "languageCapabilities": f"{base}/capabilities/{{language}}",
            "validationRule": f"{base}/validation/rules/{{code}}",
        }

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2)

    def _unavailable(self, project: str, kind: str, error: Exception) -> str:
        return self._json({
            "schemaVersion": "1.0", "status": "unavailable", "message": str(error),
            "refreshTool": "refresh_capabilities" if kind == "capabilities" else "refresh_validation_contract",
            "projectPath": project, "workspaceResource": self.references(project)[kind],
        })

    def _failed(self, kind: str, error: Exception) -> str:
        operation = "inspect-business-tasks" if kind == "tasks" else "read-project-resource"
        if isinstance(error, (ManifestError, WorkspaceBoundaryError)):
            return self._json(self._manifest_failure(operation, error))
        return self._json({
            "schemaVersion": "1.0", "operation": operation, "status": "failed",
            "diagnostics": [{
                "code": "SA_BUSINESS_TASKS_READ_FAILED" if kind == "tasks" else "SA_RESOURCE_READ_FAILED",
                "severity": "error", "message": str(error),
                "path": "$.generation.outputDirectory" if kind == "tasks" else "$.resources." + kind,
            }],
        })

    def read(self, project: str, kind: str) -> str:
        try:
            boundary = self._workspace()
            root = boundary.resolve(project)
            if kind not in _KINDS:
                raise ValueError("unknown project resource: " + kind)
            if kind == "capabilities":
                return self._json(load_cached_capabilities(root))
            if kind == "validation-contract":
                return self._json(load_validation_contract(root))
            manifest = load_manifest(root)
            if kind == "source":
                return self._json({**manifest.inspect_payload(), "resources": self.references(project)})
            if kind == "audit":
                return self._json(read_audit(manifest.workspace))
            if kind == "tasks":
                return self._json(inspect_tasks(generation_directory(manifest, boundary_root=boundary.root)))
            path = WorkspaceBoundary(manifest.workspace).resolve(manifest.canonical.output)
            text = path.read_text(encoding="utf-8")
            if kind == "dsl":
                return text
            document = yaml.safe_load(text)
            if not isinstance(document, dict):
                raise ValueError("canonical YAML must contain an object")
            return self._json(document)
        except CapabilityError as error:
            return self._unavailable(project, "capabilities", error)
        except ValidationContractError as error:
            return self._unavailable(project, "validation-contract", error)
        except (ManifestError, WorkspaceBoundaryError, OSError, ValueError, yaml.YAMLError) as error:
            return self._failed(kind, error)

    def language(self, project: str, language: str) -> str:
        try:
            root = self._workspace().resolve(project)
            return self._json(language_capability(load_cached_capabilities(root), language))
        except CapabilityError as error:
            return self._unavailable(project, "capabilities", error)
        except (WorkspaceBoundaryError, OSError, ValueError) as error:
            return self._failed("capabilities", error)

    def rule(self, project: str, code: str) -> str:
        try:
            root = self._workspace().resolve(project)
            contract = load_validation_contract(root)
            return self._json({
                "schemaVersion": contract["schemaVersion"],
                "servicegenVersion": contract["servicegenVersion"],
                "contractRevision": contract["revision"],
                "capabilityRevision": contract["capabilityRevision"],
                "diagnostic": diagnostic_descriptor(contract, code),
            })
        except ValidationContractError as error:
            return self._unavailable(project, "validation-contract", error)
        except (WorkspaceBoundaryError, OSError, ValueError) as error:
            return self._failed("validation-contract", error)
