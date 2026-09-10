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
    appearance=Appearance(x=-1600, y=1160),
)

merge_cycle_analytics = cycle_analytics_pipeline.merge(
    'Merge Cycle Analytics',
    appearance=Appearance(x=-1350, y=1160),
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
    appearance=Appearance(x=-1100, y=1160),
)

split_cycle_analytics = cycle_analytics_pipeline.split(
    'Split Cycle Analytics',
    appearance=Appearance(x=-850, y=1160),
)

continue_cycle_analytics = cycle_analytics_pipeline.filter(
    'Continue Cycle Analytics',
    function=Function(
        name='ContinueCycleAnalytics',
        package=cycleanalytics_package,
        description='Keep intermediate analytics events whose cycle counter is below three.',
        module=LOCAL_MODULE,
    ),
    appearance=Appearance(x=-600, y=1060),
)

complete_cycle_analytics = cycle_analytics_pipeline.filter(
    'Complete Cycle Analytics',
    function=Function(
        name='CompleteCycleAnalytics',
        package=cycleanalytics_package,
        description='Keep the terminal analytics event once its cycle counter reaches three.',
        module=LOCAL_MODULE,
    ),
    appearance=Appearance(x=-600, y=1260),
)

cycle_analytics_link = cycle_analytics_pipeline.cycle_link(
    'Cycle Analytics Link',
    appearance=Appearance(x=-1100, y=960),
)

write_cycle_analytics = cycle_analytics_pipeline.sink(
    'Write Cycle Analytics',
    endpoint=endpoint_cycle_analytics_result,
    value_type=analytics_event,
    appearance=Appearance(x=-350, y=1260),
)

merge_cycle_analytics << cycle_analytics_input

merge_cycle_analytics << cycle_analytics_link

merge_cycle_analytics >> advance_cycle_analytics

advance_cycle_analytics >> split_cycle_analytics

split_cycle_analytics >> continue_cycle_analytics

split_cycle_analytics >> complete_cycle_analytics

continue_cycle_analytics >> cycle_analytics_link

complete_cycle_analytics >> write_cycle_analytics
