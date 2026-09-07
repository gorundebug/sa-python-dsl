from sa_dsl import DataConnectorImplementation

from processorder.project.processorder import project

connector_analytics_functions = project.custom_connector(
    'Analytics Functions',
    implementation=DataConnectorImplementation.FUNCTION,
)
