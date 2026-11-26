---
description: Generate a target-language Service Architect project from the validated model
argument-hint: [project path] [language]
---

Request: $ARGUMENTS

Generation performs an authenticated external request and writes a ZIP archive, so
confirm the target and output path with the user before calling it.

1. `validate_project`, then `export_project`. Do not generate while validation fails.
2. Read `servicegen://capabilities/{language}` for the selected backend. If the cache
   is unavailable or `doctor` reports a capability incompatibility, call
   `refresh_capabilities` and read it again. A missing feature is unknown, not supported.
3. Call `generate_project`. Keep the credentials file and archive path
   workspace-relative, never reveal credentials, and do not automatically retry an
   unchanged failed request.

For merging into an existing destination project, use that project's merge entrypoint
and hooks — a fresh archive's default hook is not the installed project's policy.
Review stale-file removal and protect user-owned files and data.

Afterwards, read the `service-architect-implementation` skill before changing
generated sources, makers or lifecycle wiring.
