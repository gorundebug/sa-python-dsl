from __future__ import annotations

from typing import Any, Mapping


PATTERN_CATALOG: Mapping[str, dict[str, Any]] = {
    "index": {
        "selectionRule": "Choose a recipe only after completing the intent model; recipes are starting constraints, not graph macros.",
        "topics": [
            "kafka-processing",
            "iterable-worker-aggregation",
            "broadcast-fan-out",
            "conditional-routing",
            "temporal-sequential",
            "temporal-parallel",
            "temporal-scheduled",
            "failure-compensation",
            "bounded-feedback",
        ],
    },
    "kafka-processing": {
        "intent": "Consume broker messages, process them, and optionally publish results.",
        "prerequisites": ["Kafka cluster", "input topic", "consumer group", "message type"],
        "topology": ["Kafka endpoint", "Input", "narrow transformation operators", "optional Error", "optional Sink using output topic"],
        "decisions": ["delivery/idempotency", "partition key", "consumer concurrency", "retry versus error flow", "output topic"],
        "antiPatterns": ["DSL-embedded Kafka credentials", "missing consumer group on Input", "using Process for every transformation"],
    },
    "iterable-worker-aggregation": {
        "intent": "Process every item from one collection and combine correlated results.",
        "topology": ["FlatMapIterable or FlatMap", "KeyBy when aggregation needs correlation", "worker stream", "Error decision", "Join or MultiJoin"],
        "decisions": ["item type", "correlation key", "worker call semantics", "pool capacity", "join storage", "TTL", "partial failure policy"],
        "antiPatterns": ["using Split to expand an iterable", "using ParallelCall as collection expansion", "joining unkeyed streams", "stateful join without retention decision"],
    },
    "broadcast-fan-out": {
        "intent": "Deliver every unchanged message to multiple independent consumers.",
        "topology": ["source", "Split", "two or more consumer edges", "optional keyed aggregation"],
        "decisions": ["call semantics per edge", "whether completion waits for branches", "branch-specific error handling"],
        "antiPatterns": ["using Split when outputs are elements of an iterable", "adding Join when no result synchronization is required"],
    },
    "conditional-routing": {
        "intent": "Select exactly one typed branch for each message.",
        "topology": ["source", "Case Function returning zero-based index", "ordered When branches"],
        "decisions": ["branch order", "result types", "unmatched/out-of-range behavior", "recombination need"],
        "antiPatterns": ["multiple unconditional edges for mutually exclusive behavior", "assuming When evaluates its own condition"],
    },
    "temporal-sequential": {
        "intent": "Execute durable steps in a defined order with retries or compensation.",
        "topology": ["on-demand or scheduled Workflow endpoint", "Workflow Input", "Activity Sink/Input pairs in sequence", "Workflow result"],
        "decisions": ["task queues", "worker concurrency", "Activity timeouts", "retry ownership", "workflow execution timeout", "compensation"],
        "antiPatterns": ["side effects in Workflow code", "schedule fields on an on-demand endpoint", "confusing Activity retry with compensation"],
    },
    "temporal-parallel": {
        "intent": "Run several durable Activities concurrently and combine their results.",
        "topology": ["Workflow", "explicit Activity branches", "result observation", "deterministic aggregation"],
        "decisions": ["all-or-partial success", "cancellation", "per-Activity retry/timeout", "aggregation order"],
        "antiPatterns": ["using stream ParallelCall as a substitute for Workflow fan-out semantics", "leaving partial failure undefined"],
    },
    "temporal-scheduled": {
        "intent": "Start a durable Workflow or Activity from a Temporal namespace schedule.",
        "prerequisites": ["five-field cron expression", "stable schedule ID", "timezone"],
        "decisions": ["overlap policy", "missed-run policy", "endpoint enabled state", "task queue"],
        "antiPatterns": ["changing a published schedule ID casually", "supplying only expression or only schedule ID", "using Temporal schedule ID for ordinary Cron"],
    },
    "failure-compensation": {
        "intent": "Make failure flow and any compensating action explicit.",
        "topology": ["Input, Process, or Sink owner", "Error stream", "classification", "optional compensation branch"],
        "decisions": ["retryable versus domain failure", "fail-fast versus partial result", "idempotency", "compensation ordering"],
        "antiPatterns": ["Error stream without owner edge and on_error", "retry and compensation treated as the same mechanism", "more than one Error consumer per owner"],
    },
    "bounded-feedback": {
        "intent": "Feed a result back into an earlier stage deliberately.",
        "topology": ["acyclic forward graph", "CycleLink", "explicit feedback target"],
        "decisions": ["termination predicate", "maximum attempts or deadline", "delay/backoff", "failure destination"],
        "antiPatterns": ["ordinary graph cycle", "feedback with no bounded-progress rule", "retry loop without idempotency"],
    },
}


REVIEW_CHECKLIST = {
    "identity": ["Names derive stable unique keys", "references use project-owned objects"],
    "types": ["Every edge has compatible value types", "KeyBy uses a comparable key type", "Join inputs share key type"],
    "boundaries": ["Input/Sink use the intended endpoint direction", "runtime credentials are not embedded", "disabled endpoints are intentional"],
    "cardinality": ["FlatMap changes cardinality", "Split only broadcasts", "Case selects one ordered When"],
    "execution": ["Call semantics are selected per existing edge", "pool concurrency and capacity are intentional", "priority range and direction are understood"],
    "state": ["Join storage is supported", "TTL and renewTTL match retention needs", "correlation is explicit"],
    "failure": ["Failure owner has at most one Error stream", "retry, domain failure, and compensation are distinct", "partial failure behavior is stated"],
    "durability": ["Temporal is used only for durable orchestration", "Workflow code remains deterministic", "timeouts and retry ownership are explicit"],
    "scheduling": ["Cron expression is five-field", "Temporal schedule has stable ID", "timezone/overlap/missed-run policies are intentional"],
    "cycles": ["Only CycleLink closes feedback", "termination or bounded progress is explicit"],
    "proof": ["validate_project succeeds", "semantic diff matches the intent card", "canonical YAML is exported only after review"],
}
