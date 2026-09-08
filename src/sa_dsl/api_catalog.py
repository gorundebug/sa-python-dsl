from __future__ import annotations

from enum import Enum
import inspect
from typing import Any

from .model import (
    CronConnector,
    CustomConnector,
    GrpcConnector,
    HttpConnector,
    KafkaConnector,
    Pipeline,
    Project,
    Stream,
    TemporalConnector,
)


PUBLIC_API_CLASSES = (
    Project,
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

LANGUAGE_PARAMETERS = {
    "go_implementation": "Go",
    "cpp_userver_implementation": "C++ userver",
    "cpp_boost_implementation": "C++ Boost",
    "python_implementation": "Python",
    "rust_implementation": "Rust",
    "type_script_implementation": "TypeScript",
}


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
        adapters = {}
        for parameter in signature.parameters.values():
            language = LANGUAGE_PARAMETERS.get(parameter.name)
            if language is None:
                continue
            adapters[language] = _default(parameter.default)
        connectors[factory_name] = {
            "languageAdapters": adapters,
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
        "scope": "Authoring adapters exposed by this DSL version; validate_project remains authoritative for generator/runtime capability.",
        "connectors": connectors,
    }
