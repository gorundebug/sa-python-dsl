"""Canonical Service Architect process-order project."""

from .project.processorder import project
from .modules import inventory_service_api as _inventory_service_api_module
from .modules import model as _model_module
from .modules import order_service_api as _order_service_api_module
from .pools import default as _default_pool
from .pools import inventory_priority as _inventory_priority_pool
from .types import automation as _automation_types
from .types import common as _common_types
from .types import order as _order_types
from .connectors import inventory_service_api as _inventory_service_api_connector
from .connectors import local_cron as _local_cron_connector
from .connectors import order_events as _order_events_connector
from .connectors import order_service_api as _order_service_api_connector
from .connectors import temporal as _temporal_connector
from .endpoints import inventory_service_api as _inventory_service_api_endpoints
from .endpoints import local_cron as _local_cron_endpoints
from .endpoints import order_events as _order_events_endpoints
from .endpoints import order_service_api as _order_service_api_endpoints
from .endpoints import temporal as _temporal_endpoints
from .services.order_service import service as _order_service
from .services.inventory_service import service as _inventory_service
from .services.analytics_service import service as _analytics_service
from .services.automation_service import service as _automation_service

__all__ = ["project"]
