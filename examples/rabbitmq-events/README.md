# RabbitMQ events (Go, AMQP 1.0)

> Current capability correction (2026-11-18): the TypeScript projection of this
> source-map-sink example is **unsupported**. Official JS AMQP 1.0 lacks released
> native receive-credit and pause/drain control. Validation/generation now reject
> its source, including mixed source/sink graphs. TypeScript RabbitMQ **sink-only**
> generation remains supported. Go and Python whole-graph examples are unchanged.
> Historical TypeScript native/image results below predate this restriction and
> must not be used as current whole-graph acceptance. Retained overlays/images are
> research evidence; do not bypass validation to regenerate them as supported apps.


`project.py` is the typed architecture source. One pipeline receives an Event,
normalizes its Value, publishes the processed Event through the official RabbitMQ
AMQP 1.0 SDK, and returns a correlated PublicationOutcome to the input. The source
registers its callback before emitting, accepts only a confirmed publication, and
releases failed/unknown publications for redelivery. Done does not settle.

This is an at-least-once processing example: a crash between output acceptance and
input settlement can duplicate an output. Event.ID is retained for downstream
idempotency. Rejected, unroutable, modified, not-sent, and unknown publication
outcomes remain distinguishable in Reason. Async delivery callbacks may outlive
EndRequest; the sink callback captures only its input value.

The model explicitly opts into creating two durable quorum queues, a direct
exchange, and its output binding. Existing incompatible resources fail startup.
Source credit and publisher pending-count limits are both 16. Broker addresses
are explicit and credentials are supplied only at runtime, never in the model.

The `go/` tree contains user-owned functions, native record types, serializers,
and an integration test. The harness exports the Python model using the local
DSL, validates and generates a fresh service, overlays these files, and runs the
actual generated graph with Go race detection. It does not replace SDK transport
or invoke handlers directly. Each run uses unique queue/exchange names and cleans
up only those resources. The broker is neither started nor restarted by the test.

From `servicegen/`, with the local Go 1.26.4 tool on PATH and a RabbitMQ 4.x broker:

```sh
SERVICEGEN_RABBITMQ_CANONICAL=1 \
RABBITMQ_TEST_URL=amqp://127.0.0.1:15672 \
RABBITMQ_TEST_USERNAME=adapter \
RABBITMQ_TEST_PASSWORD=adapter-test \
go test ./internal/codegenerator -run '^TestGoRabbitMQCanonicalExample$' -count=1 -timeout=120s
```

`SERVICEGEN_DSL_PYTHON` can override the default `sa-python-dsl/.venv/bin/python`.
The opt-in harness requires a broker URL; it cannot silently skip native tests.
The test verifies environment overrides, record serialization, normalized output,
case-insensitive correlation propagation, and absence of input redelivery after
stopping the generated source. It also asserts that runtime-only username/password
overrides are available even though credentials are absent from topology.

For ordinary deployment the generated connector overrides include
`EVENTS_SERVERS`, `EVENTS_USERNAME`, and `EVENTS_PASSWORD`; endpoint names produce
`RECEIVE_EVENT_QUEUE_NAME`, `PUBLISH_EVENT_QUEUE_NAME`, and
`PUBLISH_EVENT_EXCHANGE_NAME` overrides. Supply authentication through the runtime
secret configuration for your environment.

## Python generated-service acceptance

The final generated Linux ARM64 Python image also passes this acceptance on
2026-11-18. Fresh typed export, ZIP and staged sources are retained under
`/private/tmp/sa-python-rabbit-image-20261118/`. The unchanged generated Dockerfile
was built with target `runtime`, local `pyservicelib-source` named context and
the configured Docker/APT/PyPI proxies. It includes the native build prerequisites
needed by Proton; no host venv is copied into the image.

Image `sa-rabbit-python-canonical:local`, identity
`sha256:9ea07550ed944f9d0b77dbd999aad3694e4777676a57b672320a6f557bed50f9`,
Python 3.12.16. Build: `/private/tmp/sa-python-rabbit-image-build.log`;
actual graph/settlement/shutdown: `/private/tmp/sa-python-rabbit-image-acceptance.log`.
All eight broker modules also load in its final slim runtime with network disabled.

The existing runner supports image acceptance. From the generated service folder:

```sh
RABBITMQ_TEST_URL=amqp://127.0.0.1:15672 \
RABBITMQ_ACCEPTANCE_IMAGE=sa-rabbit-python-canonical:local \
  /path/to/driver-python /path/to/examples/rabbitmq-events/python/acceptance.py
```

`RABBITMQ_CONTAINER_URL` optionally supplies a different broker URL inside Docker;
otherwise localhost is mapped to Docker Desktop's `host.docker.internal`.
The driver creates/removes only its named container and UUID broker resources.
This does not prove AMD64, the combined workspace image or full Kubernetes startup.

The `python/` directory contains only user-owned implementations and a broker
acceptance runner. The generator supplies graph wiring, endpoint configuration,
makers and service lifecycle. The source explicitly accepts the delivery after
a correlated successful publication outcome; request completion alone does not
settle the delivery. Processing must tolerate redelivery.

From `servicegen`, with the local Python SDK environment installed:

```sh
SERVICEGEN_RABBITMQ_PYTHON_CANONICAL=1 \
RABBITMQ_TEST_URL=amqp://127.0.0.1:15672 \
go test ./internal/codegenerator -run '^TestPythonRabbitMQCanonicalExample$' -count=1 -v
```

Use a disposable RabbitMQ 4.x broker with the test-only account
`adapter` / `adapter-test`. The runner creates uniquely named queues and an
exchange and removes them afterward; it does not restart the broker. It checks
the transformed payload, correlated publication outcome, explicit acceptance and
successful service shutdown. Credentials are passed through runtime environment
variables, never embedded in the architecture model.

## TypeScript generated-service acceptance

The actual final Linux ARM64/Node 24.19.0 image was also freshly built from the
generated Dockerfile and current SDK sources, with no host `node_modules`.
Docker/npm/GitHub/Apache downloads used the configured local proxies. Its real
RabbitMQ graph, explicit acceptance and clean container shutdown pass, and all
eight installed broker exports plus native Pulsar construction pass under the
image's unprivileged runtime user with network disabled.

Artifacts: `/private/tmp/sa-ts-rabbit-image-20261118/`; image
`sa-rabbit-typescript-canonical:local`, identity
`sha256:03ab28720fc9486143cdbdd28f0efff4e0ecce0835d08dd8e51eb73dbde60ec9`.
Evidence: `/private/tmp/sa-ts-rabbit-image-build.log`,
`/private/tmp/sa-ts-rabbit-image-acceptance-fixed.log`, and
`/private/tmp/sa-ts-rabbit-image-native-load.log`.
The unsuffixed acceptance log records an initial runner-only error using the
Python image's absolute config path; the shared driver now uses paths relative
to each image's working directory. No runtime workaround was needed.

Use the Python broker driver above with
`RABBITMQ_ACCEPTANCE_RUNTIME=typescript` and
`RABBITMQ_ACCEPTANCE_IMAGE=sa-rabbit-typescript-canonical:local`.
This proves the generated Linux source-build/install/runtime path, separately
from the SDK tarball-consumption check; it does not prove every target platform.

`typescript/` supplies user-owned types and handlers for the same Python model.
Run `SERVICEGEN_RABBITMQ_TYPESCRIPT_CANONICAL=1` with the same broker environment
and `go test ./internal/codegenerator -run '^TestTypeScriptRabbitMQCanonicalExample$' -count=1 -v`.
The gate compiles the regenerated service against the local TypeScript SDK, then
uses the shared Python AMQP test driver to verify cross-client payloads,
publication-result correlation, explicit settlement and clean shutdown.
The source accepts only after a successful publication outcome. Settlement is
a native local request, not a broker-confirmed exactly-once guarantee.

## Generated Python/TypeScript interoperability

`servicegen/scripts/check_rabbitmq_generated_interop.py` runs two freshly
generated services in both language orders. It creates UUID-owned queues and
exchanges, checks three Event JSON records (including UTF-8 and embedded NUL),
requires explicit acceptance from both input stages after publication, and
requires clean service shutdown. Only its own broker resources are removed.
Use `--help` for the artifact roots and runtime executable arguments; credentials
are supplied through `RABBITMQ_TEST_USERNAME` / `RABBITMQ_TEST_PASSWORD`.

The 2026-11-18 run passed both directions on host Python 3.14.6 / Node 24.16.0
with RabbitMQ 4.3. Evidence: `/private/tmp/sa-rabbit-generated-interop.log` and
`/private/tmp/sa-rabbit-generated-interop.json`. Fresh baseline generation evidence
is `/private/tmp/sa-rabbit-pulsar-interop-generation.log`. This covers the canonical
Event contract, not arbitrary binary/header interoperability or exactly-once
delivery.
