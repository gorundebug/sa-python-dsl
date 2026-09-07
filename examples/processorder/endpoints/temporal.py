from sa_dsl import (
    ActivityTimeouts,
    ActivityWorker,
    Function,
    ScheduleMissedRunPolicy,
    ScheduleOverlapPolicy,
    RetryPolicy,
    TemporalSchedule,
    WorkflowTimeouts,
    WorkflowWorker,
)

from processorder.connectors.temporal import connector_temporal
from processorder.packages.activity import activity_package
from processorder.packages.workflow import workflow_package

endpoint_temporal_activity_schedule = connector_temporal.activity(
    'Temporal Activity Schedule',
    enabled=True,
    tracing_enabled=False,
    function=Function(
        name='TemporalActivitySchedule',
        package=activity_package,
        public=False,
        description='Create an Activity job message identifying the durable scheduled firing.\n',
    ),
    worker=ActivityWorker(task_queue='automation-activity-schedules', max_concurrent=2),
    timeouts=ActivityTimeouts(start_to_close=30000, heartbeat=5000, workflow_execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
    schedule=TemporalSchedule(expression='*/10 * * * *', id='example-automation-activity-schedule', timezone='UTC', overlap_policy=ScheduleOverlapPolicy.SKIP, missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE),
)

endpoint_activity_job = connector_temporal.activity(
    'Activity Job',
    enabled=True,
    tracing_enabled=False,
    function=Function(
        name='ActivityJobEndpoint',
        package=activity_package,
        public=False,
        description='',
    ),
    worker=ActivityWorker(task_queue='automation-activity-jobs', max_concurrent=2),
    timeouts=ActivityTimeouts(start_to_close=30000, heartbeat=5000, workflow_execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
)

endpoint_sequential_activity_a = connector_temporal.activity(
    'Sequential Activity A',
    enabled=True,
    tracing_enabled=False,
    function=Function(
        name='SequentialActivityAEndpoint',
        package=activity_package,
        public=False,
        description='',
    ),
    worker=ActivityWorker(task_queue='automation-activity-jobs', max_concurrent=2),
    timeouts=ActivityTimeouts(start_to_close=30000, heartbeat=5000, workflow_execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
)

endpoint_sequential_activity_b = connector_temporal.activity(
    'Sequential Activity B',
    enabled=True,
    tracing_enabled=False,
    function=Function(
        name='SequentialActivityBEndpoint',
        package=activity_package,
        public=False,
        description='',
    ),
    worker=ActivityWorker(task_queue='automation-activity-jobs', max_concurrent=2),
    timeouts=ActivityTimeouts(start_to_close=30000, heartbeat=5000, workflow_execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
)

endpoint_fan_out_activity_a = connector_temporal.activity(
    'Fan-Out Activity A',
    enabled=True,
    tracing_enabled=False,
    function=Function(
        name='FanoutActivityAEndpoint',
        package=activity_package,
        public=False,
        description='',
    ),
    worker=ActivityWorker(task_queue='automation-activity-jobs', max_concurrent=2),
    timeouts=ActivityTimeouts(start_to_close=30000, heartbeat=5000, workflow_execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
)

endpoint_fan_out_activity_b = connector_temporal.activity(
    'Fan-Out Activity B',
    enabled=True,
    tracing_enabled=False,
    function=Function(
        name='FanoutActivityBEndpoint',
        package=activity_package,
        public=False,
        description='',
    ),
    worker=ActivityWorker(task_queue='automation-activity-jobs', max_concurrent=2),
    timeouts=ActivityTimeouts(start_to_close=30000, heartbeat=5000, workflow_execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
)

endpoint_fan_out_activity_c = connector_temporal.activity(
    'Fan-Out Activity C',
    enabled=True,
    tracing_enabled=False,
    function=Function(
        name='FanoutActivityCEndpoint',
        package=activity_package,
        public=False,
        description='',
    ),
    worker=ActivityWorker(task_queue='automation-heavy-activities', max_concurrent=1),
    timeouts=ActivityTimeouts(start_to_close=30000, heartbeat=5000, workflow_execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
)

endpoint_workflow_job = connector_temporal.workflow(
    'Workflow Job',
    enabled=True,
    tracing_enabled=False,
    function=Function(
        name='WorkflowJobEndpoint',
        package=workflow_package,
        public=False,
        description='',
    ),
    worker=WorkflowWorker(task_queue='automation-workflow-jobs', max_concurrent=4),
    timeouts=WorkflowTimeouts(execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
)

endpoint_fan_out_workflow_job = connector_temporal.workflow(
    'Fan-Out Workflow Job',
    enabled=True,
    tracing_enabled=False,
    function=Function(
        name='FanoutWorkflowJobEndpoint',
        package=workflow_package,
        public=False,
        description='',
    ),
    worker=WorkflowWorker(task_queue='automation-workflow-jobs', max_concurrent=4),
    timeouts=WorkflowTimeouts(execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
)

endpoint_temporal_workflow_schedule = connector_temporal.workflow(
    'Temporal Workflow Schedule',
    enabled=True,
    tracing_enabled=False,
    function=Function(
        name='TemporalWorkflowSchedule',
        package=workflow_package,
        public=False,
        description='Create a Workflow job message identifying the durable scheduled firing.\n',
    ),
    worker=WorkflowWorker(task_queue='automation-workflow-schedules', max_concurrent=4),
    timeouts=WorkflowTimeouts(execution=60000),
    retry=RetryPolicy(maximum_attempts=3),
    schedule=TemporalSchedule(expression='*/10 * * * *', id='example-automation-workflow-schedule', timezone='UTC', overlap_policy=ScheduleOverlapPolicy.SKIP, missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE),
)
