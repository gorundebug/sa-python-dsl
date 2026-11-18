# Generated Coro Redis Streams acceptance

The test projects the existing typed `project.py` to CppCoro in memory, validates
and exports it, generates a fresh archive, and overlays these business handlers.
Archive and overlay executable modes are preserved. The shared model is unchanged.

From `servicegen`, run:

```sh
GO=/Users/sergeyalexeev/sdk/go1.26.4/bin/go \
HIREDIS_NATIVE_PREFIX=/private/tmp/sa-hiredis-coro-eligibility/install \
SERVICEGEN_REDIS_STREAMS_CORO_CANONICAL_ARTIFACTS=/private/tmp/coro-redis-canonical-new \
./scripts/test-coro-redisstreams.sh
```

The artifact directory must be empty. The build uses `cppcoroservicelib-build:latest`,
`dependency-conan2`, the official hiredis 1.5.0 prefix, and two compile jobs by
default. `CPPCOROSERVICELIB_TEST_IMAGE`, `DEPENDENCY_CONAN_VOLUME`, and
`SERVICEGEN_DSL_PYTHON` override those local installations.
`REDIS_STREAMS_TEST_URL` defaults to `redis://host.docker.internal:16379`;
localhost URLs are translated for Docker. `REDIS_STREAMS_TEST_PASSWORD` defaults
to the shared acceptance fixture password. Credentials stay in runtime environment
variables, never topology or command arguments. This harness targets the standalone
plaintext fixture; SDK TLS/fault acceptance is separate.

All business behavior runs through the generated source → normalize → sink → result
graph. The source reads ordered binary fields, rejects duplicate modeled fields,
and ignores unmodeled fields. The test includes duplicate binary extra fields.
Normalization trims and uppercases `Value`; publication emits native `ID` and `Value`
fields. Context passes through unchanged, including `x-stream-id`. A callback is
registered before emitting; only a matching accepted result with a nonempty native
entry ID triggers explicit XACK. Done is independent of ACK. Sink result callbacks
may outlive `endRequest` and capture owned values.

A separate official hiredis test peer only seeds and inspects the broker. Acceptance
checks three `HELLO` records, unique output IDs matching all correlated outcomes,
preserved stream correlation, zero pending entries, and successful SIGTERM within
eight seconds. Unique input/output keys are removed even after failure; the shared
broker is never restarted. The artifact root retains `acceptance.log`, the ZIP and exported model. The
`redisstreamsevents` directory retains `service.log` and `acceptance.results.json`.
`SERVICEGEN_REDIS_STREAMS_CORO_CANONICAL_EXPORT_ONLY=1` exports without compiling or
running and reports a skipped test, never a native acceptance pass.

## Generated runtime image

After the parent builds the generated service image, run this host-side harness:

```sh
HIREDIS_NATIVE_PREFIX=/private/tmp/sa-hiredis-coro-eligibility/install \
REDIS_STREAMS_RUNTIME_IMAGE=sa-redis-coro-canonical:arm64 \
REDIS_STREAMS_RUNTIME_PLATFORM=linux/arm64 \
python3 examples/redis-streams-events/cpp-coro/image_acceptance.py \
  /private/tmp/coro-redis-canonical-1/redisstreamsevents
```

Run from `sa-python-dsl`. The application runs the image's own entrypoint and
installed configuration, with no app, source, config or library mounts. A separate
ARM peer container mounts only the precompiled official hiredis probe and its
libraries. Both use the existing broker's network namespace (port 6379), without
reconfiguring it or mounting a Docker socket. Runtime credentials are passed by
environment name rather than command-line value.

For AMD64 set `REDIS_STREAMS_RUNTIME_PLATFORM=linux/amd64` and select its image;
`REDIS_STREAMS_PEER_PLATFORM` independently defaults to `linux/arm64`.
Optional overrides are `REDIS_STREAMS_PEER_IMAGE`, `REDIS_STREAMS_NATIVE_PROBE`,
`REDIS_STREAMS_BROKER_CONTAINER`, and `REDIS_STREAMS_CONTAINER_PORT`.
Evidence files `image-acceptance.<architecture>.{results.json,service.log}` record
the immutable runtime image ID, architecture, three correlated output IDs,
zero pending entries, exit code and measured SIGTERM time. Only test-owned
containers and UUID keys are removed. A build or export alone is not an image
acceptance pass.

Verified locally on 2026-11-18: `TestCoroRedisStreamsCanonicalExample` passed in
142.36 seconds using two compile jobs. The generated archive retained all 39 shell
script modes. ARM64 runtime image acceptance passed against immutable image
`sha256:5ca6cdd358b1be85ae0af00a02a729018f4490bd6cedb4247cfb554020e122e1`,
with an independent ARM64 peer, three matching normalized outcomes, pending=0,
exit=0, and SIGTERM completion in 92.5 ms. Evidence root:
`/private/tmp/coro-redis-canonical-1/redisstreamsevents`.
This records ARM acceptance only; AMD64 requires its own image run.
# Cross-runtime acceptance

Fresh generated C++ Coro ↔ Go/Python/TypeScript chains passed in both directions
on 2026-11-18. The common driver is
`servicegen/scripts/check_redis_generated_interop.py`: supply `--coro-project`
with the built `redisstreamsevents` directory, `--hiredis-prefix`, peer artifact
arguments, and repeat `--coro-peer` for the required languages. It mounts the
built service/dependencies read-only and uses UUID-owned stream keys.
Checks cover native ID/Value fields including UTF-8/NUL, both consumer groups
with zero pending/lag after XACK, and clean service exit. This is functional
compatibility, not performance or exclusive reclaim certification.

