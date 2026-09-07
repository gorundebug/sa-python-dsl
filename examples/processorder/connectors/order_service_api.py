from sa_dsl import DataConnectorImplementation

from processorder.modules.order_service_api import order_service_api
from processorder.project.processorder import project

connector_order_service_api = project.http_connector(
    'Order Service API',
    go_implementation=DataConnectorImplementation.NET_HTTP,
    cpp_userver_implementation=DataConnectorImplementation.USERVER_HTTP,
    cpp_boost_implementation=DataConnectorImplementation.BOOST_BEAST_HTTP,
    python_implementation=DataConnectorImplementation.AIOHTTP,
    rust_implementation=DataConnectorImplementation.RUST_AXUM,
    type_script_implementation=DataConnectorImplementation.NODE_HTTP,
    use_dedicated_listener=False,
    module=order_service_api,
)
