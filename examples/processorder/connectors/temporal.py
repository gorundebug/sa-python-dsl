from sa_dsl import DataConnectorImplementation

from processorder.project.processorder import project

connector_temporal = project.temporal_connector(
    'Temporal',
    go_implementation=DataConnectorImplementation.TEMPORAL_GO,
    python_implementation=DataConnectorImplementation.TEMPORAL_PYTHON,
    type_script_implementation=DataConnectorImplementation.TEMPORAL_TYPESCRIPT,
    address='temporal:7233',
    namespace='default',
    identity='example-automation',
    api_key='',
    tls_enabled=False,
    worker_stop_timeout=5000,
)
