---
name: service-architect-implementation
description: Implement, change or review business code, maker dependencies and runtime wiring in generated Service Architect services. Use alongside modeling guidance when a change affects the process; not for unrelated application code.
---

# Implement the modeled process

Read `servicegen://authoring/implementation-guidelines` before changing sources,
sinks, makers or lifecycle integration. Use `describe_architecture_object` and
cached capabilities to find the existing mechanism; read actual SDK contracts and
canonical examples before deciding that a capability is missing. These resources
are guidance, not an alternative DSL or proof of backend support.

## Keep the model and code aligned

For process-level changes, edit typed Python first, validate and inspect the
semantic diff, export, generate/merge, then implement the generated contracts
within the authorized scope. For implementation-only changes that preserve the
process contract, avoid unnecessary model edits and generation.

The graph shows independently meaningful stages and execution choices, not AST.
Keep algorithms, SQL, encodings and local data structures inside cohesive stages.
Use native endpoints, Cron, Delay, result/error paths and pools for their supported
jobs. Do not conceal broker consumers/producers or background orchestration in
Process or a Custom Sink when a standard endpoint covers the requirement.

Every independent handler owns a named pipeline with fresh processing, error and
reply nodes. Reuse business function identities on separate nodes. Shared factories
must create fresh flows. Do not merge unrelated inputs because they share types
or functions, or add routing just to send their responses back. Real business
joins and callable SubStreams still have legitimate explicit purposes.

Inject only the capabilities each stage needs through its maker. Service-owned
shared state is valid; global service scopes and service locators in every stage
are not. Carry actual business inputs, plans and results in typed messages, not
private context/global registries hidden behind IDs. Records use `struct_type`;
interfaces and genuinely opaque types use `custom_type`.

Propagate the received context. Respect the actual consumer/result/error and
SubStream invocation contracts; they are not interchangeable. For potentially
missing results, inspect the canonical Process Order work/Delay/result-merge
pattern. Specify no-work, timeout, correlation and late-result behavior without
inventing callback success, collector lifetime tracking or a parallel dispatcher.

Identify each pipeline's endpoint, scheduled, SubStream or startup/CLI trigger.
Before changing SDK startup, inspect concurrency and cancellation and consider
narrow application-owned readiness/checkpoint coordination through makers.
Temporal is for durable orchestration, not every periodic or low-latency operation.

## Keep extensions and ownership explicit

An SDK change requires a demonstrated reusable gap after considering standard
contracts and a simpler application design. Application policy and batching belong
in user capabilities and supported endpoint properties/configuration, not new
product-specific SDK/DSL fields. Internal helpers implementing declared SDK
contracts are different from optional hooks that invisibly select behavior.

For general SDK semantic changes, check all applicable implementations and their
generated contracts. C++ userver and C++ Coro remain independent. Record missing
support and unverified cases; do not patch upstream or silently weaken guarantees.

Keep API contract modules separate from service implementations and unrelated
shared libraries. Implement a public modeled type in its declared owning module;
consumers import it, not the reverse. Do not leave a public alias pointing at a
consumer's private implementation or application model as a substitute for the
declared contract. For request-local graph values, model a private local type
instead of inventing an external contract module solely to share business code.
Audit sibling types, generated imports/serdes and module dependencies after such
a correction; remove obsolete managed contract artifacts only after tracing users.

Preserve the original error at internal failure boundaries so callers can inspect
its cause (for Go, errors.Is/As). Context cancellation is additional evidence, not
a replacement for a failed Scan/Commit/read. Redact public responses at the API
boundary; do not erase the internal cause to produce a safe public classification.

Use the destination project's merge entrypoint and hooks;
a fresh archive's default hook is not the installed project's policy. Preserve
existing template path/name headers and ownership contracts. Review stale-file
removal and protect user-owned files and data.

## Implement request-driven storage with Query

For Query work, read `servicegen://semantics/query` for the selected backend's
operations and limitations. Query is independent from Sink: the connector selects
the library, the endpoint selects the operation, and the stream declares emitted
result types. It can emit zero or many results. `EndRequest(..., out)` allows an
application-defined completion value; do not add a separate completion port.
Empty success emits zero values. If a callable SubStream awaits a reply, define
the application's empty/error reply or use a caller deadline; routing an error
does not itself return a SubStream result.

Create shared pools and native clients through service infrastructure makers,
as for gRPC. Endpoints reuse them; main and per-request handlers do not create
clients. Preserve native resource ownership through service shutdown, release
request cursors/bodies before EndRequest, and use the received context. Completion
of Query is not proof that asynchronously scheduled downstream work has finished.
The normal error lifecycle is not a panic/process-crash recovery guarantee.
Keep downstream business errors on their own Error paths; do not label an
exception from downstream code as a native database/storage failure.

Use parameterized native query builders or user-owned SQL files. Keep secrets in
runtime configuration. Do not silently retry partial results or writes whose
outcome is unknown. Check native buffering and pagination capabilities rather
than assuming every S3 implementation streams bytes or uses identical tokens.
Go's default Bun connector uses pgx through database/sql for native cancellation;
custom pool makers must preserve request cancellation and deadlines. Rust Query
handlers use `servicelib::dataquery::Collector`, matching generated endpoint
traits, and delegate delivery to the ordinary graph collector.
Authoring support alone does not prove runtime acceptance for a target language.

## Verify connected behavior

Complete the connected capability before heavyweight acceptance. Prepare tests
alongside implementation; fix errors autonomously within scope and repeat only
affected checks. Compile and exercise generated paths through their actual makers,
endpoints and result/error connections. A direct function test or YAML export is
not proof of runtime wiring. Report implemented versus verified behavior separately
and keep the functional plan current.

Use `servicegen://authoring/review-checklist` before completion. For code-call
navigation, current Go IDE analysis runs only on Refresh over saved sources and
resolved dependencies; it follows helper/interface calls to modeled business
ancestors. Multiple ancestors mean multiple links, none means no business link.
The overlay is read-only static evidence, not persisted topology or runtime proof.
