# Process Order

`processorder` is the canonical product-level example for the Service Architect Python
DSL. It describes a small distributed order-processing system as typed Python objects and
produces the same topology as the canonical ServiceGen YAML example.

The example is intentionally modular. It demonstrates how a real project can separate
services, pipelines, connectors, endpoints, domain types, modules, packages, and task
pools while still exposing one `project` object.

## System overview

The topology contains four services:

| Service | Responsibility |
| --- | --- |
| Order Service | Accept an order, split it into item-processing work, collect item results, and publish the completed order state. |
| Inventory Service | Process inventory-item requests and combine successful results with the error path returned to the caller. |
| Analytics Service | Consume completed-order events and maintain the analytics processing cycle. |
| Automation Service | Demonstrate local Cron triggers and on-demand or scheduled Temporal Activities and Workflows. |

At a high level, the business path is:

```text
Order API
    |
    v
Order Service ---- item request ----> Inventory Service
    |
    +---- completed event ----------> Analytics Service

Cron / Temporal schedules ----------> Automation Service
Temporal Activity and Workflow calls <-> Automation Service
```

## Order Service

The Order Service owns the main order orchestration flow. It receives a process-order
request, creates the branches needed for deadline handling and item processing, merges
the resulting order states, and publishes the completed result.

Its streams demonstrate:

- An inbound API boundary for a process-order request.
- A `Split` that starts independent branches from the same order.
- A soft-deadline branch that can produce an order state without blocking item work.
- Item fan-out through the Inventory Service endpoint.
- Mapping inventory results and inventory failures into the common order-state type.
- A `Merge` that accepts normal, deadline, and error results.
- Publication of an order-processed event for downstream consumers.
- Explicit `ParallelCall` and priority task-pool links where execution differs from the
  service default.

The service has two pipelines:

- `order` contains the normal order-processing graph.
- `default` contains the item-processing error stream used by the main pipeline.

Cross-pipeline connections live in
[`services/order_service/service.py`](services/order_service/service.py). Internal graph
connections and explicit link settings live beside the stream declarations in
[`services/order_service/pipelines/order.py`](services/order_service/pipelines/order.py).

Simplified flow:

```text
Process Order
    |
    v
Split Pipeline
    +----> Soft Deadline ----> Order State --+
    |                                        |
    +----> Process Items ----> Inventory ----+----> Merge Results
                               failure ------+            |
                                                         v
                                                   Publish Processed
```

## Inventory Service

The Inventory Service represents the remote item-processing boundary used by the Order
Service. It consumes an inventory request, executes the inventory lookup/update function,
and merges its successful and failed outcomes into the endpoint response flow.

Its pipeline demonstrates:

- An endpoint-backed inbound stream.
- A business processing function for an inventory item.
- A dedicated error stream.
- A multi-source merge for success and failure results.
- A priority task pool for inventory work.
- A persisted execution link whose semantics differ from the service default.

The declarations are in
[`services/inventory_service/pipelines/inventory_item.py`](services/inventory_service/pipelines/inventory_item.py).

Simplified flow:

```text
Inventory Request
    |
    v
Process Inventory Item
    +----> Item Data ----+
    +----> Item Error ---+----> Merge Inventory Result
```

## Analytics Service

The Analytics Service consumes the order-processed event published by the Order Service.
It demonstrates a small event-driven feedback cycle rather than another request/response
API.

Its pipeline demonstrates:

- A Kafka-backed Input for completed-order events.
- A counting or aggregation function over the event stream.
- A cycle between the consumer boundary and the processing stream.

The declarations are in
[`services/analytics_service/pipelines/analytics.py`](services/analytics_service/pipelines/analytics.py).

Simplified flow:

```text
Order Processed Topic
    |
    v
Consume Order Processed <----> Count Order Processed
```

## Automation Service

The Automation Service is a focused scheduling and durable-execution example. It keeps
local Cron, on-demand Temporal calls, scheduled Temporal Activities, and scheduled
Temporal Workflows in one service so their graph contracts can be compared directly.

Its pipeline demonstrates:

- A local Cron Input that produces automation jobs.
- A Split that routes jobs to Activity and Workflow submissions.
- Temporal Sink/Input pairs for on-demand request and result processing.
- A sequential Workflow that calls Activity A and then Activity B.
- A fan-out Workflow that calls multiple Activities and observes independent results.
- Activity heartbeat-aware processing.
- Workflow-compatible delays backed by durable Temporal timers.
- Scheduled Activity and Workflow endpoints with stable schedule IDs.
- Explicit task-pool and priority task-pool links for selected durable calls.

The declarations are in
[`services/automation_service/pipelines/automation.py`](services/automation_service/pipelines/automation.py).

Simplified on-demand flow:

```text
Local Cron
    |
    v
Split On-Demand Jobs
    +----> Submit Activity ----> Activity Worker ----> Observe Result
    +----> Submit Workflow ----> Workflow Worker ----> Observe Result
    +----> Fan-Out Workflow ---> Activity A ---+---> Activity B
                                               +---> Activity C
```

Scheduled endpoints form their own durable loops:

```text
Temporal Activity Schedule -> Pause -> Process Scheduled Activity
           ^                                      |
           +--------------------------------------+

Temporal Workflow Schedule -> Durable Pause -> Process Scheduled Workflow
           ^                                         |
           +-----------------------------------------+
```

## Connectors and endpoints

Connector objects contain transport-level settings. Endpoint objects contain the
operation, topic, or schedule used by Input and Sink streams.

| Connector module | Purpose |
| --- | --- |
| `connectors/order_service_api.py` | Public Order Service HTTP/gRPC API configuration. |
| `connectors/inventory_service_api.py` | Inventory Service call boundary. |
| `connectors/order_events.py` | Kafka transport for completed-order events. |
| `connectors/local_cron.py` | Local Cron scheduler implementations. |
| `connectors/temporal.py` | Temporal server, namespace, worker, and TLS configuration. |

The corresponding endpoint declarations are kept under `endpoints/`. Streams always
reference the resulting Endpoint objects, never connector or endpoint names written as
free-form strings.

## Types and ownership

Shared contracts are declared under `types/` and use objects from `modules/` and
`packages/` to describe generated ownership.

- `types/common.py` contains reusable base contracts.
- `types/order.py` contains order, item, and order-state contracts.
- `types/automation.py` contains Temporal/Cron automation messages.
- `modules/model.py` owns shared public model types.
- API modules own contracts generated for the service boundaries.
- Package objects are reused by Functions instead of repeating package strings.

`LOCAL_MODULE` explicitly means that a callback is implemented in its local service.
`None` means that the optional field is omitted. This distinction is preserved in YAML,
while explicit-null fields are omitted from the JSON request sent to the generation API.

## Task pools and links

Pools are declared once under `pools/` and passed as objects to explicit links:

```python
split_activity_a_result >> call_fan_out_activity_c

split_activity_a_result.link(
    call_fan_out_activity_c,
    call_semantics=CallSemantics.PRIORITY_TASK_POOL,
    pool=default_pool,
    priority=7,
)
```

The graph edge must exist before `link()` is called. If link semantics equal the Service
default, no explicit Link is needed and the YAML importer does not generate one.

## Directory structure

```text
processorder/
  main.py                         Compatibility entry point
  project/                        Root Project settings
  modules/                        Shared generated module owners
  packages/                       Reusable target package objects
  pools/                          Task-pool declarations
  types/                          Shared and service data contracts
  connectors/                     Connector configuration
  endpoints/                      Connector-specific endpoints
  services/
    order_service/
      service.py                  Service, Pipelines, cross-pipeline wiring
      pipelines/                  Internal stream declarations and links
    inventory_service/
    analytics_service/
    automation_service/
```

## Build and validate YAML

From the repository root:

```bash
. .venv/bin/activate

sa-dsl check examples/processorder/main.py
sa-dsl build examples/processorder/main.py --output architecture.yaml
```

The same operation is available from Python:

```python
from processorder import project

diagnostics = project.validate()
if diagnostics:
    raise RuntimeError(diagnostics)

yaml_source = project.to_yaml()
```

## Generate the target projects

Create a local `.env` from the repository template and provide the Service Architect
Cognito credentials:

```dotenv
SERVICE_ARCHITECT_USERNAME=user@example.com
SERVICE_ARCHITECT_PASSWORD=your-password
```

Then request the same generated ZIP that the designer's **Code** button downloads:

```python
from pathlib import Path
from processorder import project

archive = project.generate_code()
archive.save(Path("dist") / archive.filename)
```

The call performs Cognito SRP authentication, converts the symbolic topology to the
designer API JSON model, downloads the base64 response, and verifies that the result is a
valid ZIP before returning it.

## Round-trip guarantee

The integration test converts the canonical ServiceGen YAML into a temporary Python
package, imports the generated package, calls `to_yaml()`, and compares the normalized
result with the original topology:

```bash
python -m unittest tests.test_yaml_round_trip -v
```

This protects the example from silently diverging from the canonical product DSL as the
Python API evolves.
