from sa_dsl import (
    Appearance,
    GrpcServer,
    Golang,
    HttpServer,
    ServiceModule,
)

from processorder.project.processorder import project

automation_service = project.service(
    'Automation Service',
    appearance=Appearance(color='#00A86B'),
    language=Golang(version='1.25.4'),
    module=ServiceModule(path='github.com/gorundebug/automationservice'),
    http_server=HttpServer(port=9094),
    grpc_server=GrpcServer(port=9204, default_timeout=0),
)

automation_pipeline = automation_service.pipeline('automation')

from processorder.services.automation_service.pipelines import automation as _automation_pipeline
