# TypeScript source cancellation lifetime repair (2026-11-18)

The Redis generated workload and shutdown failure is repaired. RabbitMQ's shared
cancellation-lifetime defect is repaired, but its independent native flow-control
limitation remains open. No workload, admission limit, stop budget, native outcome
assertion or public interface was weakened.

## Implementation and invariants

- Redis Streams, RabbitMQ and Pulsar sources now retain one joined owner/generation
  Context. Reconnect aborts the old generation before creating the replacement.
  Each request still has its own cancellation owner; old delivery handles retain
  their existing epoch fence. Stop still drains before aborting the source owner.
- `src/runtime/context.ts` uses stock `AbortSignal.any` where available. Node's
  native implementation tracks weak signal dependencies, avoiding strong listener
  retention in Kafka's per-record assignment/task joins as well. Retained contexts
  still observe the original parent cancellation reason; completion does not
  synthesize cancellation. No Kafka production file change was required.
- The existing portable implementation remains for isolates without native `any`.
  Tests explicitly disable native `any` and verify generation-abort cleanup.
  Native broker adapters execute in Node; no new native transport, reactor, public
  interface, queue or policy limit was added.
- NATS already joins each request to a request controller retired on completion;
  it did not have the additional per-record generation join. Its adapter is unchanged.

Primary evidence for Node's weak dependencies and finalizer cleanup:
[Node 24.19.0 abort_controller.js](https://github.com/nodejs/node/blob/v24.19.0/lib/internal/abort_controller.js).
The code uses the public API only, not Node internal symbols.

## Regression evidence

Tests observe actual Context and MessageContext parent abort listeners. Each
source processes 1,024 completed records, explicitly settles native messages and
asserts retained listeners remain bounded, then stops under the existing deadline.
The observer is test-only and does not alter cancellation signals or SDK behavior.

- Original immutable SDK image fails the Redis test at 128 records with **130**
  retained listeners: `/private/tmp/sa-ts-source-lifetime-baseline.log`.
- Original image fails the Kafka source regression with **1,024** retained
  listeners: `/private/tmp/sa-ts-source-lifetime-kafka-baseline.log`.
- Final image: **60 focused tests pass**, including Kafka source failure routing,
  retained-parent cancellation reasons, Context, task registry, stop budgets and
  Temporal context propagation: `/private/tmp/sa-ts-source-lifetime-final-context.log`.
- Redis final native gate: listener bound, reconnect/reclaim/stale ACK, explicit
  ACK drain, cancellation-resistant handler stop:
  `/private/tmp/sa-ts-source-lifetime-final-redis.log`.
- Rabbit final native gate: listener bound, reconnect/stale settlement, admitted
  handler drain, deterministic saturation preserving unsettled messages:
  `/private/tmp/sa-ts-source-lifetime-final-rabbit.log`.
- Pulsar final native gate: listener bound, source ACK drain, stop cancellation:
  `/private/tmp/sa-ts-source-lifetime-final-pulsar.log`.

TypeScript compilation passed. Focused Context/helper lint passed. An adapter-wide
lint attempt also reported the existing unused `_entry` source-metrics loop variable
in Redis; that unrelated line was not changed or presented as a clean whole-tree
lint gate. No broad native security suite or Kafka native broker rerun was performed;
Kafka evidence here is the actual source adapter with its existing fake transport.

## Actual generated-service acceptance

Reproduce the final block:

```sh
python3 sa-python-dsl/examples/broker-performance/interpreted.py \
  --go /Users/sergeyalexeev/sdk/go1.26.4/bin/go \
  --artifacts /private/tmp/sa-ts-source-lifetime-RUN \
  --languages typescript --brokers redis-streams rabbitmq pulsar \
  --rebuild-typescript-sdk \
  --warmup 500 --count 5000 --fast-count 50000 --inflight 8 --timeout 180
```

`--rebuild-typescript-sdk` compiles the local SDK, builds a local image replacing
only SDK source/dist in the pinned dependency image, retains the generated Rabbit
application unchanged, and builds other generated applications with their canonical
overlays. No install, package version change or upstream patch. Source and compiled
SDK manifests, base/derived image IDs, application identities and compiler logs are
retained in `/private/tmp/sa-ts-source-lifetime-performance-final/results.json` and
its sibling artifacts. All three profiles passed native output/settlement assertions
and unchanged 15-second graceful shutdown, exiting zero without OOM.

| Profile | Measured records | Records/s | p50 / p95 / p99 ms | Process CPU % | Cgroup peak MiB |
|---|---:|---:|---|---:|---:|
| Redis Streams | 50000 | 7337.26 | 0.716 / 1.325 / 9.072 | 99.66 | 126.30 |
| RabbitMQ | 5000 | 2970.72 | 2.480 / 3.955 / 6.164 | 91.87 | 139.76 |
| Pulsar | 5000 | 506.41 | 11.537 / 22.865 / 23.926 | 15.79 | 102.38 |

Each is a one-CPU service sample on unchanged shared brokers, not capacity or a
cross-broker ranking. Warmup is separate. Allocation counts remain unavailable.
No native tests ran concurrently with the final measured phases.

Immutable final SDK/Rabbit image:
`sha256:e7d45ee54c559f11160a9a5d004049c6f594176f7c070d5f474c5a6613a5f2af`.
Redis image:
`sha256:e8dfcc82d49a73b03b92875753109d841850992a0b701feda1063df29de3df43`.
Pulsar image:
`sha256:2fd946fb9fad420bd23e027f75683ad05f4e824bb9b7b15be782500f966c281b`.
Earlier adapter-only intermediate results remain under
`/private/tmp/sa-ts-source-lifetime-performance-1`; final evidence above includes
the Context fix and supersedes that intermediate SDK identity.

## RabbitMQ requirement still open

The official installed `rabbitmq-amqp-js-client` 1.0.0 exposes no receive credit
window or pause/resume control through Consumer, QueueConsumerParams, Connection
or EnvironmentParams. Native receiverLink is private. The configured
consumerCredits bounds the SDK's unsettled map, not the official native receiver.
See [the retained API/source investigation](typescript-rabbitmq-admission.md).

The deterministic native saturation test sets consumerCredits=1, holds the first
handler, and publishes a second message. Overflow remains observable; neither
message is ACKed, both are retained by the broker, and Stop remains bounded. Thus
fixing retained listeners improves the measured workload but cannot establish
native flow-control support. The earlier intermittent overflow is not declared
closed merely because the rebuilt 5,000-record canonical sample passed.

Resolving this requires an official supported credit-control capability. No private
receiver access, direct-rhea replacement, upstream modification, larger hidden
buffer or raised application limit was introduced. Shared broker/container/proxy
configuration was not changed. All resources used by these tests are UUID-owned.
