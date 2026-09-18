# Plugin 0.1.11: Designer navigation and hierarchy

The plugin loads the shared embedded Designer from
`https://gorundebug.com/mcp-ui/0.1.5`. Both the plugin environment override and
the MCP server default use this immutable asset version.

Included UI changes:

- Component, pipeline and service folding with layout and route updates.
- Selection and viewport focus preserved across folding and expansion.
- Double-click or double-tap on an edge navigates to its visible destination.
- Collapsed destinations stay collapsed and their card is selected.
- Small Back/Forward buttons at the top-left of the graph.
- History skips removed targets and resets on project replacement/regeneration.
- Selecting a link preserves the current graph node while showing link details.

## Release order

1. Merge Designer MR !108:
   https://gitlab.com/sergeyalexeev/service_architect_vue3/-/merge_requests/108
2. Build the embedded Designer with `SERVICE_ARCHITECT_UI_VERSION=0.1.5 npm run build:embedded`.
3. Publish the generated `public/mcp-ui/0.1.5/` directory, including any assets,
   to the production website. Publishing only to beta is insufficient.
4. Confirm the production JS and CSS are available and exercise the plugin view.
5. Only then mark the plugin PR ready, merge and release plugin 0.1.11.

Keep older versioned assets available for existing plugin installations. Until
the production assets are published, this release must remain a draft.
