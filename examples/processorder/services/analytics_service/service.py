from sa_dsl import (
    Appearance,
    Golang,
    GrpcServer,
    HttpServer,
    ServiceModule,
)

from processorder.project.processorder import project

analytics_service = project.service(
    "Analytics Service",
    language=Golang(version="1.25.4"),
    module=ServiceModule(path="github.com/gorundebug/analyticsservice"),
    appearance=Appearance(color="#05ABF7"),
    http_server=HttpServer(port=9093),
    grpc_server=GrpcServer(port=9203, default_timeout=0),
)

analytics_pipeline = analytics_service.pipeline("analytics")

from processorder.services.analytics_service.pipelines import (
    analytics as _analytics_pipeline,
)
