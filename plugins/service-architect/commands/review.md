---
description: Review a Service Architect model against the authoring review checklist
argument-hint: [project path]
---

Target project: $ARGUMENTS (default `.`)

Validation proves model integrity; it does not prove the topology implements the
intended behavior. Review the semantics.

1. `inspect_project`, then `validate_project`.
2. `preview_architecture_diff` and review the semantic entities and links against the
   user's stated intent.
3. Read `servicegen://authoring/review-checklist` and
   `servicegen://authoring/business-modeling`, and work through the checklist.

Judge the model as a business process, not as an AST projection:

- does every node expose a business responsibility or a meaningful execution contract?
- is each independent handler its own named pipeline with fresh processing, error and
  reply nodes, reusing function identities rather than handler nodes?
- are cardinality, topology and invocation semantics modeled separately and correctly
  (FlatMap vs Split, PriorityTaskPool vs ParallelCall)?
- does every pipeline have an identifiable trigger?
- do errors that change process continuation, fallback or compensation have explicit paths?
- do typed messages carry real business data instead of IDs plus hidden context?
- are API contract modules separate from service implementations?

Report findings grouped as defects, ambiguities and observations. State the
ambiguity and ask one focused question where a requirement has several materially
different graph interpretations; do not edit the model as part of a review.
