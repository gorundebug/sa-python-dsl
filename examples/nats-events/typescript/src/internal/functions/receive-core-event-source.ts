/** User-owned endpoint implementation. The generator preserves this file. */

import type {
  MessageContext,
  RuntimeEnvironment,
  StreamContext,
} from "@gorundebug/tsservicelib/runtime/graph";
import type {
  ConsumerMessage,
  EndpointHandler as NATSSourceEndpointHandler,
  ResultContext as NATSResultContext,
} from "@gorundebug/tsservicelib/datasource/nats";

import type { Event, PublicationOutcome } from "#internal/types/index.generated.js";

export type ReceiveCoreEventSourceHandlerState = undefined;

/** Decode Event from native message bytes. Register the result callback before Collect; keep the supplied context and correlate by Event.ID. On outcome, record local publication acceptance or failure; Core has no ACK or replay. Call Done after handling the outcome. Done itself never ACKs. */
export class ReceiveCoreEventSource implements NATSSourceEndpointHandler<ReceiveCoreEventSourceHandlerState, Event, PublicationOutcome, Error> {


  public onError(context: MessageContext, stream: StreamContext<Event, PublicationOutcome, Error>, error: Error): void | Promise<void> {
    // Transport errors have no message state and do not select retry policy.
    process.stderr.write(`source error: ${error.stack}\n`);
    return stream.errorCollect(context, error);
  }

  public beginRequest(context: MessageContext, _stream: StreamContext<Event, PublicationOutcome, Error>): { readonly context: MessageContext; readonly state: ReceiveCoreEventSourceHandlerState } {
    return { context, state: undefined };
  }

  public consumeMessage(context: MessageContext, stream: StreamContext<Event, PublicationOutcome, Error>, _state: ReceiveCoreEventSourceHandlerState, message: ConsumerMessage, result: NATSResultContext<ReceiveCoreEventSourceHandlerState, Event, PublicationOutcome, Error>): void | Promise<void> {
    const event = JSON.parse(new TextDecoder().decode(message.message.data)) as Event;
    if (typeof event.ID !== "string" || typeof event.Value !== "string") throw new Error("Invalid event");
    result.setResultCallback(event.ID, (_context, _stream, _state, outcome) => {
      if (outcome.Accepted) message.jetstream?.ack(); else message.jetstream?.nak();
      process.stdout.write(JSON.stringify(outcome) + "\n");
      result.done();
      return true;
    });
    return stream.collect(context, event);
  }

  public getMessageId(context: MessageContext, stream: StreamContext<Event, PublicationOutcome, Error>, _state: ReceiveCoreEventSourceHandlerState, value: Readonly<PublicationOutcome>): string {
    return value.EventID;
  }

  public endRequest(_context: MessageContext, _stream: StreamContext<Event, PublicationOutcome, Error>, error: Error | undefined, _state: ReceiveCoreEventSourceHandlerState): void { if (error) process.stderr.write(`request error: ${error.stack}\n`); }
}

/** Construct ReceiveCoreEventSource asynchronously while the service graph is initialized. */
export function makeReceiveCoreEventSource(
  _context: MessageContext,
  _environment: RuntimeEnvironment,
): Promise<ReceiveCoreEventSource> {
  return new Promise((resolve) => {
    resolve(new ReceiveCoreEventSource());
  });
}
