from sa_dsl import (
    Appearance,
    Function,
    LOCAL_MODULE,
)

from processorder.endpoints.inventory_service_api import endpoint_process_order_item
from processorder.packages.inventory_item import inventory_item_package
from processorder.pools.inventory_priority_workers import inventory_priority_workers
from processorder.services.inventory_service.service import inventory_item_pipeline
from processorder.services.inventory_service.service import inventory_service
from processorder.types.order_item import order_item
from processorder.types.order_item_result import order_item_result

process_inventory_item = inventory_item_pipeline.input(
    'Process Inventory Item',
    endpoint=endpoint_process_order_item,
    value_type=order_item,
    appearance=Appearance(x=250, y=-400),
)

get_inventory_item_data = inventory_item_pipeline.process(
    'Get Inventory Item Data',
    function=Function(
        name='GetInventoryItemData',
        package=inventory_item_package,
        description='Reserve the requested quantity without allowing concurrent orders to overdraw stock.\nOn success, return CONFIRMED with the requested quantity available. Otherwise return OUT_OF_STOCK with the current available quantity.\nPreserve the order and item identity, requested quantity, and unit price.\nThe example starts with SKU-001: 100, SKU-002: 50, and SKU-003: 25.\n',
        module=LOCAL_MODULE,
    ),
    value_type=order_item_result,
    appearance=Appearance(x=527, y=-562),
)

merge_inventory_result = inventory_item_pipeline.merge(
    'Merge Inventory Result',
    appearance=Appearance(x=542, y=33),
)

get_inventory_item_error = inventory_item_pipeline.error(
    'Get Inventory Item Error',
    function=Function(
        name='GetInventoryItemError',
        package=inventory_item_package,
        description='When inventory processing fails, return an OUT_OF_STOCK result with no available quantity.\nPreserve the order and item identity and requested quantity, and record the failure.\n',
        module=LOCAL_MODULE,
    ),
    value_type=order_item_result,
    appearance=Appearance(x=733, y=-263),
)

merge_inventory_result >> process_inventory_item

process_inventory_item >> get_inventory_item_data

process_inventory_item.priority_task_pool_call(
    get_inventory_item_data,
    priority=10,
    pool=inventory_priority_workers,
)

merge_inventory_result << get_inventory_item_data

get_inventory_item_data.parallel_call(
    merge_inventory_result,
)

merge_inventory_result << get_inventory_item_error

get_inventory_item_data >> get_inventory_item_error
