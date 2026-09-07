from sa_dsl import Appearance

from processorder.services.order_service.service import default_pipeline
from processorder.types.order_state import order_state

process_order_item_error = default_pipeline.error(
    'ProcessOrderItemError',
    value_type=order_state,
    appearance=Appearance(x=-134, y=-129),
)
