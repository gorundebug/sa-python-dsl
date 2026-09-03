from processorder.project.processorder import project

temporal = project.temporal_connector(
    "Temporal",
    address="temporal:7233",
    namespace="default",
    identity="example-automation",
    api_key="",
    tls_enabled=False,
    worker_stop_timeout=5000,
)
