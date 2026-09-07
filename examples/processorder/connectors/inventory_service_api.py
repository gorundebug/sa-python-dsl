from sa_dsl import DataConnectorImplementation

from processorder.modules.inventory_service_api import inventory_service_api
from processorder.project.processorder import project

connector_inventory_service_api = project.grpc_connector(
    'Inventory Service API',
    go_implementation=DataConnectorImplementation.GOOGLE_GRPC,
    cpp_userver_implementation=DataConnectorImplementation.USERVER_GRPC,
    cpp_boost_implementation=DataConnectorImplementation.ASIO_GRPC,
    python_implementation=DataConnectorImplementation.GOOGLE_GRPC,
    rust_implementation=DataConnectorImplementation.RUST_TONIC,
    type_script_implementation=DataConnectorImplementation.GRPC_JS,
    address='dns:///localhost:9202',
    connections_count=1,
    module=inventory_service_api,
)
