from sa_dsl import (
    ROOT_PACKAGE,
    TypeDefinitionFormat,
)

from processorder.project.processorder import project

analytics_event = project.struct_type(
    'AnalyticsEvent',
    description='Input for the canonical analytics joins. Fields: Key AnalyticsKey, Value int, Kind string.',
    public_type=False,
    transfer_by_value=False,
    definition_format=TypeDefinitionFormat.NATIVE,
    package=ROOT_PACKAGE,
)
