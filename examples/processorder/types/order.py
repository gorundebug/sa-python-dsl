from processorder.modules.model import model

from processorder.project.processorder import project

from sa_dsl import (
    LocalType,
    ROOT_PACKAGE,
    TypeDefinitionFormat,
)

order = project.struct_type(
    "Order",
    description=(
        "E-commerce order submitted by a customer. Fields: ID string, CustomerID string, Items "
        "[]OrderItem, CreatedAt time.Time."
    ),
    public_type=False,
    module=LocalType(),
    package=ROOT_PACKAGE,
    transfer_by_value=False,
    definition_format=TypeDefinitionFormat.NATIVE,
)

order_state = project.struct_type(
    "OrderState",
    description=(
        "Processing result of an order. Fields: OrderID string, Status string (CONFIRMED — all "
        "items reserved; PARTIALLY_CONFIRMED — some items out of stock; TIMED_OUT — order timed "
        "out), ConfirmedItems []OrderItemResult, TotalAmount float64, ProcessedAt time.Time."
    ),
    public_type=False,
    module=LocalType(),
    package=ROOT_PACKAGE,
    transfer_by_value=False,
    definition_format=TypeDefinitionFormat.NATIVE,
)

order_item = project.struct_type(
    "OrderItem",
    description=(
        "A single line item within an order. Fields: OrderID string, ItemID string, SKU string, "
        "Quantity int."
    ),
    public_type=False,
    module=model,
    package=ROOT_PACKAGE,
    transfer_by_value=False,
    definition_format=TypeDefinitionFormat.NATIVE,
)

order_item_result = project.struct_type(
    "OrderItemResult",
    description=(
        "Inventory reservation result for a single order item. Fields: OrderID string, ItemID "
        "string, SKU string, RequestedQty int, AvailableQty int, Reserved bool, Status string "
        "(CONFIRMED / OUT_OF_STOCK / PROCESSING_ERROR), UnitPrice float64, Error string."
    ),
    public_type=False,
    module=model,
    package=ROOT_PACKAGE,
    transfer_by_value=False,
    definition_format=TypeDefinitionFormat.NATIVE,
)

order_processed = project.struct_type(
    "OrderProcessed",
    description=(
        "Final order-processing event. Fields: OrderID string, Status string, ProcessedAt "
        "time.Time, TotalItems int, ConfirmedItems int, FailureReason string."
    ),
    public_type=False,
    module=model,
    package=ROOT_PACKAGE,
    transfer_by_value=False,
    definition_format=TypeDefinitionFormat.NATIVE,
)
