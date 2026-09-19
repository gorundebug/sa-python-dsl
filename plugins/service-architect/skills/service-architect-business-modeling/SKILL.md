---
name: service-architect-business-modeling
description: Choose meaningful business-stage boundaries when creating, migrating, or reviewing Service Architect pipelines; avoid translating source-code AST into graph nodes.
---

# Model the business process, not the AST

The graph is a compact context for understanding the system, planning changes,
and reviewing their impact. It also communicates explicit constraints on how an
agent may change functionality. Its purpose is not to represent or generate all
application code; code generation is a supporting capability, not a completeness
criterion. It is not a call graph, control-flow graph, or inventory of implementation
details. Apply this principle before choosing operators or searching for repeated
components. For MCP guidance, read
`servicegen://authoring/business-modeling`; use
`servicegen://authoring/review-checklist` when reviewing the resulting model.

## Choose meaningful boundaries

Give a stage its own node when it represents a responsibility or outcome worth
understanding or changing independently in the business process. Also expose an
execution boundary when its streaming, ordering, concurrency, completion,
durability, or failure behavior matters at that process level.

A source-code function call, condition, loop, goroutine, wait, conversion, or
storage access is not by itself a reason for another node. Keep such details in
the implementation of their owning business stage. A stage may contain multiple
calls, internal branches, and parallel computations. Do not force one node per
function, but do not collapse an entire endpoint when it contains independently
meaningful stages either.

Use these questions to decide:

- What business responsibility or meaningful execution contract does this node expose?
- Would changing this step independently be useful to someone editing the process?
- Would hiding it change the reader's understanding of the process or its outcomes?
- Is the extra node justified by more than a matching source-code statement?

Name stages by purpose, such as `Calculate Price`, `Reserve Inventory`, or
`Record Order Statistics`. Keep source-file and implementation references in
descriptions when useful for migration, rather than using them as decomposition
rules.

## Expose semantics selectively, then model them accurately

- Use Case/When for a process-level choice, such as approval versus rejection;
  do not translate every `if` into a branch on the graph.
- Use Split/Join when independently meaningful branches and their completion
  policy should be configurable or visible in the process. Two internal parallel
  calculations can legitimately remain inside one function.
- An operator tutorial showing two Maps, KeyBy, and Join demonstrates a supported
  construction. It is not a mandatory decomposition for every similar code fragment.
- A database write, Kafka log publication, or simple external call can remain
  inside a business stage. Introduce Input/Sink and endpoints when the chosen
  architecture actually exposes a transport boundary, not merely because the
  implementation uses an SDK. Never invent an event source for an internal helper.
- Expose errors that change process continuation, fallback, compensation, or the
  business result. Locally handled technical errors do not need separate nodes.

This is not permission to hide a requested business branch, invent completion
behavior, or choose an operator with the wrong contract. After deciding what
belongs on the graph, follow the authoring skill and operator semantics for those
boundaries. Describe important internal behavior without expanding it into AST.

## Reuse and review

Treat declared stage responsibilities, input/output contracts, business rules,
outcomes, ordering, and failure/completion policies as constraints on changes.
Record these in the model's descriptions and contracts where supported; do not
invent new DSL fields or imply that prose constraints are automatically enforced
by the validator. Distinguish explicit requirements from assumptions and examples.

For a change, locate the affected stages and shared logic first, then read the
implementation needed to establish the behavior. The graph reduces the context
needed for that investigation; it does not replace the code as evidence. Absence
of implementation details from the graph is neither missing coverage nor
permission to remove or change their behavior.

Keep an implementation-only change local when it preserves the declared process
contract. If a requested change affects a declared constraint, make that impact
explicit and obtain authorization when it exceeds the agreed scope. Do not
silently weaken the contract or expand the graph merely to accommodate an edit.
Update the graph when process-level behavior changes, and use the semantic diff
to review affected responsibilities, contracts, and outcomes rather than AST
coverage or generated-code volume.

When the same business function is used by different endpoints, preserve its
function identity and equivalent meaningful subgraph. Different argument
preparation outside that stage does not make the shared logic different.
Find visual components from actual repeated logic; do not fragment pipelines
merely to manufacture matches or component counts.

For each proposed node or branch, state its process-level purpose. Fold purely
technical steps into their owning function where that preserves the business
contract. Keep independently meaningful stages visible. Judge clarity and ease
of change, not the number of nodes or the percentage of source calls represented.
