from __future__ import annotations

import json
from typing import Any, Mapping


RESOURCE_CATALOG: Mapping[str, Mapping[str, dict[str, Any]]] = {
    "semantics": {
        "overview": {
            "sourceOfTruth": "typed Python for Python-authored workspaces; canonical YAML is generated IR",
            "rules": [
                "Use concrete typed factories and object references.",
                "Validate and review semantic changes before export or generation.",
                "Preview generation before applying the immutable archive.",
                "Generated and overwrite-listed files are managed; business files are preserved.",
            ],
        },
        "operators": {
            "operators": [
                "Input", "Map", "Filter", "FlatMap", "FlatMapIterable", "KeyBy",
                "Join", "MultiJoin", "Merge", "Split", "Case", "When", "Process",
                "Delay", "CycleLink", "Sink", "Error",
            ],
            "keyed": {
                "KeyBy": "produces a keyed value",
                "Join": "one primary and one additional keyed source",
                "MultiJoin": "one primary and one or more additional keyed sources",
            },
        },
        "transports": {
            "connectors": ["HTTP", "gRPC", "Kafka", "Custom", "Cron", "Temporal"],
            "temporalEndpoints": ["Activity", "Workflow"],
            "schedule": "Cron uses portable five-field expressions; Temporal schedules also require a stable schedule ID.",
        },
        "call-semantics": {
            "values": ["Inherited", "FunctionCall", "TaskPool", "PriorityTaskPool", "ParallelCall"],
            "rule": "Omit a link override when it equals the service default call semantics.",
        },
    },
    "authoring": {
        "python": {
            "root": "Create one Project and register topology objects through typed factories.",
            "constraints": [
                "Keep topology declarations deterministic and free of unrelated application logic.",
                "Do not use network access, environment-dependent branches or loops that make graph shape unpredictable.",
                "Use Package, Module, Pool, language and configuration objects instead of stringly typed references.",
            ],
        }
    },
    "schema": {
        "dsl": {
            "schemaVersion": "1.0",
            "topLevel": ["settings", "modules", "types", "pools", "dataConnectors", "services"],
            "identity": "Canonical collections are mappings keyed by stable graph identity.",
        },
        "manifest": {
            "version": 1,
            "sections": ["project", "authoring", "canonical", "generation"],
            "authoringModes": ["python", "yaml"],
        },
    },
    "examples": {
        "index": {
            "examples": [{
                "id": "processorder",
                "description": "Canonical topology covering HTTP, gRPC, Kafka, Cron, Temporal and keyed operators.",
                "repository": "https://github.com/gorundebug/sa-python-dsl/tree/main/examples/processorder",
            }]
        }
    },
    "patterns": {
        "index": {
            "patterns": [
                "request-response-endpoint", "kafka-consume-process-publish",
                "keyed-join", "error-flow", "temporal-on-demand", "temporal-schedule",
            ],
            "guidance": "Load only the pattern relevant to the requested topology change.",
        }
    },
}


def catalog_resource(category: str, topic: str) -> str:
    category_values = RESOURCE_CATALOG.get(category)
    value = category_values.get(topic) if category_values else None
    if value is None:
        available = ", ".join(sorted(category_values or {})) or "none"
        raise ValueError(f"unknown {category} resource {topic!r}; available: {available}")
    return json_resource({
        "schemaVersion": "1.0",
        "resource": f"servicegen://{category}/{topic}",
        **value,
    })


def json_resource(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
