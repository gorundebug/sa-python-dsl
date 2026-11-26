---
description: Inspect a Service Architect project manifest, entrypoint and typed Python model
argument-hint: [project path]
---

Target project: $ARGUMENTS (default `.`)

Call `inspect_project` on the project root first. Read its entrypoint and manifest
metadata to locate the Python model, and use the returned `resources` links for a
project nested below the MCP workspace.

Do not execute project Python just to discover its structure, and do not read the
canonical YAML as the model: typed Python is the editable source of truth.

Then report:

- project name, authoring entrypoint, canonical output path and generation targets
- services, pipelines, connectors and endpoints, grouped by owning module
- each pipeline's trigger: endpoint, schedule, SubStream caller or startup/CLI
- anything the manifest declares that is missing on disk

Call `doctor` as well when the user asks whether the project is ready for
validation, export or generation.
