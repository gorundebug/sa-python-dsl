/** User-owned Query implementation. The generator preserves this file. */
import type { Collector, MessageContext, RuntimeEnvironment, Stream } from "@gorundebug/tsservicelib/runtime/graph";
import type { BeginRequest } from "@gorundebug/tsservicelib/dataquery";
import type { ExecuteHandler } from "@gorundebug/tsservicelib/dataquery/postgresqlkysely";
import type { CompiledQuery, Kysely, QueryResult } from "kysely";

import type { StorageRequest, StorageResult } from "#internal/types/index.generated.js";

/** Define the database tables, selected row and per-request state here. */
import type { Database } from "./query-state.js";
export type { Database } from "./query-state.js";
type Row = import("kysely").InsertResult;
import { finish, type HandlerState } from "./query-state.js";

/** Build and execute Execute using the connector's native request contract. Use the supplied context and maker-owned shared client. Map native results to StorageResult, preserving RequestID. EndRequest emits Kind=completed only on success; failures go to the error collector. Never retry unknown writes or partial output. No schema/bucket creation. */
export class ExecuteQuery implements ExecuteHandler<Database, HandlerState, StorageRequest, Row, StorageResult, Error> {
  public beginRequest(context: MessageContext, stream: Stream): BeginRequest<HandlerState> {
    void stream;
    return { context, state: { requestId: "" } };
  }

  public buildQuery(context: MessageContext, state: HandlerState, value: StorageRequest, db: Kysely<Database>): CompiledQuery<Row> {
    state.requestId = value.requestId;
    return db.insertInto("query_example_items").values({ key: value.key, value: value.value })
      .onConflict((conflict) => conflict.column("key").doUpdateSet({ value: value.value })).compile();
  }
  public async handleResult(context: MessageContext, state: HandlerState, result: QueryResult<Row>, out: Collector<StorageResult>): Promise<void> {
    await out.out(context, { requestId: state.requestId, kind: "command", value: Buffer.from(String(result.numAffectedRows ?? 0n)) });
  }

  /** Map errors and optionally emit application completion through out. */
  public async endRequest(context: MessageContext, stream: Stream, state: HandlerState | undefined, error: Error | undefined, out: Collector<StorageResult>, errors: Collector<Error>): Promise<void> {
    void stream;
    await finish(context, state, error, out, errors);
  }
}

export function makeExecuteQuery(context: MessageContext, environment: RuntimeEnvironment): Promise<ExecuteQuery> {
  void context; void environment;
  return Promise.resolve(new ExecuteQuery());
}
