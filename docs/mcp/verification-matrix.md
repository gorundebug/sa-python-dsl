# MCP verification matrix

This is a coverage map, not a declaration that the whole goal is complete. The
current stdio discovery exposes 21 tools, eight concrete resources and seven
resource templates. Known failures and live-service gates remain listed below.

## Tools

| Tool | Evidence / test file under `tests/` | Remaining acceptance |
| --- | --- | --- |
| `inspect_python_authoring` | `test_python_authoring.py`, `test_mcp_authoring_workflow.py` | Installed-wheel end-to-end |
| `preview_python_changes` | Source preservation, stale state, batch and invalid-expression tests in `test_python_authoring.py` | Installed-wheel end-to-end |
| `add_node` | Canonical modular project via stdio in `test_mcp_authoring_workflow.py` | Installed-wheel end-to-end |
| `add_endpoint` | HTTP canonical workflow; initial gRPC/Kafka/Cron/Temporal preview/apply checks passed in `test_mcp_endpoint_authoring.py` | Its extension connecting Input/Map/result is blocked by test-variable shadowing, not counted as passing |
| `connect_ports` | Additional Merge input and complete error route through stdio in `test_mcp_authoring_workflow.py` | Installed-wheel end-to-end |
| `apply_python_changes` | Revision, replay and concurrency cases in `test_python_authoring.py` and `test_mcp_authoring_workflow.py` | Installed-wheel end-to-end |
| `describe_architecture_object` | Reflected factories in `test_architecture_objects.py`, all 30 resource guides over stdio in `test_mcp_catalog_protocol.py` | Keep reflected API checks in regression |
| `inspect_project` | Stdio discovery in `test_mcp_protocol.py` | Installed-wheel smoke needs a corrected SDK assertion |
| `doctor` | Passive/no-credentials disclosure in `test_doctor.py`; output-root checks in `test_mcp_generation_directory.py` | No live-generation claim from doctor alone |
| `refresh_capabilities` | Unit checks plus actual stdio/local HTTP refresh, cache, credential exclusion and backend URL selection tests | Configured test-stage public endpoint returns HTTP 403 |
| `refresh_validation_contract` | Stdio/local HTTP refresh, rule lookup, invalid-evaluator/cache-preservation and backend URL selection tests | Configured test-stage public endpoint returns HTTP 403 |
| `validate_project` | Worker/model regression, canonical authoring workflow and successful canonical Example validation from an isolated installed wheel | Rebuild the wheel after remaining changes |
| `export_project` | Canonical stdio workflow and worker export regression | Preserve canonical source ownership on real generation |
| `generate_project` | HTTP client submit/poll/download/failure tests in `test_code_generation.py` | Real configured backend, not a mocked opener |
| `preview_generation` | Exact-archive preview and traversal checks in `test_generation_transaction.py`; output/source guards in `test_mcp_generation_directory.py` | Real generated ZIP/merge script |
| `apply_generation` | Replay/stale/output checks; `test_generation_apply_concurrency.py`, `test_destination_lock.py`, `test_merge_process_lifecycle.py` | Real regeneration with unchanged user business code |
| `inspect_business_tasks` | Task/progress parsing in `test_business_tasks.py`, output-root consistency in `test_mcp_generation_directory.py` | Real generated business task catalogue |
| `run_verification` | Fixed argv, bounded capture, process cleanup and audit-error tests | Correct the separate MCP timeout injection fixture; Windows execution |
| `import_yaml_project` | Existing importer/CLI regressions and stdio discovery | Re-audit a complete import/edit/export cycle from installed wheel |
| `preview_architecture_diff` | Entity and ordering regressions in `test_semantic_diff.py`; canonical editing workflow | Installed-wheel end-to-end |
| `designer_view` | Local snapshot server and real stdio in `test_mcp_protocol.py` | Package-level Designer smoke |

The table deliberately distinguishes discovery from behavioral assertions. A
tool appearing in `tools/list` is not evidence that all of its execution paths
were exercised.

## Concrete resources

| URI | Coverage / expected behavior |
| --- | --- |
| `ui://service-architect/designer` | Stdio Designer/local snapshot regression |
| `servicegen://workspace/current/capabilities` | Actual stdio/local HTTP cache round-trip and preservation after an invalid refresh in `test_mcp_metadata_refresh.py` |
| `servicegen://workspace/current/validation-contract` | Actual stdio/local HTTP cache round-trip and preservation after an invalid evaluator in `test_mcp_metadata_refresh.py` |
| `servicegen://workspace/current/source` | Passive resource regression in `test_mcp_resources.py` |
| `servicegen://workspace/current/dsl` | Passive resource regression; canonical YAML is an export, not the editable source |
| `servicegen://workspace/current/graph` | Canonical graph representation; detailed resource assertions remain in the final audit |
| `servicegen://workspace/current/tasks` | `test_mcp_task_resource.py`: generated output directory and MCP boundary rejection |
| `servicegen://workspace/current/audit` | Local audit resource; completed-operation audit-write failure regression passes |

## Resource templates

| URI template | Coverage / remaining checks |
| --- | --- |
| `servicegen://semantics/{topic}` | Every indexed resource read over stdio without running project Python in `test_mcp_metadata_protocol.py` |
| `servicegen://authoring/{topic}` | Reflected API, every indexed API topic and all object guides over real stdio |
| `servicegen://schema/{topic}` | Both indexed descriptors read and version-checked over stdio in `test_mcp_metadata_protocol.py` |
| `servicegen://examples/{topic}` | Existing example resources; do not equate readability with executable correctness |
| `servicegen://patterns/{topic}` | Ten resources readable by installed source server; worker execution and object-reference tests still have known failures |
| `servicegen://capabilities/{language}` | Actual stdio lookup after an HTTP refresh in `test_mcp_metadata_refresh.py`; configured remote endpoint is blocked |
| `servicegen://validation/rules/{code}` | Actual stdio rule/remediation lookup after an HTTP refresh; unknown-rule cases still require final coverage confirmation |

## Known incomplete checks

- The broadcast recipe needs an explicit valid result binding. Five further
  recipe checks fail on transport-guide links lacking the `-endpoint` suffix.
- The initial MCP timeout fixture replaces `subprocess.run`, which does not
  shorten the actual selected runner. Its broad string assertion also matches
  the temporary path. Separate direct process tests check the exact timeout code
  and prove that the child cannot write after timeout.
- The first installed-wheel MCP smoke used `isError` as a Python attribute;
  the installed SDK uses `is_error`. This is a smoke-driver issue, not evidence
  of a package or server defect, and the smoke is not counted as passed.
- The extended endpoint workflow test shadows its outer `arguments` parameter
  inside the async function. This blocks eight cases before endpoint editing.
  The earlier endpoint-only preview/apply/validation run passed all eight
  transports plus a negative-argument case; that does not establish the new
  connected Input/Map/result workflow until its fixture is repaired and rerun.
- Unauthenticated GETs to the configured test-stage metadata endpoints returned
  HTTP 403. API Gateway reports `MissingAuthenticationTokenException`; this may
  be a route/stage issue, not a reason to attach credentials to public requests.
- Live generation is awaiting explicit outbound-model permission. The rejected
  commands did not submit a job. No cloud deployment is part of this goal.
- POSIX locking/process cleanup has local evidence. Windows implementations
  need Windows acceptance and must not be described as tested on this machine.

Final acceptance must include a clean full suite, the installed artifact, all
named tools/resource groups, and the real generation/merge preservation scenario.
No failing tests may be skipped or removed to satisfy that gate.

## Latest acceptance checkpoint: 2026-10-11

The earlier recipe, endpoint-fixture and timeout-fixture failures recorded above
are resolved. All 283 tests and 234 subtests passed; no tests were skipped to
obtain this result. The focused corrected suite passed all 22 tests.

The freshly built wheel also passed a separate actual-stdio acceptance in a clean
virtualenv: canonical project inspection/validation/export, architecture diff,
Designer snapshot and resource retrieval, catalogue resources, YAML import into
Python, and a second validation/export with equivalent canonical YAML. This
checks the installed package rather than importing the source checkout.

Remote acceptance remains separate and incomplete: the public metadata endpoints
returned HTTP 403, and no live generation request was sent. Windows-specific
process cleanup still requires acceptance on Windows. A successful local suite
must not be reported as proof of those external/platform gates.

## Backend-error and metadata update: 2026-10-11

Latest full suite: **300 passed, 234 subtests passed**. The added checks cover
structured backend errors through client, archive generation, preview and real
MCP stdio/HTTP. Original `SG_*` codes and source paths survive, and MCP attaches
cached rule references/remediation. Generic network/protocol errors remain errors.

The rebuilt installed wheel passed canonical import/export and Designer snapshot
acceptance again. Public metadata was also verified against the production
API-key backend through the installed MCP: both refreshes, both cached resources,
Go capabilities and a specific validation rule succeeded. Earlier HTTP 403
observations apply to the legacy `/test` address, not the production metadata API.

A separate attempt at actual local-generator ZIP/merge acceptance did not pass:
the temporary gateway sent an API JSON DTO to a canonical-YAML-only endpoint.
It stopped at schema validation. Real generated-archive merge acceptance remains
open; fixture-archive tests and metadata success do not close that requirement.

## Real-generator acceptance and nested-project coverage

The latest installed-wheel acceptance used actual ServiceGen Lambda generation
code locally, not fixture archives. Both preview/apply cycles passed and preserved
an edited user-owned business function and Python authoring. Project-scoped task
and audit resources were read successfully; `run_verification("merge-validate")`
on the real output passed. Local queue/status/download HTTP behavior is simulated;
this is not evidence of an AWS queue deployment or cloud generation invocation.

Added three resource templates for explicit projects:

- `servicegen://project/{project}/{kind}`
- `servicegen://project/{project}/capabilities/{language}`
- `servicegen://project/{project}/validation/rules/{code}`

Use the links in `inspect_project.resources`. Root aliases are not a last-selected
project and do not change after calls targeting other projects. Current-workspace
source/DSL/graph/audit failures now return diagnostics rather than throwing an
unexpected resource exception. The SDK may reject an invalid resource URI before
a handler is invoked; that protocol failure must not be mistaken for a successful
read or for evidence that the handler itself processed the URI.

Full regression checkpoint: 301 tests and 234 subtests passed; one new negative
URI test still has the wrong expected failure representation. Completion remains
unproven until that test and the final full suite pass.

## Real generation and compilation gate

For every published pattern, model validation is followed by actual generator
execution and compilation of the resulting project. The canonical example must
also compile after MCP generation and merge. A fixture ZIP or schema-only check
cannot substitute for this gate.

On 2026-10-11 all ten Go recipes and the canonical example's four Go services
passed their generated `make build` targets, including transport code generation.
See [completion-audit.md](completion-audit.md) for compiler/runtime provenance,
logs and the distinction between compilation and runtime behavior tests.
