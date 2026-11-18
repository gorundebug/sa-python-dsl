# Native NATS event processing

The canonical Event JSON wire contract uses the exact field names `ID` and
`Value` in every language. Native struct member naming is not permission to
change the serialized contract. Go tags were corrected from lowercase names
after cross-language review; no broker SDK envelope or topology change is needed.

`servicegen/scripts/check_nats_generated_interop.py` checks generated services in
both language orders, with Core and JetStream. Its default is Python/TypeScript;
`--go-artifacts`, `--go-executable` and optional `--go-peer typescript` select
Go/Python or Go/TypeScript. Both Go pairs passed on 2026-11-18, including UTF-8,
embedded NUL, exact output fields, both source ACK prefixes and clean shutdown:
`/private/tmp/sa-nats-go-python-interop.json` and
`/private/tmp/sa-nats-go-typescript-interop.json` (matching `.log` files).
This does not claim untested runtime pairs or arbitrary-header compatibility.

This typed Python model describes two independent pipelines in EventProcessor:

```text
Core subject → normalize event → Core publication → input result callback
JetStream durable input → normalize event → JetStream publication → input result callback
```

Each input owns its own nodes. Both normalization nodes reuse `NormalizeEvent`;
there is no shared graph node joining unrelated handlers. Records use native
`struct_type` declarations. Serialization stays inside endpoint implementations.
The model describes contracts. The `go/internal` directory supplies the user-owned
record definitions, serializers, business functions and native acceptance test.
Generated scaffolds alone still contain TODOs; install the supplied implementation
into a freshly generated service before running the example.

Use the current development checkout of `sa-python-dsl`, since older releases
cannot author these connector types. From the DSL repository:

```sh
.venv/bin/sa-dsl validate --project examples/nats-events
.venv/bin/sa-dsl export --project examples/nats-events
```

`project.py` is authoritative. `build/project.yaml` is generated interchange and
ignored by Git. The manifest isolates generated code in `build/generated`.
The default model target is Go. The acceptance gates below export this same model
for the other runtimes and apply their user-owned implementations.

## Rust canonical graph

`rust/src/internal` supplies the Event/PublicationOutcome records and native
handlers. From `servicegen`, build a fresh retained tree:

```sh
SERVICEGEN_NATS_RUST_RUN_ARTIFACTS=/absolute/new-artifacts \
RUST_CARGO_CONFIG=/absolute/cargo-proxy-config.toml \
bash scripts/compile-rust-nats.sh
```

The Docker Rust toolchain and cached dependencies must already exist. The build
is offline; `RUST_CARGO_CONFIG` is optional when the default registry cache is
used. `GO`, `DSL_PYTHON`, `RUST_BUILD_IMAGE`, `RUST_CARGO_VOLUME` and
`RUST_TARGET_VOLUME` select local tooling. The only generated manifest change
points the SDK dependency at the read-only local checkout. No graph wiring is
handwritten. The artifact directory must not already exist.

Run `check_nats_generated_interop.py` with `--rust-project` pointing to its
`natsevents/eventprocessor` directory, alongside the Python artifact/options
shown below. Both directions passed Core and JetStream on 2026-11-18, including
UTF-8/NUL, output correlation, both source ACK prefixes and clean exit. Rust
handlers ACK only after successful publication feedback; Core has no durable ACK.
This is not a performance or fault/recovery result.

## Completion contract

`Event` carries an ID and value. Normalization preserves the ID and returns one
event. The sink sends asynchronously and returns a `PublicationOutcome` carrying
that same ID. Register the source callback before collecting into the graph, since
results may arrive synchronously. Preserve the supplied context throughout.

Core publication acceptance means the native client accepted the message. It
has no durable ACK or replay and does not prove a subscriber received it.
JetStream publication success requires the server's PubAck. On that success the
input handler explicitly ACKs its original message; on failure it NAKs it.
A failure after send can mean unknown delivery, so processing must tolerate
redelivery and duplicate output. There is no atomic consume/publish transaction
or exactly-once claim. `Done` closes the request lifecycle; it never ACKs.

## Resource and connection settings

Core uses a queue group. JetStream uses distinct `EXAMPLE_IN` and `EXAMPLE_OUT`
streams, avoiding ambiguous filters and accidental processing of its own output.
The example explicitly opts into resource creation. To exercise existing-only
mode, provision both streams and the durable consumer first, then set the three
creation flags to false. Startup must not reconfigure existing resources.

Local addresses are `nats://localhost:4222`; container deployment supplies its
broker address through generated `CORE_EVENTS_SERVERS` and
`DURABLE_EVENTS_SERVERS` overrides. Keep credentials in runtime secret overrides,
never in this Python model or server URLs. Local development infrastructure and
its native SDK acceptance are tracked in `servicegen/docs/message-brokers-plan.md`.

## Executable acceptance

From the adjacent `servicegen` checkout, with the current local Go SDK and an
installed official `nats-server` binary:

```sh
SERVICEGEN_NATS_CANONICAL=1 NATS_SERVER_BINARY=/absolute/path/to/nats-server \
  go test ./internal/codegenerator -run '^TestGoNATSCanonicalExample$' -count=1
```

The test exports this Python model, generates a fresh temporary project, copies
only `go/internal` user-owned files into it, and compiles against the adjacent
`servicelib` checkout. It starts an isolated JetStream-enabled server and exercises
both generated pipelines: three Core events and three durable events. It checks
normalized payloads, correlation IDs, output counts, explicit durable input ACKs,
and value-record serializer round trips. No existing broker or workspace is reset.
SDK fault/reconnect/shutdown acceptance is separate from this functional example.

## TypeScript generated graph acceptance

`typescript/` contains only user-owned native types, handlers and the broker
acceptance runner. The generator supplies the graph, config and lifecycle.
Run from `servicegen` with Go and Node on PATH:

```sh
SERVICEGEN_NATS_TYPESCRIPT_CANONICAL=1 \
NATS_SERVER_BINARY=/path/to/nats-server \
go test ./internal/codegenerator -run '^TestTypeScriptNATSCanonicalExample$' -count=1
```

The test compiles the fresh generated service against the local TypeScript SDK,
starts an isolated broker, verifies Core and JetStream output and feedback,
checks JetStream acknowledgment, then stops the service and broker. Sink
`getStreamId` preserves the incoming context ID so feedback reaches its request.

## Python generated graph acceptance

`python/` provides user-owned domain dataclasses and handlers. The test exports
the same typed model as Python, regenerates the graph, and starts it through the
standard process entrypoint with `--config config/config.yaml --values
config/overrides.yaml`. Run from `servicegen`:

```sh
SERVICEGEN_NATS_PYTHON_CANONICAL=1 \
NATS_SERVER_BINARY=/path/to/nats-server \
go test ./internal/codegenerator -run '^TestPythonNATSCanonicalExample$' -count=1
```

The local Python SDK environment must be installed. Core and JetStream each
have their own pipeline; JetStream ACK follows successful publication feedback.

## C++ Coro generated graph acceptance

`cpp-coro/eventprocessor/` contains user-owned records and coroutine handlers.
The opt-in gate exports this Python model for CppCoro, generates a fresh graph,
compiles it against the local SDK and official nats.c 3.14.0, then starts the
normal service executable against a disposable Docker NATS broker:

```sh
SERVICEGEN_NATS_CORO_CANONICAL=1 bash scripts/compile-coro-nats.sh
```

Run from `servicegen`. The normal Coro build image, Conan dependency volume and
SDK toolchain must already be available. `CPPCOROSERVICELIB_TEST_IMAGE`,
`DEPENDENCY_CONAN_VOLUME`, `CORO_SDK_DIR`, `GO` and `DEPENDENCY_GITHUB_RAW_URL`
can select local tooling and the dependency proxy. `NATS_ACCEPTANCE_PYTHON`
defaults to the local Python SDK virtual environment (requires nats-py).
The gate checks normalized Core/JetStream output, correlated publication
results, explicit JetStream ACK and successful shutdown. Generated startup
selects the existing SDK blocking executor for the native transport; business
handlers neither construct clients nor manage transport threads.

## C++ userver candidate acceptance

`cpp-userver/eventprocessor/` contains user-owned records and handlers for the
same example. From `servicegen`, run `bash scripts/test-userver-nats.sh` with the
normal userver toolchain prepared in `cppservicelib/build-nats/conan` and its
matching Conan volume. `USERVER_SDK_DIR`, `NATS_ACCEPTANCE_IMAGE`,
`DEPENDENCY_CONAN_VOLUME`, `GO`, and `NATS_ACCEPTANCE_PYTHON` select local tooling.
This exports the Python model, builds the generated graph and exercises it with
a disposable NATS broker using the same wire assertions as Coro.

This functional gate does **not** certify userver suitability under cancellation,
queue saturation or failed shutdown. Userver support remains conditional on
those checks. Official native APIs must not block application task processors;
the adapter uses the existing blocking task processor and returns business
callbacks to the application processor. No userver patch is permitted.

### Generated Python/TypeScript interoperability

`servicegen/scripts/check_nats_generated_interop.py` runs the canonical services
in both orders, Python → TypeScript and TypeScript → Python, over Core and
JetStream. It uses a temporary NATS process per direction, independently generated
service trees, the canonical user-owned handlers and runtime config overrides.
No shared broker resources are changed. Three checked events include UTF-8 and
an embedded NUL in the JSON string; IDs and final values must match exactly.
Both durable input consumers must reach the acknowledged prefix before shutdown.
A Core readiness probe is excluded from the checked event set.

First retain fresh artifacts using the existing generator gates:
`SERVICEGEN_NATS_PYTHON_CANONICAL_ARTIFACTS` and
`SERVICEGEN_NATS_TYPESCRIPT_CANONICAL_ARTIFACTS` with their corresponding
`SERVICEGEN_NATS_*_CANONICAL=1` flags and `NATS_SERVER_BINARY`.
Then run the verifier with the SDK Python interpreter (nats-py and PyYAML needed):

```sh
python servicegen/scripts/check_nats_generated_interop.py \
  --workspace /absolute/workspace \
  --python /absolute/python-artifacts \
  --typescript /absolute/typescript-artifacts \
  --python-executable /absolute/workspace/pyservicelib/.venv/bin/python \
  --node /absolute/path/to/node \
  --nats-server /absolute/path/to/nats-server \
  --output /absolute/path/to/interop-results.json
```

Recorded 2026-11-18: all four direction/protocol combinations pass on macOS,
Python 3.14.6, Node 24.16.0 and NATS 2.15.0. This is a functional shared Event JSON
contract check, not arbitrary-header/binary preservation, pinned Linux-platform
acceptance, a performance benchmark, or cross-runtime coverage of other brokers.
