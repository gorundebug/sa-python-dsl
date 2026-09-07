from sa_dsl import DataConnectorImplementation

from processorder.project.processorder import project

connector_local_cron = project.cron_connector(
    'Local Cron',
    go_implementation=DataConnectorImplementation.GO_GOCRON,
    cpp_userver_implementation=DataConnectorImplementation.CPP_LIBCRON,
    cpp_boost_implementation=DataConnectorImplementation.CPP_LIBCRON,
    python_implementation=DataConnectorImplementation.PYTHON_APSCHEDULER,
    rust_implementation=DataConnectorImplementation.RUST_CRONER,
    type_script_implementation=DataConnectorImplementation.NODE_CRONER,
)
