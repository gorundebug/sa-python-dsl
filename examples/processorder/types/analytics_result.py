from sa_dsl import (
    LocalType,
    ROOT_PACKAGE,
    TypeDefinitionFormat,
)

from processorder.project.processorder import project

analytics_result = project.struct_type(
    'AnalyticsResult',
    description='Output of the canonical analytics joins. Fields: Key AnalyticsKey, Total int, Kind string.',
    public_type=False,
    transfer_by_value=False,
    definition_format=TypeDefinitionFormat.NATIVE,
    module=LocalType(),
    package=ROOT_PACKAGE,
)
