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
shared libraries. Use the destination project's merge entrypoint and hooks;
a fresh archive's default hook is not the installed project's policy. Preserve
existing template path/name headers and ownership contracts. Review stale-file
removal and protect user-owned files and data.

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
