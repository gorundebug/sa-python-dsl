---
description: Open the exported Service Architect graph in the embedded read-only Designer
argument-hint: [project path]
---

Target project: $ARGUMENTS (default `.`)

Call `validate_project` and `export_project` so the Designer shows the current
revision, then call `designer_view`. It renders the exact exported revision as a
read-only graph — as an embedded resource, or through a short-lived loopback URL
when the host does not support embedded UI.

The frontend assets are versioned and hosted; the project YAML stays local and is
supplied by the MCP response. The view is a projection: make architectural changes
in typed Python, not in the Designer.
