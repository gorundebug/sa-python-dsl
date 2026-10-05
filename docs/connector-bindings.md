# Connector implementation bindings

All six connector factories accept `implementations: Mapping[str, str] | None`:

```python
project.http_connector(
    "Public API",
    implementations={"external": "vendor/http"},
)
```

Keys are open template target identifiers, not a fixed enum of languages.
Use `[A-Za-z][A-Za-z0-9_-]*`, with exact case. Values are nonempty implementation
names without surrounding whitespace. `go` is a compatibility alias for
`golang`. The dictionary does not register a runtime or provide its transport:
the selected template pack and runtime must supply that implementation.

Existing factory defaults and legacy keyword arguments are unchanged. When
selecting a different implementation for an existing target, explicitly disable
its legacy default rather than introducing two contradictory declarations:

```python
project.http_connector(
    "Public API",
    go_implementation=None,
    implementations={"golang": "custom/http"},
)
```

Equal legacy/dictionary choices are allowed. Conflicting choices, including
different `go` and `golang` values, fail validation. Unknown targets are retained
as authored data. A custom connector's `implementation` remains its default;
target-specific selections can coexist with it.

Factories copy the dictionary. Export returns detached data. YAML-to-Python
import preserves bindings and does not reinsert legacy selectors absent from
the source. Existing generated API catalog resources expose the new parameter
through signature reflection, without a separate hand-maintained signature.

This extends connector bindings only. Arbitrary service language declarations
and external runtime generation have their own capability and template-pack
requirements; this parameter does not bypass them.
