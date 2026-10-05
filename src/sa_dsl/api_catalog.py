from __future__ import annotations

from enum import Enum
import inspect
from typing import Any

from .model import (
    Component,
    CronConnector,
    CustomConnector,
    GrpcConnector,
    HttpConnector,
    KafkaConnector,
    Pipeline,
    Project,
    Service,
    Stream,
    TemporalConnector,
)


PUBLIC_API_CLASSES = (
    Project,
    Service,
    Component,
    Pipeline,
    Stream,
    HttpConnector,
    GrpcConnector,
    KafkaConnector,
    CronConnector,
    TemporalConnector,
    CustomConnector,
)

CONNECTOR_FACTORIES = (
    "http_connector",
    "grpc_connector",
    "kafka_connector",
    "cron_connector",
    "temporal_connector",
    "custom_connector",
)

def _annotation(value: Any) -> str | None:
    if value is inspect.Parameter.empty or value is inspect.Signature.empty:
        return None
    if isinstance(value, str):
        return value
    return inspect.formatannotation(value)


def _default(value: Any) -> Any:
    if value is inspect.Parameter.empty:
        return None
    if isinstance(value, Enum):
        return value.value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def _method(name: str, member: Any) -> dict[str, Any]:
    signature = inspect.signature(member)
    parameters = []
    for parameter in signature.parameters.values():
        if parameter.name == "self":
            continue
        parameters.append(
            {
                "name": parameter.name,
                "kind": parameter.kind.description,
                "required": parameter.default is inspect.Parameter.empty,
                "default": _default(parameter.default),
                "annotation": _annotation(parameter.annotation),
            }
        )
    return {
        "name": name,
        "signature": f"{name}{signature}",
        "parameters": parameters,
        "returns": _annotation(signature.return_annotation),
    }


def build_typed_api_catalog() -> dict[str, Any]:
    classes: dict[str, Any] = {}
    for class_ in PUBLIC_API_CLASSES:
        methods = {
            name: _method(name, member)
            for name, member in class_.__dict__.items()
            if callable(member) and not name.startswith("_")
        }
        classes[class_.__name__] = {"methods": methods}
    return {
        "generated": True,
        "source": "runtime reflection over sa_dsl.model public methods",
        "rule": "Use these signatures instead of inventing factory names or parameters.",
        "classes": classes,
    }


def build_connector_capabilities() -> dict[str, Any]:
    connectors: dict[str, Any] = {}
    for factory_name in CONNECTOR_FACTORIES:
        signature = inspect.signature(getattr(Project, factory_name))
        connectors[factory_name] = {
            "selection": {
                "parameter": "implementations",
                "type": _annotation(signature.parameters["implementations"].annotation),
                "defaultSource": "selected template pack",
            },
            "requiredParameters": [
                parameter.name
                for parameter in signature.parameters.values()
                if parameter.name != "self"
                and parameter.default is inspect.Parameter.empty
            ],
        }
    return {
        "generated": True,
        "source": "Project connector factory signatures",
        "scope": "Authoring factory parameters only; supported transports and defaults belong to the selected template packs and generator capabilities.",
        "connectors": connectors,
    }
