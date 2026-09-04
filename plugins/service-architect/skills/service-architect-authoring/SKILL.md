---
name: service-architect-authoring
description: Create or modify Service Architect topology projects whose editable source of truth is the typed sa-python-dsl API.
---

# Service Architect authoring

Start by calling `inspect_project` on the project root. Use its entrypoint and
manifest metadata to locate the Python model. Do not execute project Python just
to discover its structure.

Treat typed Python as the editable source of truth. Treat the canonical YAML path
reported by the manifest as a generated interchange artifact; do not edit it to
make an architectural change.

Prefer concrete factories such as pipeline stream factories, connector endpoint
factories, and type factories. They expose only properties valid for that entity.
Use object references for modules, packages, pools, types, pipelines, endpoints,
and streams rather than repeating serialized string keys.

Keep declarations in their domain folders: project, services, pipelines,
connectors, endpoints, modules, packages, pools, and types. Connect internal
pipeline streams in the pipeline module and cross-pipeline or cross-service
relationships in the owning service module.

After an edit, use `validate_project`. Export canonical YAML only after validation
succeeds.

For a YAML-only architecture, call `import_yaml_project` with workspace-relative
source and output paths. The output must be absent or empty. Treat the resulting
Python project as a migration candidate until validation and YAML round-trip agree.
