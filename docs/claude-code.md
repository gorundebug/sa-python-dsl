# Service Architect in Claude Code

The Claude Code plugin and the Codex plugin are the same plugin folder,
`plugins/service-architect`. They share the skills corpus and the pinned MCP server
in `.mcp.json`; only the manifests differ. The project contract, CLI workflow and
MCP surface are documented once in [`codex.md`](codex.md) and apply unchanged here.

## Install

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/) first: the
MCP server runs through `uvx` from an immutable commit pin.

```
/plugin install service-architect --marketplace gorundebug/sa-python-dsl
```

Or from the shell:

```bash
claude plugin marketplace add gorundebug/sa-python-dsl
claude plugin install service-architect@service-architect
```

During development, add this checkout as a local marketplace instead:

```bash
claude plugin marketplace add ./sa-python-dsl
claude plugin install service-architect@service-architect
```

Verify both manifests after changing either one:

```bash
claude plugin validate plugins/service-architect
claude plugin validate .
```

## What the plugin contributes

| Component | Path | Notes |
| --- | --- | --- |
| Manifest | `plugins/service-architect/.claude-plugin/plugin.json` | Claude Code manifest; version tracks `.codex-plugin/plugin.json`. |
| Marketplace | `.claude-plugin/marketplace.json` | Repository-root marketplace; the Codex equivalent is `.agents/plugins/marketplace.json`. |
| MCP server | `plugins/service-architect/.mcp.json` | Shared with Codex, including the immutable `git+https://...@<commit>` source pin. |
| Skills | `plugins/service-architect/skills/` | Shared with Codex, unchanged. |
| Commands | `plugins/service-architect/commands/` | Claude Code only; Codex ignores this folder. |
| Icon | `plugins/service-architect/.claude-plugin/icon.png` | 1024 px raster port of the site favicon, rebuilt by `scripts/build_plugin_icon.py`. |

### Skills

`service-architect-authoring`, `service-architect-business-modeling`,
`service-architect-validation`, `service-architect-export` and
`service-architect-implementation` load on demand from their descriptions, as in
Codex. Claude Code reads `skills/<name>/SKILL.md` with the same frontmatter, so the
files need no Claude-specific variant.

### Commands

| Command | Purpose |
| --- | --- |
| `/service-architect:inspect [path]` | Read the manifest and locate the typed Python model without executing it. |
| `/service-architect:validate [path]` | Validate and repair model-level diagnostics from their `validationRuleUri`. |
| `/service-architect:export [path]` | Validate, then export canonical YAML to the manifest's path. |
| `/service-architect:generate [path] [language]` | Capability check, then an authenticated generation request. |
| `/service-architect:review [path]` | Semantic review against `servicegen://authoring/review-checklist`. |
| `/service-architect:designer [path]` | Export and open the read-only embedded Designer. |

The commands are shortcuts into the same MCP tools and resources the skills
describe. They add no capability the skills do not already cover.

## Icon

The listing icon is the same mark as the site favicon,
`public/favicon.svg` in `service_architect_vue3`. The plugin directory accepts
PNG and JPEG at 512-2048 px, so the vector cannot be shipped and the published
`apple-touch-icon.png` is too small; `scripts/build_plugin_icon.py` rasterizes the
same geometry at 1024 px without an image dependency. Re-run it when the site mark
changes:

```bash
python3 scripts/build_plugin_icon.py
```

The directory takes the listing icon only the first time the plugin is saved or
submitted. Changing it later does not change the listing.

## Release

A release updates both manifests together. `tests/test_release_contract.py` fails
when the Claude Code and Codex manifests disagree on name, version or description,
so a bumped Codex version cannot ship a stale Claude Code manifest.

Local source changes do not update an already installed plugin or its pinned MCP
revision. Publish the tested server commit, update `.mcp.json` and both plugin
versions, then verify that exact revision — see the release
notes in the [README](../README.md).
