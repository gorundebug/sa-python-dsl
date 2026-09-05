from sa_dsl import (
    Appearance,
    Golang,
    GrpcServer,
    HttpServer,
    ServiceModule,
)

from processorder.project.processorder import project

inventory_service = project.service(
    "Inventory Service",
    language=Golang(version="1.25.4"),
    module=ServiceModule(path="github.com/gorundebug/inventoryservice"),
    appearance=Appearance(color="#6800FF"),
    http_server=HttpServer(port=9092),
    grpc_server=GrpcServer(port=9202, default_timeout=0),
)

inventory_item_pipeline = inventory_service.pipeline("inventoryItem")

from processorder.services.inventory_service.pipelines import (
    inventory_item as _inventory_item_pipeline,
)
