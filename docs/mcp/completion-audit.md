# MCP authoring and generation acceptance

Date: 2026-10-11.

## Scope

The editable source is the typed Python project. MCP exposes structured object
guidance, pattern recipes and source-preserving changes, then validates, exports,
generates and merges code. Canonical YAML and generated files are derived
artifacts, not a second authoring model.

## Verified results

| Gate | Result |
| --- | --- |
| Full Python regression suite | 314 passed; 234 subtests passed; 34.85 seconds |
| Installed wheel, actual stdio MCP discovery | 21 tools, 8 resources, 10 resource templates |
| Object guidance | 30 object guides and typed API discovery |
| Pattern catalogue | 10 executable Python recipes |
| Pattern generation | All 10 accepted by the real Lambda generation handler |
| Pattern compilation | All 10 generated Go projects passed `make build` |
| Canonical generation and merge | Three real generations; two preview/apply cycles |
| Canonical compilation | OrderService, InventoryService, AnalyticsService and AutomationService passed `make build` |
| Business-code preservation | Entire modified Go business file preserved across regeneration and merge |
| Source preservation | Python authoring bytes and environment file preserved |
| Generated merge verification through MCP | `make merge-validate`, exit 0 |
| Canonical YAML round trip | Import, validate and export preserved the parsed model |
| Nested project resources | Separate caches, scoped links and diagnostics, including paths with spaces |
| Passive resource reads | No execution of Python authoring code |
| Public deployed metadata | Capabilities and validation contract refreshed and read successfully |
| Live AWS generation through installed MCP | Canonical processorder generated and downloaded successfully in 9.49 seconds |
| Live AWS artifact compilation | All four Go services passed the generated `make build` target |
| Updated authoring and validation skills | Both passed the skill validator |

## Compiled patterns

All recipes currently target Go. Each project was generated from the published
recipe, extracted into a separate temporary directory and built with the
generated `make build` target. Where needed, this also generated OpenAPI and
protobuf bindings. No business-function implementation or generated contract was
changed to make compilation pass.

| Pattern | Generation | Compilation |
| --- | --- | --- |
| `http-request-response` | Pass | Pass |
| `conditional-routing` | Pass | Pass |
| `failure-compensation` | Pass | Pass |
| `temporal-sequential` | Pass | Pass |
| `temporal-scheduled` | Pass | Pass |
| `kafka-processing` | Pass | Pass |
| `broadcast-fan-out` | Pass | Pass |
| `iterable-worker-aggregation` | Pass | Pass |
| `temporal-parallel` | Pass | Pass |
| `bounded-feedback` | Pass | Pass |

Compiler: Go 1.26.4 on the local macOS host. Builds used the existing transport
generator tools and a temporary `go.work` replacement pointing to the local
`servicelib` checkout. Therefore these results cover the current local runtime,
not independently downloaded published runtime versions.

## Defects found during acceptance

- Composite array/map type references in API requests were not translated to
  public type names. Real generation of the iterable recipe caught this; the
  conversion and five focused regressions now cover the affected request paths.
- Nested projects had tool support but insufficiently scoped resources. Explicit
  project resource links now select the matching manifest, model, tasks, audit
  and metadata without mutable active-project state.
- Generation failures lost useful backend diagnostics. Structured diagnostics
  and project-scoped validation-rule links now survive supported API envelopes.
- Generation merge protection, destination locking, bounded verification process
  cleanup and nonfatal audit failures are covered by regression tests.

## Evidence

These are local acceptance artifacts, not portable repository fixtures:

- Full suite: `/tmp/sa-mcp-final-all-20261011.log`.
- Final wheel and installed-wheel logs: `/tmp/sa-mcp-release-final.Lxe99G/`.
- Pattern requests, models and generated ZIPs:
  `/var/folders/gp/w6c4c_m921b0cn2zlqgr1c9m0000gn/T/sa-mcp-pattern-generation-a24tjyd6/`.
- Ten compilation logs, binaries and exit-code table:
  `/tmp/sa-mcp-compilation.RgISLS/`.
- Canonical compilation: `/tmp/sa-mcp-canonical-compilation-20261011.log`.
- Canonical generated/merged workspace and actual API request bodies:
  `/var/folders/gp/w6c4c_m921b0cn2zlqgr1c9m0000gn/T/sa-mcp-real-generation-as0v9sgn/`.

## Boundaries of these results

- Real code generation used the actual local Lambda handler via an HTTP wrapper
  built with a Go overlay. Queue/status/download HTTP behavior was simulated by
  the acceptance gateway; the generated ZIPs and merge scripts were real.
- The original acceptance used the local gateway. A subsequent explicitly
  authorized live check sent the canonical processorder model through the
  installed MCP to the production AWS API and downloaded the real result.
  No cloud deployment was changed. See the live-check evidence below.
- Compiling generated business stubs is not an execution test of their future
  business logic. Kafka and Temporal services were not started for this gate.
- The compilation matrix above is Go only, not a claim about every language
  supported by Service Architect.
- Real Windows process-tree termination was not exercised on this macOS host.
- No commit, push or plugin release was performed.

## Subsequent live AWS check

The user supplied an environment file containing an API key. No API URL override
was present, so the client used its default production endpoint:
`https://z06e41vwnl.execute-api.us-east-1.amazonaws.com/prod`.
The old repository environment pointing to the legacy `/test` endpoint was not
used. Credentials were not printed; the temporary environment file was removed
after the MCP process completed.

The installed wheel's stdio MCP validated an isolated copy of the canonical
processorder Python project and ran `generate_project` against AWS. The operation
returned success with no diagnostics in 9.49 seconds, including download. This
is end-to-end client duration, not a measurement of Lambda execution alone.
No queue-transition trace was captured, so individual QUEUED/RUNNING durations
are not asserted.

The downloaded ZIP contained 546 files, occupied 526259 bytes and passed its CRC
integrity check. The generated `make build` then generated HTTP/gRPC bindings and
compiled orderservice, inventoryservice, analyticsservice and automationservice,
using the same local Go runtime override documented above. Services were not
started, and the user's working project was not changed.

- Redacted MCP results: `/tmp/sa-mcp-live-aws-20261011.log`.
- Compilation output: `/tmp/sa-mcp-live-aws-build-20261011.log`.
- Isolated model, archive and compiled output:
  `/var/folders/gp/w6c4c_m921b0cn2zlqgr1c9m0000gn/T/sa-mcp-live-aws-xmwv2ijv/`.

## Ongoing gate

A pattern change must pass typed-model validation, real generation and generated
code compilation. Keep the language/runtime and any dependency overrides in the
report. A green schema check or a successfully downloaded archive alone does not
satisfy this gate. For source-editing and merge changes, also retain the existing
preservation, stale-revision, workspace-boundary and failure-path regressions.
