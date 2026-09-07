from sa_dsl import (
    Appearance,
    GrpcServer,
    Golang,
    HttpServer,
    ServiceModule,
)

from processorder.project.processorder import project

order_service = project.service(
    'Order Service',
    appearance=Appearance(color='#FF5C00'),
    language=Golang(version='1.25.4'),
    module=ServiceModule(path='github.com/gorundebug/orderservice'),
    http_server=HttpServer(port=9091),
    grpc_server=GrpcServer(port=9201, default_timeout=0),
)

order_pipeline = order_service.pipeline('order')

default_pipeline = order_service.pipeline('default')

from processorder.services.order_service.pipelines import order as _order_pipeline

from processorder.services.order_service.pipelines import default as _default_pipeline

from processorder.services.order_service.pipelines.default import process_order_item_error

from processorder.services.order_service.pipelines.order import merge_results

from processorder.services.order_service.pipelines.order import process_order_item

process_order_item | process_order_item_error

merge_results << process_order_item_error

process_order_item >> process_order_item_error
