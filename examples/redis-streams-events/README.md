# Redis Streams events

`project.py` is the editable architecture. The three stages are Redis group
input, pure event normalization and Redis publication. The sink's correlated
result returns to the source; request completion does not acknowledge input.
The source calls XACK only after a successful publication outcome.

Input group creation and output stream creation are explicitly enabled for this
demo. Consumer identity is omitted so separate service instances receive unique
identities. Pending reclaim does not fence old processing; duplicate output is
possible and production business handlers must be idempotent. No implicit
trimming, deletion, disk persistence guarantee or exactly-once guarantee is made.

The publication outcome includes the business EventID and Redis EntryID. A
failure or unknown outcome leaves input pending. An ambiguous XADD is never
replayed automatically by the transport.

## Run the generated Go acceptance

The `go/` directory contains user-owned business functions, records, serializers
and the integration check. The generator test exports this Python model,
generates into a temporary workspace, overlays these files and runs the generated
service against a real Redis broker with the race detector enabled.

From `servicegen`, with Go 1.26.4 and the local SDK checkout available:

```sh
SERVICEGEN_REDIS_STREAMS_CANONICAL=1 \
REDIS_STREAMS_TEST_URL=redis://127.0.0.1:16379 \
REDIS_STREAMS_TEST_PASSWORD=adapter-test \
go test ./internal/codegenerator -run '^TestGoRedisStreamsCanonicalExample$' -count=1 -v
```

Use an isolated Redis instance. The check creates uniquely named keys and removes
only those keys. It verifies normalization, output count, source settlement,
generated environment configuration, serialization and service shutdown.

## Run the generated TypeScript acceptance

The same Python model is projected to TypeScript by the test. User-owned code is
in `typescript/`; `acceptance.mjs` starts the freshly generated service and uses
the official node-redis client to verify output and the input pending list.

```sh
SERVICEGEN_REDIS_STREAMS_TYPESCRIPT_CANONICAL=1 \
REDIS_STREAMS_TEST_URL=redis://127.0.0.1:16379 \
REDIS_STREAMS_TEST_PASSWORD=adapter-test \
go test ./internal/codegenerator -run '^TestTypeScriptRedisStreamsCanonicalExample$' -count=1 -v
```

The local TypeScript SDK must be built first. This check verifies all three
business IDs and returned Redis entry IDs, explicit ACK, normalized output and
clean SIGTERM shutdown. It deletes only its unique test keys.

Status: generated Go and TypeScript canonical paths pass on Redis 7.4. Complete
fault/TLS coverage, other runtime targets and release acceptance remain open.

### Generated Python/TypeScript interoperability

`servicegen/scripts/check_redis_generated_interop.py` chains both generated
services in each direction using three UUID-owned stream keys. It compares Event
fields (including UTF-8 and embedded NUL), preserves IDs, and requires both input
consumer groups to have zero pending records and zero lag before clean shutdown.
It removes only its own keys, never shared broker configuration.

Supply freshly retained `SERVICEGEN_REDIS_STREAMS_PYTHON_CANONICAL_ARTIFACTS` and
`SERVICEGEN_REDIS_STREAMS_TYPESCRIPT_CANONICAL_ARTIFACTS` roots to `--python` and
`--typescript`. Other required arguments are `--workspace`, `--python-executable`,
`--node`, `--url` and `--output`; the password is taken from
`REDIS_STREAMS_TEST_PASSWORD` (local fixture default: `adapter-test`). Run with
the SDK Python environment, which includes redis, nats-py and PyYAML for the
shared generated-fixture preparation helper.

Both directions pass on macOS with Python 3.14.6 and Node 24.16.0. This verifies
shared canonical field encoding and explicit XACK; it does not establish arbitrary
binary serde, exclusive reclaim ownership, or a performance bound. The standalone
TypeScript canonical launcher now fails initial authentication/connection errors
without indefinite native reconnect attempts; pass its password explicitly.
