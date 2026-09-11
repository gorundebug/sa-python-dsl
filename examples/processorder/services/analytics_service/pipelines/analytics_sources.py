from sa_dsl import Appearance

from processorder.endpoints.analytics_functions import endpoint_analytics_orders
from processorder.endpoints.analytics_functions import endpoint_analytics_payments
from processorder.endpoints.analytics_functions import endpoint_analytics_shipments
from processorder.services.analytics_service.service import analytics_sources_pipeline
from processorder.types.analytics_event import analytics_event

analytics_orders = analytics_sources_pipeline.input(
    'Analytics Orders',
    endpoint=endpoint_analytics_orders,
    value_type=analytics_event,
    appearance=Appearance(x=-1739, y=-1133),
)

split_analytics_orders = analytics_sources_pipeline.split(
    'Split Analytics Orders',
    appearance=Appearance(x=-1529, y=-1100),
)

analytics_payments = analytics_sources_pipeline.input(
    'Analytics Payments',
    endpoint=endpoint_analytics_payments,
    value_type=analytics_event,
    appearance=Appearance(x=-2307, y=-767),
)

split_analytics_payments = analytics_sources_pipeline.split(
    'Split Analytics Payments',
    appearance=Appearance(x=-1945, y=-776),
)

analytics_shipments = analytics_sources_pipeline.input(
    'Analytics Shipments',
    endpoint=endpoint_analytics_shipments,
    value_type=analytics_event,
    appearance=Appearance(x=12, y=-1308),
)

analytics_orders >> split_analytics_orders

analytics_payments >> split_analytics_payments
