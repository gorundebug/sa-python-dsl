# SubStream calls discovered from code

Only clicking **Refresh** starts analysis of all Go services containing SubStreams,
after displaying the model. Opening the graph does not analyze calls. Analysis
includes referenced function modules. The model supplies business identities and
SubStream names; the generator
does not emit an additional mapping. No YAML/Python links are written.

Both IDE hosts call `sa-dsl ide-substream-calls --project ... --service ...
--revision ...`; `--service` is optional for whole-project refresh. The generated-project directory can be overridden with
`--output-dir`, using the same setting as implementation navigation.

The bundled Go helper uses `golang.org/x/tools` SSA and Variable Type Analysis
(VTA). It resolves the concrete returned handle from the generated SubStream
accessor, follows interface values through makers, fields and helper calls,
and traverses incoming calls until a model business-function boundary. Multiple
nodes using the same function receive separate links. A call with no business
ancestor produces no link. Matching message types alone never identifies a
SubStream. Recursive call graphs terminate through visited-node tracking.

Purple dashed edges are **possible static calls**, not observed runtime calls or
guaranteed execution. Selecting an edge displays its evidence chain. VTA is
conservative and context-insensitive: merged field/parameter values may introduce
additional possible targets. Reflection, unsafe code, custom accessors and calls
hidden in dependency bodies may remain unresolved. No discovered edge is not
proof of no runtime call. Other implementation languages are currently reported
as unsupported, never as having zero calls.

Save source files before clicking Refresh. No source/configuration watchers are
registered for this overlay: edits leave the displayed links unchanged. Only the
next Refresh rebuilds them. A newer refresh or closing the view discards an
in-flight result. The graph revision must still
match the evaluated Python model. The normal trusted-workspace requirement applies.

Go 1.25+ must be available on the CLI's PATH. On first use, Go builds the small
bundled helper, downloading its pinned analysis dependencies if absent. The helper
is cached by source and Go version under `$XDG_CACHE_HOME/service-architect/go-calls`
(default `~/.cache`). Subsequent requests reuse the executable but analyze current
saved source. Project code is type-checked, not executed. The project must resolve
its normal Go modules/workspace and build tags; load errors are displayed rather
than replaced by guessed links.
