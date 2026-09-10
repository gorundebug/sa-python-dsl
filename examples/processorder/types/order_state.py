from sa_dsl import (
    LocalType,
    ROOT_PACKAGE,
    TypeDefinitionFormat,
)

from processorder.project.processorder import project

order_state = project.struct_type(
    'OrderState',
    description='Processing result of an order. Fields: OrderID string, Status string (CONFIRMED — all items reserved; PARTIALLY_CONFIRMED — some items out of stock; TIMED_OUT — order timed out), ConfirmedItems []OrderItemResult, TotalAmount float64, ProcessedAt time.Time.',
    public_type=False,
    transfer_by_value=False,
    definition_format=TypeDefinitionFormat.NATIVE,
    module=LocalType(),
    package=ROOT_PACKAGE,
)
