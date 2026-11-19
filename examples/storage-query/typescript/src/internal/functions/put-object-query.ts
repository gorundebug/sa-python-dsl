/** User-owned Query implementation. The generator preserves this file. */
import type { Collector, MessageContext, RuntimeEnvironment, Stream } from "@gorundebug/tsservicelib/runtime/graph";
import type { BeginRequest } from "@gorundebug/tsservicelib/dataquery";
import type { PutObjectHandler } from "@gorundebug/tsservicelib/dataquery/s3aws";
import type { PutObjectCommandInput, PutObjectCommandOutput } from "@aws-sdk/client-s3";

import type { StorageRequest, StorageResult } from "#internal/types/index.generated.js";

/** Define the per-request state here. */
import { finish, type HandlerState } from "./query-state.js";

/** Build and execute PutObject using the connector's native request contract. Use the supplied context and maker-owned shared client. Map native results to StorageResult, preserving RequestID. EndRequest emits Kind=completed only on success; failures go to the error collector. Never retry unknown writes or partial output. No schema/bucket creation. */
export class PutObjectQuery implements PutObjectHandler<HandlerState, StorageRequest, StorageResult, Error> {
  public beginRequest(context: MessageContext, stream: Stream): BeginRequest<HandlerState> {
    void stream;
    return { context, state: { requestId: "" } };
  }

  public buildRequest(context: MessageContext, state: HandlerState, value: StorageRequest): PutObjectCommandInput {
    state.requestId = value.requestId;
    return { Bucket: "query-example", Key: value.key, Body: value.value };
  }

  /** Consume native response resources within this call; do not retain them. */
  public async handleResult(context: MessageContext, state: HandlerState, result: PutObjectCommandOutput, out: Collector<StorageResult>): Promise<void> {
    await out.out(context, { requestId: state.requestId, kind: "command", value: Buffer.from(result.ETag ?? "") });
  }

  /** Map errors and optionally emit application completion through out. */
  public async endRequest(context: MessageContext, stream: Stream, state: HandlerState | undefined, error: Error | undefined, out: Collector<StorageResult>, errors: Collector<Error>): Promise<void> {
    void stream;
    await finish(context, state, error, out, errors);
  }
}

export function makePutObjectQuery(context: MessageContext, environment: RuntimeEnvironment): Promise<PutObjectQuery> {
  void context; void environment;
  return Promise.resolve(new PutObjectQuery());
}
