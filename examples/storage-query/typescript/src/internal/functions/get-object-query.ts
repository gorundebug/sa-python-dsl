import { Readable } from "node:stream";
/** User-owned Query implementation. The generator preserves this file. */
import type { Collector, MessageContext, RuntimeEnvironment, Stream } from "@gorundebug/tsservicelib/runtime/graph";
import type { BeginRequest } from "@gorundebug/tsservicelib/dataquery";
import type { GetObjectHandler } from "@gorundebug/tsservicelib/dataquery/s3aws";
import type { GetObjectCommandInput, GetObjectCommandOutput } from "@aws-sdk/client-s3";

import type { StorageRequest, StorageResult } from "#internal/types/index.generated.js";

/** Define the per-request state here. */
import { finish, type HandlerState } from "./query-state.js";

/** Build and execute GetObject using the connector's native request contract. Use the supplied context and maker-owned shared client. Map native results to StorageResult, preserving RequestID. EndRequest emits Kind=completed only on success; failures go to the error collector. Never retry unknown writes or partial output. No schema/bucket creation. */
export class GetObjectQuery implements GetObjectHandler<HandlerState, StorageRequest, StorageResult, Error> {
  public beginRequest(context: MessageContext, stream: Stream): BeginRequest<HandlerState> {
    void stream;
    return { context, state: { requestId: "" } };
  }

  public buildRequest(context: MessageContext, state: HandlerState, value: StorageRequest): GetObjectCommandInput {
    state.requestId = value.requestId;
    return { Bucket: "query-example", Key: value.key };
  }

  /** Consume native response resources within this call; do not retain them. */
  public async handleResult(context: MessageContext, state: HandlerState, result: GetObjectCommandOutput, out: Collector<StorageResult>): Promise<void> {
    if (!(result.Body instanceof Readable)) throw new Error("Expected a Node S3 response body");
    for await (const chunk of result.Body) {
      context.signal().throwIfAborted();
      await out.out(context, { requestId: state.requestId, kind: "object", value: Buffer.from(chunk) });
    }
  }

  /** Map errors and optionally emit application completion through out. */
  public async endRequest(context: MessageContext, stream: Stream, state: HandlerState | undefined, error: Error | undefined, out: Collector<StorageResult>, errors: Collector<Error>): Promise<void> {
    void stream;
    await finish(context, state, error, out, errors);
  }
}

export function makeGetObjectQuery(context: MessageContext, environment: RuntimeEnvironment): Promise<GetObjectQuery> {
  void context; void environment;
  return Promise.resolve(new GetObjectQuery());
}
