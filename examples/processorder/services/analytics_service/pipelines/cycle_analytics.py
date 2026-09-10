from sa_dsl import (
    Appearance,
    Function,
    LOCAL_MODULE,
)

from processorder.endpoints.analytics_functions import endpoint_cycle_analytics_input
from processorder.endpoints.analytics_functions import endpoint_cycle_analytics_result
from processorder.packages.cycleanalytics import cycleanalytics_package
from processorder.services.analytics_service.service import cycle_analytics_pipeline
from processorder.types.analytics_event import analytics_event

cycle_analytics_input = cycle_analytics_pipeline.input(
    'Cycle Analytics Input',
    endpoint=endpoint_cycle_analytics_input,
    value_type=analytics_event,
    appearance=Appearance(x=-2362, y=-1830),
)

merge_cycle_analytics = cycle_analytics_pipeline.merge(
    'Merge Cycle Analytics',
    appearance=Appearance(x=-1830, y=-1827),
)

advance_cycle_analytics = cycle_analytics_pipeline.map(
    'Advance Cycle Analytics',
    function=Function(
        name='AdvanceCycleAnalytics',
        package=cycleanalytics_package,
        description='Increment the cycle counter while preserving the analytics event identity.',
        module=LOCAL_MODULE,
    ),
    value_type=analytics_event,
    appearance=Appearance(x=-1502, y=-1648),
)

split_cycle_analytics = cycle_analytics_pipeline.split(
    'Split Cycle Analytics',
    appearance=Appearance(x=-830, y=-1687),
)

continue_cycle_analytics = cycle_analytics_pipeline.filter(
    'Continue Cycle Analytics',
    function=Function(
        name='ContinueCycleAnalytics',
        package=cycleanalytics_package,
        description='Keep intermediate analytics events whose cycle counter is below three.',
        module=LOCAL_MODULE,
    ),
    appearance=Appearance(x=-879, y=-2196),
)

complete_cycle_analytics = cycle_analytics_pipeline.filter(
    'Complete Cycle Analytics',
    function=Function(
        name='CompleteCycleAnalytics',
        package=cycleanalytics_package,
        description='Keep the terminal analytics event once its cycle counter reaches three.',
        module=LOCAL_MODULE,
    ),
    appearance=Appearance(x=-529, y=-1718),
)

cycle_analytics_link = cycle_analytics_pipeline.cycle_link(
    'Cycle Analytics Link',
    appearance=Appearance(x=-1311, y=-2114),
)

write_cycle_analytics = cycle_analytics_pipeline.sink(
    'Write Cycle Analytics',
    endpoint=endpoint_cycle_analytics_result,
    value_type=analytics_event,
    appearance=Appearance(x=-545, y=-2204),
)

merge_cycle_analytics << cycle_analytics_input

merge_cycle_analytics << cycle_analytics_link

merge_cycle_analytics >> advance_cycle_analytics

advance_cycle_analytics >> split_cycle_analytics

split_cycle_analytics >> continue_cycle_analytics

split_cycle_analytics >> complete_cycle_analytics

continue_cycle_analytics >> cycle_analytics_link

complete_cycle_analytics >> write_cycle_analytics
