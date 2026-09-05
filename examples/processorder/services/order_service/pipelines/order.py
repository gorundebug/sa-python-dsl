from sa_dsl import CallSemantics
from processorder.services.order_service.service import order_service
from processorder.pools.default import default_pool

from sa_dsl import (
    Appearance,
    Function,
    LOCAL_MODULE,
)

from processorder.endpoints.inventory_service_api import process_order_item

from processorder.endpoints.order_events import endpoint_order_processed

from processorder.endpoints.order_service_api import process_order

from processorder.packages.order import order_package

from processorder.services.order_service.service import order_pipeline

from processorder.types.order import (
    order,
    order_item,
    order_item_result,
    order_processed,
    order_state,
)

stream_process_order = order_pipeline.input(
    "Process Order",
    endpoint=process_order,
    appearance=Appearance(x=-760, y=-367),
    value_type=order,
)

split_pipeline = order_pipeline.split(
    "Split Pipeline",
    appearance=Appearance(x=-640, y=-597),
)

soft_deadline = order_pipeline.delay(
    "Soft Deadline",
    appearance=Appearance(x=-477, y=-444),
    function=Function(
        package=order_package,
        name="SoftDeadline",
        description="Trigger the timeout branch shortly before the request deadline, leaving the configured "
        "duration to assemble a response.\n"
        "When no request deadline exists, use the configured duration itself. Never wait past an "
        "existing deadline.\n",
        module=LOCAL_MODULE,
    ),
    duration=1000,
)

map_to_order_state = order_pipeline.map(
    "Map to Order State",
    appearance=Appearance(x=-368, y=-227),
    value_type=order_state,
    function=Function(
        package=order_package,
        name="MapToOrderState",
        description="Produce a TIMED_OUT order result that preserves the order ID and submitted total.\n"
        "Do not add item results at this stage; results received before the timeout are included "
        "in the final response.\n",
        module=LOCAL_MODULE,
    ),
)

merge_results = order_pipeline.merge(
    "Merge Results",
    appearance=Appearance(x=-228, y=130),
)

split_order_result = order_pipeline.split(
    "Split Order Result",
    appearance=Appearance(x=-671, y=-129),
)

publish_order_processed = order_pipeline.sink(
    "Publish Order Processed",
    endpoint=endpoint_order_processed,
    appearance=Appearance(x=-944, y=-255),
    value_type=order_processed,
)

process_order_items = order_pipeline.flat_map(
    "Process Order Items",
    appearance=Appearance(x=-198, y=-662),
    value_type=order_item,
    function=Function(
        package=order_package,
        name="ProcessOrderItems",
        description="Emit every order item independently for inventory processing.\n"
        "Preserve each item's data and assign the parent order ID.\n",
        module=LOCAL_MODULE,
    ),
)

stream_process_order_item = order_pipeline.sink(
    "Process Order Item",
    endpoint=process_order_item,
    appearance=Appearance(x=-60, y=-375),
    value_type=order_item_result,
)

map_order_item_result_to_order_state = order_pipeline.map(
    "Map Order Item Result To Order State",
    appearance=Appearance(x=103, y=-52),
    value_type=order_state,
    function=Function(
        package=order_package,
        name="MapOrderItemResultToOrderState",
        description="Produce an order result containing one inventory result and preserving its order ID.\n"
        "Mark it CONFIRMED when the item was reserved; otherwise mark it PARTIALLY_CONFIRMED.\n"
        "Record the time when this result is produced.\n",
        module=LOCAL_MODULE,
    ),
)

map_to_order_processed = order_pipeline.map(
    "MapToOrderProcessed",
    appearance=Appearance(x=-821, y=-26),
    value_type=order_processed,
    function=Function(
        package=order_package,
        name="MapToOrderProcessed",
        description="Create an OrderProcessed event from the final order state.\n"
        "Preserve the order ID, status, and processing time. Count all item results and reserved "
        "items; for unsuccessful orders use the final status as the failure reason.\n",
        module=LOCAL_MODULE,
    ),
)

(
    split_order_result
    >> stream_process_order
    >> split_pipeline
    >> soft_deadline
    >> map_to_order_state
)

split_pipeline.parallel_call(
    soft_deadline,
)

stream_process_order.priority_task_pool_call(
    split_pipeline,
    pool=default_pool,
    priority=1,
)

merge_results >> split_order_result >> map_to_order_processed >> publish_order_processed

split_pipeline >> process_order_items >> stream_process_order_item

split_pipeline.parallel_call(
    process_order_items,
)

stream_process_order_item >> map_order_item_result_to_order_state
