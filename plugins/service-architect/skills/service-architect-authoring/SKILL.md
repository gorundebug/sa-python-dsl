---
name: service-architect-authoring
description: Create or modify Service Architect topology projects whose editable source of truth is the typed sa-python-dsl API.
---

# Service Architect authoring

The graph reduces the context needed to understand the system, change it, and
review its behavior. It records explicit functional constraints for the agent;
it is not intended to describe or generate all implementation code. Preserve
those constraints during edits, and do not treat omitted internals as permission
to change behavior. Code generation is a supporting capability.

Before decomposing business logic, read
`../service-architect-business-modeling/SKILL.md` and the MCP resource
`servicegen://authoring/business-modeling`. Expose meaningful business stages
and process-level execution boundaries, not every function call, condition,
loop, or internal wait. Operator examples demonstrate capabilities, not a
mandatory decomposition. One function may implement an entire cohesive stage.

Start by calling `inspect_project` on the project root. Use its entrypoint and
manifest metadata to locate the Python model. Do not execute project Python just
to discover its structure.

For any change involving more than one stream, cardinality changes, concurrency, fan-out/fan-in,
conditional routing, task pools, errors, schedules, Temporal, or cross-service
communication, read `references/semantic-playbook.md` before editing. Also read
the relevant `servicegen://semantics/{topic}` resources. Do not select an API
method from a keyword alone: classify the trigger, cardinality, execution
boundary, completion behavior, durability, correlation, and failure path first.

Separate cardinality, topology, and invocation semantics. `FlatMap` or
`FlatMapIterable` expands one value into multiple values. `Split` broadcasts
each existing value to multiple graph consumers. `PriorityTaskPool` selects a
priority worker queue, while `ParallelCall` dispatches each incoming message
without a pool; neither operation expands a collection. For boundaries chosen
to be graph-visible, model each concern explicitly, then choose the call
semantics for each existing graph edge.

Declare a graph edge before assigning specialized call metadata. First use
`source >> target`, `target << source`, a factory `source`/`sources` argument, or
`from_sources()`. Only then call `source.function_call(target, ...)`,
`task_pool_call`, `priority_task_pool_call`, or `parallel_call`. These methods
validate and annotate an existing edge; they do not create it.

When a requirement has multiple materially different graph interpretations,
state the ambiguity and ask one focused question before editing. Do not silently
invent ordering, delivery, correlation, retry, compensation, or scheduling
semantics.

For an unfamiliar factory or method, read
`servicegen://authoring/object-index` or call `describe_architecture_object`
first to understand its purpose, use/avoid criteria and related recipes. Request
one object at a time; the returned factories contain live DSL signatures.
For the full method catalog, read
`servicegen://authoring/typed-api` instead of guessing its signature. Before
choosing a connector for a target language, read
`servicegen://authoring/connector-capabilities`, then read the authoritative
cached backend contract at `servicegen://capabilities/{language}`. If the cache
is unavailable or `doctor` reports a capability incompatibility, call
`refresh_capabilities` and read it again before editing. This refresh is an
explicit public network operation; passive resource reads never perform it.
Absence of a connector, endpoint kind, implementation, stream operator, call
semantics, or feature is not permission to substitute a similarly named value.
Do not hand-edit `.service-architect/capabilities.json`. For a known architecture
shape, select a recipe from `servicegen://patterns/index` and read
that recipe's decisions and anti-patterns before editing.

Keep validation metadata synchronized with capabilities. If
`servicegen://workspace/current/validation-contract` is unavailable or `doctor`
reports a revision mismatch, call `refresh_validation_contract`. For every
returned `SG_*` diagnostic, read its `validationRuleUri` before repairing the
model. Apply the catalog remediation to the reported path and details, but never
reimplement or bypass a rule whose evaluator is `servicegen`.

Treat typed Python as the editable source of truth. Treat the canonical YAML path
reported by the manifest as a generated interchange artifact; do not edit it to
make an architectural change.

Prefer concrete factories such as pipeline stream factories, connector endpoint
factories, and type factories. They expose only properties valid for that entity.
Use object references for modules, packages, pools, types, pipelines, endpoints,
and streams rather than repeating serialized string keys.

Keep declarations in their domain folders: project, services, pipelines,
connectors, endpoints, modules, packages, pools, and types. Connect internal
pipeline streams in the pipeline module and cross-pipeline or cross-service
relationships in the owning service module.

For visual components, read `servicegen://semantics/visual-components` and its
linked API signatures before editing. Components annotate equivalent connected
fragments, not whole-pipeline groups or runtime wrappers. Declare and connect
the concrete streams first, then register repetitions with `service.component`
and `component.fragment`; retain their existing function identities. Do not
introduce nested/overlapping membership or `component_instance`. After changing
member functions, types or links, validate equivalence again; use the Designer's
explicit Rebuild preview rather than silently rewriting the business topology.

For supported additions, use `inspect_python_authoring` to get the exact source
revision and an insertion site. `add_node`, `add_endpoint` and `connect_ports`
prepare previews rather than immediately changing source. Use
`preview_python_changes` for a connected batch that must validate as a whole.
Argument values are typed Python expressions and references, not another JSON
graph model. Preserve existing names, functions and module organization.

Review both sourceDiff and architectureDiff, including every affected instance
of a shared factory, before `apply_python_changes`. An expired or stale preview
must be rebuilt, not forced through. Application is atomic for one source file;
the editor does not rewrite existing expressions or flatten a modular project.
If the edit site is unsupported, use the explicit diagnostic rather than
silently regenerating Python from YAML.

For `connect_ports`, `data` creates the primary edge, `additional` appends a
Join/MultiJoin/Merge input with `<<`, and `error` creates the edge and registers
the owner's Error consumer. Do not use a primary connection to append a second
input. Review Case branch order and result bindings explicitly. No invocation
semantics is inferred by this operation.

When a pattern resource provides example code, treat it as checked model
construction, not implemented business logic or proof of runtime behavior.
Choose domain types and completion/failure policies before adapting the example.

After an edit, use `validate_project`. Export canonical YAML only after validation
succeeds.

After a complex edit, call `preview_architecture_diff` and review the semantic
entities and links against the user's intent. Validation proves model integrity;
it does not prove that the selected topology implements the intended behavior.
Use `servicegen://authoring/review-checklist` for the final architecture review.

For a YAML-only architecture, call `import_yaml_project` with workspace-relative
source and output paths. The output must be absent or empty. Treat the resulting
Python project as a migration candidate until validation and YAML round-trip agree.

## Projects inside a workspace

Use the `resources` links returned by `inspect_project` for the selected project.
`servicegen://workspace/current/*` always refers to the registered workspace root;
calling a tool with `project_path` does not change a global current project.
For a nested project, the returned links scope the canonical graph, audit, business
tasks and backend metadata to that project. Use these links as returned, including
encoded spaces and path separators. Reads are passive; validate/export explicitly
when a fresh canonical snapshot is required.
