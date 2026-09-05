from processorder.connectors.inventory_service_api import (
    connector_inventory_service_api,
)

from processorder.packages.endpoint import endpoint_package

from sa_dsl import (
    Function,
)

process_order_item = connector_inventory_service_api.unary_method(
    "Process Order Item",
    function=Function(
        name="ProcessOrderItem",
        package=endpoint_package,
        description="Reserve inventory for one order item using its order ID, item ID, SKU, and quantity.\n"
        "Return the available quantity, reservation outcome, and status. The caller combines this "
        "response with the original identity, requested quantity, and unit price.\n"
        "If the inventory call fails, the caller returns a non-reserved PROCESSING_ERROR result "
        "with the failure message.\n",
        public=False,
    ),
    method_name="ProcessOrderItem",
)
