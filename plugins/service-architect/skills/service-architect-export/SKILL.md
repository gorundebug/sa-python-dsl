---
name: service-architect-export
description: Export canonical YAML from a valid Service Architect Python project before code generation or Designer interchange.
---

# Service Architect export

Use `export_project` only after `validate_project` succeeds. Omit `output` to use
the manifest's canonical path. Supply an override only when the user explicitly
needs another workspace-relative artifact.

The exported YAML is deterministic canonical IR for Designer interchange and the
generation backend. It is not a second editable source of truth. If the export
diff is unexpected, correct the typed Python model and export again.

Do not write outside the declared project workspace. Surface returned diagnostics
to the user instead of retrying an unchanged operation.

Use `generate_project` only when the user asks for generated implementation code.
It performs an authenticated external request and writes a ZIP archive. Keep the
credentials file and archive path workspace-relative, never reveal credentials,
and do not retry an unchanged failed request automatically.
