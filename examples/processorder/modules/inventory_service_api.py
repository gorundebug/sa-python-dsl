from processorder.project.processorder import project

inventory_service_api = project.module(
    'inventory_service_api',
    module_path='github.com/gorundebug/inventory_service_api',
    golang_version='1.25.4',
)
