# Compiled-runtime NATS workload acceptance

2026-11-18. `compiled_nats.py` runs an actual generated canonical service, using
the official Go NATS load peer; no direct business-handler invocation. Supply
`--runtime rust|userver|coro`, the built `--project`, a new `--artifacts` directory
and `--go`. It uses the existing `cppservicelib-nats-acceptance` broker and only
UUID-owned subjects/streams; service and peer containers are removed, streams
are deleted. Run profiles sequentially because services share the broker network
namespace and default HTTP port. The peer is built for Linux ARM64.

The service has one CPU and 512 MiB; peer has its own one-CPU container.
Each mode uses 500 separate warmup messages and 5,000 measured messages, with
8 in flight and a 180-second phase bound. All responses have exact canonical
IDs and normalized values; invalid/unexpected counts are zero. JetStream checks
publication acknowledgements, exact stored output growth, zero input pending
and ACK-pending, and sufficient ACK floor. Core asserts only ephemeral delivery.
All three services exit zero within the unchanged 15-second stop bound, without
OOM or forced termination. Immutable image IDs, binary SHA256, peer dependency
identity, actual cgroup limits and before/after CPU/memory are in each report.

| Runtime | Mode | Messages/s | p99 ms | Measured service CPU s | Cgroup peak bytes |
| --- | --- | ---: | ---: | ---: | ---: |
| rust | core | 14612.85 | 1.255 | 0.414 | 42651648 |
| rust | jetstream | 2793.44 | 6.323 | 1.172 | 43393024 |
| userver | core | 2602.96 | 39.659 | 1.954 | 46977024 |
| userver | jetstream | 942.42 | 13.325 | 5.176 | 51818496 |
| coro | core | 6795.05 | 2.342 | 0.704 | 60633088 |
| coro | jetstream | 3585.27 | 3.975 | 1.117 | 65236992 |

These are short workload samples on a shared broker, not capacity certification
or a ranking of runtimes. Core samples last less than two seconds; GC/allocator,
connection, scheduler and persistence effects differ. Memory peak is cumulative
for the container, not the per-phase incremental allocation. Allocation count is
unavailable and explicitly null, not estimated from memory. Process metric
families differ; cgroup CPU is retained even where process counters are absent.

Raw reports/logs: `/private/tmp/sa-{rust,userver,coro}-nats-performance-20261118/`.
C++ binaries include the repeated-header fix and match the targeted generated
interoperability rebuild. Rust uses the already-verified canonical generated
binary; the preceding Rust change added tests only.

## Remaining compiled broker profiles

The same helper additionally accepts `--broker pulsar|redis-streams` and
`--native-prefix` (the official Pulsar install prefix or hiredis install prefix).
Rust is NATS-only; userver Redis is rejected as unsupported. The load peer for
these profiles is `broker-performance/peer.go`. Metrics readiness checks a valid
HTTP Prometheus response including labelled samples; absence of unlabelled Go
process counters is not treated as an unavailable endpoint. Cgroup measurements
remain independent of exporter format. An initial userver Pulsar run exposed
this helper mistake and was not accepted; the fixed run below passes.

All three profiles passed 500 warmup + 5,000 measured messages, eight in flight,
one CPU/512 MiB, exact output/native identity validation, broker settlement and
15-second clean shutdown. Pulsar input/output backlog and unacked counts reached
zero; Redis input pending/lag reached zero and output length was exactly 5,500.
These are shared-broker samples with the same limitations as above; allocation
count remains null. Redis and the first userver attempt overlapped; the final
Pulsar samples ran sequentially. No throughput ranking is inferred.

| Runtime | Broker | Messages/s | p99 ms | Measured service CPU s | Cgroup peak bytes |
| --- | --- | ---: | ---: | ---: | ---: |
| userver | pulsar | 359.29 | 33.412 | 4.719 | 91545600 |
| coro | pulsar | 377.75 | 33.214 | 1.869 | 61874176 |
| coro | redis-streams | 2524.96 | 21.653 | 2.013 | 68292608 |

Raw reports: `/private/tmp/sa-userver-pulsar-performance-fixed-20261118/`, `/private/tmp/sa-coro-pulsar-performance-20261118/`, `/private/tmp/sa-coro-redis-performance-20261118/`.
