from sa_dsl import (
    ROOT_PACKAGE,
    TypeDefinitionFormat,
)

from processorder.modules.model import model
from processorder.project.processorder import project

order_processed = project.struct_type(
    'OrderProcessed',
    description='Final order-processing event. Fields: OrderID string, Status string, ProcessedAt time.Time, TotalItems int, ConfirmedItems int, FailureReason string.',
    public_type=False,
    transfer_by_value=False,
    definition_format=TypeDefinitionFormat.NATIVE,
    module=model,
    package=ROOT_PACKAGE,
)
