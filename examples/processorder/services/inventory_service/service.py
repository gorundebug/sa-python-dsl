from sa_dsl import (
    Appearance,
    GrpcServer,
    Golang,
    HttpServer,
    ServiceModule,
)

from processorder.project.processorder import project

inventory_service = project.service(
    'Inventory Service',
    appearance=Appearance(color='#6800FF'),
    language=Golang(version='1.25.4'),
    module=ServiceModule(path='github.com/gorundebug/inventoryservice'),
    http_server=HttpServer(port=9092),
    grpc_server=GrpcServer(port=9202, default_timeout=0),
)

inventory_item_pipeline = inventory_service.pipeline('inventoryItem')

from processorder.services.inventory_service.pipelines import inventory_item as _inventory_item_pipeline

from processorder.services.inventory_service.pipelines.inventory_item import get_inventory_item_data

from processorder.services.inventory_service.pipelines.inventory_item import get_inventory_item_error

get_inventory_item_data | get_inventory_item_error
