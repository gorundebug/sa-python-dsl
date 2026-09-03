from sa_dsl import (
    CallSemantics,
    Environment,
    KubernetesWorkloadType,
    ProgrammingLanguage,
)

from processorder.project.processorder import project

inventory_service = project.service(
    "Inventory Service",
    programming_language=ProgrammingLanguage.GO,
    module_path="github.com/gorundebug/inventoryservice",
    color="#6800FF",
    default_call_semantics=CallSemantics.FUNCTION_CALL,
    http_port=9092,
    http_host="0.0.0.0",
    metrics_handler="metrics",
    status_handler="status",
    startup_handler="health/startup",
    readiness_handler="health/ready",
    liveness_handler="health/live",
    kubernetes_workload_type=KubernetesWorkloadType.DEPLOYMENT,
    grpc_port=9202,
    grpc_host="0.0.0.0",
    default_grpc_timeout=0,
    shutdown_timeout=30000,
    environment=Environment.UNDEFINED,
    golang_version="1.25.4",
)

inventory_item_pipeline = inventory_service.pipeline("inventoryItem")

from processorder.services.inventory_service.pipelines import (
    inventory_item as _inventory_item_pipeline,
)
