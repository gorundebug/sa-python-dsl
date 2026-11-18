# Generated Go broker performance samples

`run.py` validates/exports the existing typed canonical models, runs the real
local generator (`servicegen/scripts/nats-performance-generate` accepts any
validated model), preserves ZIP modes, installs only checked-in Go user overlays,
and builds actual `cmd/service` binaries against the local SDK. No public SDK,
model or generated wiring changes are made to improve a benchmark. Each scratch
image contains the generated service/config plus an external official-client peer.

```sh
python3 sa-python-dsl/examples/broker-performance/run.py \
  --go /Users/sergeyalexeev/sdk/go1.26.4/bin/go \
  --artifacts /private/tmp/sa-go-broker-performance-RUN \
  --warmup 1000 --count 10000 --inflight 16 --phase-timeout 120
```

Service limits: one Docker CPU (asserted `cpu.max=100000 100000`), GOMAXPROCS=1,
512 MiB. Peer: separate cgroup, two CPUs/256 MiB, fixed worker count and one native
receive loop. It never invokes generated handlers or SDK adapters. Pending IDs
are registered before publication. Latency ends on validated output receipt,
including the peer's explicit output settlement call. Peer input publication
awaits its native result; the actual service retains its canonical async sink.

Workload count, in-flight admission and phase duration are bounded. Warmup and
measurement are separate with unique IDs. All outputs must preserve ID, normalize
Value to `HELLO PERFORMANCE`, and have unique output identity. JSON wire fields
are `ID`/`Value`; Redis uses ordered native `ID`/`Value` stream fields. Pulsar
also validates the message key and serialized native MessageID. RabbitMQ uses
business ID, not an invented native broker MessageID. Selected official peer
versions are retained in build-info logs: Apache pulsar-client-go, redis/go-redis,
RabbitMQ rabbitmq-amqp-go-client (AMQP 1.0, with its go-amqp message/SASL types).

Uses these existing shared broker network namespaces without restart:

| Container | Native listener | Observation/admin listener |
|---|---|---|
| servicelib-pulsar-acceptance | 16650 | 18080 admin HTTP |
| servicelib-redis-streams-acceptance | 6379 | native commands |
| servicelib-rabbitmq-amqp-acceptance | 5672 | 15692 Prometheus |

All namespace/topic/stream/queue/exchange resources are UUID-owned. Pulsar's
owned namespace explicitly disables auto-topic/subscription creation. Known
fixture credentials are supplied only at runtime; no credentials/policies of
shared resources are changed. Service metrics use a per-run port, avoiding broker
listeners. Owned containers/resources are cleaned up; images/build evidence remain.
Cleanup failure fails the run. Rabbit's management HTTP plugin is not enabled or
required: provisioning uses its official AMQP 1.0 management client.

Settlement evidence:

- Redis: input XADD succeeds, output entry IDs are validated and output deliveries
  XACKed. Source XPENDING=0, group lag=0, output length equals cumulative input.
  These commands are not disk/replica durability guarantees.
- RabbitMQ: each input publication must return StateAccepted; output deliveries
  are explicitly accepted. The canonical source accepts only a correlated
  successful sink result. Source and output queue ready/unacked gauges must be
  zero. Per-queue ACK counters are retained when available, not invented if
  this broker's AMQP 1.0 statistics do not expose them. Stats may lag.
- Pulsar: native input send results, unique output MessageIDs, explicit output
  ACKs and canonical individual source ACK after correlated accepted output.
  Input/output subscription backlog and unacked gauges must reach zero.
  These are aggregate observations, not transactional exactly-once proof.

Raw reports include warmup/measurement JSON, validation counts, latency p50/p95/p99,
throughput and separate settlement-observed duration, Prometheus metric snapshots,
process CPU and Go allocation deltas, cgroup CPU/current/peak memory, Docker stats,
image/model/binary identity and clean SIGTERM status. Missing Go counters are null,
never estimated. Allocation counters include service background/scraping work.
Cgroup sampling includes Docker/peer launch and post-measurement overhead. Memory
peak is cumulative for service lifetime, not reset between phases. Broker-stat
polling can extend settlement duration; it is reported separately from output
round-trip throughput.

These are one-CPU **service samples on shared brokers**, not broker capacity,
production sizing, TLS/security or cross-broker fairness claims. Other broker
workloads, storage policy, batching and canonical concurrency vary. Scratch images
are measurement artifacts, not generated production deployment-image acceptance.

## Retained measured sample (2026-11-18)

All three passed. Raw report: `/private/tmp/sa-go-broker-performance-final-1/results.json`; host log: `/private/tmp/sa-go-broker-performance-final-1.log`. Each profile has fresh generated/model ZIP, binary/build-info and image identity, warmup/measurement logs, service stdout and cleanup log.

Parameters: 1,000 warmup + 20,000 measured records per broker; 16 in flight; 120 s phase bound. Linux ARM64; Go 1.26.4. Each service exit was 0 without OOM. All 20,000 measured outputs were validated and all 21,000 cumulative inputs satisfied the profile observation checks.

| Broker | Output records/s | Measured seconds | p50 / p95 / p99 ms | Process CPU % | Allocations/record | Allocated bytes/record | Cgroup lifetime peak MiB |
|---|---:|---:|---|---:|---:|---:|---:|
| pulsar | 481.42 | 41.544 | 32.999 / 43.715 / 44.935 | 5.34 | 159.20 | 11378.38 | 14.54 |
| redis-streams | 7610.99 | 2.628 | 1.765 / 3.432 / 4.106 | 42.24 | 116.71 | 7374.00 | 14.05 |
| rabbitmq | 825.60 | 24.225 | 18.194 / 27.374 / 37.118 | 8.32 | 153.18 | 9888.00 | 13.37 |

The Redis measured interval is only 2.63 seconds; treat it as a short sample, not a sustained-capacity benchmark. Pulsar/RabbitMQ are far below CPU saturation in this closed-loop canonical profile. Broker/service scheduling, storage and peer receipt waits all contribute. No relative performance ranking is asserted.

RabbitMQ exposes ready/unacked queue gauges but no per-queue AMQP 1.0 ACK counter in this fixture; the report does **not** synthesize an ACK count. The observed empty queues plus canonical explicit-acceptance control flow are the evidence; asynchronously collected broker gauges are not a per-message settlement receipt. Pulsar backlog/ACK observations are likewise aggregate. Redis reports the final output length 21,000 and zero source pending/lag.

The initial port-discovery failure is retained under `/private/tmp/sa-go-broker-performance-smoke-1`; no workload ran there. The corrected three-profile smoke gate (20 warmup/100 measured, window 8) passed under `/private/tmp/sa-go-broker-performance-smoke-2`. Neither smoke run supplies the measured table above. No SDK/model defects were found, and no SDK/model changes were made.

## Generated Python / TypeScript matrix

`interpreted.py` runs both runtimes across NATS Core/JetStream, Pulsar, Redis
Streams and RabbitMQ, using the same official Go broker peers plus the existing
NATS peer. It accepts the retained fresh generated source trees listed in
`SOURCES`, installs only checked-in canonical user overlays, and compiles the
TypeScript application offline with the local pinned compiler. RabbitMQ runs the
provided final generated images directly. Other profiles reuse those images'
dependency/SDK layers with the appropriate generated application/configuration.
SDK sources inside each selected base image must match the current checkout;
a mismatch fails the gate. Immutable image IDs, source/overlay/compiled manifests,
compiler logs and SDK source manifests are retained. No SDK code or generated
wiring is patched. This is actual generated service execution, not handler calls.

```sh
python3 sa-python-dsl/examples/broker-performance/interpreted.py \
  --go /Users/sergeyalexeev/sdk/go1.26.4/bin/go \
  --artifacts /private/tmp/sa-python-ts-broker-performance-RUN \
  --warmup 500 --count 5000 --inflight 8 --timeout 120
```

Each service has one CPU/512 MiB; peer cgroups are separate. NATS uses UUID
subjects/streams on the existing official broker. Core output receipt is checked,
but Core has no ACK, persistence or replay claim. JetStream requires input
PubAcks, output stream growth and zero pending/ACK-pending with advanced source
ACK floor. Other brokers retain the exact observation semantics above. The NATS
peer's optional URL/subject/stream/metric-port/uppercase-wire settings leave its
accepted Go defaults unchanged. No accepted Go measurement is rerun.

Python/TypeScript allocation counts are unavailable through the existing exporter
and are explicitly null. Process metrics and cgroup CPU/current/peak memory remain
available; no instrumentation hooks or synthetic allocation estimates are added.
Memory peak is cumulative over the service's warmup/measurement lifetime (including
both NATS profiles when they share a process). Shared-broker limits still apply.

## Python / TypeScript measured evidence (2026-11-18)

Eight profiles passed without the failures below. TypeScript RabbitMQ passed a repeat but has an unresolved admission-overflow failure; TypeScript Redis failed clean shutdown. The complete ten-profile gate is **not passed**.

Parameters: 500 separate warmup records, eight in flight, 50,000 measured Core/Redis records and 5,000 for other profiles. Initial phase deadline 180 seconds. Linux ARM64, one service CPU/512 MiB. Allocation counts unavailable (null). These are shared-broker samples, not capacity rankings.

| Runtime | Profile | Records/s | p50 / p95 / p99 ms | Process CPU % | Lifetime cgroup peak MiB |
|---|---|---:|---|---:|---:|
| python | core | 3401.69 | 2.278 / 2.738 / 3.639 | 99.87 | 83.78 |
| python | jetstream | 1992.54 | 3.824 / 5.394 / 6.889 | 90.84 | 83.78 |
| python | pulsar | 370.54 | 21.957 / 24.167 / 33.159 | 18.01 | 100.53 |
| python | redis-streams | 1975.34 | 3.529 / 6.529 / 9.199 | 86.30 | 102.02 |
| python | rabbitmq | 63.66 | 124.025 / 145.880 / 155.429 | 6.70 | 241.93 |
| typescript | core | 10029.29 | 0.733 / 1.188 / 1.765 | 85.79 | 83.40 |
| typescript | jetstream | 3524.89 | 1.797 / 4.800 / 7.467 | 71.27 | 84.70 |
| typescript | pulsar | 526.13 | 11.242 / 22.839 / 24.085 | 35.17 | 93.51 |
| typescript | rabbitmq (repeat only) | 1494.31 | 4.963 / 8.805 / 21.145 | 40.77 | 135.34 |

Raw evidence roots (each contains results.json, native peer logs, generated/overlay/
compiled identities, service logs, resource snapshots and cleanup evidence):

- `/private/tmp/sa-python-ts-broker-performance-final-1`: eight passing profiles;
  TypeScript Redis measured phase timed out at 180 seconds.
- `/private/tmp/sa-python-ts-broker-performance-final-2`: Redis extended 300-second
  workload bound validated all 50,000 outputs (287.13/s), but failed the unchanged
  15-second shutdown deadline (exit137, not OOM). Not an accepted performance gate.
- `/private/tmp/sa-python-ts-broker-performance-final-3`: Rabbit admission failure.
- `/private/tmp/sa-python-ts-broker-performance-final-4`: Rabbit diagnostic repeat
  passed with the same immutable service image; initial failure remains open.
- `/private/tmp/sa-python-ts-broker-performance-smoke-2`: all ten small smoke cases
  passed; not a substitute for the measured workload.

See [Redis lifetime finding](typescript-redis-lifetime.md) and
[RabbitMQ admission finding](typescript-rabbitmq-admission.md). No SDK fixes were
made. Historical failed reports can retain an individual row marked `running`
when the top-level result is `failed`; neither is acceptance evidence. The runner
now marks the interrupted row failed. No owned `sa-perf-*` containers remained
after final cleanup.

Pinned base/generated Rabbit image identities:

- Python: `sha256:9ea07550ed944f9d0b77dbd999aad3694e4777676a57b672320a6f557bed50f9`.
- TypeScript: `sha256:03ab28720fc9486143cdbdd28f0efff4e0ecce0835d08dd8e51eb73dbde60ec9`.

Each report records derived image IDs and exact source manifests. Base application
identity logs retain configuration/application hashes and runtime versions;
SDK module source comparison found no differences against the local checkout.
To reproduce the initial measured block, use the command above with
`--fast-count 50000 --timeout 180`. Select `--languages typescript --brokers
redis-streams` or `rabbitmq` for scoped follow-up; do not repeat accepted Go runs.

## SDK-owned follow-up

[Source lifetime repair and final evidence](typescript-source-lifetime-fix.md):
Redis, RabbitMQ and Pulsar passed the unchanged generated workloads on rebuilt
current SDK images. Redis's prior shutdown failure is repaired. RabbitMQ's native
credit-control gap remains independently demonstrated and open. The historical
failed samples above are retained; passing repeats do not erase them. The runner's
`--rebuild-typescript-sdk` option records fresh SDK build/source/dist identities
without changing generated application wiring or installed native dependencies.
