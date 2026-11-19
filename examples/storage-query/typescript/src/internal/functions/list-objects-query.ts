/** User-owned Query implementation. The generator preserves this file. */
import type { Collector, MessageContext, RuntimeEnvironment, Stream } from "@gorundebug/tsservicelib/runtime/graph";
import type { BeginRequest } from "@gorundebug/tsservicelib/dataquery";
import type { ListObjectsHandler } from "@gorundebug/tsservicelib/dataquery/s3aws";
import type { ListObjectsV2CommandInput, ListObjectsV2CommandOutput } from "@aws-sdk/client-s3";

import type { StorageRequest, StorageResult } from "#internal/types/index.generated.js";

/** Define the per-request state here. */
import { finish, type HandlerState } from "./query-state.js";

/** Build and execute ListObjects using the connector's native request contract. Use the supplied context and maker-owned shared client. Map native results to StorageResult, preserving RequestID. EndRequest emits Kind=completed only on success; failures go to the error collector. Never retry unknown writes or partial output. No schema/bucket creation. */
export class ListObjectsQuery implements ListObjectsHandler<HandlerState, StorageRequest, StorageResult, Error> {
  public beginRequest(context: MessageContext, stream: Stream): BeginRequest<HandlerState> {
    void stream;
    return { context, state: { requestId: "" } };
  }

  public buildRequest(context: MessageContext, state: HandlerState, value: StorageRequest): ListObjectsV2CommandInput {
    state.requestId = value.requestId;
    return { Bucket: "query-example", Prefix: value.key };
  }

  /** Consume native response resources within this call; do not retain them. */
  public async handleResult(context: MessageContext, state: HandlerState, result: ListObjectsV2CommandOutput, out: Collector<StorageResult>): Promise<void> {
    const entries = (result.Contents ?? []).map((item) => ({ key: item.Key, size: item.Size }));
    await out.out(context, { requestId: state.requestId, kind: "page", value: Buffer.from(JSON.stringify(entries)) });
  }

  /** Map errors and optionally emit application completion through out. */
  public async endRequest(context: MessageContext, stream: Stream, state: HandlerState | undefined, error: Error | undefined, out: Collector<StorageResult>, errors: Collector<Error>): Promise<void> {
    void stream;
    await finish(context, state, error, out, errors);
  }
}

export function makeListObjectsQuery(context: MessageContext, environment: RuntimeEnvironment): Promise<ListObjectsQuery> {
  void context; void environment;
  return Promise.resolve(new ListObjectsQuery());
}
