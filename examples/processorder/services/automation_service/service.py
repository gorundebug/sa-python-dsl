from sa_dsl import (
    CallSemantics,
    Environment,
    KubernetesWorkloadType,
    ProgrammingLanguage,
)

from processorder.project.processorder import project

automation_service = project.service(
    "Automation Service",
    programming_language=ProgrammingLanguage.GO,
    module_path="github.com/gorundebug/automationservice",
    color="#00A86B",
    default_call_semantics=CallSemantics.FUNCTION_CALL,
    http_port=9094,
    http_host="0.0.0.0",
    metrics_handler="metrics",
    status_handler="status",
    startup_handler="health/startup",
    readiness_handler="health/ready",
    liveness_handler="health/live",
    kubernetes_workload_type=KubernetesWorkloadType.DEPLOYMENT,
    grpc_port=9204,
    grpc_host="0.0.0.0",
    default_grpc_timeout=0,
    shutdown_timeout=30000,
    environment=Environment.UNDEFINED,
    golang_version="1.25.4",
)

automation_pipeline = automation_service.pipeline("automation")

from processorder.services.automation_service.pipelines import (
    automation as _automation_pipeline,
)
