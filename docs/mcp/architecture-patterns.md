# Architecture patterns: working specification

This is the engineering design file for the agent-facing recipe collection.
The existing machine-readable recipes live in
`src/sa_dsl/architecture_patterns.py` and are served as
`servicegen://patterns/{topic}`. They already contain intentions, decisions and
anti-patterns. The richer specifications below are the next acceptance target,
not a claim that executable pattern instantiation is already implemented.

## Common recipe contract

Every recipe must state its business responsibility, when to use it and when not
to use it, required project-owned objects, value/key types, cardinality, ordering,
execution boundaries, completion, correlation, retention, errors and durability.
List unresolved decisions rather than inventing business policy. Include exact
DSL API links, a runnable Python example, and positive/negative tests. Examples
are graph-visible business stages, not a prescription to expose every helper.

The recipe should be selectable before editing and reviewable after editing.
Its expected semantic diff and business implementation obligations must be clear.

## Existing recipes to complete

| Recipe | Purpose | Decisions that must remain explicit |
| --- | --- | --- |
| kafka-processing | Consume business events and optionally publish results | Consumer group, key, duplicate handling, retry owner, completion/ack behavior |
| iterable-worker-aggregation | Expand items, process them and correlate results | Item/correlation type, scheduling, result completion, TTL, partial failure |
| broadcast-fan-out | Send the same value to independent branches | Per-edge scheduling, branch failures, whether any aggregation is needed |
| conditional-routing | Select a business outcome through Case/When | Ordered branch indices, invalid index behavior, recombination |
| temporal-sequential | Execute durable activities in sequence | Task queues, timeouts, retries, idempotency, compensation |
| temporal-parallel | Coordinate concurrent durable activities | Completion condition, cancellation, aggregation order, partial failure |
| temporal-scheduled | Start durable work on a schedule | Stable schedule ID, timezone, overlap, missed runs |
| failure-compensation | Expose a meaningful failure and recovery route | Owner, retry versus compensation, external side effects, failure of compensation |
| bounded-feedback | Return to an earlier stage deliberately | Termination, attempts/deadline, backoff, idempotency |

## Additional recipes to specify and test

### Request / response

An endpoint receives a request, stages compute a result, and the response producer
is bound back to the request Input. Returning a result is not a second incoming
request connection. Keep transport failures distinct from a valid domain refusal.
Test the input type and result type independently. Define a bounded wait and do
not assume that a timeout rolls back work or side effects.

### HTTP to gRPC

Expose the public HTTP request and the remote service call as transport boundaries.
Use a shared gRPC endpoint contract referenced by the caller Sink and callee Input;
never create a cross-service stream edge. Decide unary versus streaming behavior,
timeouts and response mapping. The existing http-grpc semantics/example resources
are the starting point, not proof that a complete runnable recipe is bundled.

### Callable local subgraph

Use SubStream for a meaningful service-local computation called from business code.
Its entry type is the argument; the result producer defines the result type.
Decide collector completion, cancellation, deadline and correlation. Completion
does not cancel the entire subgraph and does not imply durable execution.

### Alternative business strategy

Preserve the input/output contract and compare a changed meaningful stage or path.
If topology is unchanged, use DI through the business-function maker rather than
duplicating a graph unnecessarily. Isolate side effects when evaluating alternatives.
Equivalence is established by business tests, not by visual similarity.

### Repeated visual component

Register already-declared equivalent connected fragments. Keep function identities,
types and links intact. Folding changes presentation only; do not synthesize a
runtime wrapper or create nested/overlapping memberships.

## Publication rules

Only publish examples as runnable after testing against the actual typed DSL and
validating the resulting model. Mark conceptual recipes as conceptual. Preserve
backend capability limits and never describe retry, exactly-once delivery or
compensation guarantees that the model/runtime does not provide.
