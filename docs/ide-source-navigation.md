# IDE source navigation

Python factories, loops, imported stream references and f-strings are ordinary
supported authoring code, not separate graph constructs. Navigation must identify
the objects actually produced by that code rather than guess their names from AST.

`ide-snapshot` evaluates and validates the model in the existing isolated worker.
Only that worker temporarily records node creation, source/source-list assignments,
error routes and explicit call-semantics declarations. The hooks are restored even
if authoring raises. Normal validation, export and code generation do not enable
this instrumentation.

The snapshot writes the usual canonical YAML and a separate generated artifact:
`.service-architect/build/source-locations.json`. The latter maps service/node and
service/source/target keys to Python file/line locations. Factory-produced objects
point to the factory's declaration or connection, with their actual instance keys.
The map is filtered against the final model, not intermediate graph objects.
Explicit call-semantics declarations take priority over plain connection locations.
No navigation fields enter YAML, runtime configuration or generated business code.

`ide-locate` reads this index without executing Python. Source-file and manifest
fingerprints plus the canonical YAML digest detect stale snapshots. Changed source
or YAML requires Refresh instead of silently opening a potentially unrelated line.
Materialized child projects are indexed independently. Paths must stay inside the
project. Projects without an index retain conservative static navigation until the
first refresh using the updated CLI.

Regression coverage includes factories, stream-reference route tables, f-strings,
error and multi-source links, explicit semantics, stale/escaping locations and
restoration after exceptions. The canonical example checks all inferred source,
sources and errorStream edges, not only optional entries in services.links.

IDE snapshots also carry node ranges and source fingerprints in `sourceLocations`.
Ranges use one-based lines and UTF-16 columns with an exclusive end, matching IDE
editors (not Python AST byte offsets). Related factory call sites are retained:
the factory body highlights all instances, a particular invocation only its nodes.
Unsaved edits invalidate that file's ranges until the saved model is refreshed.

Both IDE plugins highlight associated nodes as the caret moves, without moving the
camera or sending graph-to-code navigation events. **Service Architect: Show in
Graph** explicitly focuses a node; shared implementations offer a chooser. Business
code uses the installed IDE language provider's current symbols in the configured
generated directory, with a file match fallback when symbols are unavailable. It
supports Go, C++ userver/Coro, Rust, Python and TypeScript without a generator map.
File-level/ambiguous matches retain all associated nodes rather than choosing one.
