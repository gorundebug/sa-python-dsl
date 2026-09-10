from sa_dsl import (
    LocalType,
    ROOT_PACKAGE,
    TypeDefinitionFormat,
)

from processorder.project.processorder import project

order = project.struct_type(
    'Order',
    description='E-commerce order submitted by a customer. Fields: ID string, CustomerID string, Items []OrderItem, CreatedAt time.Time.',
    public_type=False,
    transfer_by_value=False,
    definition_format=TypeDefinitionFormat.NATIVE,
    module=LocalType(),
    package=ROOT_PACKAGE,
)
