# Typed Python pattern recipes

The maintained catalogue has two parts: intent and design decisions in
`src/sa_dsl/architecture_patterns.py`, and complete model-construction examples
with explicit contracts in `src/sa_dsl/pattern_recipes.py`. Both are served through
`servicegen://patterns/<name>`; `servicegen://patterns/index` lists the available
recipes. This is guidance over the typed DSL, not a second architecture model.

## Selecting a recipe

Read the recipe's `useWhen` and `avoidWhen` before copying its topology. Each recipe
states six contracts: types, cardinality, execution, correlation, completion and
failure. Its `objects` links lead to object guides with reflected, current Python
factory signatures. Consult the target runtime's capabilities before selecting
operators or transports. The examples use Go; that does not imply every other
runtime supports every combination.

| Resource suffix | Purpose | Important boundary |
| --- | --- | --- |
| `http-request-response` | A request, one meaningful stage, one response | Result binding is not a second processing cycle |
| `kafka-processing` | Process a delivered broker message | Consumer groups do not guarantee exactly-once side effects |
| `broadcast-fan-out` | Deliver each value to independent observers | Split neither expands a collection nor waits for all results |
| `iterable-worker-aggregation` | Expand a collection and collect invocation-local results | The business collector decides completion and partial failure |
| `conditional-routing` | Select one ordered alternative | When does not evaluate its own predicate |
| `failure-compensation` | Explicit error routing and recovery | Error routes an already-typed failure; it does not convert it |
| `bounded-feedback` | Revisit a stage through CycleLink | Business code must implement and test the termination bound |
| `temporal-sequential` | Call durable Activities in order | Side effects belong in Activities, not Workflow code |
| `temporal-parallel` | Orchestrate independent Activity calls | Workflow-safe concurrency is implemented by the business function |
| `temporal-scheduled` | Start durable work from a namespace schedule | Stable schedule identity, overlap and missed-run policies matter |

## Applying a recipe to an existing project

1. Use `inspect_python_authoring` to locate declarations, insertion sites and the
   current source revision. Do not flatten the user's factories into a new file.
2. Use `add_node`, `add_endpoint` or `connect_ports` for one operation, or
   `preview_python_changes` for a coherent batch. These prepare a preview, not an
   immediate source edit.
3. Inspect both the source diff and architecture diff. An edit inside a shared
   factory may affect more than one pipeline instance.
4. Apply the exact preview with `apply_python_changes`. A stale source or expired
   preview requires a new preview; do not silently force an old change.
5. Implement the generated business contracts and verify runtime behavior.

A data edge, an additional input and an error output are different operations.
The error role creates both the owner-to-Error edge and the owner's `on_error`
binding. It is not enough to add only one of them.

## What the checks establish

`tests/test_pattern_recipes.py` reads the actual resource payload, executes its
Python example through the ordinary export worker, and checks object links and
contract coverage. `tests/test_mcp_catalog_protocol.py` reads the catalogues over
the real MCP stdio transport without executing project authoring code.

These checks establish model/resource correctness when they pass. They do not
prove that a business implementation is idempotent, that a collector terminates,
that Workflow code replays correctly, or that a generated service meets a latency
target. Those require business and runtime tests. The examples intentionally do
not invent implementations for those contracts.
