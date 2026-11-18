# TypeScript RabbitMQ intermittent admission failure

> Follow-up: [SDK lifetime repair and final rebuilt-image evidence](typescript-source-lifetime-fix.md). Redis shutdown is repaired; Rabbit native credit control remains open. Historical evidence below is preserved.

SDK and official client unchanged. The full generated image is
`sha256:03ab28720fc9486143cdbdd28f0efff4e0ecce0835d08dd8e51eb73dbde60ec9`.
Both attempts used 500 warmup, 5,000 measured records, eight in flight, one service
CPU, and a 180-second phase bound against UUID-owned queues/exchanges.

- `/private/tmp/sa-python-ts-broker-performance-final-3/results.json` failed.
  `typescript-rabbitmq/service.log` reports repeated `RabbitMQ source admission
  overflow; unsettled input will be redelivered`. The peer rejected an
  invalid/duplicate/unexpected output after 2,330 unique Accepted application
  result IDs. That old assertion does not identify which condition failed;
  do not call it proven duplicate delivery or malformed serialization.
- `/private/tmp/sa-python-ts-broker-performance-final-4/results.json` passed with
  more specific peer diagnostics and unchanged service/SDK. All 5,000 outputs
  validated, native input publication returned Accepted, both queue gauges
  reached ready/unacked zero, and service shutdown exited zero without OOM.
  It measured 1,494.31 records/s, p50/p95/p99 4.963/8.805/21.145 ms.
  This successful rerun does not explain or close the first failure.

`tsservicelib/src/internal/rabbitmq/worker.ts:24` derives a local unsettled-map
limit from consumerCredits (16 in this canonical config). Its createConsumer
call at line125 does not pass native credits. Exceeding that map bound at line147
fails the connection and causes unsettled input redelivery. A bounded local map
is not equivalent to native receive flow control.

Installed official `rabbitmq-amqp-js-client` 1.0.0
`src/consumer.ts:44` exposes QueueConsumerParams with source, preSettled and
messageHandler only. Consumer at line93 exposes start/close/id/replyTo; its
receiverLink is private. The inspected receiver configuration does not expose
credit_window. There is no supported public per-consumer credit control visible
in this version's API. Investigate official supported flow-control capability
before proposing a fix; do not reach into private links, patch upstream, silently
increase limits, or introduce an alternative transport.

At-least-once delivery can legally duplicate after connection loss. The benchmark
rejects duplicate workload outputs to flag a failed uninterrupted load gate; it
is not an exactly-once contract. The self-induced admission overflow remains a
separate actionable suitability issue despite the successful repeat. Both raw
attempts and cleanup logs are retained; shared brokers were not restarted.
