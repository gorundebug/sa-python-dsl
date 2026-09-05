from sa_dsl import CallSemantics
from processorder.services.inventory_service.service import inventory_service
from processorder.pools.inventory_priority import inventory_priority_workers

from sa_dsl import (
    Appearance,
    Function,
    LOCAL_MODULE,
)

from processorder.endpoints.inventory_service_api import process_order_item

from processorder.packages.inventory_item import inventory_item_package

from processorder.services.inventory_service.service import inventory_item_pipeline

from processorder.types.order import (
    order_item,
    order_item_result,
)

process_inventory_item = inventory_item_pipeline.input(
    "Process Inventory Item",
    endpoint=process_order_item,
    appearance=Appearance(x=250, y=-400),
    value_type=order_item,
)

get_inventory_item_data = inventory_item_pipeline.process(
    "Get Inventory Item Data",
    appearance=Appearance(x=527, y=-562),
    value_type=order_item_result,
    function=Function(
        package=inventory_item_package,
        name="GetInventoryItemData",
        description="Reserve the requested quantity without allowing concurrent orders to overdraw stock.\n"
        "On success, return CONFIRMED with the requested quantity available. Otherwise return "
        "OUT_OF_STOCK with the current available quantity.\n"
        "Preserve the order and item identity, requested quantity, and unit price.\n"
        "The example starts with SKU-001: 100, SKU-002: 50, and SKU-003: 25.\n",
        module=LOCAL_MODULE,
    ),
)

merge_inventory_result = inventory_item_pipeline.merge(
    "Merge Inventory Result",
    appearance=Appearance(x=542, y=33),
)

get_inventory_item_error = inventory_item_pipeline.error(
    "Get Inventory Item Error",
    appearance=Appearance(x=733, y=-263),
    value_type=order_item_result,
    function=Function(
        package=inventory_item_package,
        name="GetInventoryItemError",
        description="When inventory processing fails, return an OUT_OF_STOCK result with no available "
        "quantity.\n"
        "Preserve the order and item identity and requested quantity, and record the failure.\n",
        module=LOCAL_MODULE,
    ),
)

(
    merge_inventory_result
    >> process_inventory_item
    >> get_inventory_item_data
    >> get_inventory_item_error
)

process_inventory_item.priority_task_pool_call(
    get_inventory_item_data,
    pool=inventory_priority_workers,
    priority=10,
)

merge_inventory_result << get_inventory_item_data << get_inventory_item_error

get_inventory_item_data | get_inventory_item_error

get_inventory_item_data.parallel_call(
    merge_inventory_result,
)
