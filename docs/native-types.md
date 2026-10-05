# Native type bindings

Every public `Project.*_type` factory accepts an optional `bindings` mapping.
Keys are the native-binding target names expected by the selected template
pack, not a closed Python enum. Values are `NativeTypeBinding` objects:

```python
from sa_dsl import NativeTypeBinding, Project

project = Project("Native Records")
record = project.custom_type(
    "Record",
    bindings={
        "external.runtime": NativeTypeBinding(
            definition="ExternalRecord",
            import_path="example.records",
            package="records",
        ),
    },
)
```

| Python field | Type | YAML/API field | Meaning |
| --- | --- | --- | --- |
| `definition` | `str` or `None` | `definition` | Authored native expression/declaration, preserved verbatim |
| `import_path` | `str` or `None` | `import` | Import or header reference interpreted by the template pack |
| `package` | `str` or `None` | `package` | Optional native package/alias metadata |

`None` omits a field. An empty string is retained, so `NativeTypeBinding()` and
`NativeTypeBinding(definition="")` do not mean the same thing. An explicitly
empty dictionary is also retained; omitting `bindings` introduces no binding.
The DSL does not infer a target from the language of a service, translate native
source, or copy one target's definition into another target's entry.

The example emits:

```yaml
bindings:
  external.runtime:
    definition: ExternalRecord
    import: example.records
    package: records
```

YAML-to-Python import reconstructs the mapping using `NativeTypeBinding(...)`
with `import_path` for the wire key `import`. Python-to-YAML export and the
flat JSON generation request retain the same binding records.

Mappings are copied at construction and export. Mutating the caller's mapping
or an exported document does not mutate the type. Deliberate edits to a type's
internal properties are validated before export; unknown fields and malformed
binding values are not silently ignored.

## Removed fields

The numbered `typeDefinitionLang1/2` and `typeImportLang1/2` fields are not
supported. The unqualified `typeDefinition` and `typeImport` fields and Python
`type_definition` / `type_import` constructor arguments are not supported
either. There is no legacy fallback or automatic target selection for them.
Move native data into the target's `bindings` entry explicitly.

This is native type metadata only. `definition_format`, module ownership,
message flow and service deployment boundaries retain their existing meaning.
