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
            "values": {
                "Inherited": {
                    "meaning": "Use the owning service default call semantics.",
                    "api": "ordinary graph connection",
                    "requires": [],
                },
                "FunctionCall": {
                    "meaning": "Invoke the downstream stream using function-call semantics.",
                    "api": "source.function_call(target)",
                    "requires": [],
                    "doesNotMean": ["worker queue", "collection fan-out"],
                },
                "TaskPool": {
                    "meaning": "Submit the downstream invocation to a worker pool.",
                    "api": "source.task_pool_call(target, pool=pool)",
                    "requires": ["pool"],
                    "doesNotMean": ["priority ordering", "collection fan-out"],
                },
                "PriorityTaskPool": {
                    "meaning": "Submit the downstream invocation to a prioritized worker queue.",
                    "api": "source.priority_task_pool_call(target, pool=pool, priority=priority)",
                    "requires": ["pool", "priority"],
                    "doesNotMean": ["collection fan-out", "independent parallel branch"],
                },
                "ParallelCall": {
                    "meaning": "Dispatch an independent downstream call using parallel-call semantics.",
                    "api": "source.parallel_call(target)",
                    "requires": [],
                    "doesNotMean": ["collection partitioning", "worker-pool selection"],
                },
            },
            "selectionRules": [
                "Choose graph topology before invocation semantics.",
                "Do not infer a method from the word parallel alone.",
                "Omit a link override when it equals the service default call semantics.",
                "Declare the specialized link where the graph connection is added.",
                "A persisted Link must correspond to a real stream connection.",
            ],
        },
        "intent-model": {
            "requiredAxes": [
                "trigger",
                "cardinality",
                "ordering",
                "completion",
                "execution",
                "durability",
                "correlation",
                "failure",
                "schedule",
            ],
            "ambiguityRule": "Ask one focused question when a missing answer changes graph shape; otherwise state the assumption.",
            "proof": ["validate_project", "preview_architecture_diff"],
        },
        "fan-out": {
            "intent": "Process each element of a collection, potentially concurrently, and optionally aggregate results.",
            "shape": ["Split collection", "Optional KeyBy", "Worker stream", "Error decision", "Optional Join or MultiJoin"],
            "rules": [
                "ParallelCall does not split a collection.",
                "PriorityTaskPool does not split a collection.",
                "Choose correlation before Join or MultiJoin.",
                "Model fan-out topology separately from worker-edge call semantics.",
            ],
        },
        "conditional-routing": {
            "operator": "Case When",
            "rules": [
                "Use for conditionally selected branches, not unconditional fan-out.",
                "Define unmatched or default behavior.",
                "Keep branch result types compatible with their consumers.",
            ],
        },
        "aggregation": {
            "Join": "Combine the defined paired inputs using an explicit correlation strategy.",
            "MultiJoin": "Collect multiple named branches using an explicit correlation strategy.",
            "rules": ["Arrival order is not correlation.", "Decide partial-failure behavior before connecting error paths."],
        },
        "error-handling": {
            "rules": [
                "Use the supported Error connection only with an Error stream.",
                "Separate domain failure flow from transport or runtime retries.",
                "For fan-out, decide fail-fast versus collected partial failures.",
                "For Temporal, separate Activity retry from Workflow compensation.",
            ],
        },
        "temporal-orchestration": {
            "Workflow": "Durable orchestration of steps, retries, waiting, and compensation.",
            "Activity": "Externally executed operation called by Temporal orchestration.",
            "onDemand": "A Temporal Sink submission path does not imply a schedule.",
            "scheduled": "Supply a five-field cron expression and a stable Temporal schedule ID.",
            "ordinaryCron": "Cron requires a schedule expression and does not use Temporal schedule ID.",
        },
        "authoring-api": {
            "connectionMethods": [
                "function_call(target)",
                "task_pool_call(target, pool=pool)",
                "priority_task_pool_call(target, pool=pool, priority=priority)",
                "parallel_call(target)",
            ],
            "factoryRule": "Use the concrete factory for the entity type and only parameters exposed by its typed signature.",
            "referenceRule": "Pass project-owned objects for types, modules, packages, pools, pipelines, endpoints, connectors, and streams; do not recreate serialized keys.",
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
