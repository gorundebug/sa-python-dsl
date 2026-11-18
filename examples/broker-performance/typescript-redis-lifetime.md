# TypeScript Redis performance/shutdown defect (SDK unchanged)

> Follow-up: [SDK lifetime repair and final rebuilt-image evidence](typescript-source-lifetime-fix.md). Redis shutdown is repaired; Rabbit native credit control remains open. Historical evidence below is preserved.

The generated TypeScript Redis canonical service did not pass the full bounded
performance gate. This is not hidden by a smaller workload or longer Stop.

## Native evidence

- `/private/tmp/sa-python-ts-broker-performance-final-1/typescript-redis-streams/`:
  500 warmup records passed; the 50,000-record phase hit its 180-second deadline.
  The service log ends around measurement ID 49337, still publishing Accepted
  outputs. The peer timeout is retained; this failed run is not a throughput result.
- `/private/tmp/sa-python-ts-broker-performance-final-2/results.json` and
  `typescript-redis-streams/measure.log`: same source/image profile, 300-second
  workload bound. All 50,000 normalized outputs and unique Redis IDs validated;
  source pending/lag were zero and output length was 50,500. Measurement took
  174.137 seconds (287.13 records/s), process CPU about 99.90% of one CPU.
  p50/p95/p99 were 25.494/63.503/111.243 ms. Cgroup peak was 156,377,088 bytes.
- That second run failed the unchanged 15-second graceful-stop gate: service
  `ExitCode=137`, `OOMKilled=false`. Both state and resource evidence are retained.
  Owned keys/containers were cleaned up. No shared broker restart or SDK edit.

## Concrete retention finding

`tsservicelib/src/datasource/redisstreams/index.ts:217` creates
`owner.withExternalCancellation(this.#generation.signal)` for every record.
Both parent signals live for the entire source generation. `Context` eagerly
combines them (`src/runtime/context.ts:187`), adding listeners to both parents.
`combineAbortSignals` (`src/runtime/context.ts:89`) removes those listeners only
when one of those parents aborts.

The per-request cancellation controller in `handle` is downstream of that
intermediate generation context. Finalizing/aborting the request removes child
listeners but does not abort or dispose the per-record intermediate context.
Thus each completed record leaves two parent listeners until generation stop.
This is unbounded retained source-lifetime bookkeeping, even with bounded
in-flight messages and successful per-request cleanup.

Reproducible read-only diagnosis against the actual Node 24.19.0 runtime image:

```sh
docker run --rm \
  -v "$PWD/sa-python-dsl/examples/broker-performance/redis-context-lifetime-probe.mjs:/probe.mjs:ro" \
  --entrypoint node sha256:03ab28720fc9486143cdbdd28f0efff4e0ecce0835d08dd8e51eb73dbde60ec9 /probe.mjs
```

`/private/tmp/sa-python-ts-broker-performance-final-1/redis-context-lifetime.log`
shows 1/128/1024 completed requests retaining 1/128/1024 listeners on EACH
parent. Aborting the generation removes them all. The probe uses the actual
public Context implementation; it is a lifetime assertion, not a substitute
for generated-service timing. Diagnostic warning suppression in that probe
changes no SDK behavior or listener counts; native performance runs use the
unmodified SDK/image.

This retention is consistent with throughput degradation and costly shutdown,
but no CPU-profile attribution or claim that it explains every timing variance
is made. Shared broker conditions remain a limitation.

## Suggested SDK-owned follow-up (not implemented here)

Use one retained combined owner/generation context per generation, or ensure
per-delivery parent bindings are retired with the delivery. Preserve epoch
fencing and cancellation propagation; do not change public interfaces, weaken
fences, add arbitrary limits or increase the stop timeout. Add a regression
asserting parent listener count remains bounded after many completed requests,
then rerun only this generated Redis profile and affected lifecycle tests.
Performance harness ownership does not authorize editing the SDK in this block.

The two Redis generated images have distinct build identities (retained in the
reports), but their implemented-source and compiled-output manifests are exactly
equal. Both use the same verified SDK base image:
`sha256:03ab28720fc9486143cdbdd28f0efff4e0ecce0835d08dd8e51eb73dbde60ec9`.
Initial generated image:
`sha256:9f5da875ffffee8538c0aeb9541c38e5306385b3df62dd2b062bc10b1d1fe175`.
Extended-bound image:
`sha256:0e41822b6581e55be960b60d4c0e17d6f577454e7087c7830fa511704fe45932`.
No source/SDK change explains the difference between these two measurements.
