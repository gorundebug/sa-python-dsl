from sa_dsl import (
    Appearance,
    Function,
    LOCAL_MODULE,
)

from processorder.endpoints.local_cron import endpoint_local_schedule
from processorder.endpoints.temporal import endpoint_activity_job
from processorder.endpoints.temporal import endpoint_fan_out_activity_a
from processorder.endpoints.temporal import endpoint_fan_out_activity_b
from processorder.endpoints.temporal import endpoint_fan_out_activity_c
from processorder.endpoints.temporal import endpoint_fan_out_workflow_job
from processorder.endpoints.temporal import endpoint_sequential_activity_a
from processorder.endpoints.temporal import endpoint_sequential_activity_b
from processorder.endpoints.temporal import endpoint_temporal_activity_schedule
from processorder.endpoints.temporal import endpoint_temporal_workflow_schedule
from processorder.endpoints.temporal import endpoint_workflow_job
from processorder.packages.automation import automation_package
from processorder.pools.default_pool import default_pool
from processorder.services.automation_service.service import automation_pipeline
from processorder.services.automation_service.service import automation_service
from processorder.types.automation_job import automation_job

local_schedule = automation_pipeline.input(
    'Local Schedule',
    endpoint=endpoint_local_schedule,
    value_type=automation_job,
    appearance=Appearance(x=-1250, y=500),
)

split_on_demand_jobs = automation_pipeline.split(
    'Split On-Demand Jobs',
    appearance=Appearance(x=-1010, y=500),
)

submit_activity_job = automation_pipeline.sink(
    'Submit Activity Job',
    endpoint=endpoint_activity_job,
    value_type=automation_job,
    appearance=Appearance(x=-760, y=350),
)

consume_activity_job = automation_pipeline.input(
    'Consume Activity Job',
    endpoint=endpoint_activity_job,
    value_type=automation_job,
    appearance=Appearance(x=-500, y=350),
)

activity_pause = automation_pipeline.delay(
    'Activity Pause',
    duration=250,
    function=Function(
        name='ActivityPause',
        package=automation_package,
        description='Apply the ordinary local Delay while processing an on-demand Temporal Activity.\n',
        module=LOCAL_MODULE,
    ),
    appearance=Appearance(x=-251, y=219),
)

process_activity_job = automation_pipeline.map(
    'Process Activity Job',
    function=Function(
        name='ProcessActivityJob',
        package=automation_package,
        description='Record Activity progress with DurableCallHeartbeat and return the processed job result.\n',
        module=LOCAL_MODULE,
    ),
    value_type=automation_job,
    appearance=Appearance(x=10, y=350),
)

observe_activity_result = automation_pipeline.map(
    'Observe Activity Result',
    function=Function(
        name='ObserveActivityResult',
        package=automation_package,
        description='Preserve the result returned through the on-demand Activity endpoint.\n',
        module=LOCAL_MODULE,
    ),
    value_type=automation_job,
    appearance=Appearance(x=-500, y=500),
)

submit_workflow_job = automation_pipeline.sink(
    'Submit Workflow Job',
    endpoint=endpoint_workflow_job,
    value_type=automation_job,
    appearance=Appearance(x=-807, y=629),
)

consume_workflow_job = automation_pipeline.input(
    'Consume Workflow Job',
    endpoint=endpoint_workflow_job,
    value_type=automation_job,
    appearance=Appearance(x=-515, y=635),
)

workflow_pause = automation_pipeline.delay(
    'Workflow Pause',
    duration=250,
    function=Function(
        name='WorkflowPause',
        package=automation_package,
        description='Use the same Delay contract backed by the Temporal Workflow timer.\n',
        module=LOCAL_MODULE,
    ),
    appearance=Appearance(x=-233, y=504),
)

call_sequential_activity_a = automation_pipeline.sink(
    'Call Sequential Activity A',
    endpoint=endpoint_sequential_activity_a,
    value_type=automation_job,
    appearance=Appearance(x=49, y=473),
)

call_sequential_activity_b = automation_pipeline.sink(
    'Call Sequential Activity B',
    endpoint=endpoint_sequential_activity_b,
    value_type=automation_job,
    appearance=Appearance(x=270, y=650),
)

process_workflow_job = automation_pipeline.map(
    'Process Workflow Job',
    function=Function(
        name='ProcessWorkflowJob',
        package=automation_package,
        description='Continue the Workflow as new once, then return its final result.\n',
        module=LOCAL_MODULE,
    ),
    value_type=automation_job,
    appearance=Appearance(x=-59, y=654),
)

observe_workflow_result = automation_pipeline.map(
    'Observe Workflow Result',
    function=Function(
        name='ObserveWorkflowResult',
        package=automation_package,
        description='Preserve the result returned through the on-demand Workflow endpoint.\n',
        module=LOCAL_MODULE,
    ),
    value_type=automation_job,
    appearance=Appearance(x=-650, y=788),
)

consume_sequential_activity_a = automation_pipeline.input(
    'Consume Sequential Activity A',
    endpoint=endpoint_sequential_activity_a,
    value_type=automation_job,
    appearance=Appearance(x=302, y=489),
)

process_sequential_activity_a = automation_pipeline.map(
    'Process Sequential Activity A',
    function=Function(
        name='ProcessSequentialActivityA',
        package=automation_package,
        description="Return sequential Activity A's typed result to its Temporal sink.\n",
        module=LOCAL_MODULE,
    ),
    value_type=automation_job,
    appearance=Appearance(x=568, y=486),
)

consume_sequential_activity_b = automation_pipeline.input(
    'Consume Sequential Activity B',
    endpoint=endpoint_sequential_activity_b,
    value_type=automation_job,
    appearance=Appearance(x=503, y=658),
)

process_sequential_activity_b = automation_pipeline.map(
    'Process Sequential Activity B',
    function=Function(
        name='ProcessSequentialActivityB',
        package=automation_package,
        description="Return sequential Activity B's typed result to its Temporal sink.\n",
        module=LOCAL_MODULE,
    ),
    value_type=automation_job,
    appearance=Appearance(x=804, y=660),
)

consume_fan_out_activity_a = automation_pipeline.input(
    'Consume Fan-Out Activity A',
    endpoint=endpoint_fan_out_activity_a,
    value_type=automation_job,
    appearance=Appearance(x=-277, y=1051),
)

process_fan_out_activity_a = automation_pipeline.map(
    'Process Fan-Out Activity A',
    function=Function(
        name='ProcessFanoutActivityA',
        package=automation_package,
        description="Return Activity A's typed result before the Workflow Split.\n",
        module=LOCAL_MODULE,
    ),
    value_type=automation_job,
    appearance=Appearance(x=-268, y=819),
)

consume_fan_out_activity_b = automation_pipeline.input(
    'Consume Fan-Out Activity B',
    endpoint=endpoint_fan_out_activity_b,
    value_type=automation_job,
    appearance=Appearance(x=295, y=996),
)

process_fan_out_activity_b = automation_pipeline.map(
    'Process Fan-Out Activity B',
    function=Function(
        name='ProcessFanoutActivityB',
        package=automation_package,
        description="Return Activity B's typed fan-out result.\n",
        module=LOCAL_MODULE,
    ),
    value_type=automation_job,
    appearance=Appearance(x=705, y=1001),
)

consume_fan_out_activity_c = automation_pipeline.input(
    'Consume Fan-Out Activity C',
    endpoint=endpoint_fan_out_activity_c,
    value_type=automation_job,
    appearance=Appearance(x=553, y=1503),
)

process_fan_out_activity_c = automation_pipeline.map(
    'Process Fan-Out Activity C',
    function=Function(
        name='ProcessFanoutActivityC',
        package=automation_package,
        description="Return Activity C's typed fan-out result.\n",
        module=LOCAL_MODULE,
    ),
    value_type=automation_job,
    appearance=Appearance(x=931, y=1493),
)

submit_fan_out_workflow_job = automation_pipeline.sink(
    'Submit Fan-Out Workflow Job',
    endpoint=endpoint_fan_out_workflow_job,
    value_type=automation_job,
    appearance=Appearance(x=-967, y=1034),
)

consume_fan_out_workflow_job = automation_pipeline.input(
    'Consume Fan-Out Workflow Job',
    endpoint=endpoint_fan_out_workflow_job,
    value_type=automation_job,
    appearance=Appearance(x=-635, y=1287),
)

call_fan_out_activity_a = automation_pipeline.sink(
    'Call Fan-Out Activity A',
    endpoint=endpoint_fan_out_activity_a,
    value_type=automation_job,
    appearance=Appearance(x=-271, y=1284),
)

split_activity_aresult = automation_pipeline.split(
    'Split Activity A Result',
    appearance=Appearance(x=40, y=1312),
)

call_fan_out_activity_b = automation_pipeline.sink(
    'Call Fan-Out Activity B',
    endpoint=endpoint_fan_out_activity_b,
    value_type=automation_job,
    appearance=Appearance(x=7, y=990),
)

observe_fan_out_activity_b = automation_pipeline.map(
    'Observe Fan-Out Activity B',
    function=Function(
        name='ObserveFanoutActivityB',
        package=automation_package,
        description='Observe the typed result returned by the Activity B fan-out branch.\n',
        module=LOCAL_MODULE,
    ),
    value_type=automation_job,
    appearance=Appearance(x=-11, y=793),
)

call_fan_out_activity_c = automation_pipeline.sink(
    'Call Fan-Out Activity C',
    endpoint=endpoint_fan_out_activity_c,
    value_type=automation_job,
    appearance=Appearance(x=317, y=1313),
)

observe_fan_out_activity_c = automation_pipeline.map(
    'Observe Fan-Out Activity C',
    function=Function(
        name='ObserveFanoutActivityC',
        package=automation_package,
        description='Observe the typed result returned by the Activity C fan-out branch.\n',
        module=LOCAL_MODULE,
    ),
    value_type=automation_job,
    appearance=Appearance(x=587, y=1121),
)

temporal_activity_schedule = automation_pipeline.input(
    'Temporal Activity Schedule',
    endpoint=endpoint_temporal_activity_schedule,
    value_type=automation_job,
    appearance=Appearance(x=-1917, y=639),
)

scheduled_activity_pause = automation_pipeline.delay(
    'Scheduled Activity Pause',
    duration=250,
    function=Function(
        name='ScheduledActivityPause',
        package=automation_package,
        description='Apply the ordinary local Delay inside an Activity started by Temporal Schedule.\n',
        module=LOCAL_MODULE,
    ),
    appearance=Appearance(x=-1661, y=402),
)

process_scheduled_activity = automation_pipeline.map(
    'Process Scheduled Activity',
    function=Function(
        name='ProcessScheduledActivity',
        package=automation_package,
        description='Return the visible result of one scheduled Activity execution.\n',
        module=LOCAL_MODULE,
    ),
    value_type=automation_job,
    appearance=Appearance(x=-1442, y=655),
)

temporal_workflow_schedule = automation_pipeline.input(
    'Temporal Workflow Schedule',
    endpoint=endpoint_temporal_workflow_schedule,
    value_type=automation_job,
    appearance=Appearance(x=-1906, y=846),
)

scheduled_workflow_pause = automation_pipeline.delay(
    'Scheduled Workflow Pause',
    duration=250,
    function=Function(
        name='ScheduledWorkflowPause',
        package=automation_package,
        description='Use the official Temporal Workflow timer for a scheduled Workflow.\n',
        module=LOCAL_MODULE,
    ),
    appearance=Appearance(x=-1684, y=1167),
)

process_scheduled_workflow = automation_pipeline.map(
    'Process Scheduled Workflow',
    function=Function(
        name='ProcessScheduledWorkflow',
        package=automation_package,
        description='Return the visible result of one scheduled Workflow execution.\n',
        module=LOCAL_MODULE,
    ),
    value_type=automation_job,
    appearance=Appearance(x=-1411, y=856),
)

local_schedule >> split_on_demand_jobs

split_on_demand_jobs >> submit_activity_job

process_activity_job >> consume_activity_job

consume_activity_job >> activity_pause

activity_pause >> process_activity_job

submit_activity_job >> observe_activity_result

split_on_demand_jobs >> submit_workflow_job

process_workflow_job >> consume_workflow_job

consume_workflow_job >> workflow_pause

workflow_pause >> call_sequential_activity_a

workflow_pause.task_pool_call(
    call_sequential_activity_a,
    pool=default_pool,
)

call_sequential_activity_a >> call_sequential_activity_b

call_sequential_activity_a.priority_task_pool_call(
    call_sequential_activity_b,
    priority=2,
    pool=default_pool,
)

call_sequential_activity_b >> process_workflow_job

call_sequential_activity_b.task_pool_call(
    process_workflow_job,
    pool=default_pool,
)

submit_workflow_job >> observe_workflow_result

process_sequential_activity_a >> consume_sequential_activity_a

consume_sequential_activity_a >> process_sequential_activity_a

process_sequential_activity_b >> consume_sequential_activity_b

consume_sequential_activity_b >> process_sequential_activity_b

process_fan_out_activity_a >> consume_fan_out_activity_a

consume_fan_out_activity_a >> process_fan_out_activity_a

process_fan_out_activity_b >> consume_fan_out_activity_b

consume_fan_out_activity_b >> process_fan_out_activity_b

process_fan_out_activity_c >> consume_fan_out_activity_c

consume_fan_out_activity_c >> process_fan_out_activity_c

split_on_demand_jobs >> submit_fan_out_workflow_job

consume_fan_out_workflow_job >> call_fan_out_activity_a

consume_fan_out_workflow_job.task_pool_call(
    call_fan_out_activity_a,
    pool=default_pool,
)

call_fan_out_activity_a >> split_activity_aresult

split_activity_aresult >> call_fan_out_activity_b

split_activity_aresult.priority_task_pool_call(
    call_fan_out_activity_b,
    priority=2,
    pool=default_pool,
)

call_fan_out_activity_b >> observe_fan_out_activity_b

split_activity_aresult >> call_fan_out_activity_c

split_activity_aresult.priority_task_pool_call(
    call_fan_out_activity_c,
    priority=7,
    pool=default_pool,
)

call_fan_out_activity_c >> observe_fan_out_activity_c

process_scheduled_activity >> temporal_activity_schedule

temporal_activity_schedule >> scheduled_activity_pause

scheduled_activity_pause >> process_scheduled_activity

process_scheduled_workflow >> temporal_workflow_schedule

temporal_workflow_schedule >> scheduled_workflow_pause

scheduled_workflow_pause >> process_scheduled_workflow
