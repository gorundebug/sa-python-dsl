from sa_dsl import TypeDefinitionFormat

from processorder.project.processorder import project

inventory_failure = project.struct_type(
    'InventoryFailure',
    description='Inventory shortage data passed to GetInventoryItemError. Preserves the original order item and available quantity without throwing an exception.',
    public_type=False,
    definition_format=TypeDefinitionFormat.NATIVE,
)
