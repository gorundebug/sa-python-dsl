# Request-driven PostgreSQL and S3

`project.py` is the editable model. `build_project(target)` supports `go`,
`typescript`, `python`, `rust`, `cpp-userver` and `cpp-coro`, selecting the
corresponding PostgreSQL library and S3 connector. The manifest defaults to Go.

Each operation owns a callable SubStream, Query and Error node: Rows, Execute, Returning,
GetObject, HeadObject, ListObjects, PutObject and DeleteObject. The caller sends
StorageRequest and receives StorageResult. These are callable stages, not startup
flows. EndRequest emits a completed result on success, including empty reads;
Query adds no completion port. The Error branch is separate from successful data.

Python (`python/src`), Go (`go/internal`) and TypeScript (`typescript/src`)
supply records and all eight handlers. Returning is an independent pipeline
using the existing PostgreSQL Rows operation for `INSERT ... RETURNING value`;
it is not a new SDK operation. Its model and handlers exist for all six runtimes.
Generation, compilation and live Returning graph acceptance passed for all six.
Each test sends a quoted key and binary value through Returning, checks the
returned record and completion, then reads the key through Rows to verify the
write persisted. PostgreSQL and MinIO are disposable Compose resources.
Rows uses a bound SQLAlchemy selection; Execute upserts a key/value pair. S3 reads
bounded chunks, returns metadata/pages and performs puts/deletes. Apply
`python/schema.sql` explicitly to a disposable database and create the
`query-example` bucket before live execution. The code never provisions them.
Rust handlers in `rust/src` compile and pass the generated live graph test for
all seven operations against disposable Compose PostgreSQL and MinIO, including
empty Rows, explicit completion and graceful service shutdown. C++ userver handlers and the generated service pass all seven live operations,
including concurrent SQL/S3 calls with a one-connection PostgreSQL pool. C++ Coro canonical handlers and the complete generated service compile and link
with libpq and the AWS SDK, and pass the seven-operation generated live graph
with binary data, empty Rows, explicit completion and graceful shutdown. The baseline live graph is accepted for all six runtimes. Full cross-language
SQL type mapping and DML RETURNING through the canonical graph are now accepted
at the scopes recorded in the plan; the remaining negative/concurrency matrix
is still a separate acceptance item.

Use service infrastructure makers for shared clients/pools. Supply DSNs, userver
S3 address and credentials through runtime overrides/environment. The example
sets bucket because userver clients are bucket-bound. No implicit schema/bucket
creation, retries of partial results or retries of unknown write outcomes.

From the DSL checkout:

```sh
.venv/bin/sa-dsl validate --project examples/storage-query
.venv/bin/sa-dsl export --project examples/storage-query
```

Generated YAML belongs in ignored `build/`; never edit it as model source.

Runtime names, S3 credential differences and the generated Helm/Vault path are
documented in [deployment.md](deployment.md).

## Combined generation and compilation

From the sibling `servicegen` checkout, run the lightweight model-to-generator
check with the development DSL interpreter:

```sh
SA_QUERY_DSL_PYTHON="$(pwd)/../sa-python-dsl/.venv/bin/python" \
SA_QUERY_CANONICAL_OUTPUT=/tmp/query-canonical-all-targets \
go test ./internal/codegenerator -run '^TestCanonicalStorageQueryAllTargets$' -count=1
```

Before compiling, compare the direct Query client versions with local SDK
manifests without installing anything:

```sh
python3 scripts/check_query_dependency_pins.py --artifacts /tmp/query-canonical-all-targets
```

This checks Go/TypeScript/Python/Rust direct client pins, Go pgx/Bun dialect,
Python botocore, exact TypeScript pg/pg-cursor versions, and Coro libpq/AWS
recipe versions in all three platform Conan locks. Userver system packages,
full transitive resolution and real TLS negotiation remain separate checks.

Use an **absolute** interpreter path if the Go test changes working directory.
Then `servicegen/scripts/check_query_canonical_builds.py --artifacts PATH` accepts
`--go`, `--node`, and `--python` executable paths to check those generated targets
against the sibling development SDKs. Dependencies must already be installed;
the Go branch disables proxy downloads. The script changes only generated output
and build caches, not model sources. Rust/C++ native builds remain separate.

The combined seven-operation service passed Go/TypeScript compilation and Python
compilation/runtime-module imports. These compilation checks alone do not prove native PostgreSQL/S3 execution.

## Python business implementation

After generating into a disposable output directory, overlay only user-owned
files (do not replace generated makers, endpoints or lifecycle code):

```sh
cp -R examples/storage-query/python/src/storage_worker/. \
  /tmp/query-canonical-all-targets/python/storagequery/storageworker/src/storage_worker/
PYTHONPATH=/tmp/query-canonical-all-targets/python/storagequery/storageworker/src:../pyservicelib/src \
  ../pyservicelib/.venv/bin/python examples/storage-query/python/test_handlers.py
```

The lightweight suite invokes generated function makers and real SDK consumers
with substituted native I/O. It covers all seven handlers, request-local state,
bound parameters, multiple results, explicit completion, empty objects, native
errors and resource closing. It does not validate live servers, full SubStream
routing or infrastructure startup. Shared clients are still made by the generated
infrastructure makers; the business implementation creates no clients or pools.

## Go business implementation

After generating into the disposable output directory:

```sh
cp -R examples/storage-query/go/internal/. \
  /tmp/query-canonical-all-targets/go/storagequery/storageworker/internal/
GOWORK=off go -C /tmp/query-canonical-all-targets/go/storagequery/storageworker build ./...
GOWORK=off go -C /tmp/query-canonical-all-targets/go/storagequery/storageworker test ./internal/functions
```

Use the same explicitly applied `python/schema.sql` for both implementations.
Go uses Bun's placeholder escaping for Rows and upsert Execute. GetObject copies
bounded chunks before handing them to downstream processing; buffers are never
reused while owned by a result. Each invocation has its own state pointer.

The Go tests exercise all five S3 operations through the AWS serializer/parser,
real SDK consumers and an in-process HTTP transport, including two-page listing.
They also check failure does not emit success. They do not connect to S3 or
PostgreSQL servers; PostgreSQL is compiled but native execution remains open.

## TypeScript business implementation

After generating into the disposable output directory:

```sh
cp -R examples/storage-query/typescript/src/internal/. \
  /tmp/query-canonical-all-targets/typescript/storagequery/storageworker/src/internal/
mkdir -p /tmp/query-canonical-all-targets/typescript/storagequery/storageworker/test
cp examples/storage-query/typescript/test/query-example.test.mjs \
  /tmp/query-canonical-all-targets/typescript/storagequery/storageworker/test/
node ../tsservicelib/node_modules/typescript/bin/tsc --build \
  /tmp/query-canonical-all-targets/typescript/storagequery/storageworker/tsconfig.json
node --test /tmp/query-canonical-all-targets/typescript/storagequery/storageworker/test/query-example.test.mjs
```

The implementation uses typed Kysely builders and the same explicitly applied
schema as Python/Go. Both database consumers are tested with real SQL compilation
and substituted connections, including release-before-completion and parameter
binding. Five S3 operations use the AWS serializer/parser with an in-process
transport. These checks do not validate live servers or full SubStream routing.
Infrastructure makers and generated endpoint bindings remain unchanged.

## Rust business implementation — compilation pending

`rust/src/internal` contains records and all seven handlers, using SQLx
`PgArguments` and native AWS fluent builders. Overlay it onto the corresponding
generated service's `src/internal`; do not replace generated modules or makers.
The bindings infer the handler's request-local state, so no generated file needs
changing. The same explicitly applied SQL schema is used by the other examples.

This implementation has **not passed compilation or runtime acceptance**. The
cached `servicelib-standalone-rust:1.98.1` image has a rustup `rustfmt` launcher but
no installed rustfmt component; the attempted formatting check did not run.
No dependency installation or heavy Rust/AWS build was started.

## C++ userver business implementation

Overlay `cpp-userver/storageworker/internal` onto the generated userver service's
`internal` directory. All seven handlers are implemented. The PostgreSQL reader
uses a transaction portal and native bytea decoding; Execute uses typed parameters
and Bytea for the upsert. Apply the shared SQL schema explicitly.

S3 preserves userver's native behavior: GetObject receives the whole object,
listing receives v1 XML pages and maps each page to JSON entries. HeadObject
reads standard HTTP headers; the bucket belongs to the connector/endpoint config.
No client construction was moved into the handlers or main.

The generated `functions.generated.cpp` and `endpoints.generated.cpp` passed
`g++ -std=c++20 -fsyntax-only` against the cached userver headers and development
SDK. This checks native signatures and template bindings, not linking, startup,
network behavior or full SubStream execution. Those remain acceptance work.

## C++ Coro business implementation — partial verification

Overlay `cpp-coro/storageworker/internal` onto the generated Coro service's
`internal`. All seven handlers use the existing Query interfaces and generated
makers. PostgreSQL keeps SQL and values separate, binds bytea in binary format
and requests binary result bytes. The shared explicit schema is unchanged.

S3 handlers construct native AWS requests and map metadata/pages; GetObject
consumes the already-buffered native response in copied chunks. This does not
turn AWS C++ buffered transport into a streaming network API. Upload state and
response lifetime stay within the SDK operation; no client is created per request.

Both PostgreSQL handler headers passed `g++ -std=c++20 -fsyntax-only` against
actual libpq and Boost headers in the cached build image. S3 compilation is still
unverified: the inspected cached images do not contain AWS C++ headers. No heavy
SDK build or dependency installation was performed. Linking, generated endpoint
instantiation for Coro and live operations remain pending.

## Python generated graph verification

Run `python/test_graph.py` with the same interpreter/PYTHONPATH as the handler
suite. It constructs the generated service graph, overrides native clients via
its infrastructure makers, binds all seven generated endpoints and calls every
public SubStream accessor. It verifies correlated return values, successful
completion after native resource closing and four interleaved calls sharing the
same GetObject handler. Connector shutdown releases both supplied resources.
The test starts no HTTP listener and uses substituted database/S3 I/O; live
server acceptance and full service startup/shutdown remain separate.

## Live Python graph acceptance

`run-live.sh python GENERATED_PYTHON_SERVICE` runs the real seven-operation graph
against temporary PostgreSQL and MinIO containers, limited to loopback ports and
memory. Set `SA_QUERY_S3_IMAGE` to an already cached MinIO-compatible image;
`SA_QUERY_PG_IMAGE` defaults to `postgres:17-alpine`. Missing images fail before
startup; the runner does not build or pull images. Both containers and their
in-memory data are removed on exit. Overlay Python handlers before running it.

The live test passed on PostgreSQL 17 and the cached MinIO test image. It covers
all seven generated SubStream routes, an empty selection, quoted SQL keys,
upsert/update, binary payloads including NUL, multi-chunk object reads, metadata,
listing, empty objects, deletion and four concurrent reads with correlated IDs.
Native clients come from the default generated infrastructure makers. This is
functional acceptance of the Python graph, not all-language acceptance, native
failure/recovery coverage or a full service listener startup/shutdown check.

## Live TypeScript graph acceptance

After compiling the overlaid service, run `run-live.sh typescript GENERATED_SERVICE`
with the same cached-image settings. Set `SA_QUERY_NODE` when Node is not on PATH.
The runner copies the live test into the generated service for package resolution.

The TypeScript test passed against real PostgreSQL/MinIO through generated
infrastructure makers, streams, endpoint bindings and SubStream accessors.
It checks the same seven operations, quoted keys, NUL-containing binary values,
empty results/objects, upsert/update and four concurrent reads as Python. Native
failure/recovery coverage and complete listener lifecycle remain separate.

This check exposed missing Query error-serde registration in the TypeScript
generator. The template now registers it, and canonical generation asserts the
registration for each of the seven Query nodes before runtime acceptance.

## Live Go graph acceptance

Run `run-live.sh go GENERATED_SERVICE` after overlaying `go/internal`. Set
`SA_QUERY_GO` to the installed Go executable if needed. The runner copies the
live test into the generated package and uses cached dependencies only.

The test passes through generated runtime construction, default infrastructure
makers, endpoint binding and public SubStream accessors against real PostgreSQL
and MinIO. It verifies all seven operations, empty rows/objects, quoted SQL keys,
binary NUL-containing data, upsert/update, metadata/list/delete and four parallel
object reads. It starts connectors explicitly and releases the service loader;
HTTP listeners are not started. This is not complete service lifecycle or
failure/recovery acceptance.

## Native failures and cancellation

Python and TypeScript live suites additionally verify an absent S3 object
(`NoSuchKey`), a real missing-table SQL error (`42P01`), cancellation of SQL
confirmed as waiting on a PostgreSQL table lock, and successful reuse of the
same connectors afterward. They observe normal handler finalization and assert
there is no successful `completed` result on these paths.

The example's Error output is separate from its SubStream return. A storage error
does not automatically finish the SubStream call: callers need a deadline or an
explicit application error-to-reply policy. The failure tests cancel the waiting
caller after observing failed finalization. They do not invent a completion port
or silently turn failures into successful completion.


Go PostgreSQL uses Bun with the pgx database/sql driver (v5.11.0). The default
infrastructure maker owns the pool. The live test also checks native S3/SQL errors,
cancels SQL after PostgreSQL reports it waiting on a table lock, and verifies
`context.Canceled`, no success completion, and subsequent pool reuse. Using
pgdriver previously delayed cancellation until a socket timeout; pgx handles it
natively without a connector-specific cancellation wrapper.


To check regeneration ownership for all six languages without building services,
run the generator's `TestCanonicalStorageQueryAllTargets` with
`SA_QUERY_CHECK_MERGE=1` and `SA_QUERY_DSL_PYTHON` set to the development DSL Python.
The test generates into temporary directories, installs these user implementations,
runs the generated merge script, and compares all business files and a custom SQL
file byte for byte. It also verifies that stale generated endpoints are refreshed.

Rust Query handlers use `servicelib::dataquery::Collector<R>` for both mapping and
EndRequest. It forwards to the normal graph collector and accounts for Query
result emissions; other stream collectors keep their existing interface. It
creates no queue or automatic completion message. The example and generator use
the same type; Rust native compilation remains a separate pending check.

### Rust live graph through Compose

Build the generated Rust development image with the current local SDK first.
Then run the complete seven-operation graph against disposable stores:

```sh
SA_QUERY_S3_IMAGE=YOUR_CACHED_MINIO_IMAGE \
  ./examples/storage-query/run-rust-compose.sh /absolute/path/to/storageworker
```

The runner overlays the canonical handlers, uses the generated Compose service,
creates tmpfs PostgreSQL/MinIO stores and removes them on exit. It uses Docker
Desktop's `host.docker.internal` for the ephemeral store ports. The test is
explicitly ignored in ordinary `cargo test`; this command enables it and requires
`SA_QUERY_DISPOSABLE=1`. It sends SIGTERM only to its own test process inside the
container to exercise the generated service shutdown. No host Rust installation,
production credentials or persistent database volumes are needed.

## Completion and downstream work

`EndRequest` says the native operation has finished, its request resources have
been released, and its results have been handed to the graph. It does not wait
for work scheduled through a parallel or queued link to finish.

For example, with `Query (Rows) → ParallelCall → Slow processing`:

1. Query emits a row through the ordinary collector.
2. The graph schedules Slow processing, which may still be running.
3. The native operation closes its cursor and Query calls `EndRequest`.
4. Slow processing finishes independently.

The Go SDK has an executable example of this boundary in
`operators/query_completion_boundary_test.go`: a real Query endpoint uses the
standard ParallelCall link, downstream is held at an explicit gate, and
EndRequest plus the caller return before the gate is released. No SQL server is
required because the assertion concerns graph scheduling, not database I/O.

If EndRequest emits an application `completed` result, it uses the same ordinary
output as rows. A parallel link may process that message before an earlier row
finishes. Choose the existing link semantics and an explicit business aggregation
stage when the caller needs completion of downstream work. Query neither adds a
private queue nor changes the guarantees of the chosen graph link.

## PostgreSQL native values and failed writes

Native library values are mapped by the endpoint handler into application types.
The SDK does not silently convert exact database numbers into floating point.
For Kysely/pg, `numeric` and `int8` remain strings by default; converting them to
JavaScript `number` can lose precision. The default pg `timestamptz` parser creates
a `Date` with millisecond precision. When microseconds matter, supply a pool-local
native type parser through the infrastructure maker and map the returned text
explicitly. Do not change the process-global pg type registry for one connector.
`test/query-postgresql.integration.mjs` in the TypeScript SDK demonstrates this
with exact decimal/int64, timestamp, UUID, bytes, JSON and NULL through both the
Kysely builder and parameterized SQL.

An error during result mapping is not proof that a write rolled back. SQLAlchemy
and userver Rows own a transaction that can roll back on mapper failure; the
Kysely/pg autocommit path can retain a successful INSERT even if mapping its
RETURNING row fails. The common Query guarantee is one terminal outcome and no
automatic replay, not a cross-library guarantee of rollback for every failure.
Already emitted rows remain emitted in either case. Use application idempotency
when a caller needs to recover an uncertain write outcome.

For Rust/SQLx, use `sqlx::types::BigDecimal` when PostgreSQL `numeric` precision
exceeds `rust_decimal`'s range. Both native features are enabled in the SDK and
generated Cargo manifest. `rust_decimal` can round a large PostgreSQL numeric
rather than reject it; it is not a substitute for arbitrary precision. The native
SQLx acceptance test checks a 38-digit numeric without conversion to float,
alongside NULL, int64, microsecond timestamps, UUID, bytes and JSON.

The userver live fixture uses native nullable/int64/bytea readers and explicit
SQL text projections for arbitrary-precision numeric, UTC microsecond timestamps,
UUID and JSON. This is an application mapping choice, not a new SDK codec or a
claim that every native numeric mapping preserves arbitrary precision. The same
single-connection pool is reused for RETURNING, rollback and cancellation checks.

## C++ Coro native S3 edge test

The SDK target `cppcoroservicelib_query_s3_native_test` requires the S3 feature,
GTest and a disposable S3-compatible server. Set `SA_QUERY_S3_ADDRESS`,
`SA_QUERY_DISPOSABLE=1` and native AWS credential environment variables inside
the Compose test container. The test creates bucket `query-edges` with three
empty objects; remove the disposable server after the run. Without an address
it skips, so a skipped test is not acceptance evidence.

The test uses the SDK client factory and asynchronous Query operations for
empty Get/Head, typed 404 errors, one-object pagination, an empty prefix and a
page-mapper failure. Fixture provisioning runs outside the coroutine event loop.
It tests native adapter behaviour, not AWS IAM or all graph queue modes.


## Disposable TLS acceptance fixture

`compose.tls.yaml` starts PostgreSQL with a public test-only certificate from
`tls/`, ephemeral data and no published host ports. Test runners can share its
network namespace (`network_mode: service:postgres`) and use `localhost:5432`.
Mount `tls/` at `/fixtures`; verify the server with `/fixtures/ca.pem` and confirm
that `/fixtures/untrusted-ca.pem` fails. Use native driver-specific TLS settings;
do not disable verification or reuse these certificates in deployment. The Go
`TestPostgreSQLNativeTLS` additionally queries `pg_stat_ssl` to rule out a silent
plaintext fallback. Stop the Compose project with volumes after acceptance.


PostgreSQL TLS URI settings are native-client specific. Go/pgx and TypeScript/pg
accept `sslmode=verify-full&sslrootcert=/fixtures/ca.pem` in the connection URI.
For SQLAlchemy/asyncpg, use `ssl=verify-full` in the SQLAlchemy URL and provide
`PGSSLROOTCERT=/fixtures/ca.pem` through the service environment. SQLAlchemy
passes URL query entries as asyncpg keyword arguments; libpq `sslmode` and
`sslrootcert` are not those keyword names. For an application-specific SSLContext,
supply the engine through the existing infrastructure maker. No TLS verification
bypass is needed. PostgreSQL TLS is verified across all six targets, including
SQLx and both C++ clients: each rejects an unrelated CA and confirms encrypted
connections using `pg_stat_ssl`. Coro requires libpq built with OpenSSL; its Conan
recipe enables this explicitly.

S3 TLS is also verified across all six targets against `tls/s3_server.py` (a
minimal HeadObject HTTPS fixture, not an S3 emulator). Trust configuration is
native-client specific:

| Target | Tested custom CA configuration |
| --- | --- |
| Go / Python | `AWS_CA_BUNDLE` |
| TypeScript | `NODE_EXTRA_CA_CERTS`, set before starting Node |
| Rust | `SSL_CERT_FILE`, set before starting the service |
| C++ Coro / userver | Container system CA bundle at `/etc/ssl/certs/ca-certificates.crt` |

The C++ checks use the normal connector makers; userver runs the Query HeadObject
operation in the generated service. `AWS_CA_BUNDLE` did not configure the pinned
Coro client's trust store and must not be advertised as a portable C++ setting.
Deployments can mount the system CA bundle through Compose/Kubernetes; preserve
any other roots their services require. The fixture replaces only disposable
container trust stores. No certificate or hostname verification is disabled.

### Generated Compose and Helm with custom trust

Generated Compose forwards the native CA variables listed above when the
corresponding Query connector is present. A CA path is a path **inside** the
container. `compose.query-tls.example.yaml` demonstrates a read-only mount; set
`QUERY_CA_BUNDLE_FILE` to the host bundle and the relevant native variable to
`/etc/query-trust/ca.pem`. Combine this overlay with the generated Compose file.
For Python, the database DSN still needs `ssl=verify-full`; for libpq-compatible
clients use the verified DSN settings above.

`helm.query-tls.example.yaml` demonstrates the same setup for Python using the
existing chart `env`, `extraVolumes` and `extraVolumeMounts`. Create the public
`query-trust` ConfigMap from your CA bundle. DSN and credentials remain in
`storageworker-env`, synchronized by the project's existing VaultStaticSecret;
the example contains no credential values. For Go, TS or Rust change only the
native CA environment variable as listed in the table.

For C++ mount the complete deployment CA bundle at
`/etc/ssl/certs/ca-certificates.crt` (Helm: mount its ConfigMap key with `subPath`).
Do not set AWS_CA_BUNDLE expecting it to configure the pinned C++ client. Preserve
system roots required by other connectors. Private client keys, if used, belong
in Vault-backed Secrets rather than the public trust ConfigMap.
