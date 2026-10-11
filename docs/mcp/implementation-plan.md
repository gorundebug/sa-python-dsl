# MCP authoring and verification plan

## Objective and invariants

Keep typed Python as the single editable architecture source. Agents should
understand the meaning of an object before selecting its factory. They should
be able to add a node, connect existing ports and add an endpoint through MCP,
without rewriting YAML or flattening Python factories into generated source.

Preserve user functions, comments, imports, module organization and unrelated
files. Validate candidate changes before applying them. Reject ambiguous or
unsupported edit sites instead of silently changing semantics. Runtime support
comes from the backend capability contract, not a similarly named DSL method.

## Sequence

1. Run the current regression suite and inventory every tool/resource family.
2. Repair confirmed defects and establish an honest baseline, distinguishing
   implementation failures from sandbox restrictions and stale test doubles.
3. Expose bounded, intent-first object guides with reflected DSL signatures.
4. Implement inspectable Python edit plans for add-node, connect-ports and
   add-endpoint, sharing one validation/apply mechanism.
5. Add semantic and source diffs, revision checks, failure atomicity and tests
   for modular projects, factory-built models, branch/result/error connections.
6. Complete the recipe specifications in architecture-patterns.md, expose
   executable, tested examples through the existing MCP pattern resources.
7. Exercise the end-to-end workflow on isolated copies of canonical projects,
   including generation/merge and preservation of business implementations.
8. Check packaging, documentation, skills and the actual stdio MCP interface.

## Verification matrix

| Surface | Existing coverage to run | Additional acceptance evidence |
| --- | --- | --- |
| inspect / doctor | manifest_workflow, doctor | Missing manifest, incompatible cache, no Python execution |
| resources / signatures | mcp_resources, api_catalog, semantic_playbook | All object and recipe links resolve, bounded responses |
| validate / export | manifest_workflow, model validation suites | Invalid candidate never replaces valid Python/YAML |
| YAML import | yaml_round_trip, importer_symbol_collisions | Re-export matches semantics, source names preserved |
| architecture diff | semantic_diff | Correct changed nodes, endpoints, edges and metadata |
| capability/diagnostic refresh | servicegen_capabilities, servicegen_validation | Cache mismatch, failures, explicit network boundary |
| Designer | designer_view, mcp_protocol | Exact revision, loopback errors reported structurally |
| generate ZIP | code_generation, generation_build_options | Real backend run separately from mocked transport tests |
| preview / apply | generation_transaction | Stale/replayed/tampered preview, user code protection |
| tasks / verification | business_tasks, operation_audit | Generated output directory and allow-listed commands |
| new Python edits | New dedicated suite | Conflicts, source preservation, validation, no partial writes |
| protocol / package | mcp_protocol, release_contract | Actual tool schemas, resource discovery, packaged guidance |

## Initial baseline: 2026-10-11

186 tests ran. One outdated generation test double does not accept on_progress.
Two Designer tests require a loopback listener disallowed by the default sandbox.
The production Designer tool also needs a structured error for failed listener
startup rather than propagating an OSError through the MCP protocol.

The baseline suite is not proof of full backend correctness: several tests use
transport or merge fixtures. Record real generation/merge evidence separately.

## Implementation checkpoint: 2026-10-11

The test runner now uses pytest rather than silently omitting function-style
tests. Existing IDE fixtures have been aligned with persisted canonical output.
Object discovery is implemented for 30 object kinds with reflected typed API
signatures, semantic links and pattern guidance.

Confirmed and repaired a generation-directory defect: MCP preview/apply,
business tasks, verification and doctor used the architecture directory instead
of the manifest's outputDirectory. Parent/sibling output, authoring protection,
workspace boundaries and stale output are covered by new regressions. This
suite initially reached 212 passed and one failed assertion: a test secret named
"private" also matched macOS's /private path. The fixture now uses a unique
secret and the generation-directory regressions pass.

Python editing now has an initial implementation in python_authoring.py and a
MCP adapter in mcp_authoring.py. Its six tools are now registered and covered by
stdio discovery, source inspection, stale-revision and boundary tests. It
supports single-file insertion batches, source and semantic diffs, worker
validation on a shadow copy, immutable previews and atomic application. See
python-authoring.md for its deliberately narrow editing contract.

The Project-name mismatch and adapter import have been corrected. The complete
suite now reports 224 passed, 5 failed and 234 subtests passed (8.28 seconds).
All five failures are new editor tests blocked at baseline validation because
their HTTP connector fixture lacks its required contract module. Correct the
fixture without bypassing that validation.

A separate canonical-project reproduction found a real editor defect: the
shadow directory loses the original processorder package name, so its main.py
cannot import processorder. Preserve the root basename inside the temporary
parent for both preview and apply. Error connections also need the ordinary
edge before on_error; additional merge/join inputs need an explicit << role.
Application locking should cover the whole workspace, not only one preview ID.
These corrections and a successful real edit/apply protocol test remain pending.
Tool registration is not evidence that the authoring workflow is complete.

Fixed an existing verification-discovery defect: targets in included generated
Makefiles were invisible. Discovery now follows bounded, workspace-local literal
includes and wildcard includes without evaluating Make or shell expressions.
It handles include cycles and rejects paths outside the workspace. Combined
business-task, stdio and generation-directory regressions: 16 passed.

Remaining: richer runnable pattern recipes and tests, actual MCP edit protocol,
package/docs alignment and real
backend generation/merge acceptance. The goal is not complete.

## Source editing design

Do not add a hidden second graph or regenerate all Python from canonical YAML.
Locate existing declarations and references, distinguish a factory definition
from its instances, and preserve source bytes outside the selected edit.
Treat the requested port role explicitly: ordinary input, additional join input,
ordered Case branch, result binding, error route and feedback are not aliases.
Decide ambiguity before writing. Existing Python factories remain supported for
ordinary authoring even when automated editing must decline a particular site.

## Completion gate

All existing operations have positive and negative coverage; new operations
change the real Python source and preserve unrelated text; recipes have checked
DSL examples and explicit semantic decisions; package/protocol tests and isolated
generation/merge scenarios pass. No cloud deployment or Git publication is
included without an explicit user request.

## Checkpoint: 2026-10-11, catalogues and verification lifecycle

This checkpoint supersedes older status counts above; the goal is not complete.

- The HTTP fixture now supplies its required module and `golang_version`.
  All 14 source-authoring tests pass, including the five previously blocked cases.
- Canonical package identity in shadow execution, complete error connections,
  additional Merge inputs and the workspace-wide edit lock have dedicated passing
  regressions. The canonical stdio authoring workflow passes.
- The catalogue now exposes ten Python recipes, their six semantic contracts,
  object references and links to preview/apply operations. Actual stdio resource
  reads succeed. Nine recipe models export successfully; broadcast still needs a
  valid result binding. Transport references need the existing `-endpoint` names.
  These six recipe/resource test failures remain explicit, not skipped.
- The last full suite before lifecycle work: 238 tests and 234 subtests passed;
  six failures all concern those new recipes. A fresh full suite is required after
  repairs. Passing narrow suites must not be reported as a complete audit.
- Direct reproduction confirmed that the old verification timeout killed Make
  while its child continued. Verification now owns a process group and bounds
  captured output while continuously draining both pipes. Nineteen focused tests
  pass, including child termination, noisy output, Unicode and injected runners.
- The initial MCP timeout test still needs its timeout injection corrected: the
  old runner default was bound at function definition, so replacing
  `subprocess.run` did not shorten it. Its broad string check also matched the
  temporary path. The separate direct regression checks the exact
  `SA_VERIFICATION_TIMEOUT` code and the child's marker; do not drop that check.
- Live ZIP generation/merge acceptance has not run. The environment rejected
  outbound model transfer pending explicit destination approval. Local inspection
  proves the request is a 43,124-byte architecture JSON document from the Example
  fixture, not a source archive, with no nonempty secret fields. The configured
  destination is the user's AWS Service Architect API, us-east-1, test stage.
  No network request or remote deployment was performed by the rejected commands.

Remaining gates include repairing all new recipe checks and the MCP timeout
fixture, a clean complete regression run, package/release checks, and actual
ZIP regeneration/merge preserving business code. The audit-write defect after a
successful operation was reproduced and repaired: MCP returns the actual result
with a warning instead of raising after completion. Its regression passes as part
of a 21-test focused run. Generation-apply concurrency and resource output-root
consistency still require focused investigation. Do not mark the goal complete
until those named gates have evidence.

Latest full regression after lifecycle/audit fixes:
`/tmp/sa-mcp-regression-20261011-lifecycle.log` records 244 passed tests,
234 passed subtests and seven failures in 17.21 seconds. Six failures are the
catalogue issues listed above; the seventh is the explicitly identified timeout
injection fixture. No tests were disabled. The production timeout fix has its
separate passing exact-code/child-lifetime regression. Live generation remains
unexecuted, awaiting the outbound-model permission requested from the user.

## Checkpoint: 2026-10-11, destination locking and resource consistency

- Reproduced and fixed the tasks resource reading the authoring directory instead
  of `generation.outputDirectory`. Both nested-output discovery and rejection of
  output outside the MCP boundary now have passing resource-level tests.
- Reproduced two successful concurrent applies of the same or different previews.
  Apply now takes an OS-backed lock keyed by the resolved output directory before
  checking revisions, and holds it through merge and the applied marker. Tests
  cover separate authoring projects targeting the same output, another process,
  independent destinations, and automatic release when a process exits. Lock
  files are private and outside the project, preserving preview revisions.
- Reproduced a merge child writing after the parent timed out. Moved the tested
  bounded process runner into `process_execution.py` and reused it for merge and
  verification. Twenty-six focused tests passed after the move.
- Added direct capability and validation-contract resource links to every recipe.
- Added `verification-matrix.md`: all 21 discovered tools, eight concrete
  resources and seven resource templates, with evidence and remaining gates.
- Built `/tmp/sa-mcp-release.zFsdx3/sa_python_dsl-0.1.0-py3-none-any.whl` offline,
  installed it and 29 runtime dependencies in a clean temporary venv, and
  validated the canonical Example successfully with that installed CLI. The
  artifact predates the final common-process-runner move and must be rebuilt
  before final acceptance. The package-level MCP smoke also needs its Python
  SDK assertion corrected (`is_error`, not `isError`); it is not a passing gate.
- Latest full regression: 253 passed tests, 234 passed subtests, seven known
  failures, 19.68 seconds. Log:
  `/tmp/sa-mcp-regression-20261011-destination-lock.log`.
  The seven failures are still the six recipe checks and the original MCP timeout
  injection fixture; no tests were disabled. This is not a green release.

The earlier audit, task-root and concurrent-apply investigation items are now
resolved with regressions. Remaining work includes all known failing examples /
fixtures, installed-artifact protocol and Designer acceptance, fuller endpoint
transport mutation coverage, the final metadata/resource coverage audit and live
ZIP regeneration/merge preservation. Outbound-model approval is still pending;
no remote generation request has been sent by the rejected acceptance commands.

## 2026-10-11: repair checkpoint and installed-wheel acceptance

This checkpoint supersedes the earlier reports of 7 and 15 failing tests.

- Corrected endpoint-test variable shadowing, the verification-timeout injection,
  object-guide resource links, and the broadcast recipe's required result binding.
  The broadcast result returns the original value; it is not an observer-completion
  barrier. No assertions were removed and no tests were skipped.
- Focused repair suite: 22 passed. Full suite: 283 passed and 234 subtests passed,
  in 33.03 seconds. Log: `/tmp/sa-mcp-regression-20261011-repaired.log`.
- Built the current wheel offline and installed it into a separate virtualenv.
  Through actual MCP stdio, the installed package successfully inspected,
  validated and exported the canonical Example, produced an architecture diff
  and Designer snapshot, served Designer/catalogue resources, imported the YAML
  into a new typed Python project, and validated/exported it again. Parsed YAML
  before and after import/export was identical. Package imports were confirmed
  to come from the installed wheel, not the source checkout.
- Wheel acceptance artifacts and log: `/tmp/sa-mcp-release.6kKBor/`.
- The user's instruction is to continue ordinary corrections and already agreed
  checks without asking for approval of each individual repair.

The goal remains active. The public test backend's metadata endpoints returned
HTTP 403 (`MissingAuthenticationTokenException`), and live generation against
that backend has not been executed because the environment rejected the network
operation. Local generation/merge tests do not replace that remote acceptance.
No cloud settings were changed, and no commits or pushes were made.

## 2026-10-11: backend diagnostics and public metadata acceptance

- Confirmed a production error-handling defect using a real ServiceGen problem
  response: generation and preview converted backend `SG_*` diagnostics to a
  generic `SA_*` string. The client now preserves structured diagnostics from
  direct responses, gateway envelopes and failed-job details. Archive generation
  and generation preview retain code, source/path, stage and details. MCP adds
  the cached validation-rule URI and remediation. Invalid/missing diagnostics
  still use the original generic failure; no server errors become successes.
- Added 17 regression cases, including real HTTP plus MCP stdio and checks that
  a failed generation creates no archive/preview and exposes no test credential.
  Focused suite: 24 passed. Full suite: 300 passed, 234 subtests passed in 34.80s.
  Log: `/tmp/sa-mcp-regression-20261011-diagnostics.log`.
- Rebuilt and installed the updated wheel in a clean virtualenv. Canonical
  validation/export, Designer snapshot and YAML/Python round-trip passed again.
  Artifacts: `/tmp/sa-mcp-release-diagnostics.eSKzWT/`.
- Public metadata is NOT generally blocked. The API-key client's default backend
  `https://z06e41vwnl.execute-api.us-east-1.amazonaws.com/prod` returned HTTP 200
  for capabilities and the validation contract. Actual installed-wheel MCP
  refreshes succeeded, followed by reads of both cached documents, Go
  capabilities and the `SG_SCHEMA_WRONG_TYPE` rule. Requests were public GETs,
  with no credentials or model upload. The previous 403 is specific to the old
  `/test` backend URL selected in the earlier check. Client metadata defaults
  already use the production API-key URL; no fallback or URL change was needed.

Remaining generation acceptance: the temporary local gateway incorrectly
forwarded the cloud API's flat JSON DTO directly into the local generator's
canonical-YAML endpoint. That attempt correctly failed schema validation before
any ZIP/merge. This is an acceptance-harness mismatch, not evidence that the MCP
model or generator is defective. The harness needs the authoritative API-to-model
conversion; substituting an unrelated pre-exported model would weaken the check.
No successful end-to-end real-generator ZIP/merge claim is made from that run.
Live cloud generation was not submitted. No deployment, commits or pushes occurred.

## 2026-10-11: real generated archives and project-scoped resources

- Corrected the temporary acceptance backend by running the actual
  `cmd/awslambda.HandleGenerationRequest` through a localhost HTTP wrapper built
  with a Go overlay. The production worker and Lambda both decode the flat API
  request into `api.StreamApp` and call `GenerateCodeWithOptions`; no canned YAML
  or fixture ZIP was substituted. Repository generator files were not modified.
- The installed wheel completed two real generations, queued/running/succeeded
  protocol transitions in the local gateway, ZIP downloads, two previews and two
  applies. Preview did not write generated files. After the first merge, a
  user-owned Go business file was changed; its full bytes survived the second
  preview and apply. Python authoring bytes and its environment file also survived.
  Download/public metadata requests carried no generation credential.
- This exposed a genuine nested-project resource defect: tools accepted a child
  `project_path`, but current-workspace resources read only the workspace root.
  Added explicit project-scoped resource templates and `inspect_project.resources`
  links, without any mutable current-project selection. Rule URIs now select the
  matching project's cached validation contract. Root aliases remain available;
  missing manifests/artifacts yield diagnostic payloads rather than tracebacks.
- The real generation acceptance then passed, including project-scoped tasks and
  audit reads. It found 69 pending business tasks and the generated allow-listed
  verification targets. Invoking `run_verification` for `merge-validate` through
  the installed MCP returned exit code 0 and `Post-merge validation: PASS`.
- Updated authoring/validation skills for explicit project resource links; both
  passed the skill validator. Passive resource tests verified separate caches,
  nested paths with spaces and no Python authoring execution.

Artifacts: `/tmp/sa-mcp-release-scoped.FNw1nh/`; generated project and backend
requests/ZIPs: `/var/folders/gp/w6c4c_m921b0cn2zlqgr1c9m0000gn/T/sa-mcp-real-generation-j9sbbyvs`.
The local gateway simulates queue/status/object-storage HTTP behavior, not AWS
infrastructure. Actual code generation and generated merge/verification scripts
are real. Cloud generation was not submitted or deployed.

Latest full suite: 301 passed, 234 subtests passed, 1 failed in 35.29 seconds.
Remaining failure is a new negative resource-test expectation: the MCP SDK rejects
`servicegen://project/..%2Foutside/audit` as `Unknown resource` before our handler,
where the test expected a JSON boundary diagnostic. The safety rejection is real;
the test must distinguish protocol-level rejection from handler-level rejection
and still prove that no outside data is read. Do not count this suite as green.

## 2026-10-11: generation and compilation acceptance gate

The user explicitly requires checking generated code, not just valid pattern
models. Completion now requires each of the ten published Python recipes to pass
validation, actual code generation, transport-binding generation and compilation,
plus compilation of the canonical processorder example. A valid model or a ZIP
alone is not sufficient. Do not replace generated contracts or implement business
stubs just to make this gate pass. Record the tested language/runtime explicitly;
a Go compilation result is not evidence for other language backends.

- Fixed the negative resource test to accept the SDK's precise unknown-resource
  rejection, with independent handler boundary tests. The full suite now passes:
  314 tests and 234 subtests, 34.85 seconds.
- Real generation of the iterable aggregation recipe exposed unresolved composite
  type references in the API request. Array/map valueType and keyType now map to
  the same public type names as other references; five regression tests cover
  nested composites, unknown references and both generation client protocols.
- All ten published recipes now generate successfully through the actual Lambda
  generation handler, with no canned archives. These recipes currently target Go.
- The final installed wheel passes canonical import/export, Designer snapshot,
  three real generations and preservation/merge verification. Compilation is the
  next gate and is not yet claimed as successful.

Generation artifacts:
`/var/folders/gp/w6c4c_m921b0cn2zlqgr1c9m0000gn/T/sa-mcp-pattern-generation-a24tjyd6`.
Final wheel and acceptance logs: `/tmp/sa-mcp-release-final.Lxe99G/`.

### Compilation completed

All ten Go pattern projects passed their generated `make build` target, including
all three Temporal recipes. The canonical example also built OrderService,
InventoryService, AnalyticsService and AutomationService after the installed-wheel
MCP generation/merge acceptance. HTTP and gRPC bindings were generated as part of
the build. No business stubs or generated contracts were altered.

The first attempt was blocked by sandbox access to the host Go build cache; the
same commands succeeded with authorized cache access. This was an environment
restriction, not a generated-code error. Builds use Go 1.26.4, existing transport
tools and a temporary go.work override to the local servicelib checkout.

See [completion-audit.md](completion-audit.md) for the results, exact artifact
locations and limitations. In particular, no live AWS generation, other-language
compilation or Kafka/Temporal runtime execution is claimed from this acceptance.
