"""Project-independent guidance for agents implementing Service Architect models.

Documentation only: these rules neither change SDK contracts nor add validation.
"""

GUIDANCE_RESOURCES = {
    "modeling": "servicegen://authoring/business-modeling",
    "implementation": "servicegen://authoring/implementation-guidelines",
    "review": "servicegen://authoring/review-checklist",
}

SERVER_INSTRUCTIONS = """Service Architect uses typed Python as the editable architecture source;
canonical YAML is generated interchange. Before model or implementation changes,
read servicegen://authoring/business-modeling and
servicegen://authoring/implementation-guidelines; use
servicegen://authoring/review-checklist before completion. Keep meaningful business
stages visible without expanding source-code AST. Each independent handler owns
its pipeline and stream instances; reuse function implementations, not handler
nodes. Inspect existing SDK contracts and canonical examples before adding custom
orchestration or proposing SDK changes. Inject narrow capabilities through makers
and carry business data in typed messages. For process changes, edit the model,
validate/export, generate/merge, implement and verify the generated path within the
user's authorized scope. These resources are guidance, not extra DSL fields or
proof that a backend supports an operation."""

IMPLEMENTATION_GUIDE = {
    "purpose": "Implement the modeled process using existing SDK execution contracts, with cohesive business code and independently editable handler flows.",
    "scope": "Project-independent engineering guidance. Project requirements, authorization and backend capabilities still determine the actual design. This resource does not enforce model validation.",
    "modelingResource": GUIDANCE_RESOURCES["modeling"],
    "reviewResource": GUIDANCE_RESOURCES["review"],
    "workflow": [
        "For process-level changes: inspect typed Python and relevant SDK contracts, edit the model, validate and review the semantic diff, export, generate/merge, then implement the generated contracts. Do not retrofit the graph after building a different orchestration in code.",
        "Implementation-only changes preserving process contracts need not change the model or regenerate unrelated code.",
        "Complete one connected functional change before heavyweight acceptance. Prepare tests with the implementation; use cheap focused feedback as needed, then verify the affected generated paths together. Do not alternate full acceptance with edits to individual fields.",
        "Fix in-scope implementation and fixture errors without repeated permission requests. Respect actual access restrictions and out-of-scope actions; do not weaken expected behavior just to make checks pass.",
        "Track implemented versus verified work and remaining limitations in one functional plan. Reopen accepted work only for relevant changes or new evidence; an unreproduced historical failure is not a proven fix.",
    ],
    "frameworkFirst": [
        "Assume the SDK may already support the requirement. Inspect the selected implementation's contracts, capabilities and canonical examples before concluding that it needs an extension.",
        "Use supported Input/Sink endpoints, Cron, Delay, result/error paths, pools and request lifecycle for their declared jobs. Do not hide a Kafka consumer/producer, scheduler or background processing loop inside Process or a Custom Sink when a standard endpoint covers it.",
        "A Custom source/sink is appropriate for a genuinely unsupported boundary, not a way to conceal an available native transport. SQL, codecs, indexes and cohesive algorithms can remain ordinary business code; not every library call needs a node.",
        "Do not preserve an awkward custom design by adding duplicate dispatchers, registries, queues, completion machines or wrappers. Renaming that machinery does not remove it.",
        "Business-specific batching, policy and state remain in application capabilities and supported endpoint properties/configuration. Do not add application-specific fields to the DSL, API or SDK.",
    ],
    "handlerOwnership": [
        "Every independent handler has its own named pipeline and fresh processing, error and reply nodes. A reader must be able to change this handler's flow without changing another handler's topology.",
        "Reuse the same function identity/package across distinct nodes. Model factories may create similar flows but must return fresh nodes per handler. Shared libraries or state do not imply shared graph nodes.",
        "Do not merge unrelated inputs just because their types or implementations match, or add a reply-routing Case/Split solely to undo that merge. Preserve each endpoint's SDK request/reply lifecycle.",
        "A deliberate single endpoint with one request/response contract may use a bounded event discriminator. Use Case when processing differs; do not create identical branches for every enum value. Different contracts stay separate.",
        "Real business joins, fan-out, callable SubStreams and shared transport/service boundaries remain valid when they have an explicit process purpose. Reducing node count alone is not that purpose.",
    ],
    "messagesAndMakers": [
        "Pass each stage only the interfaces or restricted capabilities it needs through its maker. A service can own shared state and initialize it, but do not inject a global service scope or service locator into every function.",
        "Carry actual business input, intermediate plans and results as typed messages. An ID is appropriate for a real domain reference; it must not hide the current payload, a prepared result or executable continuation in a private context/global registry.",
        "Use struct_type for records, including records implemented in another package; custom_type is for interfaces and genuinely opaque shapes. Preserve existing type identity and user-owned fields, and select supported value/reference transfer explicitly.",
        "Propagate received cancellation, deadlines and tracing context. Do not replace it with context.Background() in Go, or hide business payload/routing in context. Create root context only at a genuine application entrypoint where none exists.",
        "Use the actual result/error contract. In Go, runtime.Consumer.Consume has no error return; this is not a missing feature. Distinguish it from a callable SubStream's invocation error and from business results emitted by that invocation.",
        "Keep transport failures before message receipt distinct from processing failures. Do not invent optional maker/type-assertion hooks that silently switch delivery or failure policy.",
    ],
    "completionAndStartup": [
        "When a result might never arrive, inspect the canonical Process Order work/Delay/result-merge pattern and servicegen://patterns/bounded-feedback. Define correlation, timeout, late/duplicate handling and no-work outcomes; Delay is not proof of business success.",
        "Do not add automatic success for an empty callback, collector emission tracking or a parallel Submit/wait protocol to repair an application completion flow already covered by SDK result/error paths.",
        "Identify the real trigger for every pipeline: endpoint, schedule, SubStream caller or startup/CLI invocation. Document external invocation in the model description; do not invent graph edges for calls with no modeled business ancestor.",
        "Before proposing startup phases or StartGraph-like APIs, inspect actual start concurrency and cancellation. Consider a small application-owned readiness/checkpoint capability shared through the relevant makers; check that waiting cannot block the component that must signal it.",
        "Use Cron for ordinary periodic work and Temporal when durable, restartable orchestration is required. Account for Temporal latency/operational cost; it is not a universal replacement for local scheduling or low-latency execution.",
    ],
    "boundariesAndReuse": [
        "pipeline organizes a scenario; component only folds equivalent concrete fragments visually; SubStream provides service-local invocation semantics; service is an independent deployment/network boundary. Do not interchange these concepts.",
        "Keep service-owned API contracts in independent API modules, separate from service implementation and unrelated shared libraries. API modules must not require service implementation modules; make genuine shared protocol dependencies explicit rather than coupling unrelated service APIs.",
        "Adapters convert partner protocols at declared boundaries while preserving ownership. A local and a remote implementation of the same public role should supply the same complete contract; do not secretly reconstruct one provider's missing response from its private state.",
        "IDE-discovered SubStream calls are a read-only possible-call overlay, not persisted graph links or runtime proof. For current Go analysis, Refresh uses saved code, follows helpers/interfaces including local modules, and creates one link per modeled business ancestor. No ancestor means no business link. Do not add watchers or claim equivalent analysis for other languages without implementation.",
        "If call analysis fails, check the generated workspace, saved sources, resolved SDK/module versions and visible diagnostics before changing topology. A valid Python model alone does not prove Go code can be analyzed or compiled.",
    ],
    "sdkChanges": [
        "An SDK extension needs a concrete uncovered requirement and an explanation of why existing contracts plus simpler application coordination cannot meet it. Make any extension explicit and reusable, not a product-specific hook or a way to legitimize redundant code.",
        "Internal helpers implementing an existing declared contract (schedule parsing, cancellation, transport startup retry) are not automatically hidden application behavior. Judge their semantics rather than deleting them merely because they are new.",
        "For general API/lifecycle/behavior changes, audit all applicable SDK implementations, generated handlers and language template sets. Keep C++ userver and C++ Coro independent. Report implemented, tested and unsupported cases separately; source edits alone do not prove parity.",
        "Use supported upstream APIs. Do not patch/vendor a framework or silently weaken a guarantee to simulate missing support; declare the implementation limitation and reassess the design. Such a fork requires a separate explicit decision.",
    ],
    "generationAndVerification": [
        "Preserve template path/name headers and existing generation/ownership contracts. Put project-specific merge behavior in the destination project's supported merge hooks, not new writePolicy values or SDK behavior.",
        "Use the installed destination project's merge entrypoint/hooks. A freshly generated archive's empty/default hooks are not the project's policy. Inspect stale-file removal before applying it; preserve user-owned code and data.",
        "After implementation changes, verify model/export where affected, generated code compilation and the actual generated invocation path through makers/endpoints. Tests calling only a business function cannot prove graph wiring, reply/error routing or lifecycle behavior.",
        "For call overlays, verify both discovered identities and displayed links; distinguish resolution from invocation and invocation from end-to-end business success.",
        "When retiring an authorized obsolete feature, trace callers first and remove it from model, code, registration, configuration and relevant deployment/docs/tests. Do not leave old/ copies or compatibility aliases without a requirement. Remove only resulting source directories, never user data or runtime volumes.",
    ],
    "examples": [
        {"situation": "Two independent HTTP handlers reuse pricing logic", "decision": "Two named pipelines with distinct pricing nodes referencing the same function; each has its own reply/error path."},
        {"situation": "A background refresh consumes Kafka and updates an in-memory index", "decision": "Native Kafka endpoint/Input, meaningful apply-state stage, typed results and error path; index internals stay in code and a narrow maker capability exposes state access."},
        {"situation": "A stage builds a file with many conversions and SQL statements", "decision": "Keep cohesive encoding/query algorithms in the stage; expose separately meaningful ingestion, publication or completion boundaries, not every statement."},
        {"situation": "A source needs a snapshot before consuming events", "decision": "Inspect startup scheduling and existing endpoint checkpoint contracts, then use cancellable narrow state coordination if supported; do not assume a new SDK lifecycle API is necessary."},
    ],
}
