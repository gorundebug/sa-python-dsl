from __future__ import annotations

import json
from typing import Any, Mapping

from .api_catalog import build_connector_capabilities, build_typed_api_catalog
from .architecture_patterns import PATTERN_CATALOG, REVIEW_CHECKLIST


RESOURCE_CATALOG: Mapping[str, Mapping[str, dict[str, Any]]] = {
    "semantics": {
        "visual-components": {
            "purpose": "Group whole pipelines within one service for Designer navigation and collapse/expand.",
            "runtimeEffect": "None. Components are editor metadata, not runtime operators, services, modules or deployment units.",
            "apiResources": [
                "servicegen://authoring/typed-api-Service-component",
                "servicegen://authoring/typed-api-Service-pipeline",
                "servicegen://authoring/typed-api-Component-pipeline",
            ],
            "rules": [
                "Create a Component through its owning service and pass that object to service.pipeline(component=...).",
                "Alternatively use component.pipeline(name) to create a pipeline in that component.",
                "A component may contain multiple whole pipelines, but all must belong to one service.",
                "A pipeline belongs to at most one component; do not group individual streams independently.",
                "Keep component identity stable when changing its display name.",
                "Do not change stream connections, endpoints, message types or call semantics merely to group the diagram.",
                "Preserve versioned service appearance.components metadata through editor interchange.",
                "Exclude component metadata from code-generation requests; preserve it in the source workspace.",
                "Collapsed/expanded is local view state, not persisted architecture and not Python source.",
                "Components do not allow persisted links across services; cross-service communication still uses transports.",
            ],
            "example": "booking = service.component('Booking')\nvalidation = booking.pipeline('validation')\nreservation = service.pipeline('reservation', component=booking)",
        },
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
                    "meaning": "Invoke the downstream stream directly; async_ is the only optional link property for this mode.",
                    "api": "source.function_call(target, async_=None)",
                    "requires": [],
                    "optional": ["async_"],
                    "doesNotMean": ["worker queue", "collection fan-out"],
                },
                "TaskPool": {
                    "meaning": "Enqueue the downstream invocation in a named FIFO worker pool.",
                    "api": "source.task_pool_call(target, pool=pool)",
                    "requires": ["pool"],
                    "doesNotMean": ["priority ordering", "collection fan-out"],
                },
                "PriorityTaskPool": {
                    "meaning": "Enqueue the downstream invocation in a named priority worker pool; larger priorities run first.",
                    "api": "source.priority_task_pool_call(target, pool=pool, priority=priority)",
                    "requires": ["pool", "priority"],
                    "priorityRange": [0, 255],
                    "doesNotMean": ["collection fan-out", "independent parallel branch"],
                },
                "ParallelCall": {
                    "meaning": "Dispatch every incoming message using runtime parallel-call semantics without a pool.",
                    "api": "source.parallel_call(target)",
                    "requires": [],
                    "doesNotMean": ["iterable expansion", "new graph branch", "worker-pool selection"],
                },
            },
            "selectionRules": [
                "Choose graph topology before invocation semantics.",
                "Do not infer a method from the word parallel alone.",
                "Declare the graph edge before calling a typed call-semantics method.",
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
            "intent": "Expand iterable or callback-produced items, optionally broadcast each item, process them, and optionally aggregate keyed results.",
            "shape": ["FlatMapIterable or FlatMap", "Optional KeyBy", "Optional Split broadcast", "Worker stream", "Error decision", "Optional Join or MultiJoin"],
            "rules": [
                "FlatMapIterable expands an iterable without a Function; FlatMap uses a Function to emit zero or more values.",
                "Split broadcasts each existing message and does not expand an iterable.",
                "ParallelCall and PriorityTaskPool do not expand an iterable.",
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
            "Join": "Combine exactly two KeyValue inputs; supports Inner, Left, Right, or Outer join type.",
            "MultiJoin": "Combine one primary and one or more ordered additional KeyValue inputs; the typed API has no join_type argument.",
            "storage": ["HashMap", "RocksDB", "Aerospike"],
            "rules": [
                "All inputs use the same comparable key type; MultiJoin value types may differ.",
                "Arrival order is not correlation.",
                "Positive TTL bounds retained state and renewTTL extends it on arrivals while the callback keeps the key.",
                "Decide partial-failure behavior before connecting error paths.",
            ],
        },
        "error-handling": {
            "rules": [
                "Only Input, Process, and Sink expose a dedicated Error output.",
                "Declare the owner-to-Error graph edge before owner.on_error(error_stream).",
                "An owner has at most one Error consumer and both streams belong to the same service.",
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
                "function_call(target, async_=None)",
                "task_pool_call(target, pool=pool)",
                "priority_task_pool_call(target, pool=pool, priority=priority)",
                "parallel_call(target)",
            ],
            "wiring": {
                "source >> target": "Set the target primary source and return target.",
                "target << source": "Append an additional source and return target.",
                "target.from_sources(*sources)": "Replace the complete multi-source list.",
                "typed call method": "Annotate an already declared graph edge; does not create the edge.",
            },
            "factoryRule": "Use the concrete factory for the entity type and only parameters exposed by its typed signature.",
            "referenceRule": "Pass project-owned objects for types, modules, packages, pools, pipelines, endpoints, connectors, and streams; do not recreate serialized keys.",
        },
        "operator-selection": {
            "Map": "Transform one input into one output.",
            "Filter": "Retain or discard the input.",
            "Process": "Execute or collect with a dedicated error output; do not choose it from the business verb process alone.",
            "FlatMap": "Use a Function to emit zero or more outputs.",
            "FlatMapIterable": "Expand an iterable input without a Function.",
            "KeyBy": "Produce KeyValue<K,V>; K must be comparable and enables keyed operations.",
            "Merge": "Combine compatible sources without a user callback.",
            "Split": "Broadcast every existing message to multiple consumers.",
            "Case": "Return the zero-based index of exactly one ordered When branch.",
            "Delay": "Defer delivery using duration and delay Function semantics.",
            "CycleLink": "Close an intentional feedback loop while keeping the ordinary graph acyclic.",
        },
        "process-patterns": {
            "Execute": "Perform a side effect and synchronously emit zero or more results.",
            "Collect": "Accumulate results and emit them in a batch.",
        },
        "pools": {
            "TaskPool": "Named FIFO worker queue.",
            "PriorityTaskPool": "Named priority worker queue; larger priority values run first.",
            "executorsCount": "Positive worker concurrency.",
            "queueCapacity": "Positive initial queue capacity; defaults to 256.",
            "priorityRange": [0, 255],
        },
        "boundaries": {
            "Input": "Admit messages from a concrete connector Endpoint.",
            "Sink": "Submit messages through a concrete connector Endpoint.",
            "HTTP": "GET or POST with a required path unique within the connector.",
            "gRPC": "Requires a contract Module and explicit unary/client/server/bidirectional streaming method; Sink usage also requires address.",
            "Kafka": "Requires brokers and topic; Input usage also requires consumer group; credentials are runtime-only.",
            "disabledEndpoint": "Remains in the graph but does not start its transport or scheduler integration.",
            "endpointIdentity": "Endpoint names are globally unique.",
        },
        "cycles": {
            "rule": "Use CycleLink for intentional feedback; do not create an ordinary graph cycle.",
            "designRequirement": "State the termination, delay, deadline, or bounded-progress mechanism.",
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


RESOURCE_CATALOG["authoring"].update(
    {
        "typed-api": build_typed_api_catalog(),
        "connector-capabilities": build_connector_capabilities(),
        "review-checklist": REVIEW_CHECKLIST,
    }
)
RESOURCE_CATALOG["patterns"].update(PATTERN_CATALOG)


# Keep protocol responses small: clients may truncate the full reflected catalog.
_TYPED_API = RESOURCE_CATALOG["authoring"]["typed-api"]
RESOURCE_CATALOG["authoring"]["typed-api"] = {
    "generated": True,
    "source": _TYPED_API["source"],
    "rule": "Read a class index, then its method resource for the complete signature and parameters.",
    "classes": {
        name: {"resource": f"servicegen://authoring/typed-api-{name}"}
        for name in _TYPED_API["classes"]
    },
}
for _class_name, _class in _TYPED_API["classes"].items():
    RESOURCE_CATALOG["authoring"][f"typed-api-{_class_name}"] = {
        "generated": True,
        "methods": {
            name: {"resource": f"servicegen://authoring/typed-api-{_class_name}-{name}"}
            for name in _class["methods"]
        },
    }
    for _method_name, _method in _class["methods"].items():
        RESOURCE_CATALOG["authoring"][f"typed-api-{_class_name}-{_method_name}"] = {
            "generated": True,
            "class": _class_name,
            **_method,
        }

RESOURCE_CATALOG["semantics"]["http-grpc"] = {
    "intent": "An HTTP request invokes a unary gRPC operation in another service and receives its result.",
    "rules": [
        "Use an HTTP connector route for the public request and one shared gRPC connector endpoint for the internal operation.",
        "The caller owns the gRPC Sink; the callee owns the gRPC Input. Do not connect streams directly across services.",
        "The gRPC Sink input type must match the callee Input output type; its result must match the callee response type.",
        "Connect the service-local response stream back to its request Input as the response source, as shown in the canonical example.",
        "A gRPC connector requires a contract Module; calling it through a Sink also requires an address.",
        "Choose explicit failure behavior and bounded request timeouts; transport failures are not successful reservations.",
        "Topology does not implement business logic: inventory checks, atomic reservation and idempotency belong in user functions.",
    ],
    "exampleResource": "servicegen://examples/http-grpc",
    "apiResource": "servicegen://authoring/typed-api",
}
RESOURCE_CATALOG["examples"]["http-grpc"] = {
    "description": "HTTP Order Service calls the unary Inventory Service API in the canonical processorder project.",
    "repository": "https://github.com/gorundebug/sa-python-dsl/tree/main/examples/processorder",
    "paths": [
        "connectors/order_service_api.py",
        "connectors/inventory_service_api.py",
        "endpoints/inventory_service_api.py",
        "services/inventory_service/pipelines/inventory_item.py",
    ],
    "semanticsResource": "servicegen://semantics/http-grpc",
    "scope": "A guide to the canonical example, not an embedded runnable project.",
}


def catalog_resource(category: str, topic: str) -> str:
    category_values = RESOURCE_CATALOG.get(category)
    value = category_values.get(topic) if category_values else None
    if topic == "index" and category_values is not None:
        # Preserve existing index metadata while making every topic discoverable.
        value = {
            **(value or {}),
            "topics": sorted(name for name in category_values if name != "index"),
            "resources": [
                f"servicegen://{category}/{name}"
                for name in sorted(category_values) if name != "index"
            ],
        }
    if value is None:
        return json_resource({
            "schemaVersion": "1.0",
            "resource": f"servicegen://{category}/{topic}",
            "status": "not_found",
            "message": f"Unknown {category} resource {topic!r}; read the index for available topics.",
            "indexResource": f"servicegen://{category}/index",
        })
    return json_resource({
        "schemaVersion": "1.0",
        "resource": f"servicegen://{category}/{topic}",
        **value,
    })


def json_resource(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
