# MCP release check

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
