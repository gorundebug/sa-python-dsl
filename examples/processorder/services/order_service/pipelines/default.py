from sa_dsl import Appearance

from processorder.services.order_service.service import order_default_pipeline

from processorder.types.order import order_state

process_order_item_error = order_default_pipeline.error(
    "ProcessOrderItemError",
    appearance=Appearance(x=-134, y=-129),
    value_type=order_state,
)
