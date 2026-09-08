---
name: service-architect-validation
description: Diagnose invalid Service Architect typed Python projects and repair model-level topology errors from stable diagnostics.
---

# Service Architect validation

Call `validate_project` for the project root and reason from diagnostic `code`,
`path`, and `message`. Fix the typed Python declaration that owns the diagnostic;
never patch generated YAML as a workaround.

Read each diagnostic's `validationRuleUri`. If the validation-contract resource
is unavailable, call `refresh_validation_contract` once and validate again. Use
the exact cached condition and remediation together with runtime `details`;
`evaluation: servicegen` means the catalog explains the rule but does not replace
the authoritative validator. Do not infer a fix from the code name alone.

Preserve graph invariants: references must belong to the same project, links must
correspond to an actual stream connection, entity keys must be unique, required
properties must be present, and concrete factories must receive only supported
properties.

Run validation again after related diagnostics have been addressed. Do not export
or request code generation while validation reports errors.
