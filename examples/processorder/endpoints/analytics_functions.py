from sa_dsl import Function

from processorder.connectors.analytics_functions import connector_analytics_functions
from processorder.packages.endpoint import endpoint_package

endpoint_analytics_orders = connector_analytics_functions.endpoint(
    'Analytics Orders',
    function=Function(
        name='AnalyticsOrders',
        package=endpoint_package,
        public=False,
        description='Produce a deterministic order analytics event for the canonical join examples.',
    ),
)

endpoint_analytics_payments = connector_analytics_functions.endpoint(
    'Analytics Payments',
    function=Function(
        name='AnalyticsPayments',
        package=endpoint_package,
        public=False,
        description='Produce a deterministic payment analytics event for the canonical join examples.',
    ),
)

endpoint_analytics_shipments = connector_analytics_functions.endpoint(
    'Analytics Shipments',
    function=Function(
        name='AnalyticsShipments',
        package=endpoint_package,
        public=False,
        description='Produce a deterministic shipment analytics event for the canonical multi-way join example.',
    ),
)

endpoint_joined_analytics = connector_analytics_functions.endpoint(
    'Joined Analytics',
    function=Function(
        name='JoinedAnalytics',
        package=endpoint_package,
        public=False,
        description='Validate and record the result of the two-way analytics join.',
    ),
)

endpoint_high_value_analytics = connector_analytics_functions.endpoint(
    'High Value Analytics',
    function=Function(
        name='HighValueAnalytics',
        package=endpoint_package,
        public=False,
        description='Validate and record analytics results routed to the high-value Case branch.',
    ),
)

endpoint_standard_analytics = connector_analytics_functions.endpoint(
    'Standard Analytics',
    function=Function(
        name='StandardAnalytics',
        package=endpoint_package,
        public=False,
        description='Validate and record analytics results routed to the standard Case branch.',
    ),
)
