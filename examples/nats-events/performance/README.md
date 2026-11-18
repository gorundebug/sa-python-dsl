# Generated Go NATS one-CPU performance acceptance

`run.py` exports the existing `project.py`, validates and freshly generates its
canonical service through ServiceGen, applies the unchanged `go/` user overlays,
and compiles the real `cmd/service`. It never measures an SDK stub or calls
business handlers directly. The peer uses official nats.go, already pinned by the
SDK. No SDK or typed model changes are made.

Run from any directory (Docker and the project Go/Python toolchains required):

```sh
python3 sa-python-dsl/examples/nats-events/performance/run.py \
  --artifacts /private/tmp/sa-go-nats-performance-unique \
  --go /Users/sergeyalexeev/sdk/go1.26.4/bin/go \
  --core-count 500000 --jetstream-count 50000 --warmup 2000 \
  --inflight 32 --phase-timeout 60 --platform linux/arm64
```

Use a fresh artifact directory. `--count` defaults to a short 5000-record smoke
run; the per-protocol overrides above provide a longer acceptance sample. Bounds:
one million measured messages per mode, 100000 warmup messages, at most256 in
flight, and at most300 seconds per phase. Each command also has a finite timeout.
Failure, missing/invalid/duplicate output, missing confirmation or resource-limit
mismatch fails the run. There is no invented universal throughput/latency SLA.

## What is measured

- Separate warmup and measurement processes per protocol; warmup is never folded
  into measured throughput or percentiles. The generated service stays alive.
- Closed-loop fixed concurrency. Each slot publishes an event and waits for the
  matching normalized output, decoding the Event JSON fields and exact
  `HELLO PERFORMANCE`. No open-loop rate target or coordinated-omission correction.
- Round-trip samples use the peer's monotonic clock, immediately before native
  input publication through output reception. Samples include JSON, native/client
  queues, broker routing and the generated receive/map/sink graph. Percentiles
  use the sorted sample at floor((N-1)*p). Maximum outstanding IDs and native
  publication futures are bounded by the requested window.
- Core input uses native Publish and the canonical async output callback reports
  local acceptance. Correlated output reception proves the tested round trip;
  it is not a broker ACK, durable delivery or replay guarantee.
- JetStream input uses native PublishAsync/PubAck. The canonical output handler
  awaits its own PubAck through the async result callback, then the canonical
  source calls DoubleAck. After the output sample window, the peer verifies exact
  output stream growth, zero pending/ACK-pending input messages, and a consumer
  ACK floor covering every warmup/measured record. `settled_seconds` includes that
  final barrier; output latency alone does not prove source ACK completion.

## Resources and telemetry

The generated service runs with Docker `--cpus=1`, `--memory=512m` and
`GOMAXPROCS=1`. Both Docker NanoCpus and actual cgroup v2 `cpu.max` are checked.
This is one CPU of quota, not pinning/exclusivity to one physical core. Broker and
peer each have separate two-CPU quotas. Broker memory512MiB; peer memory256MiB.
All share only a unique test-owned `--network none` broker network namespace;
there are no host ports or shared-broker restarts. JetStream uses the isolated
broker's ephemeral writable-layer file storage, not a production replicated disk.

The service retains normal metrics; logs/tracing use the existing noop settings.
The peer scrapes actual service Prometheus counters before/after each phase:
`process_cpu_seconds_total`, `go_memstats_mallocs_total`, and
`go_memstats_alloc_bytes_total`. Missing metrics are JSON null, never estimates.
Allocation deltas per message include normal runtime/background and scrape work;
these are not per-handler allocation microbenchmarks. Process CPU percentage uses
that counter delta over the settled phase duration (collector timing/rounding is
visible on short phases).

Cgroup CPU delta and its separate observation-window duration cover peer container
startup/exit and the small resource-reader exec overhead as well as load. They
must not be divided by only the shorter round-trip window. `memory.current` and
`memory.peak` are real cgroup observations; peak is cumulative service lifetime,
not reset between phases. Docker stats is a post-phase snapshot, not load-average
CPU. Raw metric snapshots/cgroup values remain in results.json.

Artifacts retain model YAML, original generated ZIP (extracted with archive file
modes), generated service plus overlays, go.work, static binaries, image build,
phase reports, service/broker logs, image IDs, CPU/memory configuration and clean
shutdown status. Normal completion requires service SIGTERM exit0 without OOM.
A finally block removes only owned containers. The uniquely tagged local image
is intentionally retained for review; no release/push happens. Other host loads,
Docker VM scheduling, filesystem cache, and the canonical serial-per-endpoint
source profile affect results; one sample does not establish production capacity.

## Recorded run

2026-11-18, native linux/arm64 on Docker Desktop (LinuxKit6.12.76,
Docker29.5.3, VM18 CPUs). Authoritative artifacts:
`/private/tmp/sa-go-nats-performance-2/`, host log
`/private/tmp/sa-go-nats-performance-2.log`. The earlier `-1` directory is the
5000-record smoke run, not the longer performance sample.

| Mode | Measured records | Seconds | msg/s | p50 ms | p95 ms | p99 ms | Process CPU % | allocations/msg | allocated bytes/msg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Core | 500000 | 6.949 | 71954 | 0.358 | 0.769 | 1.174 | 79.87 | 86.02 | 6441.44 |
| JetStream | 50000 | 12.841 | 3894 | 8.101 | 12.200 | 18.401 | 39.33 | 152.09 | 10801.11 |

Warmup2000 each; in-flight32; timeout60s each. All normalized outputs matched;
no duplicate/unexpected outputs. JetStream input PubAcks50000 in measurement,
52000 total stored outputs and source ACK floor52000, zero pending/ACK-pending.
Service exited0 on SIGTERM, no OOM. Cgroup cpu.max was100000/100000 and memory
limit536870912 bytes. Cumulative cgroup memory peak14381056 bytes (13.71MiB);
post-measurement process RSS25714688 bytes Core /25804800 bytes JetStream.
RSS and charged cgroup memory are different accounting views, not interchangeable.
Cgroup-window average CPU was74.65% Core /38.33% JetStream; see the longer
resource observation windows and raw snapshots before comparing to process CPU.

The generated binary image is retained as `sa-nats-perf-8ed51f9b14cf:local`;
use `results.json`'s run_id/image_id as the authoritative image identity.
This recorded run predates canonical Go wire-field alignment to `ID`/`Value`.
The peer's Go decoder accepts both spellings; do not attribute this historical
binary's performance numbers to a subsequently rebuilt service.
No capacity maximum, production disk durability/replication, multi-runtime parity,
interactive IDE behavior or performance-regression threshold is established here.
