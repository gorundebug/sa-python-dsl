from processorder.project.processorder import project

order_service_api = project.module(
    'order_service_api',
    module_path='github.com/gorundebug/order_service_api',
    golang_version='1.25.4',
)
