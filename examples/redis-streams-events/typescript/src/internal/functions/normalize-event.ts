/** User-owned function implementation. The generator preserves this file. */

import type {
  Collector,
  MessageContext,
  RuntimeEnvironment,
  Stream,
} from "@gorundebug/tsservicelib/runtime/graph";
import type {
  MapFunction,
} from "@gorundebug/tsservicelib/transformation";

import type { Event } from "#internal/types/index.generated.js";

/** Preserve Event.ID and normalize Event.Value. One input produces one event; no broker I/O. */
export class NormalizeEvent implements MapFunction<Event, Event> {
  public map(context: MessageContext, stream: Stream, value: Readonly<Event>, out: Collector<Event>): void | Promise<void> {
    void stream;
    return out.out(context, {ID: value.ID, Value: value.Value.trim().toUpperCase()});
  }
}

/** Construct NormalizeEvent asynchronously while the service graph is initialized. */
export function makeNormalizeEvent(
  context: MessageContext,
  environment: RuntimeEnvironment,
): Promise<NormalizeEvent> {
  void context; void environment;
  return new Promise((resolve) => {
    resolve(new NormalizeEvent());
  });
}
