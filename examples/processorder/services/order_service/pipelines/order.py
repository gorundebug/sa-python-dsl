from sa_dsl import (
    Appearance,
    Function,
    LOCAL_MODULE,
)

from processorder.endpoints.inventory_service_api import endpoint_process_order_item
from processorder.endpoints.order_events import endpoint_order_processed
from processorder.endpoints.order_service_api import endpoint_process_order
from processorder.packages.order import order_package
from processorder.pools.default_pool import default_pool
from processorder.services.order_service.service import order_pipeline
from processorder.services.order_service.service import order_service
from processorder.types.order import order
from processorder.types.order_item import order_item
from processorder.types.order_item_result import order_item_result
from processorder.types.order_processed import order_processed
from processorder.types.order_state import order_state

process_order = order_pipeline.input(
    'Process Order',
    endpoint=endpoint_process_order,
    value_type=order,
    appearance=Appearance(x=-760, y=-367),
)

split_pipeline = order_pipeline.split(
    'Split Pipeline',
    appearance=Appearance(x=-640, y=-597),
)

soft_deadline = order_pipeline.delay(
    'Soft Deadline',
    duration=1000,
    function=Function(
        name='SoftDeadline',
        package=order_package,
        description='Trigger the timeout branch shortly before the request deadline, leaving the configured duration to assemble a response.\nWhen no request deadline exists, use the configured duration itself. Never wait past an existing deadline.\n',
        module=LOCAL_MODULE,
    ),
    appearance=Appearance(x=-477, y=-444),
)

map_to_order_state = order_pipeline.map(
    'Map to Order State',
    function=Function(
        name='MapToOrderState',
        package=order_package,
        description='Produce a TIMED_OUT order result that preserves the order ID and submitted total.\nDo not add item results at this stage; results received before the timeout are included in the final response.\n',
        module=LOCAL_MODULE,
    ),
    value_type=order_state,
    appearance=Appearance(x=-368, y=-227),
)

merge_results = order_pipeline.merge(
    'Merge Results',
    appearance=Appearance(x=-228, y=130),
)

split_order_result = order_pipeline.split(
    'Split Order Result',
    appearance=Appearance(x=-671, y=-129),
)

publish_order_processed = order_pipeline.sink(
    'Publish Order Processed',
    endpoint=endpoint_order_processed,
    value_type=order_processed,
    appearance=Appearance(x=-944, y=-255),
)

process_order_items = order_pipeline.flat_map(
    'Process Order Items',
    function=Function(
        name='ProcessOrderItems',
        package=order_package,
        description="Emit every order item independently for inventory processing.\nPreserve each item's data and assign the parent order ID.\n",
        module=LOCAL_MODULE,
    ),
    value_type=order_item,
    appearance=Appearance(x=-198, y=-662),
)

process_order_item = order_pipeline.sink(
    'Process Order Item',
    endpoint=endpoint_process_order_item,
    value_type=order_item_result,
    appearance=Appearance(x=-60, y=-375),
)

map_order_item_result_to_order_state = order_pipeline.map(
    'Map Order Item Result To Order State',
    function=Function(
        name='MapOrderItemResultToOrderState',
        package=order_package,
        description='Produce an order result containing one inventory result and preserving its order ID.\nMark it CONFIRMED when the item was reserved; otherwise mark it PARTIALLY_CONFIRMED.\nRecord the time when this result is produced.\n',
        module=LOCAL_MODULE,
    ),
    value_type=order_state,
    appearance=Appearance(x=103, y=-52),
)

map_to_order_processed = order_pipeline.map(
    'MapToOrderProcessed',
    function=Function(
        name='MapToOrderProcessed',
        package=order_package,
        description='Create an OrderProcessed event from the final order state.\nPreserve the order ID, status, and processing time. Count all item results and reserved items; for unsuccessful orders use the final status as the failure reason.\n',
        module=LOCAL_MODULE,
    ),
    value_type=order_processed,
    appearance=Appearance(x=-821, y=-26),
)

split_order_result >> process_order

process_order >> split_pipeline

process_order.priority_task_pool_call(
    split_pipeline,
    priority=1,
    pool=default_pool,
)

split_pipeline >> soft_deadline

split_pipeline.parallel_call(
    soft_deadline,
)

soft_deadline >> map_to_order_state

merge_results << map_to_order_state

merge_results << map_order_item_result_to_order_state

merge_results >> split_order_result

map_to_order_processed >> publish_order_processed

split_pipeline >> process_order_items

split_pipeline.parallel_call(
    process_order_items,
)

process_order_items >> process_order_item

process_order_item >> map_order_item_result_to_order_state

split_order_result >> map_to_order_processed
