# Semantic authoring playbook

Use this playbook before creating or changing a non-trivial Service Architect
topology. The goal is to translate business intent into explicit graph semantics
instead of guessing an API from words in the prompt.

## 1. Build an intent card

Record these decisions before editing:

| Axis | Questions |
|---|---|
| Trigger | HTTP, gRPC, broker message, Cron, Temporal schedule, or internal stream? |
| Cardinality | One value, a collection to partition, or several independent branches? |
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

### Collection fan-out and fan-in

For "process every item in parallel":

1. Split the collection into item messages.
2. Optionally key items when ordering or correlation is required.
3. Send each item to the worker stream using the required invocation semantics.
4. Route worker failures explicitly.
5. Join or multi-join results using an explicit correlation strategy.

`ParallelCall` alone does not split a collection. `PriorityTaskPool` alone does
not introduce parallel branches.

### Independent branches

For "call A and B independently", create both graph branches. Use
`parallel_call()` only when the runtime invocation itself must use parallel-call
semantics. Add a join only when downstream processing must wait for or combine
their results.

### Conditional routing

Use Case When for mutually selected branches and document the unmatched/default
behavior. Do not model a condition as multiple unconditional outgoing links.

### Correlated aggregation

Use Join when combining the defined paired inputs. Use MultiJoin when collecting
multiple named branches. Establish the correlation/key behavior before adding
either operator; arrival order is not a correlation strategy.

## 3. Choose invocation semantics

| Intent | Typed API | Required arguments | Important exclusion |
|---|---|---|---|
| Invoke directly under function-call semantics | `source.function_call(target)` | none | Not a worker queue |
| Submit to a worker pool | `source.task_pool_call(target, pool=workers)` | `pool` | Does not express priority |
| Submit to a prioritized worker queue | `source.priority_task_pool_call(target, pool=workers, priority=n)` | `pool`, `priority` | Does not create fan-out |
| Dispatch an independent parallel call | `source.parallel_call(target)` | none | Does not partition collections |

When the service default already expresses the desired semantics, prefer the
ordinary graph connection and do not persist a redundant Link override. Create
a specialized link method at the same place where the stream connection is
declared. Never create a Link for streams that are not actually connected.

Do not combine unsupported semantics by passing invented parameters. If the
topology needs fan-out plus a priority pool, model fan-out explicitly and use
`priority_task_pool_call()` on the worker invocation edge.

## 4. Failure design

Every failure-capable boundary needs an explicit decision:

- Route domain or processing failures through the supported Error connection.
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

## 6. Edit and prove

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
