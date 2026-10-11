"""Portable typed-Python examples for intent-first MCP architecture recipes.

These programs build and validate models. They are not implementations of their
business functions, deployment manifests or substitutes for runtime capabilities.
"""

from __future__ import annotations

from typing import Any


_SETUP = '''from sa_dsl import (
    Project, Golang, ServiceModule, Function, LOCAL_MODULE,
    ActivityWorker, ActivityTimeouts, WorkflowWorker, WorkflowTimeouts,
    TemporalSchedule, KafkaCluster,
)

project = Project("Example")
contracts = project.module("Contracts", module_path="example.com/contracts", golang_version="1.25.4")
value = project.string_type("Value", module=contracts)
service = project.service("Quotes", language=Golang(version="1.25.4"),
                          module=ServiceModule("example.com/quotes"))
pipeline = service.pipeline("Quotes")
'''

_HTTP = '''
http = project.http_connector("Quote API", module=contracts)
request = http.post("Quote Request", path="/quote", function=Function("ReadQuote"))
entry = pipeline.input("Receive Quote Request", endpoint=request, value_type=value)
'''


def _workflow_source(*, scheduled: bool = False) -> str:
    schedule = ('    schedule=TemporalSchedule(expression="0 9 * * *", '
                'id="daily-quote-reminder", timezone="UTC"),\n') if scheduled else ""
    return '''
temporal = project.temporal_connector("Durable Work", address="temporal:7233", namespace="default")
workflow = temporal.workflow(
    "Quote Workflow", function=Function("QuoteWorkflow", public=False),
    worker=WorkflowWorker(task_queue="quote-workflows", max_concurrent=4),
    timeouts=WorkflowTimeouts(execution=60000),
''' + schedule + ''')
entry = pipeline.input("Receive Workflow", endpoint=workflow, value_type=value)
'''


def _example(body: str) -> dict[str, Any]:
    return {"language": "python", "entrypoint": "architecture:project", "projectName": "Example",
            "code": _SETUP + body,
            "scope": "Runnable typed-Python model construction, not a ready-to-run service.",
            "validation": "Checked by the ordinary Python export worker; business implementations and runtime execution require separate tests.",
            "usage": ["Adapt the business names and public value types to the current project.",
                      "Read capabilities for the target runtime before choosing its connector and operators.",
                      "Implement each Function contract; Python validation does not implement or prove business behavior.",
                      "Review source and semantic diffs before applying a model change."]}


PATTERN_RECIPES: dict[str, dict[str, Any]] = {
    "http-request-response": {
        "intent": "Expose one meaningful request-processing stage and bind its result to the caller.",
        "useWhen": ["One request has one final business result.", "A cohesive calculation is independently meaningful."],
        "avoidWhen": ["The job must survive process restarts.", "The caller should receive an acknowledgement and observe completion later."],
        "topology": ["HTTP endpoint", "Input", "Map", "result binding to Input"],
        "decisions": ["request and response contracts", "deadline", "business failure representation"],
        "antiPatterns": ["treating the result binding as a second ordinary request-processing cycle", "splitting every helper call into a node"],
        "contracts": {
            "types": "The example uses a public string Value; use domain types and implement endpoint conversion in a real service.",
            "cardinality": "One request produces one result through the Map contract.",
            "execution": "Ordinary in-process graph invocation, not durable workflow execution.",
            "correlation": "Preserve the request MessageContext through the stage.",
            "completion": "result >> entry binds the final result to the original Input.",
            "failure": "Endpoint and stage implementations must handle cancellation, deadlines and business errors explicitly.",
        },
        "example": _example(_HTTP + '''
result = pipeline.map("Calculate Quote", source=entry, value_type=value,
                      function=Function("CalculateQuote", module=LOCAL_MODULE))
result >> entry
'''),
    },
    "conditional-routing": {
        "useWhen": ["Exactly one business alternative should handle each input."],
        "avoidWhen": ["Every branch must receive each message.", "The condition is only an implementation detail of one stage."],
        "contracts": {
            "types": "Both branches return the same public Value, so Merge can combine them without a callback.",
            "cardinality": "Case selects one ordered When; it does not broadcast.",
            "execution": "The ordinary graph call semantics apply; no worker pool is implied.",
            "correlation": "The original invocation context follows the selected branch.",
            "completion": "Only the selected branch reaches Merge and completes the request.",
            "failure": "SelectQuotePolicy must return 0 or 1; define handling of invalid indices rather than silently choosing a branch.",
        },
        "example": _example(_HTTP + '''
choice = pipeline.case("Choose Quote Policy", source=entry,
                       function=Function("SelectQuotePolicy", module=LOCAL_MODULE))
standard = pipeline.when("Standard Policy", source=choice, value_type=value)
manual = pipeline.when("Manual Review Policy", source=choice, value_type=value)
quote = pipeline.map("Calculate Standard Quote", source=standard, value_type=value,
                     function=Function("StandardQuote", module=LOCAL_MODULE))
review = pipeline.map("Prepare Manual Review", source=manual, value_type=value,
                      function=Function("ManualReview", module=LOCAL_MODULE))
result = pipeline.merge("Selected Quote Result", sources=(quote, review))
result >> entry
'''),
    },
    "failure-compensation": {
        "useWhen": ["A failure changes the business outcome or requires an explicit compensating action."],
        "avoidWhen": ["The error is handled entirely within a stage.", "A durable multi-step compensation is being mistaken for local rollback."],
        "contracts": {
            "types": "The owner emits the declared Value on its error output. Error routes that value; it has no conversion function. CompensateReservation produces a recovered Value.",
            "cardinality": "Emit one success or one recovered result, never success followed by an additional failure completion.",
            "execution": "Local execution; this example does not implement persistent retries or a durable saga.",
            "correlation": "Preserve the owner's MessageContext, including request identity and cancellation.",
            "completion": "Both alternatives feed one Merge and the original Input result binding.",
            "failure": "CompensateReservation must be idempotent and handle its own failure policy. The graph does not infer which side effects occurred.",
        },
        "example": _example(_HTTP + '''
reserve = pipeline.process("Reserve Capacity", source=entry, value_type=value,
                           function=Function("ReserveCapacity", module=LOCAL_MODULE))
failure = pipeline.error("Reservation Failed", value_type=value)
reserve >> failure
reserve.on_error(failure)
recovered = pipeline.map("Compensate Reservation", source=failure, value_type=value,
                         function=Function("CompensateReservation", module=LOCAL_MODULE))
result = pipeline.merge("Reservation Outcome", sources=(reserve, recovered))
result >> entry
'''),
    },
    "temporal-sequential": {
        "useWhen": ["A durable workflow must wait for one external step before starting another."],
        "avoidWhen": ["Ordinary request-scoped local execution is sufficient.", "The steps are intentionally independent."],
        "contracts": {
            "types": "The example exchanges Value at each endpoint; real workflows should use versioned public request/result contracts.",
            "cardinality": "One Workflow calls two Activities sequentially and returns one final result.",
            "execution": "Temporal Workflow context submits Activity calls; the Activity inputs execute the external operations.",
            "correlation": "Use stable business identifiers for idempotent side effects; do not correlate by arrival order.",
            "completion": "Each Activity result is bound back to its Input; the Workflow completes after the second Activity result.",
            "failure": "Set business-specific retry/timeout/compensation policies. Workflow code must be replay-safe, Activities must tolerate repeated execution.",
        },
        "example": _example(_workflow_source() + '''
def activity(name):
    endpoint = temporal.activity(
        name, function=Function(name + "Endpoint", public=False),
        worker=ActivityWorker(task_queue="quote-activities", max_concurrent=4),
        timeouts=ActivityTimeouts(start_to_close=30000),
    )
    received = pipeline.input("Receive " + name, endpoint=endpoint, value_type=value)
    completed = pipeline.map("Execute " + name, source=received, value_type=value,
                             function=Function("Execute" + name, module=LOCAL_MODULE))
    completed >> received
    return endpoint

reserve = activity("Reserve")
confirm = activity("Confirm")
reserved = pipeline.sink("Call Reserve", source=entry, endpoint=reserve, value_type=value)
confirmed = pipeline.sink("Call Confirm", source=reserved, endpoint=confirm, value_type=value)
confirmed >> entry
'''),
    },
    "temporal-scheduled": {
        "useWhen": ["A service-backed schedule should start durable work independently of the application process lifetime."],
        "avoidWhen": ["Only process-local periodic work is needed.", "An on-demand endpoint must not create a schedule."],
        "contracts": {
            "types": "The schedule endpoint implementation creates a Value for each firing; replace it with a meaningful scheduled-job contract.",
            "cardinality": "One scheduled firing starts one Workflow under the chosen overlap and missed-run policies.",
            "execution": "The Delay inside the Workflow uses the Workflow timer, not blocking sleep.",
            "correlation": "Use a stable schedule ID and preserve the execution identity within each firing.",
            "completion": "The final Map result completes that scheduled Workflow invocation.",
            "failure": "Choose overlap, missed-run, timeout and retry policies for the job; scheduling alone does not make side effects idempotent.",
        },
        "example": _example(_workflow_source(scheduled=True) + '''
pause = pipeline.delay("Wait Before Reminder", source=entry, duration=250,
                       function=Function("ReminderDelay", module=LOCAL_MODULE))
result = pipeline.map("Prepare Reminder", source=pause, value_type=value,
                      function=Function("PrepareReminder", module=LOCAL_MODULE))
result >> entry
'''),
    },
}


PATTERN_RECIPES.update({
    "kafka-processing": {
        "useWhen": ["An independently delivered broker message triggers one business processing stage."],
        "avoidWhen": ["The caller requires an immediate HTTP response.", "Exactly-once side effects are being assumed from a consumer group alone."],
        "contracts": {
            "types": "The topic endpoint decodes a message to Value and converts the processing result for its completion contract.",
            "cardinality": "This example produces one processing result per delivered message; a broker may redeliver a message.",
            "execution": "Kafka consumer execution, not a durable Workflow or an implicit transaction across external systems.",
            "correlation": "Keep the broker message identity and a stable business idempotency key through processing.",
            "completion": "The result binding completes the Input invocation. Acknowledgement and offset policy remain the connector/runtime contract, not a guarantee of exactly-once processing.",
            "failure": "Implement duplicate handling, retry and poison-message policy. Do not acknowledge success before the intended side effect has succeeded.",
        },
        "example": _example('''
kafka = project.kafka_connector("Quote Events", cluster=KafkaCluster(brokers="redpanda:9092"))
topic = kafka.topic("Quote Requested", topic="quote-requested", consumer_group="quote-processors",
                    function=Function("QuoteRequested", public=False))
entry = pipeline.input("Receive Quote Event", endpoint=topic, value_type=value)
result = pipeline.process("Record Quote Request", source=entry, value_type=value,
                          function=Function("RecordQuoteRequest", module=LOCAL_MODULE))
result >> entry
'''),
    },
    "broadcast-fan-out": {
        "useWhen": ["Every message must reach independent observers, without combining their results."],
        "avoidWhen": ["Exactly one alternative should run.", "The operation must wait for a correlated set of branch results."],
        "contracts": {
            "types": "Split preserves Value for both observers; it does not unpack a collection.",
            "cardinality": "Each input reaches both Process stages and the SubStream result binding. ObserveQuote and AuditQuote are terminal side effects and emit no results; Split returns the original Value to the caller.",
            "execution": "No asynchronous edge or pool is selected here. Split alone does not promise parallel execution.",
            "correlation": "Both observers receive the original invocation context and business identity.",
            "completion": "The service-local SubStream caller uses its context/deadline and receives the original Value. This result binding is not an all-observers completion barrier and does not cancel remaining observer work. Do not interpret it as confirmation that all side effects completed.",
            "failure": "Choose failure isolation and idempotency for each observer. Fan-out neither rolls back previous observers nor retries them atomically.",
        },
        "example": _example('''
entry = pipeline.substream("Observe Quote", value_type=value)
branches = pipeline.split("Quote Observers", source=entry)
observe = pipeline.process("Observe Quote Outcome", source=branches, value_type=value,
                           function=Function("ObserveQuote", module=LOCAL_MODULE))
audit = pipeline.process("Audit Quote Outcome", source=branches, value_type=value,
                         function=Function("AuditQuote", module=LOCAL_MODULE))
branches >> entry
'''),
    },
    "iterable-worker-aggregation": {
        "useWhen": ["One invocation supplies a collection and needs results correlated to that invocation."],
        "avoidWhen": ["The input is already one item.", "Cross-request event joins or durable recovery are required."],
        "topology": ["HTTP Input", "Process invoking a service-local SubStream", "FlatMapIterable", "Map per item", "SubStream collector", "one HTTP result"],
        "contracts": {
            "types": "The SubStream accepts Values (an array of Value) and returns individual Value results; the outer Process aggregates them into one Value.",
            "cardinality": "Each item produces one Map result. QuoteCollection must explicitly handle an empty collection, expected count and partial failures.",
            "execution": "FlatMapIterable expands the collection; it does not introduce a worker pool. Choose edge scheduling separately if parallel work is needed.",
            "correlation": "The SubStream invocation's collector correlates results. Arrival order is not item identity; use explicit item IDs when order matters.",
            "completion": "QuoteCollection receives the typed SubStream accessor through its maker/DI, invokes it with a deadline, and completes the collector when all expected results arrive. Collector completion does not cancel all remaining work.",
            "failure": "The business function must decide timeout, cancellation and partial-result policy and emit the outer result once. SubStream is local, not durable.",
        },
        "example": _example(_HTTP + '''
values = project.array_type("Values", value_type=value, module=contracts)
items = pipeline.substream("Quote Items", value_type=values)
item = pipeline.flat_map_iterable("Each Quote Item", source=items, value_type=value)
quoted = pipeline.map("Quote One Item", source=item, value_type=value,
                      function=Function("QuoteOneItem", module=LOCAL_MODULE))
quoted >> items
result = pipeline.process("Quote Collection", source=entry, value_type=value,
                          function=Function("QuoteCollection", module=LOCAL_MODULE))
result >> entry
'''),
    },
    "temporal-parallel": {
        "useWhen": ["Independent Activities should overlap inside a durable Workflow, with an explicit all-or-partial result policy."],
        "avoidWhen": ["One Activity requires the other's result.", "An ordinary worker pool is being used to implement Workflow concurrency."],
        "topology": ["Workflow Input", "Process orchestrating two typed SubStream calls", "one Activity Sink per SubStream", "Workflow-safe aggregation", "Workflow result"],
        "contracts": {
            "types": "Each Activity's public input/result is Value. Separate named SubStreams identify the two results.",
            "cardinality": "RunQuoteChecks initiates two Activity calls and produces exactly one combined Workflow result.",
            "execution": "Concurrency belongs to RunQuoteChecks: use the target runtime's Workflow-safe concurrent primitives, not OS threads or ParallelCall. The graph does not automatically start both calls.",
            "correlation": "Inject the typed CheckCapacity and CheckPrice accessors through the business-function maker. Associate results with the named check, not completion order.",
            "completion": "RunQuoteChecks waits for both outcomes under an explicit policy and emits once. Bind each Activity implementation result to its own Input.",
            "failure": "Handle partial failure, Activity retries and cancellation explicitly; avoid non-deterministic Workflow code and make external side effects idempotent.",
        },
        "example": _example(_workflow_source() + '''
def check(name):
    endpoint = temporal.activity(
        name, function=Function(name + "Endpoint", public=False),
        worker=ActivityWorker(task_queue="quote-checks", max_concurrent=4),
        timeouts=ActivityTimeouts(start_to_close=30000),
    )
    received = pipeline.input("Receive " + name, endpoint=endpoint, value_type=value)
    completed = pipeline.map("Execute " + name, source=received, value_type=value,
                             function=Function("Execute" + name, module=LOCAL_MODULE))
    completed >> received
    call = pipeline.substream("Check " + name, value_type=value)
    result = pipeline.sink("Call " + name, source=call, endpoint=endpoint, value_type=value)
    result >> call
    return call

capacity = check("Capacity")
price = check("Price")
result = pipeline.process("Run Quote Checks", source=entry, value_type=value,
                          function=Function("RunQuoteChecks", module=LOCAL_MODULE))
result >> entry
'''),
    },
    "bounded-feedback": {
        "useWhen": ["A meaningful business stage must revisit a previous stage with explicit progress and a bounded completion rule."],
        "avoidWhen": ["The loop is merely a local implementation detail.", "The work must survive a process restart."],
        "contracts": {
            "types": "Value must encode the iteration state needed by AdvanceQuote and ChooseQuoteCompletion; a real service should use a domain record.",
            "cardinality": "Each iteration selects exactly one branch: continue or complete. Complete emits the single request result.",
            "execution": "CycleLink marks feedback explicitly. The ordinary forward graph remains acyclic; no retry scheduler or backoff is implied.",
            "correlation": "Preserve the invocation context and bounded iteration state through each feedback step.",
            "completion": "ChooseQuoteCompletion returns index 1 at success or the maximum-attempt boundary; index 0 continues. Implement and test the bound in business code and retain a deadline.",
            "failure": "A bounded loop still needs a failure outcome for exhausted attempts and cancellation. Repeated side effects must be idempotent.",
        },
        "example": _example(_HTTP + '''
iterations = pipeline.merge("Quote Iterations", sources=(entry,))
advanced = pipeline.map("Advance Quote", source=iterations, value_type=value,
                        function=Function("AdvanceQuote", module=LOCAL_MODULE))
choice = pipeline.case("Quote Completion", source=advanced,
                       function=Function("ChooseQuoteCompletion", module=LOCAL_MODULE))
again = pipeline.when("Continue Quote", source=choice, value_type=value)
done = pipeline.when("Complete Quote", source=choice, value_type=value)
feedback = pipeline.cycle_link("Next Quote Iteration", source=again)
iterations << feedback
done >> entry
'''),
    },
})


_OBJECTS = {
    "http-request-response": ("http-endpoint", "input", "map"),
    "kafka-processing": ("kafka-endpoint", "input", "process"),
    "broadcast-fan-out": ("substream", "split", "process"),
    "iterable-worker-aggregation": ("substream", "flat-map-iterable", "map", "process"),
    "conditional-routing": ("case", "when", "merge"),
    "failure-compensation": ("process", "error", "map", "merge"),
    "bounded-feedback": ("merge", "case", "when", "cycle-link"),
    "temporal-sequential": ("temporal-endpoint", "input", "sink"),
    "temporal-parallel": ("temporal-endpoint", "substream", "process", "sink"),
    "temporal-scheduled": ("temporal-endpoint", "delay", "map"),
}

for _name, _recipe in PATTERN_RECIPES.items():
    _recipe["objects"] = ["servicegen://authoring/object-" + kind for kind in _OBJECTS[_name]]
    _recipe["capabilitiesResource"] = "servicegen://workspace/current/capabilities"
    _recipe["validationContractResource"] = "servicegen://workspace/current/validation-contract"
    _recipe["authoring"] = {
        "inspect": "inspect_python_authoring",
        "preview": ["add_node", "add_endpoint", "connect_ports", "preview_python_changes"],
        "apply": "apply_python_changes",
        "rule": "Adapt the recipe to existing Python objects; preserve user factories and comments. Preview the complete change and inspect its source and architecture diffs before applying.",
    }
