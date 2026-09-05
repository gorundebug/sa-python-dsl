from processorder.connectors.temporal import temporal

from processorder.packages.activity import activity_package
from processorder.packages.workflow import workflow_package

from sa_dsl import (
    ActivityTimeouts,
    ActivityWorker,
    RetryPolicy,
    TemporalSchedule,
    WorkflowTimeouts,
    WorkflowWorker,
    Function,
    ScheduleMissedRunPolicy,
    ScheduleOverlapPolicy,
)

temporal_activity_schedule = temporal.activity(
    "Temporal Activity Schedule",
    function=Function(
        name="TemporalActivitySchedule",
        package=activity_package,
        description="Create an Activity job message identifying the durable scheduled firing.\n",
        public=False,
    ),
    worker=ActivityWorker(task_queue="automation-activity-schedules", max_concurrent=2),
    timeouts=ActivityTimeouts(start_to_close=30000, heartbeat=5000, workflow_execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
    schedule=TemporalSchedule(expression="*/10 * * * *", id="example-automation-activity-schedule", timezone="UTC", overlap_policy=ScheduleOverlapPolicy.SKIP, missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE),
    enabled=True,
    tracing_enabled=False,
)

activity_job = temporal.activity(
    "Activity Job",
    function=Function(
        name="ActivityJobEndpoint",
        package=activity_package,
        description="",
        public=False,
    ),
    worker=ActivityWorker(task_queue="automation-activity-jobs", max_concurrent=2),
    timeouts=ActivityTimeouts(start_to_close=30000, heartbeat=5000, workflow_execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
    enabled=True,
    tracing_enabled=False,
)

sequential_activity_a = temporal.activity(
    "Sequential Activity A",
    function=Function(
        name="SequentialActivityAEndpoint",
        package=activity_package,
        description="",
        public=False,
    ),
    worker=ActivityWorker(task_queue="automation-activity-jobs", max_concurrent=2),
    timeouts=ActivityTimeouts(start_to_close=30000, heartbeat=5000, workflow_execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
    enabled=True,
    tracing_enabled=False,
)

sequential_activity_b = temporal.activity(
    "Sequential Activity B",
    function=Function(
        name="SequentialActivityBEndpoint",
        package=activity_package,
        description="",
        public=False,
    ),
    worker=ActivityWorker(task_queue="automation-activity-jobs", max_concurrent=2),
    timeouts=ActivityTimeouts(start_to_close=30000, heartbeat=5000, workflow_execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
    enabled=True,
    tracing_enabled=False,
)

fan_out_activity_a = temporal.activity(
    "Fan-Out Activity A",
    function=Function(
        name="FanoutActivityAEndpoint",
        package=activity_package,
        description="",
        public=False,
    ),
    worker=ActivityWorker(task_queue="automation-activity-jobs", max_concurrent=2),
    timeouts=ActivityTimeouts(start_to_close=30000, heartbeat=5000, workflow_execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
    enabled=True,
    tracing_enabled=False,
)

fan_out_activity_b = temporal.activity(
    "Fan-Out Activity B",
    function=Function(
        name="FanoutActivityBEndpoint",
        package=activity_package,
        description="",
        public=False,
    ),
    worker=ActivityWorker(task_queue="automation-activity-jobs", max_concurrent=2),
    timeouts=ActivityTimeouts(start_to_close=30000, heartbeat=5000, workflow_execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
    enabled=True,
    tracing_enabled=False,
)

fan_out_activity_c = temporal.activity(
    "Fan-Out Activity C",
    function=Function(
        name="FanoutActivityCEndpoint",
        package=activity_package,
        description="",
        public=False,
    ),
    worker=ActivityWorker(task_queue="automation-heavy-activities", max_concurrent=1),
    timeouts=ActivityTimeouts(start_to_close=30000, heartbeat=5000, workflow_execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
    enabled=True,
    tracing_enabled=False,
)

workflow_job = temporal.workflow(
    "Workflow Job",
    function=Function(
        name="WorkflowJobEndpoint",
        package=workflow_package,
        description="",
        public=False,
    ),
    worker=WorkflowWorker(task_queue="automation-workflow-jobs", max_concurrent=4),
    timeouts=WorkflowTimeouts(execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
    enabled=True,
    tracing_enabled=False,
)

fan_out_workflow_job = temporal.workflow(
    "Fan-Out Workflow Job",
    function=Function(
        name="FanoutWorkflowJobEndpoint",
        package=workflow_package,
        description="",
        public=False,
    ),
    worker=WorkflowWorker(task_queue="automation-workflow-jobs", max_concurrent=4),
    timeouts=WorkflowTimeouts(execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
    enabled=True,
    tracing_enabled=False,
)

temporal_workflow_schedule = temporal.workflow(
    "Temporal Workflow Schedule",
    function=Function(
        name="TemporalWorkflowSchedule",
        package=workflow_package,
        description="Create a Workflow job message identifying the durable scheduled firing.\n",
        public=False,
    ),
    worker=WorkflowWorker(task_queue="automation-workflow-schedules", max_concurrent=4),
    timeouts=WorkflowTimeouts(execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
    schedule=TemporalSchedule(expression="*/10 * * * *", id="example-automation-workflow-schedule", timezone="UTC", overlap_policy=ScheduleOverlapPolicy.SKIP, missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE),
    enabled=True,
    tracing_enabled=False,
)
