from sa_dsl import CallSemantics
from processorder.services.automation_service.service import automation_service
from processorder.pools.default import default_pool

from sa_dsl import (
    Appearance,
    Function,
    LOCAL_MODULE,
)

from processorder.endpoints.local_cron import local_schedule

from processorder.endpoints.temporal import (
    activity_job,
    fan_out_activity_a,
    fan_out_activity_b,
    fan_out_activity_c,
    fan_out_workflow_job,
    sequential_activity_a,
    sequential_activity_b,
    temporal_activity_schedule,
    temporal_workflow_schedule,
    workflow_job,
)

from processorder.packages.automation import automation_package

from processorder.services.automation_service.service import automation_pipeline

from processorder.types.automation import automation_job

stream_local_schedule = automation_pipeline.input(
    "Local Schedule",
    endpoint=local_schedule,
    appearance=Appearance(x=-1250, y=500),
    value_type=automation_job,
)

split_on_demand_jobs = automation_pipeline.split(
    "Split On-Demand Jobs",
    appearance=Appearance(x=-1010, y=500),
)

submit_activity_job = automation_pipeline.sink(
    "Submit Activity Job",
    endpoint=activity_job,
    appearance=Appearance(x=-760, y=350),
    value_type=automation_job,
)

consume_activity_job = automation_pipeline.input(
    "Consume Activity Job",
    endpoint=activity_job,
    appearance=Appearance(x=-500, y=350),
    value_type=automation_job,
)

activity_pause = automation_pipeline.delay(
    "Activity Pause",
    appearance=Appearance(x=-251, y=219),
    function=Function(
        package=automation_package,
        name="ActivityPause",
        description="Apply the ordinary local Delay while processing an on-demand Temporal Activity.\n",
        module=LOCAL_MODULE,
    ),
    duration=250,
)

process_activity_job = automation_pipeline.map(
    "Process Activity Job",
    appearance=Appearance(x=10, y=350),
    value_type=automation_job,
    function=Function(
        package=automation_package,
        name="ProcessActivityJob",
        description="Record Activity progress with DurableCallHeartbeat and return the processed job result.\n",
        module=LOCAL_MODULE,
    ),
)

observe_activity_result = automation_pipeline.map(
    "Observe Activity Result",
    appearance=Appearance(x=-500, y=500),
    value_type=automation_job,
    function=Function(
        package=automation_package,
        name="ObserveActivityResult",
        description="Preserve the result returned through the on-demand Activity endpoint.\n",
        module=LOCAL_MODULE,
    ),
)

submit_workflow_job = automation_pipeline.sink(
    "Submit Workflow Job",
    endpoint=workflow_job,
    appearance=Appearance(x=-807, y=629),
    value_type=automation_job,
)

consume_workflow_job = automation_pipeline.input(
    "Consume Workflow Job",
    endpoint=workflow_job,
    appearance=Appearance(x=-515, y=635),
    value_type=automation_job,
)

workflow_pause = automation_pipeline.delay(
    "Workflow Pause",
    appearance=Appearance(x=-233, y=504),
    function=Function(
        package=automation_package,
        name="WorkflowPause",
        description="Use the same Delay contract backed by the Temporal Workflow timer.\n",
        module=LOCAL_MODULE,
    ),
    duration=250,
)

call_sequential_activity_a = automation_pipeline.sink(
    "Call Sequential Activity A",
    endpoint=sequential_activity_a,
    appearance=Appearance(x=49, y=473),
    value_type=automation_job,
)

call_sequential_activity_b = automation_pipeline.sink(
    "Call Sequential Activity B",
    endpoint=sequential_activity_b,
    appearance=Appearance(x=270, y=650),
    value_type=automation_job,
)

process_workflow_job = automation_pipeline.map(
    "Process Workflow Job",
    appearance=Appearance(x=-59, y=654),
    value_type=automation_job,
    function=Function(
        package=automation_package,
        name="ProcessWorkflowJob",
        description="Continue the Workflow as new once, then return its final result.\n",
        module=LOCAL_MODULE,
    ),
)

observe_workflow_result = automation_pipeline.map(
    "Observe Workflow Result",
    appearance=Appearance(x=-650, y=788),
    value_type=automation_job,
    function=Function(
        package=automation_package,
        name="ObserveWorkflowResult",
        description="Preserve the result returned through the on-demand Workflow endpoint.\n",
        module=LOCAL_MODULE,
    ),
)

consume_sequential_activity_a = automation_pipeline.input(
    "Consume Sequential Activity A",
    endpoint=sequential_activity_a,
    appearance=Appearance(x=302, y=489),
    value_type=automation_job,
)

process_sequential_activity_a = automation_pipeline.map(
    "Process Sequential Activity A",
    appearance=Appearance(x=568, y=486),
    value_type=automation_job,
    function=Function(
        package=automation_package,
        name="ProcessSequentialActivityA",
        description="Return sequential Activity A's typed result to its Temporal sink.\n",
        module=LOCAL_MODULE,
    ),
)

consume_sequential_activity_b = automation_pipeline.input(
    "Consume Sequential Activity B",
    endpoint=sequential_activity_b,
    appearance=Appearance(x=503, y=658),
    value_type=automation_job,
)

process_sequential_activity_b = automation_pipeline.map(
    "Process Sequential Activity B",
    appearance=Appearance(x=804, y=660),
    value_type=automation_job,
    function=Function(
        package=automation_package,
        name="ProcessSequentialActivityB",
        description="Return sequential Activity B's typed result to its Temporal sink.\n",
        module=LOCAL_MODULE,
    ),
)

consume_fan_out_activity_a = automation_pipeline.input(
    "Consume Fan-Out Activity A",
    endpoint=fan_out_activity_a,
    appearance=Appearance(x=-277, y=1051),
    value_type=automation_job,
)

process_fan_out_activity_a = automation_pipeline.map(
    "Process Fan-Out Activity A",
    appearance=Appearance(x=-268, y=819),
    value_type=automation_job,
    function=Function(
        package=automation_package,
        name="ProcessFanoutActivityA",
        description="Return Activity A's typed result before the Workflow Split.\n",
        module=LOCAL_MODULE,
    ),
)

consume_fan_out_activity_b = automation_pipeline.input(
    "Consume Fan-Out Activity B",
    endpoint=fan_out_activity_b,
    appearance=Appearance(x=295, y=996),
    value_type=automation_job,
)

process_fan_out_activity_b = automation_pipeline.map(
    "Process Fan-Out Activity B",
    appearance=Appearance(x=705, y=1001),
    value_type=automation_job,
    function=Function(
        package=automation_package,
        name="ProcessFanoutActivityB",
        description="Return Activity B's typed fan-out result.\n",
        module=LOCAL_MODULE,
    ),
)

consume_fan_out_activity_c = automation_pipeline.input(
    "Consume Fan-Out Activity C",
    endpoint=fan_out_activity_c,
    appearance=Appearance(x=553, y=1503),
    value_type=automation_job,
)

process_fan_out_activity_c = automation_pipeline.map(
    "Process Fan-Out Activity C",
    appearance=Appearance(x=931, y=1493),
    value_type=automation_job,
    function=Function(
        package=automation_package,
        name="ProcessFanoutActivityC",
        description="Return Activity C's typed fan-out result.\n",
        module=LOCAL_MODULE,
    ),
)

submit_fan_out_workflow_job = automation_pipeline.sink(
    "Submit Fan-Out Workflow Job",
    endpoint=fan_out_workflow_job,
    appearance=Appearance(x=-967, y=1034),
    value_type=automation_job,
)

consume_fan_out_workflow_job = automation_pipeline.input(
    "Consume Fan-Out Workflow Job",
    endpoint=fan_out_workflow_job,
    appearance=Appearance(x=-635, y=1287),
    value_type=automation_job,
)

call_fan_out_activity_a = automation_pipeline.sink(
    "Call Fan-Out Activity A",
    endpoint=fan_out_activity_a,
    appearance=Appearance(x=-271, y=1284),
    value_type=automation_job,
)

split_activity_a_result = automation_pipeline.split(
    "Split Activity A Result",
    appearance=Appearance(x=40, y=1312),
)

call_fan_out_activity_b = automation_pipeline.sink(
    "Call Fan-Out Activity B",
    endpoint=fan_out_activity_b,
    appearance=Appearance(x=7, y=990),
    value_type=automation_job,
)

observe_fan_out_activity_b = automation_pipeline.map(
    "Observe Fan-Out Activity B",
    appearance=Appearance(x=-11, y=793),
    value_type=automation_job,
    function=Function(
        package=automation_package,
        name="ObserveFanoutActivityB",
        description="Observe the typed result returned by the Activity B fan-out branch.\n",
        module=LOCAL_MODULE,
    ),
)

call_fan_out_activity_c = automation_pipeline.sink(
    "Call Fan-Out Activity C",
    endpoint=fan_out_activity_c,
    appearance=Appearance(x=317, y=1313),
    value_type=automation_job,
)

observe_fan_out_activity_c = automation_pipeline.map(
    "Observe Fan-Out Activity C",
    appearance=Appearance(x=587, y=1121),
    value_type=automation_job,
    function=Function(
        package=automation_package,
        name="ObserveFanoutActivityC",
        description="Observe the typed result returned by the Activity C fan-out branch.\n",
        module=LOCAL_MODULE,
    ),
)

stream_temporal_activity_schedule = automation_pipeline.input(
    "Temporal Activity Schedule",
    endpoint=temporal_activity_schedule,
    appearance=Appearance(x=-1917, y=639),
    value_type=automation_job,
)

scheduled_activity_pause = automation_pipeline.delay(
    "Scheduled Activity Pause",
    appearance=Appearance(x=-1661, y=402),
    function=Function(
        package=automation_package,
        name="ScheduledActivityPause",
        description="Apply the ordinary local Delay inside an Activity started by Temporal Schedule.\n",
        module=LOCAL_MODULE,
    ),
    duration=250,
)

process_scheduled_activity = automation_pipeline.map(
    "Process Scheduled Activity",
    appearance=Appearance(x=-1442, y=655),
    value_type=automation_job,
    function=Function(
        package=automation_package,
        name="ProcessScheduledActivity",
        description="Return the visible result of one scheduled Activity execution.\n",
        module=LOCAL_MODULE,
    ),
)

stream_temporal_workflow_schedule = automation_pipeline.input(
    "Temporal Workflow Schedule",
    endpoint=temporal_workflow_schedule,
    appearance=Appearance(x=-1906, y=846),
    value_type=automation_job,
)

scheduled_workflow_pause = automation_pipeline.delay(
    "Scheduled Workflow Pause",
    appearance=Appearance(x=-1684, y=1167),
    function=Function(
        package=automation_package,
        name="ScheduledWorkflowPause",
        description="Use the official Temporal Workflow timer for a scheduled Workflow.\n",
        module=LOCAL_MODULE,
    ),
    duration=250,
)

process_scheduled_workflow = automation_pipeline.map(
    "Process Scheduled Workflow",
    appearance=Appearance(x=-1411, y=856),
    value_type=automation_job,
    function=Function(
        package=automation_package,
        name="ProcessScheduledWorkflow",
        description="Return the visible result of one scheduled Workflow execution.\n",
        module=LOCAL_MODULE,
    ),
)

(
    stream_local_schedule
    >> split_on_demand_jobs
    >> submit_activity_job
    >> observe_activity_result
)

split_on_demand_jobs >> submit_workflow_job >> observe_workflow_result

process_activity_job >> consume_activity_job >> activity_pause >> process_activity_job

(
    process_workflow_job
    >> consume_workflow_job
    >> workflow_pause
    >> call_sequential_activity_a
    >> call_sequential_activity_b
    >> process_workflow_job
)

call_sequential_activity_b.task_pool_call(
    process_workflow_job,
    pool=default_pool,
)

call_sequential_activity_a.priority_task_pool_call(
    call_sequential_activity_b,
    pool=default_pool,
    priority=2,
)

workflow_pause.task_pool_call(
    call_sequential_activity_a,
    pool=default_pool,
)

(
    process_sequential_activity_a
    >> consume_sequential_activity_a
    >> process_sequential_activity_a
)

(
    process_sequential_activity_b
    >> consume_sequential_activity_b
    >> process_sequential_activity_b
)

process_fan_out_activity_a >> consume_fan_out_activity_a >> process_fan_out_activity_a

process_fan_out_activity_b >> consume_fan_out_activity_b >> process_fan_out_activity_b

process_fan_out_activity_c >> consume_fan_out_activity_c >> process_fan_out_activity_c

split_on_demand_jobs >> submit_fan_out_workflow_job

consume_fan_out_workflow_job >> call_fan_out_activity_a >> split_activity_a_result

consume_fan_out_workflow_job.task_pool_call(
    call_fan_out_activity_a,
    pool=default_pool,
)

split_activity_a_result >> call_fan_out_activity_b >> observe_fan_out_activity_b

split_activity_a_result.priority_task_pool_call(
    call_fan_out_activity_b,
    pool=default_pool,
    priority=2,
)

split_activity_a_result >> call_fan_out_activity_c >> observe_fan_out_activity_c

split_activity_a_result.priority_task_pool_call(
    call_fan_out_activity_c,
    pool=default_pool,
    priority=7,
)

(
    process_scheduled_activity
    >> stream_temporal_activity_schedule
    >> scheduled_activity_pause
    >> process_scheduled_activity
)

(
    process_scheduled_workflow
    >> stream_temporal_workflow_schedule
    >> scheduled_workflow_pause
    >> process_scheduled_workflow
)
