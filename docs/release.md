# MCP release check

## IDE viewer 0.1.17: consistent SubStream result selection

JetBrains 0.1.28 and VS Code 0.1.21 bundle the same immutable viewer 0.1.17.
Visual validation treats an Input result binding as passive, matching semantic
validation instead of falsely coloring a valid callable red. The filtered
SubStream result selector excludes an independent Input request body while
preserving the existing unfiltered authoring mode. Input result bindings can
still select a Split inside a callable body. These interactions were exercised
through Designer's actual properties UI; 20 focused model/generation/history
tests pass. A dedicated browser regression is included for CI.

The Python runtime and managed CLI environment 0.1.22 are unchanged. Codex
0.1.27 keeps its deployed remote viewer selection; the Designer MR must be
deployed separately. This is an IDE asset correction, not an SDK release.

## Plugin 0.1.27: SubStream Input result bindings

Codex pins runtime `09f45bdd8e4e5e39d4051cac4391167acbb01d86`, which
stops SubStream traversal at passive Input result bindings without weakening
return ownership or service boundaries. Its remote Designer stays at the
deployed 0.1.10; publishing this plugin does not deploy the Designer MR.

JetBrains 0.1.27 and VS Code 0.1.20 package that runtime and the matching
immutable EmbeddedDesigner 0.1.16. Both advance their private CLI environment
to 0.1.22 so managed installations do not reuse the old validator. Explicit
external CLI overrides must be updated separately. Python package metadata
remains 0.1.0. Packages are published as GitHub Releases, not to IDE marketplaces.

## Runtime correction: SubStream result bindings

An Input reached through its incoming result binding terminates SubStream body
traversal. It does not re-enter that Input's independent request body. The callable
still requires its own reachable return, and cross-service result bindings remain
invalid. This is a generic validator correction, not an SDK/application exception.

Python distribution metadata remains 0.1.0; Git-backed consumers must pin the
immutable runtime commit containing this correction. Existing Codex manifests,
IDE bundles and explicit CLI environments do not update merely because main moves.

## Plugin 0.1.26: implementation guidance and local SubStream analysis

The Git-pinned runtime exposes implementation guidance through MCP handshake,
project inspection and object discovery. The plugin also ships the new
`service-architect-implementation` skill. These are engineering recommendations,
not new model validation rules or changes to SDK contracts.

Go SubStream analysis handles generated acronym casing and follows helper bodies
in other local modules. VS Code 0.1.18 and JetBrains 0.1.25 bundle this runtime,
use private CLI environment 0.1.21 and matching EmbeddedDesigner 0.1.15 assets.
JetBrains labels the explicit refresh action "Refresh graph & calls".

The Codex MCP manifest pins the published runtime by immutable Git revision;
its remote Designer selection remains 0.1.10. Python package metadata remains
0.1.0. Publication uses GitHub Releases, not PyPI or IDE marketplaces.

## Plugin 0.1.25 and IDE SubStream call analysis

Codex 0.1.25 pins the published DSL runtime through its immutable Git revision in
`plugins/service-architect/.mcp.json`. It includes Custom endpoint `enabled`
support and the read-only Go SubStream call-analysis CLI. The Python distribution
metadata remains 0.1.0; this is a Git-backed release, not a PyPI publication.
Codex's remote Designer selection remains 0.1.10; no cloud UI deployment is implied.

VS Code 0.1.17 and JetBrains 0.1.24 bundle the same DSL sources, including the
Go analyzer, and use private CLI environment 0.1.20. Their Refresh action can show
possible Go SubStream calls without modifying Python/YAML topology. See
[the analysis contract and requirements](ide-substream-calls.md). External CLI
overrides and project virtual environments must be updated separately.

The IDE packages include matching updated viewer bundles for the call overlay.
They do not change the Codex plugin's independently selected remote Designer UI.
Both installable IDE packages are built and tested in Docker and published as
GitHub Release assets; this does not publish them to the IDE marketplaces.

## IDE packages: Custom endpoint enablement

JetBrains 0.1.20 (private CLI environment 0.1.17) and VS Code 0.1.13
(private CLI environment 0.1.11) bundle `CustomConnector.endpoint(enabled=...)`.
The default is `True`; `False` is preserved in the canonical model. Increasing
both private environment versions prevents reuse of an older managed CLI.
Explicit external CLI paths and project virtual environments remain user-selected
and must contain the same updated DSL.

These are local IDE packages. Codex plugin 0.1.24 still pins the previous published
Git revision; rebuilding IDE packages does not update that MCP runtime. A Codex
release requires publishing the DSL change and pinning its immutable commit.


## Plugin 0.1.24: interval scheduling and evaluated source navigation

The MCP runtime is pinned to `d9812ea72639fb977a3194f371d25ef488a59349`.
It includes typed `IntervalSchedule` authoring, validation and lossless YAML
import/export, with matching MCP discovery resources and a local interval example.
The same runtime includes evaluated Python source ranges and business
implementation identities used by the IDE navigation hosts.

JetBrains 0.1.19 and VS Code 0.1.12 bundle these CLI sources and use new private
CLI environment versions. Their shared Designer assets remain at 0.1.14;
Codex's remote Designer selection remains at 0.1.10. No UI asset deployment or
PyPI publication is implied. The Python distribution metadata remains 0.1.0;
the immutable Git revision and bundled CLI environment identify the update.

Release verification: 42 focused tests and three subtests passed. A clean
installation of the pinned runtime exposed 21 MCP tools and eight resources.
Both IDE plugins were built and tested in Docker; all 53 bundled DSL files in
each installable package match this runtime's source files byte-for-byte.

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
