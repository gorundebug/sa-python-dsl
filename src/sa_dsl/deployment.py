"""Explicit, optional generation policy, independent of runtime graph semantics."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from typing import Any

from ._deployment_contract import (
    DeploymentAffinity, DeploymentContainer, DeploymentEnvFrom, DeploymentEnvVar,
    DeploymentPodSecurityContext, DeploymentProbes, DeploymentResources,
    DeploymentSecurityContext, DeploymentServiceAccount, DeploymentStrategy,
    DeploymentToleration, DeploymentUpdateStrategy, DeploymentVolume,
    DeploymentVolumeMount,
)
from ._deployment_validation import validate_deployment


def _camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.title() for part in rest)


def _copy(value: Any, active: set[int] | None = None) -> Any:
    active = set() if active is None else active
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, Mapping) or isinstance(value, (tuple, list)):
        if id(value) in active:
            raise ValueError("Deployment configuration contains cyclic data")
        active.add(id(value))
        try:
            if isinstance(value, Mapping):
                if any(not isinstance(key, str) for key in value):
                    raise ValueError("Deployment mapping keys must be strings")
                return {key: _copy(item, active) for key, item in value.items()}
            return [_copy(item, active) for item in value]
        finally:
            active.remove(id(value))
    raise ValueError("Deployment configuration must contain document values only")


@dataclass(frozen=True, slots=True)
class SecretKeyRef:
    name: str | None = None
    key: str | None = None
    optional: bool | None = None

    def to_document(self) -> dict[str, Any]:
        if any(value is not None and (not isinstance(value, str) or not value) for value in (self.name, self.key)):
            raise ValueError("SecretKeyRef name and key must be nonempty text when specified")
        if self.optional is not None and type(self.optional) is not bool:
            raise ValueError("SecretKeyRef.optional must be boolean")
        result = {key: value for key, value in (("name", self.name), ("key", self.key)) if value is not None}
        if self.optional is not None:
            result["optional"] = self.optional
        return result


@dataclass(frozen=True, slots=True)
class KubernetesDeployment:
    replica_count: int | None = None
    termination_grace_period_seconds: int | None = None
    deployment_strategy: DeploymentStrategy | None = None
    update_strategy: DeploymentUpdateStrategy | None = None
    command: Sequence[str] | None = None
    init_containers: Sequence[DeploymentContainer] | None = None
    extra_containers: Sequence[DeploymentContainer] | None = None
    extra_env: Sequence[DeploymentEnvVar] | None = None
    secret_env: Mapping[str, SecretKeyRef] | None = None
    secret_env_from: Sequence[str] | None = None
    extra_env_from: Sequence[DeploymentEnvFrom] | None = None
    extra_volumes: Sequence[DeploymentVolume] | None = None
    extra_volume_mounts: Sequence[DeploymentVolumeMount] | None = None
    resources: DeploymentResources | None = None
    annotations: Mapping[str, str] | None = None
    pod_annotations: Mapping[str, str] | None = None
    pod_labels: Mapping[str, str] | None = None
    pod_security_context: DeploymentPodSecurityContext | None = None
    security_context: DeploymentSecurityContext | None = None
    service_account: DeploymentServiceAccount | None = None
    node_selector: Mapping[str, str] | None = None
    tolerations: Sequence[DeploymentToleration] | None = None
    affinity: DeploymentAffinity | None = None
    probes: DeploymentProbes | None = None

    def to_document(self) -> dict[str, Any]:
        result = {}
        for field in fields(self):
            value = getattr(self, field.name)
            if value is None:
                continue
            if field.name in {"replica_count", "termination_grace_period_seconds"}:
                minimum = 1 if field.name == "replica_count" else 0
                if type(value) is not int or value < minimum:
                    raise ValueError(f"{field.name} must be an integer >= {minimum}")
            elif field.name in {"command", "secret_env_from"}:
                if not isinstance(value, (tuple, list)) or any(not isinstance(item, str) for item in value):
                    raise ValueError(f"{field.name} must be a sequence of strings")
            elif field.name in {"init_containers", "extra_containers", "extra_env", "extra_env_from", "extra_volumes", "extra_volume_mounts", "tolerations"}:
                if not isinstance(value, (tuple, list)) or any(not isinstance(item, Mapping) for item in value):
                    raise ValueError(f"{field.name} must be a sequence of Kubernetes objects")
            elif not isinstance(value, Mapping):
                raise ValueError(f"{field.name} must be a mapping")
            if field.name == "secret_env":
                if any(not isinstance(key, str) or not isinstance(ref, SecretKeyRef) for key, ref in value.items()):
                    raise ValueError("secret_env must map environment names to SecretKeyRef objects")
                value = {key: ref.to_document() for key, ref in value.items()}
            result[_camel(field.name)] = _copy(value)
        validate_deployment(result)
        return result


@dataclass(frozen=True, slots=True)
class Deployment:
    kubernetes: KubernetesDeployment | None = None

    def to_document(self) -> dict[str, Any]:
        if self.kubernetes is None:
            return {}
        if not isinstance(self.kubernetes, KubernetesDeployment):
            raise ValueError("Deployment.kubernetes must be KubernetesDeployment")
        return {"kubernetes": self.kubernetes.to_document()}
