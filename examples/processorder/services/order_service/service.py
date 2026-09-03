from sa_dsl import (
    CallSemantics,
    Environment,
    KubernetesWorkloadType,
    ProgrammingLanguage,
)

from processorder.project.processorder import project

order_service = project.service(
    "Order Service",
    programming_language=ProgrammingLanguage.GO,
    module_path="github.com/gorundebug/orderservice",
    color="#FF5C00",
    default_call_semantics=CallSemantics.FUNCTION_CALL,
    http_port=9091,
    http_host="0.0.0.0",
    metrics_handler="metrics",
    status_handler="status",
    startup_handler="health/startup",
    readiness_handler="health/ready",
    liveness_handler="health/live",
    kubernetes_workload_type=KubernetesWorkloadType.DEPLOYMENT,
    grpc_port=9201,
    grpc_host="0.0.0.0",
    default_grpc_timeout=0,
    shutdown_timeout=30000,
    environment=Environment.UNDEFINED,
    golang_version="1.25.4",
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
