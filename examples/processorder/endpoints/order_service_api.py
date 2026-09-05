from processorder.connectors.order_service_api import connector_order_service_api

from processorder.packages.endpoint import endpoint_package

from sa_dsl import (
    Function,
)

process_order = connector_order_service_api.post(
    "Process Order",
    function=Function(
        name="ProcessOrder",
        package=endpoint_package,
        public=False,
        description="Accept orders with at least one item and positive quantities; reject malformed or "
        "invalid requests as client errors.\n"
        "Reuse X-Request-ID when supplied, otherwise generate an order ID. Preserve customer, "
        "item, price, and X-Trace data, and apply the configured timeout of five seconds by "
        "default.\n"
        "Return one response per order. When all items finish, use CONFIRMED only if every item "
        "was reserved; otherwise use PARTIALLY_CONFIRMED. If the deadline wins, return TIMED_OUT "
        "with the item results received so far.\n"
        "Calculate the total from processed item prices, falling back to the submitted total when "
        "no item result arrived, and include individual item failures in the response.\n",
    ),
    path="/v1/processorder",
)
