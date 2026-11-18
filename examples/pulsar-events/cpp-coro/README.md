# Pulsar Coro canonical overlay

This implements the existing `../project.py` process for C++ Coro: native input,
normalization, native asynchronous publication, correlated result, individual ACK.
The Go test projects the same typed model to CppCoro in memory, validates/exports
it, regenerates a fresh service, and copies only these user-owned implementation
files over its stubs. No graph, generated configuration, SDK or Docker dependency
implementation is replaced by the overlay.

`ReceiveEventSource` decodes the JSON Event and registers its result callback
before collect. The callback accepts only its business EventID, acknowledges only
an Accepted publication carrying a native MessageID, then logs the outcome and
calls Done. Done itself never acknowledges. Failed publication outcomes remain
unacknowledged; the example does not automatically retry ambiguous sends.

`PublishEventSink` snapshots the business ID into its asynchronous callback,
sets the native key/properties and JSON bytes, and calls `send(callback)` without
forcing synchronous publication. Native MessageIds are serialized and base64
encoded for the string result field, matching the Python canonical representation.
`NormalizeEvent` only trims and uppercases Value, preserving ID and context.

## Run the complete gate

From the workspace:

```sh
PULSAR_NATIVE_PREFIX=/private/tmp/pulsar-cpp-eligibility/install/usr \
GO=/Users/sergeyalexeev/sdk/go1.26.4/bin/go \
SERVICEGEN_PULSAR_CORO_CANONICAL_ARTIFACTS=/private/tmp/pulsar-coro-canonical-new \
bash servicegen/scripts/test-coro-pulsar.sh
```

The artifact directory must be empty. Omit it for automatic temporary cleanup.
The exporter preserves every ZIP entry's permission mode and the overlay's modes;
generated shell scripts remain executable for Docker builds. It retains
`generated.zip`, `model.exported.yaml` and the build/native log. Set
`SERVICEGEN_PULSAR_CORO_CANONICAL_EXPORT_ONLY=1` to prepare artifacts without
Docker; that branch is explicitly reported **skipped**, not native acceptance.

Defaults: `cppcoroservicelib-build:latest`, `dependency-conan2`, shared broker
host port 16650 and admin port 18080. Override `CPPCOROSERVICELIB_TEST_IMAGE`,
`DEPENDENCY_CONAN_VOLUME`, `PULSAR_TEST_URL`, `PULSAR_TEST_ADMIN_URL`, or
`CORO_BUILD_JOBS` when needed. The test mounts the SDK and official client read-only.
It uses the SDK's existing test-only frame proxy to rewrite advertised lookup
addresses, without fabricating broker responses. The generated application uses
only official native SDK endpoints; `probe.cpp` is a separate test peer.

The supervisor creates a UUID namespace, disables both automatic topic and
subscription creation there, starts the generated service using environment
configuration overrides, and waits for its actual native producer and consumer.
An explicitly created observer subscription sees three normalized records with
business keys, retained caller property and inherited stream correlation. Their
native MessageIds must equal the three generated graph outcomes. Source broker
stats must show zero backlog and zero unacknowledged messages. SIGTERM must exit
zero within eight seconds. Only the test namespace/topics are deleted; the shared
broker is never restarted.

This is a generated-process functional gate using the provided build image and
official installed C++ client. It does not claim generated production Docker image,
TLS/auth, architecture matrix or throughput acceptance; those are separate gates.


## Already-built runtime image gate

The host orchestrator uses the image's own entrypoint, packaged configuration and
libraries without mounting application sources or replacing its executable. It
runs both application and the separate prebuilt official native peer with
`--network container:servicelib-pulsar-acceptance`, so the broker's advertised
loopback address resolves naturally. No proxy, Docker socket mount, broker restart,
or additional compile is needed. The host uses admin port 18080; containers use
native port 16650 and admin port 18080 inside the existing broker network namespace.

```sh
PULSAR_RUNTIME_IMAGE=sa-pulsar-coro-canonical:arm64 \
PULSAR_RUNTIME_PLATFORM=linux/arm64 \
PULSAR_PEER_PLATFORM=linux/arm64 \
PULSAR_NATIVE_PREFIX=/private/tmp/pulsar-cpp-eligibility/install/usr \
python3 sa-python-dsl/examples/pulsar-events/cpp-coro/image_acceptance.py \
  /private/tmp/coro-pulsar-canonical-1/pulsarevents
```

The image must already exist. `PULSAR_RUNTIME_IMAGE` defaults to the tag above;
`PULSAR_RUNTIME_PLATFORM` defaults to `linux/arm64` and is checked against image
metadata. Set it to `linux/amd64` for an AMD64 runtime, keeping
`PULSAR_PEER_PLATFORM=linux/arm64` when reusing the ARM peer. This explicitly tests
an AMD64 service against an ARM native peer, not an AMD64 peer build. The runtime
is launched by immutable image ID, recorded with both platforms in evidence.

Optional overrides: `PULSAR_PEER_IMAGE` (default `cppcoroservicelib-build:latest`),
`PULSAR_NATIVE_PROBE` (default artifact `build/canonical-probe`),
`PULSAR_BROKER_CONTAINER`, `PULSAR_TEST_ADMIN_URL` (host admin),
`PULSAR_CONTAINER_URL`, and `PULSAR_CONTAINER_ADMIN_URL`. The probe executable and
official client prefix must match the peer platform. Only the peer receives these
read-only mounts; it does not load the runtime application's implementation.

The same three normalized records, business keys, native MessageId correlation,
explicit source ACK stats and zero exit within eight seconds of SIGTERM are
required. A fresh namespace has automatic resource creation disabled. Cleanup
removes only this test's containers and namespace, even after failure. Forced
failure cleanup is never counted as graceful shutdown. Results and image identity
are written to `image-acceptance.results.json`, with service and peer logs beside
it; preserve those files between architecture runs if using the same artifact root.
