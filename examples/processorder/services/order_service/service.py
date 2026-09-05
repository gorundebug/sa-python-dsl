from sa_dsl import (
    Appearance,
    Golang,
    GrpcServer,
    HttpServer,
    ServiceModule,
)

from processorder.project.processorder import project

order_service = project.service(
    "Order Service",
    language=Golang(version="1.25.4"),
    module=ServiceModule(path="github.com/gorundebug/orderservice"),
    appearance=Appearance(color="#FF5C00"),
    http_server=HttpServer(port=9091),
    grpc_server=GrpcServer(port=9201, default_timeout=0),
)

order_pipeline = order_service.pipeline("order")

order_default_pipeline = order_service.pipeline("default")

from processorder.services.order_service.pipelines import (
    default as _default_pipeline,
    order as _order_pipeline,
)

from processorder.services.order_service.pipelines.default import (
    process_order_item_error,
)

from processorder.services.order_service.pipelines.order import (
    map_order_item_result_to_order_state,
    map_to_order_state,
    merge_results,
    process_order_items,
    soft_deadline,
    split_order_result,
    split_pipeline,
    stream_process_order,
    stream_process_order_item,
)


(
    merge_results
    << map_to_order_state
    << map_order_item_result_to_order_state
    << process_order_item_error
)

stream_process_order_item >> process_order_item_error

stream_process_order_item | process_order_item_error
