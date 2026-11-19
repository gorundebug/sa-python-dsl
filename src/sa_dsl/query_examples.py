"""Executable architecture examples; native business handlers are user-owned."""

QUERY_EXAMPLES = {
    "query-postgresql": {
        "purpose": "Read PostgreSQL rows through a callable Query pipeline.",
        "language": "GoLang",
        "semanticsResource": "servicegen://semantics/query",
        "python": '''from sa_dsl import Project, Golang, Function, ServiceModule

project = Project("PostgreSQL query example")
text = project.string_type("Text")
# Connection string comes from runtime environment/secrets, not this model.
database = project.postgresql_bun_connector("Database", connections_count=10)
rows = database.endpoint(
    "List matching records", function=Function("ListMatchingRecords"),
    query_operation="Rows", fetch_size=256,
)
service = project.service("Reader", language=Golang(),
                          module=ServiceModule("example.com/reader"))
flow = service.pipeline("Read records")
request = flow.substream("Read records request", value_type=text)
result = flow.query("Read matching records", endpoint=rows,
                    value_type=text, source=request)
result >> request
''',
        "implementation": [
            "Configure a shared Bun pool through the service infrastructure maker when customization is needed; endpoints reuse it and managed shutdown closes it.",
            "Implement the endpoint's query builder using Bun and bound parameters; the SQL can be built in code. Use sql_file only when a user-owned SQL file is desired.",
            "Map each native row to Text and emit it through out. Rows may produce no values.",
            "EndRequest receives out and the error collector. Emit a completion value only if the application contract needs it; this example introduces no completion port.",
            "The SubStream entry is explicitly callable from a business function. It is not an autonomous startup pipeline.",
            "This model does not define a reply for empty results or failures. When calling the SubStream, supply a deadline or implement an explicit application reply from EndRequest/error handling; an Error stream alone does not complete the caller.",
        ],
        "acceptance": "Model validation/export only. Generated native database execution must be checked separately against the selected runtime and generator.",
    },
    "query-s3": {
        "purpose": "Load an S3 object through a request-driven Query endpoint.",
        "language": "GoLang",
        "semanticsResource": "servicegen://semantics/query",
        "python": '''from sa_dsl import Project, Golang, Function, ServiceModule

project = Project("S3 query example")
text = project.string_type("Text")
objects = project.s3_aws_connector("Objects", region="eu-west-1")
read = objects.endpoint(
    "Read object", function=Function("ReadObject"),
    query_operation="GetObject", bucket="example-snapshots",
)
service = project.service("ObjectReader", language=Golang(),
                          module=ServiceModule("example.com/objectreader"))
flow = service.pipeline("Load object")
request = flow.substream("Object key", value_type=text)
result = flow.query("Load object contents", endpoint=read,
                    value_type=text, source=request)
result >> request
''',
        "implementation": [
            "Configure the shared S3 client through the generated service infrastructure maker, not main or a per-request handler. Keep native automatic retries disabled.",
            "Build the native GetObject request from the incoming object key; credentials belong to runtime configuration.",
            "Decode or stream the body according to the application's result contract. Do not collect an unbounded object into memory implicitly.",
            "Close the response body before EndRequest, including cancellation and decoding failures. Pass the supplied context throughout.",
            "The callable SubStream needs an explicit application reply or a caller deadline when decoding emits no values or the operation fails. Routing an error alone does not return a SubStream result.",
            "ListObjects, HeadObject, PutObject and DeleteObject use their own endpoint operation and native mapping contract; do not model them as Get/Put stream subclasses.",
        ],
        "acceptance": "Authoring example, not a claim of completed S3 adapter implementation. Verify selected backend capabilities and native execution before use.",
    },
}
