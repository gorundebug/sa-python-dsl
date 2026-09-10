from sa_dsl import (
    Appearance,
    Function,
    JoinStorageType,
    JoinType,
    LOCAL_MODULE,
)

from processorder.endpoints.analytics_functions import endpoint_joined_analytics
from processorder.packages.joinanalytics import joinanalytics_package
from processorder.services.analytics_service.service import join_analytics_pipeline
from processorder.types.analytics_event import analytics_event
from processorder.types.analytics_key import analytics_key
from processorder.types.analytics_result import analytics_result

key_orders_for_join = join_analytics_pipeline.key_by(
    'Key Orders For Join',
    function=Function(
        name='KeyOrdersForJoin',
        package=joinanalytics_package,
        description='Key the order analytics event by correlation key.',
        module=LOCAL_MODULE,
    ),
    value_type=analytics_event,
    key_type=analytics_key,
    appearance=Appearance(x=-1258, y=-1007),
)

key_payments_for_join = join_analytics_pipeline.key_by(
    'Key Payments For Join',
    function=Function(
        name='KeyPaymentsForJoin',
        package=joinanalytics_package,
        description='Key the payment analytics event by correlation key.',
        module=LOCAL_MODULE,
    ),
    value_type=analytics_event,
    key_type=analytics_key,
    appearance=Appearance(x=-1377, y=-723),
)

join_order_payment_analytics = join_analytics_pipeline.join(
    'Join Order Payment Analytics',
    join_type=JoinType.INNER,
    join_storage=JoinStorageType.HASH_MAP,
    ttl=60000,
    renew_ttl=True,
    function=Function(
        name='JoinOrderPaymentAnalytics',
        package=joinanalytics_package,
        description='Join matching order and payment analytics events and emit their combined total.',
        module=LOCAL_MODULE,
    ),
    value_type=analytics_result,
    appearance=Appearance(x=-637, y=-1050),
)

write_joined_analytics = join_analytics_pipeline.sink(
    'Write Joined Analytics',
    endpoint=endpoint_joined_analytics,
    value_type=analytics_result,
    appearance=Appearance(x=-231, y=-1079),
)

key_orders_for_join >> join_order_payment_analytics

join_order_payment_analytics << key_payments_for_join

join_order_payment_analytics >> write_joined_analytics
