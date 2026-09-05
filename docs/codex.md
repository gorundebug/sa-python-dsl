# Service Architect in Codex

Service Architect uses typed Python as the editable architecture source and YAML as
generated canonical interchange. Codex should edit Python declarations, validate the
object graph, and export YAML only when another product boundary needs it.

## Project contract

Every project root contains `.service-architect/project.yaml`:

```yaml
version: 1

project:
  name: Example

authoring:
  mode: python
  entrypoint: main:project

canonical:
  output: .service-architect/build/processorder.yaml

generation:
  targets:
    - go
```

The entrypoint uses `module.path:attribute` syntax. Discovery validates this declaration
without importing the module. Paths are forward-slash paths relative to the project root;
absolute paths and parent traversal are rejected.

## CLI workflow

Run commands from the Python DSL repository after installing it into the active virtual
environment:

```bash
sa-dsl inspect --project examples/processorder --format json
sa-dsl validate --project examples/processorder --format json
sa-dsl export --project examples/processorder --format json
sa-dsl generate --project examples/processorder --format json
```

`inspect` reads only the manifest. `validate` and `export` execute the declared trusted
Python entrypoint in a separate process with a bounded runtime. `export` atomically writes
the canonical YAML path declared by the manifest.

`generate` validates and serializes the same model, submits an API-key-authorized
asynchronous generation job, polls it, validates the downloaded ZIP, and writes it under
`dist/` by default. Credentials come from a workspace-relative `.env` file:

```dotenv
SERVICE_ARCHITECT_API_KEY=sa_live_<key-id>_<secret>
SERVICE_ARCHITECT_API_URL=https://z06e41vwnl.execute-api.us-east-1.amazonaws.com/prod
```

An existing YAML architecture can be migrated into a modular Python package:

```bash
sa-dsl import architecture.yaml --output processorder --format json
```

The importer creates `.service-architect/project.yaml`, derives generation targets from
the service programming languages, and points the manifest at the generated `main:project`
entrypoint. Validate the imported project and compare its exported canonical YAML with the
original before adopting Python as the source of truth.

## MCP tools

The `sa-dsl-mcp` command starts the local stdio server. It exposes:

| Tool | Side effects | Purpose |
| --- | --- | --- |
| `inspect_project` | Reads the manifest only | Discover project metadata without running Python. |
| `validate_project` | Executes trusted project Python | Return stable model diagnostics. |
| `export_project` | Writes canonical YAML | Produce deterministic interchange for Designer or backend use. |
| `generate_project` | Calls the backend and writes ZIP | Download generated target-language projects. |
| `import_yaml_project` | Creates a new project directory | Migrate canonical YAML into modular typed Python and create its manifest. |
| `designer_view` | Executes trusted project Python and starts a local snapshot view | Inspect the exact exported revision as a read-only graph. |

All tools return a `schemaVersion`, operation, status, and diagnostics. Diagnostics contain
a stable code, severity, model path, and message so an agent can repair the owning Python
declaration rather than editing generated YAML.

The server must be started with an explicit `--workspace` root. Every tool path is a
forward-slash relative path below that root. Absolute paths, parent traversal, backslash
paths and symlink escapes fail with `SA_WORKSPACE_BOUNDARY_VIOLATION`.

## Read-only Designer

`designer_view` validates and exports the same typed project used by the other tools,
then returns a content-addressed snapshot with its canonical SHA-256 revision. It never
opens a floating working copy and never writes graph edits back to Python.

Hosts with MCP Apps support render `ui://service-architect/designer`. The small HTML
resource loads the pinned frontend bundle from
`https://gorundebug.com/mcp-ui/0.1.0/`; the graph payload arrives in structured tool
output and is not uploaded to that site. The resource receives no filesystem access,
API key, Cognito token, `.env` contents or AWS credentials.

Other clients use the returned `fallbackUrl`. It binds to `127.0.0.1`, contains an
unguessable token, expires after 15 minutes, sends `Cache-Control: no-store`, and stops
with the MCP process. Both presentations are read-only: selection, inspection, pan,
zoom, Fit Graph and renderer switching are available, while Build Mode, connecting,
moving, adding, deleting, saving and generation controls are absent.

For a pinned alternative asset host, set `SERVICE_ARCHITECT_UI_ASSET_BASE` to an HTTPS
URL containing the compatible versioned `designer.js` and `designer.css` bundle.

## Codex plugin

The plugin is under `plugins/service-architect`. Its MCP configuration uses `uvx` to run
`sa-dsl-mcp` directly from the public `gorundebug/sa-python-dsl` repository, so it does
not depend on a cloned repository, activated virtual environment, or absolute local path.
Its skills teach Codex the authoring, validation, export, and generation boundaries.

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then register the
public GitHub marketplace and install the plugin:

```bash
codex plugin marketplace add gorundebug/sa-python-dsl
codex plugin add service-architect@service-architect
```

Confirm the installation:

```bash
codex plugin marketplace list
codex plugin list
```

The plugin is loaded when a new Codex task starts. `uvx` downloads and caches the Python
package on first MCP startup. After a marketplace release, upgrade the marketplace and
reinstall or update the plugin before testing it in a new task.

The intended loop is:

```text
inspect manifest
      |
      v
edit typed Python
      |
      v
validate object graph
      |
      v
export canonical YAML ----> Designer interchange
      |
      v
generate project ZIP -----> Go / C++ / Python / Rust / TypeScript
```

## Execution boundary

Project discovery never executes Python. Validation and export intentionally do, because a
Python authoring project is executable code. The child-process boundary supplies a timeout,
isolated interpreter mode, filtered environment, captured output, and a file-based result
protocol. It is fault containment, not a security sandbox. Only execute projects from a
trusted workspace; stronger isolation should use a container or restricted worker.
