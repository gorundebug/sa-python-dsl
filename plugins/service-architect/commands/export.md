---
description: Export canonical Service Architect YAML from a validated typed Python project
argument-hint: [project path]
---

Target project: $ARGUMENTS (default `.`)

Run `validate_project` first and stop if it reports errors. Then call
`export_project`, omitting `output` so the manifest's canonical path is used.
Supply an override only when the user explicitly asks for another
workspace-relative artifact, and never write outside the project workspace.

The exported YAML is deterministic canonical IR for Designer interchange and the
generation backend, not a second editable source of truth. If the export diff is
unexpected, correct the typed Python model and export again.

Surface returned diagnostics to the user instead of retrying an unchanged operation.
