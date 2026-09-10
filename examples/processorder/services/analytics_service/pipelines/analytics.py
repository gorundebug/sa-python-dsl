from sa_dsl import (
    Appearance,
    Function,
    LOCAL_MODULE,
)

from processorder.endpoints.local_cron import endpoint_analytics_schedule
from processorder.endpoints.order_events import endpoint_order_processed
from processorder.packages.analytics import analytics_package
from processorder.services.analytics_service.service import analytics_pipeline
from processorder.types.automation_job import automation_job
from processorder.types.order_processed import order_processed

analytics_schedule = analytics_pipeline.input(
    'Analytics Schedule',
    endpoint=endpoint_analytics_schedule,
    value_type=automation_job,
    appearance=Appearance(x=-1600, y=-205),
)

consume_order_processed = analytics_pipeline.input(
    'Consume Order Processed',
    endpoint=endpoint_order_processed,
    value_type=order_processed,
    appearance=Appearance(x=-1190, y=-205),
)

count_order_processed = analytics_pipeline.process(
    'Count Order Processed',
    function=Function(
        name='CountOrderProcessed',
        package=analytics_package,
        description='Count successful and unsuccessful orders independently, then return the event unchanged.\n',
        module=LOCAL_MODULE,
    ),
    value_type=order_processed,
    appearance=Appearance(x=-1390, y=-19),
)

count_order_processed >> consume_order_processed

consume_order_processed >> count_order_processed
