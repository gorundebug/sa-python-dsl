from sa_dsl import (
    ROOT_PACKAGE,
    TypeDefinitionFormat,
)

from processorder.modules.model import model
from processorder.project.processorder import project

order_item = project.struct_type(
    'OrderItem',
    description='A single line item within an order. Fields: OrderID string, ItemID string, SKU string, Quantity int.',
    public_type=False,
    transfer_by_value=False,
    definition_format=TypeDefinitionFormat.NATIVE,
    module=model,
    package=ROOT_PACKAGE,
)
