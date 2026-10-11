# MCP release check

## Plugin 0.1.23: build verification and stable task completion

The plugin pins its MCP runtime to
`41eca14526026dd15805e3e6f51cba3268608b69`. The existing `run_verification`
tool now supports the allow-listed `build` target when the generated workspace
provides it. Arbitrary commands and Make variable overrides remain disallowed.

Business-task completion is matched by owner, function name and language rather
than a task-file number that can change during regeneration. Adjacent progress
entries are parsed independently; ambiguous filename-only entries stay pending.

Before release preparation, the runtime passed 319 tests and 239 subtests.
Three Go architecture scenarios were exercised through MCP authoring, real code
generation, compilation and eight HTTP cases. Initial generations used AWS;
the generator-side fix for refreshing task descriptions was checked on a local
generator. That separate ServiceGen change is not deployed by this plugin release.
Compilation used Go 1.26.4 and the local servicelib checkout.

This remains a Git-backed plugin release, not a PyPI publication. Python package
metadata stays at `0.1.0`, and Designer assets stay at `0.1.10`. Updating the
repository does not replace an already running MCP process.

## Plugin 0.1.22: typed Python authoring and verified generation

The plugin pins its MCP runtime to
`dc198e0d639b16eb7b1e012f246bba52a1a5057a`. It exposes 21 tools, including
source-preserving Python previews and edits, adding nodes and endpoints,
connecting ports, and structured object discovery. Agents can read 30 object
guides and ten executable architecture recipes. Project-scoped resources keep
nested workspaces and their metadata separate.

Generation preserves backend diagnostics and business-owned files. Destination
locking, revision checks, bounded verification subprocesses and safe audit
failures are covered by the regression suite. Composite type references are
resolved correctly in generation requests. Passive Error nodes do not accept a
business-function argument; error handling uses the documented graph contracts.

Acceptance includes 314 passing tests, real generation and compilation of all ten
Go recipes and the canonical example's four services. The installed MCP also
completed live production AWS generation, downloaded a valid archive and built
its four Go services. Compilation used the local servicelib checkout; this is
not a claim about other language backends or execution of business stubs.
See [the acceptance audit](mcp/completion-audit.md) for scope and evidence.

The Python distribution metadata remains `0.1.0`, as in earlier plugin releases;
the immutable Git source identifies this runtime revision. This is a Git-backed
plugin release, not a PyPI publication. Designer UI selection stays at `0.1.10`,
and no IDE plugin binaries or cloud deployment are changed by this release.
Run `make mcp-conformance` against this exact published revision before publishing
the updated plugin manifest. The release gate requires all 21 tools.

## IDE viewer 0.1.11: extensible node context menu

Both IDE plugins package the same immutable Designer `0.1.11` assets. Right-click
or Shift+F10 offers Python Code (IDE hosts only), Show Component and Show Pipeline
according to live membership. Scope navigation is shared with the Designer browsers.
`scripts/sync_ide_assets.py --check` verifies both packaged builds. This change does
not switch the Codex/MCP remote asset default: it remains `0.1.10` until the new
versioned assets are deployed and a separate plugin release selects them.

## Plugin 0.1.20: shared Designer 0.1.10 and model bindings

The shared Designer source builds immutable UI `0.1.10`. VS Code and JetBrains
package byte-identical copies of that build; both use the `designer_view` snapshot
contract and `service-architect:selection` events. The Codex plugin selects
`https://gorundebug.com/mcp-ui/0.1.10`, and the standalone MCP runtime uses the
same default. The plugin pins the updated Python runtime to an immutable commit,
including connector implementations, native type bindings and IDE support.

Keep this release PR in Draft until both `designer.js` and `designer.css` are
available on the production domain and the release gate below has passed.
Deploying only beta is insufficient. Do not overwrite `0.1.9` in place.
Preparing this PR does not deploy the assets or update installed plugins.

The Designer updates, including the versioned assets, are included in
[MR !156](https://gitlab.com/sergeyalexeev/service_architect_vue3/-/merge_requests/156).
Use `scripts/sync_ide_assets.py --check --source-dir <release-checkout>/public/mcp-ui/0.1.10`
before packaging the IDE plugins; a dirty Designer checkout may build different bytes.

## Plugin 0.1.18: complete error-path highlighting

This UI-only release selects Designer assets at
`https://gorundebug.com/mcp-ui/0.1.9`. Both graph renderers color the complete
error-only path red until ordinary flow joins it. Only edges entering Error
nodes are dashed; subsequent error-path edges are solid. Selected error edges
remain bright red. Topology edits recompute downstream path colors.

The MCP runtime commit and Python wheel are unchanged. Keep this release PR
in Draft until both `designer.js` and `designer.css` are published on the
production domain from Designer MR 137.

## Plugin 0.1.17: Designer link selection

This UI-only release selects Designer assets at
`https://gorundebug.com/mcp-ui/0.1.8`. The shared graph renderer preserves
explicit routed-edge selection and the configured highlight color, including
red error connections. The website Links page keeps single-edge selection
available even when build mode is enabled.

The MCP runtime commit and Python wheel are unchanged. Keep this release PR
in Draft until both `designer.js` and `designer.css` are published on the
production domain from the corresponding Designer release.

## Plugin 0.1.16: complete HTTP method support

The MCP runtime is pinned to `d06719b425952f00d72a506023824ea0ec0261fb`.
The typed model, validation, MCP guidance and YAML importer support GET, POST,
PUT, PATCH, DELETE, HEAD, OPTIONS, TRACE and CONNECT.
The Designer wheel is rebuilt from the same source revision, with a new
content hash in its worker URL. The Python distribution remains `0.1.0`;
the plugin is `0.1.16`. Embedded Designer assets remain at `0.1.7`.


## Plugin 0.1.15: Error node borders

This UI-only release selects Designer assets at
`https://gorundebug.com/mcp-ui/0.1.7`. Error nodes use dark-red borders when
unselected and bright-red borders when selected, in both VisNetwork and VueFlow.
The MCP runtime commit and Python wheel are unchanged. Keep the release PR in Draft
until both `designer.js` and `designer.css` are published on the production domain.

## Plugin 0.1.13: identifier-safe graph keys

The MCP runtime is pinned to `7597e363d2ef39fa7afa6dafbf87fd9994cde83c`.
Automatically derived keys remove punctuation, use a leading underscore for
numeric names, and retain strict validation for explicitly provided keys.
The Designer wheel uses the same normalization and an updated cache hash.
This does not migrate invalid keys in previously exported YAML documents.


## Plugin 0.1.12: YAML round-trip and passive Error validation

The MCP runtime is pinned to `430dee7043c85a95dd705d5a2a8e26f5ad8624d8`.
This revision preserves stream keys independently of display labels, avoids
Python symbol collisions, and rejects functions on passive Error streams.
Redundant synchronous links matching service defaults remain omitted.

The Designer wheel must be rebuilt from this runtime revision and its worker
URL content hash updated to invalidate browser caches. The Python distribution
version remains `0.1.0`; the plugin version is `0.1.12`. Designer UI assets
remain at `https://gorundebug.com/mcp-ui/0.1.5`.

## Plugin 0.1.9: large-graph routing and shared endpoints

This release selects Designer UI `0.1.4` and pins the MCP runtime to
`194fa2e529ec94f69538781c6cd118db64f48f9f`, including validation support for
multiple independent Sink streams sharing a compatible endpoint.

The shared Designer includes full-graph route reuse across scoped navigation,
local rerouting, read-only graph preparation, atomic external-edge snapshots,
and routing-search optimizations. Routes, arrowheads and saved coordinates are
preserved; no production time cutoff or direct-line shortcut is introduced.

Keep the release PR in Draft until both `designer.js` and `designer.css` are
published at `https://gorundebug.com/mcp-ui/0.1.4/`. Deploying only the beta
website is insufficient. Existing plugin releases keep their prior asset URL.

The Codex plugin does not install the MCP server from a moving branch. Its
`.mcp.json` manifest references one immutable Git commit so every installation
uses the same Python DSL, validation rules, resources, and tool contracts.

Run the complete release gate before changing that revision:

```bash
make release-check
```

The gate performs three checks:

1. Runs the local unit and protocol suite, including hostile authoring-code,
   timeout, semantic-diff, preview/apply, audit, and merge-contract scenarios.
2. Builds the exact pinned revision in an isolated `uvx` environment.
3. Starts that installed `sa-dsl-mcp` over stdio, initializes an MCP session,
   lists its tools and resources, and then closes the session normally.

Use `make mcp-conformance` to repeat only the clean-install and MCP handshake.
The command reads the revision from the plugin manifest; do not duplicate the
revision in scripts or documentation.

The release check never reads credential values. Runtime operations keep only
metadata in `.service-architect/audit.jsonl`; generated archives and source code
are not copied into the audit log.

## Plugin 0.1.8: Designer routing

The plugin loads Designer UI `0.1.3`, with responsive orthogonal edge routing in
VisNetwork and VueFlow. The MCP runtime stays pinned to the existing validated
commit; this release changes the UI selection, not the Python authoring API.

Publish `https://gorundebug.com/mcp-ui/0.1.3/designer.js` and `designer.css` from
the Designer repository before merging this plugin release. A beta-only website
deployment does not satisfy this production URL. The routing worker must be
bundled inline: the loopback host intentionally keeps `worker-src blob:` and
`connect-src 'none'`, and must not fetch a worker script from another origin.
