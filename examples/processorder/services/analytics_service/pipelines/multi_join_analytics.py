from sa_dsl import (
    Appearance,
    Function,
    JoinStorageType,
    LOCAL_MODULE,
)

from processorder.endpoints.analytics_functions import endpoint_high_value_analytics
from processorder.endpoints.analytics_functions import endpoint_standard_analytics
from processorder.packages.multijoinanalytics import multijoinanalytics_package
from processorder.services.analytics_service.service import multi_join_analytics_pipeline
from processorder.types.analytics_event import analytics_event
from processorder.types.analytics_key import analytics_key
from processorder.types.analytics_result import analytics_result

key_orders_for_multi_join = multi_join_analytics_pipeline.key_by(
    'Key Orders For Multi Join',
    function=Function(
        name='KeyOrdersForMultiJoin',
        package=multijoinanalytics_package,
        description='Key the order analytics event for the multi-way join.',
        module=LOCAL_MODULE,
    ),
    value_type=analytics_event,
    key_type=analytics_key,
    appearance=Appearance(x=-1467, y=-1583),
)

key_payments_for_multi_join = multi_join_analytics_pipeline.key_by(
    'Key Payments For Multi Join',
    function=Function(
        name='KeyPaymentsForMultiJoin',
        package=multijoinanalytics_package,
        description='Key the payment analytics event for the multi-way join.',
        module=LOCAL_MODULE,
    ),
    value_type=analytics_event,
    key_type=analytics_key,
    appearance=Appearance(x=-766, y=-1038),
)

key_shipments_for_multi_join = multi_join_analytics_pipeline.key_by(
    'Key Shipments For Multi Join',
    function=Function(
        name='KeyShipmentsForMultiJoin',
        package=multijoinanalytics_package,
        description='Key the shipment analytics event for the multi-way join.',
        module=LOCAL_MODULE,
    ),
    value_type=analytics_event,
    key_type=analytics_key,
    appearance=Appearance(x=-451, y=-1340),
)

multi_join_analytics_events = multi_join_analytics_pipeline.multi_join(
    'Multi Join Analytics Events',
    join_storage=JoinStorageType.HASH_MAP,
    ttl=60000,
    renew_ttl=True,
    function=Function(
        name='MultiJoinAnalyticsEvents',
        package=multijoinanalytics_package,
        description='Combine matching order, payment, and shipment analytics events.',
        module=LOCAL_MODULE,
    ),
    value_type=analytics_result,
    appearance=Appearance(x=-465, y=-1578),
)

route_analytics_result = multi_join_analytics_pipeline.case(
    'Route Analytics Result',
    function=Function(
        name='RouteAnalyticsResult',
        package=multijoinanalytics_package,
        description='Route high-value analytics results to the first branch and all others to the second branch.',
        module=LOCAL_MODULE,
    ),
    appearance=Appearance(x=-119, y=-1606),
)

high_value_analytics = multi_join_analytics_pipeline.when(
    'High Value Analytics',
    value_type=analytics_result,
    appearance=Appearance(x=221, y=-1646),
)

standard_analytics = multi_join_analytics_pipeline.when(
    'Standard Analytics',
    value_type=analytics_result,
    appearance=Appearance(x=-116, y=-1263),
)

write_high_value_analytics = multi_join_analytics_pipeline.sink(
    'Write High Value Analytics',
    endpoint=endpoint_high_value_analytics,
    value_type=analytics_result,
    appearance=Appearance(x=533, y=-1703),
)

write_standard_analytics = multi_join_analytics_pipeline.sink(
    'Write Standard Analytics',
    endpoint=endpoint_standard_analytics,
    value_type=analytics_result,
    appearance=Appearance(x=257, y=-1274),
)

key_orders_for_multi_join >> multi_join_analytics_events

multi_join_analytics_events << key_payments_for_multi_join

multi_join_analytics_events << key_shipments_for_multi_join

multi_join_analytics_events >> route_analytics_result

route_analytics_result >> high_value_analytics

route_analytics_result >> standard_analytics

high_value_analytics >> write_high_value_analytics

standard_analytics >> write_standard_analytics
