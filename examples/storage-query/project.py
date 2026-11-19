"""Callable storage stages; each operation owns its pipeline and error path."""
from sa_dsl import (
    Project, Function, ServiceModule, TypeDefinitionFormat,
    Golang, TypeScript, Python, Rust, CppUserver, CppCoro,
)

TARGETS = {
    "go": (Golang, "postgresql_bun_connector"),
    "typescript": (TypeScript, "postgresql_kysely_connector"),
    "python": (Python, "postgresql_sqlalchemy_connector"),
    "rust": (Rust, "postgresql_sqlx_connector"),
    "cpp-userver": (CppUserver, "postgresql_userver_connector"),
    "cpp-coro": (CppCoro, "postgresql_libpq_connector"),
}


def build_project(target="go"):
    language, postgres_factory = TARGETS[target]
    project = Project("StorageQuery", repo_path="example.com/storage-query")
    request = project.struct_type("StorageRequest", definition_format=TypeDefinitionFormat.NATIVE,
        description="RequestID string; Key string; Value bytes. Key is a bound SQL value or object key, never SQL syntax.")
    result = project.struct_type("StorageResult", definition_format=TypeDefinitionFormat.NATIVE,
        description="RequestID string; Kind string (record, command, object, page, completed); Value bytes. Completion is emitted explicitly by EndRequest.")
    failure = project.error_type("StorageFailure")
    service = project.service("StorageWorker", language=Golang(version="1.26.4") if target == "go" else language(),
        module=ServiceModule("example.com/storage-query/storageworker"))
    timeouts = {"operation_timeout_ms": 2000}
    if target != "cpp-userver":
        timeouts["connect_timeout_ms"] = 1000
    database = getattr(project, postgres_factory)("Database", connections_count=4, **timeouts)
    objects = (project.s3_userver_connector if target == "cpp-userver" else project.s3_aws_connector)(
        "Objects", region="eu-west-1")
    operations = [(database, "Rows"), (database, "Execute"), (database, "Returning")]
    operations += [(objects, op) for op in ("GetObject", "HeadObject", "ListObjects", "PutObject", "DeleteObject")]
    for connector, operation in operations:
        endpoint = connector.endpoint(operation, query_operation="Rows" if operation == "Returning" else operation,
            function=Function(operation, description=(
                ("Insert the bound key/value and return the stored value using PostgreSQL Rows (INSERT RETURNING). "
                 if operation == "Returning" else f"Build and execute {operation} using the connector's native request contract. ") +
                "Use the supplied context and maker-owned shared client. Map native results to StorageResult, "
                "preserving RequestID. EndRequest emits Kind=completed only on success; failures go to the "
                "error collector. Never retry unknown writes or partial output. No schema/bucket creation.")),
            **({"bucket": "query-example"} if connector is objects else {"fetch_size": 64}))
        flow = service.pipeline(operation)
        entry = flow.substream(operation + " request", value_type=request)
        query = flow.query(operation + " storage operation", endpoint=endpoint, source=entry, value_type=result)
        query >> entry
        flow.error(operation + " failure", source=query, value_type=failure)
    return project


project = build_project()
