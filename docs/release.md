# MCP release check

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
