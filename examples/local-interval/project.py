"""Local maintenance cadence; domain ownership remains a maker dependency.

Go runtime example. Other providers require interval-support acceptance before
using this example with a different target. Functions are generated contracts,
not a supplied maintenance implementation.
"""

from sa_dsl import Function, Golang, IntervalSchedule, LOCAL_MODULE, Project, ServiceModule

project = Project("IntervalExample")
value = project.string_type("Tick")
service = project.service(
    "Maintenance", language=Golang(version="1.25.4"),
    module=ServiceModule("example.com/interval/maintenance"),
)
pipeline = service.pipeline("PendingResolution")
schedule = project.cron_connector("Local maintenance").schedule(
    "Pending sweep", trigger=IntervalSchedule(milliseconds=100),
    function=Function("StartPendingSweep", module=LOCAL_MODULE,
        description="Emit one explicit maintenance request per trigger using the received context. "
        "The narrow maker selects only state owned by this service; do not start a private timer."),
)
entry = pipeline.input("Start pending sweep", endpoint=schedule, value_type=value)
result = pipeline.map(
    "Resolve pending outcomes", source=entry, value_type=value,
    function=Function("ResolvePendingOutcomes", module=LOCAL_MODULE,
        description="Resolve a bounded batch under the existing state owner and return one completion. "
        "No per-record graph expansion, hidden work in context, or detached background task."),
)
result >> entry
# Completion, not enqueueing the worker, owns the scheduled invocation.
worker = project.pool("Maintenance worker", executors_count=1, queue_capacity=16)
entry.task_pool_call(result, pool=worker)
