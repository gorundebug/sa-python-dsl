---
description: Validate a Service Architect project and repair model-level diagnostics
argument-hint: [project path]
---

Target project: $ARGUMENTS (default `.`)

Call `validate_project` for the project root and reason from each diagnostic's
`code`, `path` and `message`. Read every diagnostic's `validationRuleUri` before
repairing; if the validation-contract resource is unavailable or `doctor` reports a
revision mismatch, call `refresh_validation_contract` once and validate again.

Fix the typed Python declaration that owns the diagnostic. Never patch generated
YAML as a workaround, and never reimplement or bypass a rule whose `evaluation` is
`servicegen` — apply the catalog remediation to the reported path and details.

Preserve graph invariants: references belong to the same project, links correspond
to an actual stream connection, entity keys are unique, required properties are
present, and concrete factories receive only supported properties.

Validate again after related diagnostics have been addressed. Report remaining
errors instead of exporting or generating while validation fails.
