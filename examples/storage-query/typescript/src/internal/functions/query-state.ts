import type { Collector, MessageContext } from "@gorundebug/tsservicelib/runtime/graph";
import type { StorageResult } from "#internal/types/index.generated.js";

export interface HandlerState { requestId: string }
export interface Database { query_example_items: { key: string; value: Uint8Array } }

export async function finish(context: MessageContext, state: HandlerState | undefined,
  error: Error | undefined, out: Collector<StorageResult>, errors: Collector<Error>): Promise<void> {
  if (error !== undefined) { await errors.out(context, error); return; }
  if (state === undefined) throw new Error("Successful Query has no request state");
  await out.out(context, { requestId: state.requestId, kind: "completed", value: new Uint8Array() });
}
