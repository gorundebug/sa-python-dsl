# Semantic authoring playbook

Use this playbook before creating or changing a non-trivial Service Architect
topology. The goal is to translate business intent into explicit graph semantics
instead of guessing an API from words in the prompt.

## 1. Build an intent card

Record these decisions before editing:

| Axis | Questions |
|---|---|
| Trigger | HTTP, gRPC, broker message, Cron, Temporal schedule, or internal stream? |
| Cardinality | One value, an iterable to expand, callback-produced zero-or-more values, or unchanged messages to broadcast? |
| Ordering | Sequential, unordered parallel, keyed ordering, or priority ordering? |
| Completion | Does the caller wait, observe later, or ignore the result? |
| Execution | In-process function, worker pool, priority pool, or independent parallel call? |
| Durability | Ordinary stream execution or durable Temporal orchestration? |
| Correlation | What key associates branches, replies, and joined results? |
| Failure | Fail the flow, route to an Error stream, retry, compensate, or collect partial failures? |
| Schedule | On demand, five-field Cron, or Temporal schedule with stable schedule ID? |

If a missing answer changes the graph shape, ask one focused question. If it
only affects a non-critical default, state the assumption.

## 2. Choose topology before call semantics

Topology answers where values flow. Call semantics answer how one persisted
edge invokes its consumer. Never use a call semantic as a substitute for a
missing graph operator.

### Expansion, fan-out, and fan-in

For "process every item in parallel":

1. Use `flat_map_iterable` when the incoming value is already an iterable, or
   `flat_map` when a Function must produce zero or more item values.
2. Optionally use `key_by` to produce `KeyValue<K,V>` when a keyed operation or
   later correlation requires it.
3. Use `split` only when every resulting item must be broadcast unchanged to
   multiple downstream consumers.
4. Connect each item to the worker stream using the required invocation semantics.
5. Route worker failures explicitly.
6. Join or multi-join keyed results only when aggregation is required.

`Split`, `ParallelCall`, and `PriorityTaskPool` do not expand an iterable.
`FlatMap` and `FlatMapIterable` change cardinality but do not select a worker
pool or create multiple downstream branches.

### Independent branches

For "send each message to A and B", create both graph edges, normally through an
explicit Split when the branch point is part of the architecture. Use
`parallel_call()` only when an edge must dispatch every incoming message using
runtime parallel-call semantics without a pool. Add a join only when downstream
processing must wait for or combine keyed branch results.

### Conditional routing

Use Case with ordered When streams for mutually selected branches. The Case
Function returns the zero-based index of exactly one attached When. Document
out-of-range/unmatched behavior and do not model a condition as multiple
unconditional outgoing links.

### Correlated aggregation

Use Join for exactly two `KeyValue` flows. Use MultiJoin for one primary and one
or more ordered additional `KeyValue` flows. Every input must have the same key
type; MultiJoin value types may differ. Establish key and correlation behavior
before adding either operator; arrival order is not correlation.

Join accepts `INNER`, `LEFT`, `RIGHT`, or `OUTER`; MultiJoin has no `join_type`
argument in the typed API. Both require configured storage. TTL is milliseconds;
a positive TTL bounds retained state, and `renew_ttl` extends retention on new
arrivals while the callback keeps the key. The join callback result determines
whether retained values are complete and can be cleared.

### Operator selection

| Intent | Operator |
|---|---|
| Transform one input into one output | `map` |
| Retain or discard the input | `filter` |
| Perform side-effect/output processing with an error output | `process` |
| Produce zero or more outputs using a Function | `flat_map` |
| Expand an already iterable input without a Function | `flat_map_iterable` |
| Produce `KeyValue<K,V>` for keyed processing | `key_by` |
| Combine compatible streams without a callback | `merge` |
| Broadcast each message to several consumers | `split` |
| Select exactly one ordered branch | `case` + `when` |
| Defer delivery by a computed/fixed duration contract | `delay` |
| Close an intentional feedback loop | `cycle_link` |

For Process, `EXECUTE` performs a side effect and may synchronously emit zero or
more results. `COLLECT` accumulates and emits results in a batch. Do not choose
Process merely because the business text says "process".

## 3. Choose invocation semantics

| Intent | Typed API | Required arguments | Important exclusion |
|---|---|---|---|
| Invoke directly under function-call semantics | `source.function_call(target, async_=...)` | optional `async_` | Not a worker queue |
| Submit to a worker pool | `source.task_pool_call(target, pool=workers)` | `pool` | Does not express priority |
| Submit to a prioritized worker queue | `source.priority_task_pool_call(target, pool=workers, priority=n)` | `pool`, `priority` | Does not create fan-out |
| Dispatch every incoming message without a pool | `source.parallel_call(target)` | none | Does not expand iterables or create graph branches |

First declare the edge using `source >> target`, `target << source`, `source=`,
`sources=`, or `from_sources()`. Only then call a specialized method. The call
method annotates and validates an existing edge; it does not create one.

`>>` sets the target's primary source and returns the target. `<<` appends an
additional source and returns the target. `from_sources()` replaces the complete
multi-source list. Keep one obvious wiring statement per relationship.

When the service default already expresses the desired semantics, keep only the
ordinary graph connection and do not persist a redundant Link override. Never
create Link metadata for streams that are not actually connected.

TaskPool is a named FIFO queue. `executors_count` controls worker concurrency and
must be positive; `queue_capacity` is an initial queue capacity and defaults to
256. PriorityTaskPool processes larger priority values first; Designer accepts
priority values from 0 through 255.

Do not combine unsupported semantics by passing invented parameters. If the
topology needs fan-out plus a priority pool, model fan-out explicitly and use
`priority_task_pool_call()` on the worker invocation edge.

## 4. Failure design

Every failure-capable boundary needs an explicit decision:

- Input, Process, and Sink can expose a dedicated error relationship. Connect
  the owner to an Error stream and then register `owner.on_error(error_stream)`.
- An owner has at most one error consumer, and the Error stream must belong to
  the same service.
- Keep transport/runtime retry behavior distinct from domain error streams.
- For fan-out, decide whether one failed item fails the aggregate or becomes a
  collected partial result.
- For Temporal, distinguish Activity retry from Workflow-level compensation.
- Do not invent an Error link to a normal stream; validation requires an Error
  stream and a real graph connection.

## 5. Temporal and scheduling

Use Temporal Workflow for durable orchestration and Temporal Activity for an
externally executed operation. A Temporal Sink is an on-demand submission path;
it does not imply a schedule.

For scheduled Temporal execution, provide both a portable five-field cron
expression and a stable schedule ID. Keep both empty for on-demand endpoints.
For an ordinary Cron endpoint, the cron expression is required and Temporal
schedule ID does not apply. Timezone is explicit and defaults to UTC where the
product contract allows it.

## 6. External boundaries

Input admits messages from an Endpoint; Sink submits messages through an
Endpoint. Choose the concrete connector endpoint before the boundary stream:

- HTTP supports typed GET and POST routes. Route path is required and unique per
  connector. A dedicated listener is not supported for C++ userver.
- gRPC requires a contract Module and a unary, client-streaming,
  server-streaming, or bidirectional-streaming method. A Sink also requires the
  connector address.
- Kafka requires cluster brokers and topic. An Input additionally requires a
  consumer group. Credentials belong to runtime configuration, not the DSL.
- Custom is an in-process connector intended for internal/testing integration.
- Cron is process-local scheduling. Temporal is durable service-backed work.

Endpoint names are globally unique because streams reference endpoint identity.
When an endpoint is disabled it remains in the graph, but its transport or
scheduler integration is not started.

## 7. Intentional cycles

Do not create an ordinary graph cycle. Use `cycle_link` to make feedback explicit
and keep the remaining graph acyclic. State the termination, delay, deadline, or
other bounded-progress rule; an unbounded feedback loop is not a complete design.

## 8. Edit and prove

1. Inspect the project without executing authoring code.
2. Read the relevant semantic resources.
3. Present a compact proposed topology when the change is complex.
4. Edit only typed Python declarations.
5. Validate the project.
6. Preview the semantic architecture diff.
7. Compare entities, links, errors, schedules, and call semantics with the intent
   card. Correct the Python model when they differ.
8. Export canonical YAML only after the semantic review succeeds.

Validation proves that a graph is legal. The intent card and semantic diff prove
that the legal graph is the graph the user asked for.
