from sa_dsl import (
    Appearance,
    Function,
    LOCAL_MODULE,
)

from processorder.endpoints.local_cron import analytics_schedule

from processorder.endpoints.order_events import endpoint_order_processed

from processorder.packages.analytics import analytics_package

from processorder.services.analytics_service.service import analytics_pipeline

from processorder.types.automation import automation_job

from processorder.types.order import order_processed

stream_analytics_schedule = analytics_pipeline.input(
    "Analytics Schedule",
    endpoint=analytics_schedule,
    appearance=Appearance(x=-1600, y=-205),
    value_type=automation_job,
)

consume_order_processed = analytics_pipeline.input(
    "Consume Order Processed",
    endpoint=endpoint_order_processed,
    appearance=Appearance(x=-1190, y=-205),
    value_type=order_processed,
)

count_order_processed = analytics_pipeline.process(
    "Count Order Processed",
    appearance=Appearance(x=-1390, y=-19),
    value_type=order_processed,
    function=Function(
        package=analytics_package,
        name="CountOrderProcessed",
        description="Count successful and unsuccessful orders independently, then return the event unchanged.\n",
        module=LOCAL_MODULE,
    ),
)

count_order_processed >> consume_order_processed >> count_order_processed
