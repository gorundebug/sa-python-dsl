# Python source editing through MCP

The source of truth is the typed Python project. Editing never imports canonical
YAML back into Python and never replaces user factories with a flattened graph.

## Workflow

1. Read `describe_architecture_object` for the intended business-stage or endpoint
   semantics, its exact DSL signatures and capability resource.
2. Call `inspect_python_authoring` to find source files. Inspect a selected file
   to obtain declarations, source text, a revision and insertion sites.
3. Call `add_node`, `add_endpoint` or `connect_ports` to prepare an edit. For a
   complete connected fragment use `preview_python_changes` with multiple
   operations, so that only the complete candidate needs to be valid.
4. Review both `sourceDiff` and `architectureDiff`. Editing a Python factory can
   change every instance of that factory, not just one displayed node.
5. Call `apply_python_changes` with the returned preview ID and revision. Then
   export the model if the Designer or code generator needs canonical YAML.

The convenience tools prepare previews; their names do not mean an immediate
mutation. Preview runs the normal Python export/validation worker on an isolated
copy. Apply repeats validation and atomically replaces a single source file.
Neither operation performs code generation or contacts the generation backend.

## Operation vocabulary

`add_node` and `add_endpoint` receive an existing Python `receiver`, a typed
factory method, a new Python `symbol`, an architecture `name`, and `arguments`.
Argument values are Python expressions, not a parallel JSON model. Examples:

```json
{
  "kind": "add_node",
  "receiver": "pipeline",
  "factory": "map",
  "symbol": "quote",
  "name": "Calculate Quote",
  "arguments": {
    "function": "Function('CalculateQuote')",
    "value_type": "quote_type",
    "source": "entry"
  }
}
```

Use `imports: ["Function"]` only when the source needs that public DSL class.
Literals, references and imported typed DSL constructors are supported. Arbitrary
function calls, comprehensions, argument expansion and executable code strings
are not supported. Existing user factories remain untouched and continue to run
through the ordinary DSL worker.

```json
{"kind": "connect_ports", "source": "quote", "target": "entry", "role": "data"}
```

This inserts `quote >> entry`, using the actual DSL result-binding behavior when
`entry` is an Input. `role: "additional"` inserts `target << source` for an
additional Join/MultiJoin/Merge input. `role: "error"` inserts the ordinary
`source >> target` edge followed by `source.on_error(target)`. The editor
does not invent numerical port IDs, change invocation semantics or reorder an
existing Case branch. Inspect the resulting semantic diff for ordering effects.
For additional inputs and SubStream result connections use actual stream
references and the documented DSL semantics, not a new port abstraction.

## Deliberate limits

- One file per atomic edit, with up to 100 operations. A modular project can be
  edited one file at a time when intermediate models remain valid.
- Insert at a reported statement boundary in a module or synchronous function.
  No control-flow-block, generator-body or asynchronous-function rewriting.
- Existing statements and comments are preserved. This is not a refactoring
  engine: replacing an existing edge or splitting expressions is unsupported.
- An unchanged exported model is rejected, including edits in unused factories.
- Python source must be UTF-8 and at most 1 MiB. Shadow inputs are bounded to
  5000 regular files and 50 MiB; use a dedicated architecture directory.
- Dependencies, IDE metadata, generated caches, `.env` credentials and edit
  artifacts are excluded from the shadow project. Symlink inputs are rejected.
  A project requiring an excluded local input will fail validation, not be
  silently rewritten.
- A preview expires after 15 minutes. Changed inputs, altered preview contents,
  concurrent application and replay are rejected. No Git operation is performed.

The worker's existing isolation rules still apply. A shadow workspace is not a
claim that arbitrary project Python is safe to execute outside that worker.

## Explicit project resources

`inspect_project(project_path=...)` includes a `resources` object with links for
`source`, `dsl`, `graph`, `tasks`, `audit`, `capabilities`, `validation-contract`,
and templates named `languageCapabilities` and `validationRule`. Use these links
rather than assuming the architecture manifest lives at the workspace root.

For nested projects, the resource templates are:

```text
servicegen://project/{project}/{kind}
servicegen://project/{project}/capabilities/{language}
servicegen://project/{project}/validation/rules/{code}
```

`project` is a percent-encoded workspace-relative path, including path separators
and spaces; `kind` is one of the seven concrete resource names above. Root-project
links retain the existing `servicegen://workspace/current/*` and rule/capability
URIs. Tools do not mutate a shared current-project selection. A request for one
project cannot change the meaning of another project's resource URI.

Resource reads do not execute Python, export YAML or fetch network metadata.
Missing manifests/artifacts return diagnostics; absent metadata returns
`status: unavailable`. Tasks use the selected project's configured generated-output
directory, while audit and metadata remain attached to its Python project.
