from processorder.modules.inventory_service_api import inventory_service_api

from processorder.project.processorder import project

connector_inventory_service_api = project.grpc_connector(
    "Inventory Service API",
    module=inventory_service_api,
    address="dns:///localhost:9202",
    connections_count=1,
)
