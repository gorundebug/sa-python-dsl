from sa_dsl import (
    CallSemantics,
    Environment,
    KubernetesWorkloadType,
    ProgrammingLanguage,
)

from processorder.project.processorder import project

analytics_service = project.service(
    "Analytics Service",
    programming_language=ProgrammingLanguage.GO,
    module_path="github.com/gorundebug/analyticsservice",
    color="#05ABF7",
    default_call_semantics=CallSemantics.FUNCTION_CALL,
    http_port=9093,
    http_host="0.0.0.0",
    metrics_handler="metrics",
    status_handler="status",
    startup_handler="health/startup",
    readiness_handler="health/ready",
    liveness_handler="health/live",
    kubernetes_workload_type=KubernetesWorkloadType.DEPLOYMENT,
    grpc_port=9203,
    grpc_host="0.0.0.0",
    default_grpc_timeout=0,
    shutdown_timeout=30000,
    environment=Environment.UNDEFINED,
    golang_version="1.25.4",
)

analytics_pipeline = analytics_service.pipeline("analytics")

from processorder.services.analytics_service.pipelines import (
    analytics as _analytics_pipeline,
)
