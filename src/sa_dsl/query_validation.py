"""Storage Query contracts; no implicit Source/Sink compatibility."""

POSTGRES_TARGETS = {
    "PostgreSQLBun": "GoLang", "PostgreSQLKysely": "TypeScript",
    "PostgreSQLSQLAlchemy": "Python", "PostgreSQLSQLx": "Rust",
    "PostgreSQLUserver": "CppUserver", "PostgreSQLLibpq": "CppCoro",
}
S3_TARGETS = {
    "S3AWS": {"GoLang", "Python", "TypeScript", "Rust", "CppCoro"},
    "S3Userver": {"CppUserver"},
}


def validate_query_bindings(stream):
    endpoint = stream.endpoint
    if endpoint is None:
        return []
    connector = endpoint.connector
    storage = connector.type in POSTGRES_TARGETS or connector.type in S3_TARGETS
    if stream.type != "Query":
        return [("endpoint", "Storage endpoints require Query, not Input or Sink")] if storage else []
    if not storage:
        return [("endpoint", "Query requires a PostgreSQL or S3 query connector")]
    errors = []
    language = stream.service.programming_language
    targets = {POSTGRES_TARGETS[connector.type]} if connector.type in POSTGRES_TARGETS else S3_TARGETS[connector.type]
    if language not in targets:
        errors.append(("endpoint", f"{connector.type} does not support {language}"))
    operations = {"Rows", "Execute"} if connector.type in POSTGRES_TARGETS else {"GetObject", "HeadObject", "ListObjects", "PutObject", "DeleteObject"}
    operation = endpoint.properties.get("queryOperation")
    if not isinstance(operation, str) or operation not in operations:
        errors.append(("endpoint", f"queryOperation must be one of {sorted(operations)}"))
    size = endpoint.properties.get("fetchSize", 256)
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        errors.append(("endpoint", "fetchSize must be a positive integer"))
    elif connector.type == "PostgreSQLUserver" and size > 4294967295:
        errors.append(("endpoint", "PostgreSQLUserver fetchSize must fit uint32 (maximum 4294967295)"))
    if not stream.properties.get("valueType"):
        errors.append(("valueType", "Query requires an explicit result type"))
    return errors


def validate_query_connector(connector):
    if connector.type in S3_TARGETS:
        style = connector.properties.get("forcePathStyle")
        if style is not None and not isinstance(style, bool):
            return [("forcePathStyle", "forcePathStyle must be a boolean")]
        if connector.type == "S3Userver" and style is True:
            return [("forcePathStyle", "S3Userver supports virtual-host addressing only; forcePathStyle must be false")]
        return []
    if connector.type not in POSTGRES_TARGETS:
        return []
    errors = []
    for field, minimum in (("connectionsCount", 1), ("connectTimeoutMs", 0), ("operationTimeoutMs", 0)):
        value = connector.properties.get(field)
        if field == "connectTimeoutMs" and connector.type == "PostgreSQLUserver" and value is not None:
            errors.append((field, "connectTimeoutMs must be omitted: PostgreSQLUserver has no independent native connection timeout"))
            continue
        if field == "connectTimeoutMs" and connector.type == "PostgreSQLSQLx":
            minimum = 1
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= 2147483647:
            errors.append((field, f"{field} must be an integer in {minimum}..2147483647"))
    return errors
