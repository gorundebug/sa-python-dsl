from processorder.modules.order_service_api import order_service_api

from processorder.project.processorder import project

connector_order_service_api = project.http_connector(
    "Order Service API",
    use_dedicated_listener=False,
    module=order_service_api,
)
