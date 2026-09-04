---
name: service-architect-validation
description: Diagnose invalid Service Architect typed Python projects and repair model-level topology errors from stable diagnostics.
---

# Service Architect validation

Call `validate_project` for the project root and reason from diagnostic `code`,
`path`, and `message`. Fix the typed Python declaration that owns the diagnostic;
never patch generated YAML as a workaround.

Preserve graph invariants: references must belong to the same project, links must
correspond to an actual stream connection, entity keys must be unique, required
properties must be present, and concrete factories must receive only supported
properties.

Run validation again after related diagnostics have been addressed. Do not export
or request code generation while validation reports errors.
