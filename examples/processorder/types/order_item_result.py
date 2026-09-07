from sa_dsl import (
    ROOT_PACKAGE,
    TypeDefinitionFormat,
)

from processorder.modules.model import model
from processorder.project.processorder import project

order_item_result = project.struct_type(
    'OrderItemResult',
    description='Inventory reservation result for a single order item. Fields: OrderID string, ItemID string, SKU string, RequestedQty int, AvailableQty int, Reserved bool, Status string (CONFIRMED / OUT_OF_STOCK / PROCESSING_ERROR), UnitPrice float64, Error string.',
    public_type=False,
    transfer_by_value=False,
    definition_format=TypeDefinitionFormat.NATIVE,
    module=model,
    package=ROOT_PACKAGE,
)
