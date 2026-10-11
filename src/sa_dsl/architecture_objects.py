"""Small intent-first guides backed by the real Python DSL signatures.

This is documentation, not another architecture model or a capability registry.
Transport support is determined by the selected backend's capability contract.
"""
from __future__ import annotations

from typing import Any

from .api_catalog import describe_typed_factory


def _guide(purpose, use_when, avoid_when, factories, *, semantics="overview", patterns=()):
    return {
        "purpose": purpose,
        "useWhen": use_when,
        "avoidWhen": avoid_when,
        "factories": factories,
        "semanticsResource": f"servicegen://semantics/{semantics}",
        "patternResources": [f"servicegen://patterns/{name}" for name in patterns],
    }


OBJECT_GUIDES = {
    "service": _guide(
        "An independently runnable and deployable application owning pipelines.",
        "An execution/deployment or transport boundary is needed.",
        "Only a visual group or another stage inside the same process is needed.",
        [("Project", "service")]),
    "pipeline": _guide(
        "Organize the streams belonging to one meaningful scenario.",
        "A business scenario needs an explicit name and local processing structure.",
        "You need an automatic queue, new process, or durable execution boundary.",
        [("Service", "pipeline")]),
    "component": _guide(
        "Name equivalent connected fragments for visual folding, without runtime effects.",
        "Concrete repeated fragments should be recognizable as the same responsibility.",
        "You need a callable subgraph or want to group arbitrary unrelated nodes.",
        [("Service", "component"), ("Component", "fragment")], semantics="visual-components"),
    "type": _guide(
        "Define the value contract shared by graph stages.",
        "A message, key, collection, or API value needs an explicit type.",
        "Only a local implementation variable needs a type.",
        [("Project", name) for name in ("struct_type", "array_type", "map_type", "custom_type")]),
    "pool": _guide(
        "Configure worker concurrency and queue capacity for explicitly scheduled calls.",
        "An existing graph edge should use a worker pool.",
        "You merely need to expand an iterable or broadcast a message.",
        [("Project", "pool"), ("Stream", "task_pool_call"), ("Stream", "priority_task_pool_call")],
        semantics="call-semantics"),
    "connection": _guide(
        "Connect existing same-service streams through typed Python references.",
        "A value or result must flow between already declared stages.",
        "The link crosses a service boundary; use endpoints and a transport instead.",
        [("Stream", "from_sources"), ("Stream", "function_call"),
         ("Stream", "task_pool_call"), ("Stream", "parallel_call")], semantics="authoring-api"),
    "input": _guide(
        "Receive values through a connector endpoint into the service graph.",
        "An external request, event, or scheduled invocation enters the scenario.",
        "The stage is an internal helper without a transport boundary.",
        [("Pipeline", "input")], semantics="boundaries"),
    "sink": _guide(
        "Send values through a connector endpoint; response behavior follows its contract.",
        "An external operation is an explicit stage of the architecture.",
        "A local implementation detail is being exposed only because it uses an SDK.",
        [("Pipeline", "sink")], semantics="boundaries"),
    "substream": _guide(
        "A service-local callable subgraph with typed arguments and collected results.",
        "Business code needs to invoke and collect results from a reusable graph section.",
        "You only need visual folding, a separate service, or durable queuing.",
        [("Pipeline", "substream")], semantics="substreams"),
    "map": _guide(
        "Transform a value into a result through a business function.",
        "A meaningful stage transforms the message without collection expansion.",
        "The function emits multiple values or selects a branch.",
        [("Pipeline", "map")], semantics="operator-selection"),
    "filter": _guide(
        "Pass or discard a value according to a predicate.",
        "A business condition decides whether the message continues.",
        "Both accepted and rejected outcomes require separate routes; consider Case/When.",
        [("Pipeline", "filter")], semantics="operator-selection"),
    "flat-map": _guide(
        "A business function emits zero or more values per input.",
        "The scenario explicitly expands one message into multiple messages.",
        "Each consumer should receive the same unchanged message; use Split.",
        [("Pipeline", "flat_map")], semantics="fan-out", patterns=("iterable-worker-aggregation",)),
    "flat-map-iterable": _guide(
        "Expand an iterable value into its elements without a business function.",
        "The input is already a collection and each element becomes a graph message.",
        "You need to broadcast the whole collection or choose execution concurrency.",
        [("Pipeline", "flat_map_iterable")], semantics="fan-out", patterns=("iterable-worker-aggregation",)),
    "key-by": _guide(
        "Associate a correlation key with each value.",
        "A later keyed aggregation needs to match related messages.",
        "There is no defined correlation rule; do not invent one from arrival order.",
        [("Pipeline", "key_by")], semantics="operators", patterns=("iterable-worker-aggregation",)),
    "join": _guide(
        "Combine two keyed sources through a business function and join policy.",
        "Results from two sources must be correlated by key.",
        "You only need forwarding, or have not decided retention and partial failure.",
        [("Pipeline", "join")], semantics="operators", patterns=("iterable-worker-aggregation",)),
    "multi-join": _guide(
        "Combine one primary and one or more additional keyed sources.",
        "A stage requires correlated values from multiple sources.",
        "You assume completion or retention without defining the collection contract.",
        [("Pipeline", "multi_join")], semantics="operators", patterns=("iterable-worker-aggregation",)),
    "merge": _guide(
        "Forward compatible messages from multiple sources into one stream.",
        "Alternative or independent routes should continue through the same stage.",
        "You need synchronization or keyed aggregation; Merge is not Join.",
        [("Pipeline", "merge")], semantics="operator-selection"),
    "split": _guide(
        "Broadcast each message to multiple consumers.",
        "Several independent stages must receive the same value.",
        "You need iterable expansion or a mutually exclusive choice.",
        [("Pipeline", "split")], semantics="fan-out", patterns=("broadcast-fan-out",)),
    "case": _guide(
        "Select a branch using the index returned by the business function.",
        "A process-level decision selects among ordered When branches.",
        "All branches should receive every message, or the condition is only local code.",
        [("Pipeline", "case")], semantics="conditional-routing", patterns=("conditional-routing",)),
    "when": _guide(
        "Declare an ordered branch selected by a Case node.",
        "You are adding an explicit outcome of an existing Case decision.",
        "You expect When to evaluate its own independent predicate.",
        [("Pipeline", "when")], semantics="conditional-routing", patterns=("conditional-routing",)),
    "process": _guide(
        "Represent a business stage using the selected Process execution/collection contract.",
        "The stage requires Process-specific behavior rather than a narrow transformation.",
        "Map, Filter or FlatMap already expresses the intended contract.",
        [("Pipeline", "process")], semantics="operator-selection"),
    "delay": _guide(
        "Schedule deferred processing using the operator's duration and function contract.",
        "A delay is meaningful at the process level.",
        "You require restart-safe workflow timers or are exposing an internal wait.",
        [("Pipeline", "delay")], semantics="operator-selection", patterns=("bounded-feedback",)),
    "cycle-link": _guide(
        "Declare an intentional feedback edge through the graph's cycle mechanism.",
        "A process must revisit an earlier stage under an explicit termination policy.",
        "The loop has no deadline, attempt limit or progress condition.",
        [("Pipeline", "cycle_link")], semantics="operators", patterns=("bounded-feedback",)),
    "error": _guide(
        "Handle the failure flow of a supported owning stream.",
        "Failure changes process continuation, compensation or the business outcome.",
        "The error is handled entirely inside a business function.",
        [("Pipeline", "error"), ("Stream", "on_error")],
        semantics="operators", patterns=("failure-compensation",)),
}

_ENDPOINTS = {
    "http": ("HttpConnector", ("get", "post", "put", "patch", "delete", "head", "options", "trace", "connect")),
    "grpc": ("GrpcConnector", ("unary_method", "client_streaming_method", "server_streaming_method", "bidirectional_streaming_method")),
    "kafka": ("KafkaConnector", ("topic",)),
    "cron": ("CronConnector", ("schedule",)),
    "temporal": ("TemporalConnector", ("activity", "workflow")),
    "custom": ("CustomConnector", ("endpoint",)),
}
for _transport, (_owner, _methods) in _ENDPOINTS.items():
    OBJECT_GUIDES[f"{_transport}-endpoint"] = _guide(
        f"Declare a {_transport} endpoint on a connector, then reference it from Input/Sink as supported.",
        "The architecture needs an explicit external interaction or trigger.",
        "Only an internal graph edge is needed. Endpoint declaration alone does not wire a pipeline.",
        [("Project", f"{_transport}_connector"), *[(_owner, method) for method in _methods]],
        semantics="transports",
        patterns={"kafka": ("kafka-processing",), "temporal": ("temporal-sequential", "temporal-parallel", "temporal-scheduled")}.get(_transport, ()),
    )


def architecture_object_index() -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "sourceOfTruth": "typed Python DSL; this catalog is guidance, not another model",
        "objects": [
            {"kind": kind, "purpose": guide["purpose"],
             "resource": f"servicegen://authoring/object-{kind}"}
            for kind, guide in sorted(OBJECT_GUIDES.items())
        ],
    }


def describe_architecture_object(kind: str) -> dict[str, Any]:
    """Return one bounded, intent-first guide with live DSL signatures."""
    normalized = kind.strip().casefold().replace("_", "-")
    guide = OBJECT_GUIDES.get(normalized)
    if guide is None:
        return {
            "schemaVersion": "1.0", "status": "not_found",
            "message": f"Unknown architecture object {kind!r}",
            "indexResource": "servicegen://authoring/object-index",
        }
    return {
        "schemaVersion": "1.0", "status": "success", "kind": normalized,
        **{key: value for key, value in guide.items() if key != "factories"},
        "factories": [describe_typed_factory(owner, method) for owner, method in guide["factories"]],
        "capabilityRule": "Check cached servicegen://capabilities/{language}; a DSL factory is not proof of backend support.",
        "nextSteps": ["Read relevant semantics and patterns", "Edit Python using project-owned references",
                      "validate_project", "preview_architecture_diff"],
    }
