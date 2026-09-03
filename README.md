# Service Architect Python DSL

`sa-python-dsl` is a typed authoring layer for Service Architect graphs. Python is
used to compose and reuse graph definitions; the resulting YAML remains the stable
input contract for the existing designer and code generator.

<p align="center">
  <a href="https://www.gorundebug.com"><strong>Open Service Architect</strong></a>
  &nbsp;&middot;&nbsp;
  <a href="https://www.gorundebug.com/help/python-dsl">Python DSL documentation</a>
  &nbsp;&middot;&nbsp;
  <a href="https://github.com/gorundebug/sa-python-dsl/tree/main/examples/processorder">Process Order example</a>
  &nbsp;&middot;&nbsp;
  <a href="https://www.youtube.com/watch?v=fNv2Jz8lHiw">Watch demo</a>
</p>

![A Service Architect graph compiled into generated service code](screen.png)

The SDK deliberately hides numeric IDs. Services, streams, connectors and endpoints
reference Python objects, while the serializer emits the symbolic YAML references
expected by `servicegen`.

The graph is the source of truth. The visual designer, canonical YAML, and typed Python
API are three interfaces over the same architecture. A validated Project can be sent to
the existing generation backend to download complete target-language projects.

## Explore the product

| Resource | Description |
| --- | --- |
| [Open Service Architect](https://www.gorundebug.com) | Design and inspect the executable service graph. |
| [Service Architect Help](https://www.gorundebug.com/help) | Product documentation for the graph, types, connectors, generation, runtimes, and lifecycle. |
| [Python DSL Help](https://www.gorundebug.com/help/python-dsl) | Python API guide, typed factories, YAML conversion, authentication, and code generation. |
| [Process Order example](examples/processorder/README.md) | Four-service Python topology with HTTP, gRPC, Kafka, Cron, and Temporal. |
| [Demo video](https://www.youtube.com/watch?v=fNv2Jz8lHiw) | Watch Service Architect model and generate the example system. |
| [ServiceGen](https://github.com/gorundebug/servicegen) | Shared validator and multi-language project generator. |
| [ServiceLib for Go](https://github.com/gorundebug/servicelib) | Go runtime used by generated services. |

## Generated runtime examples

The same product topology is generated for multiple target runtimes:

| Target | Generated project |
| --- | --- |
| Go | [gorundebug/goexample](https://github.com/gorundebug/goexample) |
| C++ userver | [gorundebug/cppexample](https://github.com/gorundebug/cppexample) |
| C++ Boost | [gorundebug/cppboostexample](https://github.com/gorundebug/cppboostexample) |
| Python | [gorundebug/pyexample](https://github.com/gorundebug/pyexample) |
| Rust | [gorundebug/rustexample](https://github.com/gorundebug/rustexample) |
| TypeScript | [gorundebug/tsexample](https://github.com/gorundebug/tsexample) |

Related runtime libraries:

- [Go ServiceLib](https://github.com/gorundebug/servicelib)
- [C++ userver ServiceLib](https://github.com/gorundebug/cppservicelib)
- [C++ Boost ServiceLib](https://github.com/gorundebug/cppboostservicelib)
- [Python ServiceLib](https://github.com/gorundebug/pyservicelib)
- [Rust ServiceLib](https://github.com/gorundebug/rustservicelib)
- [TypeScript ServiceLib](https://github.com/gorundebug/tsservicelib)

## Install for development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

## Build YAML

A source file must expose either a `project` object or a `build()` function returning
a `Project`.

```bash
sa-dsl check examples/processorder/main.py
sa-dsl build examples/processorder/main.py --output architecture.yaml
```

Use standard output when the result should be piped to another command:

```bash
sa-dsl build examples/processorder/main.py
```

## Generate project code

Put the Cognito credentials in the local, git-ignored `.env` file:

```dotenv
SERVICE_ARCHITECT_USERNAME=user@example.com
SERVICE_ARCHITECT_PASSWORD=your-password
```

Then call the same authenticated generation endpoint used by the designer. The client
performs Cognito SRP authentication, obtains a temporary ID token and sends it in
`Authorization`, matching the Amplify client:

```python
from processorder import project

archive = project.generate_code()
archive.save(archive.filename)
```

The default API URL is the designer's Service Architect API. Set
`SERVICE_ARCHITECT_API_URL` or pass `base_url` to target another environment. A successful
call returns `GeneratedProjectArchive`; HTTP, API payload, base64 and ZIP errors raise
`CodeGenerationError`, which exposes `status_code` and `details`.

Reuse a configured client when generating more than one project:

```python
from sa_dsl import ServiceArchitectClient

client = ServiceArchitectClient.from_env()
archive = client.generate_code(project)
```

The designer-compatible YAML-to-API conversion is also public:

```python
from sa_dsl import yaml_to_api_document

payload = yaml_to_api_document("architecture.yaml")
```

`examples/processorder/main.py` is the entry point for the modular Python representation of the canonical
`servicegen/cmd/codegenerator/examples/example.yaml` graph from the framework repository.

## Authoring model

```python
from sa_dsl import ConnectorType, DataConnectorImplementation, DataType, HTTPMethodType, ProgrammingLanguage, Project, StreamType

project = Project("Orders")
order = project.type("Order", DataType.CUSTOM)

service = project.service(
    "Order Service",
    programming_language=ProgrammingLanguage.GO,
    module_path="github.com/example/orders/orderservice",
)

http = project.connector(
    "Order API",
    ConnectorType.HTTP,
    go_implementation="net/http",
)
create_order = http.endpoint(
    "Create Order",
    function_name="CreateOrder",
    function_package="endpoint",
    http_method_type=HTTPMethodType.POST,
    path="/v1/orders",
)

incoming = service.stream(
    "Create Order Input",
    StreamType.INPUT,
    endpoint=create_order,
    value_type=order,
)
service.stream(
    "Validate Order",
    StreamType.PROCESS,
    source=incoming,
    function_name="ValidateOrder",
    function_package="orders",
    value_type=order,
)
```

Declare streams first, then describe long graph paths without repetitive source assignments:

```python
incoming >> validate_order >> enrich_order >> publish_order
merge_results << http_result << kafka_result << processing_error
```

`source >> consumer` sets the primary `source`. `consumer << source` appends an
additional entry to `sources`, which is used by Merge, Join and MultiJoin operators.

Python keyword arguments use `snake_case`; YAML properties are emitted as
`camelCase`. This applies to both first-class and newly introduced properties, so a
new graph property can be used before the SDK adds a dedicated convenience method:

```python
connector = project.connector(
    "Kafka",
    ConnectorType.KAFKA,
    brokers="redpanda:9092",
    connections_count=4,
    go_implementation=DataConnectorImplementation.IBM_SARAMA,
)
```

Graph keys are derived with the same lower-camel-case algorithm as the designer's
`toYaml()` and are not part of the public constructors:

```python
# YAML key is temporalWorkflowSchedule; no explicit key is needed.
temporal.endpoint("Temporal Workflow Schedule", function_name="TemporalWorkflowSchedule")
```

References to declared modules are objects rather than repeated strings:

```python
model = project.module(
    "model",
    module_path="github.com/example/orders/model",
    golang_version="1.25.4",
)
order = project.type("Order", DataType.CUSTOM, public_type=True, module=model)
```

## Cron and Temporal schedules

A Cron endpoint requires a portable five-field expression without seconds:

```python
cron.endpoint(
    "Weekday Trigger",
    function_name="WeekdayTrigger",
    schedule="0 9 * * 1-5",
    timezone="UTC",
)
```

Most Temporal endpoints are called on demand through a Temporal Sink. Both schedule
fields should be empty in that case:

```python
temporal.endpoint(
    "Process Activity",
    function_name="ProcessActivityEndpoint",
    temporal_execution_type=TemporalExecutionType.ACTIVITY,
    task_queue="activities",
    schedule="",
    schedule_id="",
)
```

A scheduled Temporal endpoint requires both the cron expression and a permanent,
user-chosen Schedule ID within the Temporal namespace:

```python
temporal.endpoint(
    "Daily Workflow",
    function_name="DailyWorkflowEndpoint",
    temporal_execution_type=TemporalExecutionType.WORKFLOW,
    task_queue="workflows",
    schedule="0 9 * * 1-5",
    schedule_id="daily-workflow-schedule",
    timezone="UTC",
)
```

The Python validator is ported from ServiceGen's `ValidateStreamApp`. It reports the same
stable `SG_*` diagnostic families for schema, semantic and capability failures across
settings, modules, types, pools, services, connectors, endpoints, streams and links.
ServiceGen remains authoritative; when its validation contract changes, this port must be
synchronized with `servicegen/internal/codegenerator/validation.go`.

## Explicit links

The ordinary data-flow relationship is expressed by a stream's `source` or `sources`.
Call `Stream.link()` on the source when the persisted edge needs explicit delivery
settings. The graph connection must already exist:

```python
incoming >> processor

incoming.link(
    processor,
    call_semantics=CallSemantics.PRIORITY_TASK_POOL,
    pool=workers,
    priority=5,
)
```

## Extension boundary

## Import YAML

Convert an existing Service Architect YAML document into a modular typed Python project:

```bash
sa-dsl import architecture.yaml --output examples/processorder
```

The same conversion is available as a Python function:

```python
from sa_dsl import yaml_to_python_project

entrypoint = yaml_to_python_project(
    "architecture.yaml",
    "examples/processorder",
)
```

The generated project separates project configuration, packages, modules, pools, types,
connectors, endpoints, services and pipelines. Pipeline-local connections are emitted in
pipeline files; persisted links and cross-pipeline connections are emitted in service files.

The importer reconstructs the declarative graph. Python-only control flow, helper functions
and abstractions from a previous Python source cannot be recovered from YAML.
