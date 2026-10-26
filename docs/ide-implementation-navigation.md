# Business implementation navigation

IDE snapshots optionally include `implementations[serviceKey][streamKey]` and
`generationOutputDirectory`. Identities are derived from the **evaluated Python
DSL export**, so loops, factories and shared module references work without
re-parsing authoring text or modifying the generator. Canonical YAML is only
the intermediate export already produced by snapshot refresh, not an editable
source or an additional generation dependency.

Each identity contains `name`, `symbols`, `language`, `role`, `owner`, `package`
and `service`. Input/Sink identities refer to the endpoint's source/sink handler;
ordinary business operators refer to their function. Passive nodes without a
function have no entry. Names are queried as symbols, never interpreted as shell
commands or generated directory layouts. Module/package fields remain descriptive
context; moved files are found through IDE indexing rather than guessed paths.

The common viewer's Implementation action emits a selection with
`action: "implementation"`. Both hosts validate the selected revision and look
up identities in their **own cached snapshot**, rather than accepting symbols
or file paths from webview messages. Existing Python Code and selection events
remain compatible. Search is confined to the configured generation destination
and current IDE project/workspace, ignores dependency/build trees, and rejects
symlinks escaping the root. Ambiguous results require a chooser. Symbol positions
come from the IDE at lookup time; fallback file matches never claim a resolved
line. A missing implementation gives a diagnostic, not a guessed navigation.

Both IDEs need the relevant language plugin for symbol resolution. A plugin for
GoLand does not add C++ or Rust indexing; file-only navigation remains available
for recognizable implementation filenames when a symbol provider is absent.
Generated code and separately checked-out modules must be available locally
under the chosen root. No build or application launch is needed for navigation.
