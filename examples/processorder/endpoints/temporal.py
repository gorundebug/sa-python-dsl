from processorder.connectors.temporal import temporal

from processorder.packages.activity import activity_package
from processorder.packages.workflow import workflow_package

from sa_dsl import (
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
    activity_start_to_close_timeout=30000,
    activity_heartbeat_timeout=5000,
    max_concurrent_activities=2,
    task_queue="automation-activity-schedules",
    enabled=True,
    tracing_enabled=False,
    schedule="*/10 * * * *",
    schedule_id="example-automation-activity-schedule",
    timezone="UTC",
    overlap_policy=ScheduleOverlapPolicy.SKIP,
    missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE,
    workflow_execution_timeout=60000,
    maximum_attempts=3,
)

activity_job = temporal.activity(
    "Activity Job",
    function=Function(
        name="ActivityJobEndpoint",
        package=activity_package,
        description="",
        public=False,
    ),
    activity_start_to_close_timeout=30000,
    activity_heartbeat_timeout=5000,
    max_concurrent_activities=2,
    task_queue="automation-activity-jobs",
    enabled=True,
    tracing_enabled=False,
    schedule="",
    schedule_id="",
    timezone="UTC",
    overlap_policy=ScheduleOverlapPolicy.SKIP,
    missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE,
    workflow_execution_timeout=60000,
    maximum_attempts=3,
)

sequential_activity_a = temporal.activity(
    "Sequential Activity A",
    function=Function(
        name="SequentialActivityAEndpoint",
        package=activity_package,
        description="",
        public=False,
    ),
    activity_start_to_close_timeout=30000,
    activity_heartbeat_timeout=5000,
    max_concurrent_activities=2,
    task_queue="automation-activity-jobs",
    enabled=True,
    tracing_enabled=False,
    schedule="",
    schedule_id="",
    timezone="UTC",
    overlap_policy=ScheduleOverlapPolicy.SKIP,
    missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE,
    workflow_execution_timeout=60000,
    maximum_attempts=3,
)

sequential_activity_b = temporal.activity(
    "Sequential Activity B",
    function=Function(
        name="SequentialActivityBEndpoint",
        package=activity_package,
        description="",
        public=False,
    ),
    activity_start_to_close_timeout=30000,
    activity_heartbeat_timeout=5000,
    max_concurrent_activities=2,
    task_queue="automation-activity-jobs",
    enabled=True,
    tracing_enabled=False,
    schedule="",
    schedule_id="",
    timezone="UTC",
    overlap_policy=ScheduleOverlapPolicy.SKIP,
    missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE,
    workflow_execution_timeout=60000,
    maximum_attempts=3,
)

fan_out_activity_a = temporal.activity(
    "Fan-Out Activity A",
    function=Function(
        name="FanoutActivityAEndpoint",
        package=activity_package,
        description="",
        public=False,
    ),
    activity_start_to_close_timeout=30000,
    activity_heartbeat_timeout=5000,
    max_concurrent_activities=2,
    task_queue="automation-activity-jobs",
    enabled=True,
    tracing_enabled=False,
    schedule="",
    schedule_id="",
    timezone="UTC",
    overlap_policy=ScheduleOverlapPolicy.SKIP,
    missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE,
    workflow_execution_timeout=60000,
    maximum_attempts=3,
)

fan_out_activity_b = temporal.activity(
    "Fan-Out Activity B",
    function=Function(
        name="FanoutActivityBEndpoint",
        package=activity_package,
        description="",
        public=False,
    ),
    activity_start_to_close_timeout=30000,
    activity_heartbeat_timeout=5000,
    max_concurrent_activities=2,
    task_queue="automation-activity-jobs",
    enabled=True,
    tracing_enabled=False,
    schedule="",
    schedule_id="",
    timezone="UTC",
    overlap_policy=ScheduleOverlapPolicy.SKIP,
    missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE,
    workflow_execution_timeout=60000,
    maximum_attempts=3,
)

fan_out_activity_c = temporal.activity(
    "Fan-Out Activity C",
    function=Function(
        name="FanoutActivityCEndpoint",
        package=activity_package,
        description="",
        public=False,
    ),
    activity_start_to_close_timeout=30000,
    activity_heartbeat_timeout=5000,
    max_concurrent_activities=1,
    task_queue="automation-heavy-activities",
    enabled=True,
    tracing_enabled=False,
    schedule="",
    schedule_id="",
    timezone="UTC",
    overlap_policy=ScheduleOverlapPolicy.SKIP,
    missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE,
    workflow_execution_timeout=60000,
    maximum_attempts=3,
)

workflow_job = temporal.workflow(
    "Workflow Job",
    function=Function(
        name="WorkflowJobEndpoint",
        package=workflow_package,
        description="",
        public=False,
    ),
    max_concurrent_workflow_tasks=4,
    task_queue="automation-workflow-jobs",
    enabled=True,
    tracing_enabled=False,
    schedule="",
    schedule_id="",
    timezone="UTC",
    overlap_policy=ScheduleOverlapPolicy.SKIP,
    missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE,
    workflow_execution_timeout=60000,
    maximum_attempts=3,
)

fan_out_workflow_job = temporal.workflow(
    "Fan-Out Workflow Job",
    function=Function(
        name="FanoutWorkflowJobEndpoint",
        package=workflow_package,
        description="",
        public=False,
    ),
    max_concurrent_workflow_tasks=4,
    task_queue="automation-workflow-jobs",
    enabled=True,
    tracing_enabled=False,
    schedule="",
    schedule_id="",
    timezone="UTC",
    overlap_policy=ScheduleOverlapPolicy.SKIP,
    missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE,
    workflow_execution_timeout=60000,
    maximum_attempts=3,
)

temporal_workflow_schedule = temporal.workflow(
    "Temporal Workflow Schedule",
    function=Function(
        name="TemporalWorkflowSchedule",
        package=workflow_package,
        description="Create a Workflow job message identifying the durable scheduled firing.\n",
        public=False,
    ),
    max_concurrent_workflow_tasks=4,
    task_queue="automation-workflow-schedules",
    enabled=True,
    tracing_enabled=False,
    schedule="*/10 * * * *",
    schedule_id="example-automation-workflow-schedule",
    timezone="UTC",
    overlap_policy=ScheduleOverlapPolicy.SKIP,
    missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE,
    workflow_execution_timeout=60000,
    maximum_attempts=3,
)
