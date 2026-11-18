# Pulsar events

## Generated Python/TypeScript interoperability

`servicegen/scripts/check_pulsar_generated_interop.py` runs the generated service
in both language orders. It creates an isolated namespace with implicit topic
and subscription creation disabled, then checks the endpoints' explicit creation,
three JSON records with UTF-8 and embedded NUL, message IDs in publication
outcomes, partition keys, zero input backlog/unacked records and clean shutdown.
Only its own namespace/topics are removed. Use `--help` for artifact roots,
runtime executables and local broker/admin URLs.

Both directions passed on 2026-11-18 with host Python 3.14.6 and Node 24.16.0:
`/private/tmp/sa-pulsar-generated-interop.log` and `.json`. Fresh canonical
generation baselines are recorded in
`/private/tmp/sa-rabbit-pulsar-interop-generation.log`. This is canonical Event
interoperability, not arbitrary-header/binary parity, a performance measurement
or an exactly-once guarantee.

## Model

The editable Python model contains one pipeline: native topic input, pure event
normalization and native topic publication. Publication results return to the
input, which individually acknowledges only successful correlated results with
a native MessageID. Local Done does not settle input. Duplicates remain possible;
this example makes no exactly-once guarantee. JSON is this example's explicit
business payload format, not an SDK transport envelope.

Topic and subscription creation are explicitly enabled. The namespace must exist
with automatic topic/subscription creation disabled. The endpoint does not alter
namespace policy, expand partitions, delete topics or reset existing cursors.
Credentials belong to runtime configuration.

## Generated Go acceptance

`go/` contains user-owned handlers, records, serializers and the integration test.
The generator test validates/exports `project.py`, generates in a temporary
workspace, overlays that code and runs the generated graph with the race detector.
From `servicegen` with Go 1.26.4 and the local SDK checkout:

```sh
SERVICEGEN_PULSAR_CANONICAL=1 \
PULSAR_TEST_ADMIN_URL=http://127.0.0.1:18080 \
PULSAR_TEST_URL=pulsar://127.0.0.1:16650 \
go test ./internal/codegenerator -run '^TestGoPulsarCanonicalExample$' -count=1 -v
```

Use an isolated Pulsar instance with the public tenant. Only the test harness
creates a uniquely named namespace and sets its policies. Application startup
creates the modeled topics and subscription. Cleanup deletes only those resources.
The check verifies three normalized payloads and keys, correlated native publish
results, broker-observed source ACK, environment overrides and record codecs.
TLS/authentication, failure recovery, throughput and other SDKs have separate gates.

## Generated Python acceptance

The same Python model is projected to a Python service. `python/` contains only
user-owned records/handlers and the process-level broker check; generated startup,
makers, configuration and graph wiring remain generated.

```sh
SERVICEGEN_PULSAR_PYTHON_CANONICAL=1 \
PULSAR_TEST_ADMIN_URL=http://127.0.0.1:18080 \
PULSAR_TEST_URL=pulsar://127.0.0.1:16650 \
go test ./internal/codegenerator -run '^TestPythonPulsarCanonicalExample$' -count=1 -v
```

The local `pyservicelib/.venv` must contain the official Pulsar 3.13.0 dependency.
The harness verifies native output IDs against the correlated graph results,
source ACK at the broker, environment settings and clean SIGTERM shutdown. It
creates and removes only its own namespace, topics and subscriptions. The test
harness uses synchronous native IO outside the service process; the SDK inside
the service uses the official asyncio API.

## Generated TypeScript acceptance

`typescript/` contains user-owned record and handler implementations plus the
external acceptance harness. Service startup, makers, graph and configuration
are generated from the same Python model. Build the local TypeScript SDK first.

```sh
SERVICEGEN_PULSAR_TYPESCRIPT_CANONICAL=1 \
PULSAR_TEST_ADMIN_URL=http://127.0.0.1:18080 \
PULSAR_TEST_URL=pulsar://127.0.0.1:16650 \
go test ./internal/codegenerator -run '^TestTypeScriptPulsarCanonicalExample$' -count=1 -v
```

The harness uses official `pulsar-client` 1.18.0 to send input and independently
read output. Application handlers use only native SDK endpoints. It checks three
normalized outputs and keys, native MessageID correlation, broker-observed ACK,
environment configuration and clean SIGTERM exit. All resources belong to a
unique test namespace and are removed after the run. Native fault/TLS and Linux
image tests remain separate gates.

To run the same acceptance against a built runtime image, set
`PULSAR_ACCEPTANCE_IMAGE=sa-pulsar-typescript-canonical:arm64` in the command above.
The harness starts its own container sharing only the network namespace of
`PULSAR_BROKER_CONTAINER` (default `servicelib-pulsar-acceptance`), supplies the
unique topic URLs, and uses Docker stop to verify the service's real entrypoint
and graceful shutdown. The test owns and removes this container. The local
harness's native client remains outside the application container.

The artifact export variable
`SERVICEGEN_PULSAR_TYPESCRIPT_CANONICAL_ARTIFACTS` saves generated files plus
user implementations with ZIP permissions intact, before local node_modules
links are added. It can therefore supply an isolated Docker build context.

For an authenticated broker, supply `EVENTS_TOKEN` for native message operations
and optionally `EVENTS_ADMIN_TOKEN` for REST preflight/provisioning. A tenant-admin
identity is sufficient for the latter; the native token can remain scoped to
produce/consume permissions. Do not put either token in `project.py` or its YAML
export. Generated environment bindings accept them from your runtime secret store.
The harness also accepts `PULSAR_AUTH_MANIFEST`: the owner-readable manifest
produced by `tsservicelib/test/native-probes/pulsar-auth-fixture.mjs`. Keep that
fixture process running while testing. In this mode the harness creates its own
tenant and namespace, supplies a tenant-admin REST token and a scoped native token,
checks cross-namespace denial, validates that service logs do not contain tokens,
and removes its resources. With `PULSAR_ACCEPTANCE_IMAGE`, credentials are passed
through an owner-only temporary Docker env file, not command-line values; that
file is removed during cleanup. Never commit the fixture manifest.

```sh
SERVICEGEN_PULSAR_TYPESCRIPT_CANONICAL=1 \
PULSAR_AUTH_MANIFEST=/absolute/path/to/fixture/manifest.json \
PULSAR_ACCEPTANCE_IMAGE=sa-pulsar-typescript-auth:arm64 \
go test ./internal/codegenerator -run '^TestTypeScriptPulsarCanonicalExample$' -count=1 -v
```

Set `PULSAR_ACCEPTANCE_COMPOSE=1` together with `PULSAR_ACCEPTANCE_IMAGE` and
`PULSAR_AUTH_MANIFEST` to exercise the generated Docker Compose service. The
harness overrides only the test image/network and endpoint topic variables.
Connector addresses and both credentials must pass through the generated
Compose environment bindings; the harness does not insert them in its override.
This mode passed scoped-token messaging, denied cross-namespace access, native
ID correlation, explicit ACK, secret-free logs and normal shutdown.
