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

export type ReceiveDurableEventSourceHandlerState = undefined;

/** Decode Event from native message bytes. Register the result callback before Collect; keep the supplied context and correlate by Event.ID. On outcome, ACK only a confirmed successful publication; NAK publication failures. A missing ACK can cause redelivery; processing must be idempotent. Call Done after handling the outcome. Done itself never ACKs. */
export class ReceiveDurableEventSource implements NATSSourceEndpointHandler<ReceiveDurableEventSourceHandlerState, Event, PublicationOutcome, Error> {


  public onError(context: MessageContext, stream: StreamContext<Event, PublicationOutcome, Error>, error: Error): void | Promise<void> {
    // Transport errors have no message state and do not select retry policy.
    process.stderr.write(`source error: ${error.stack}\n`);
    return stream.errorCollect(context, error);
  }

  public beginRequest(context: MessageContext, _stream: StreamContext<Event, PublicationOutcome, Error>): { readonly context: MessageContext; readonly state: ReceiveDurableEventSourceHandlerState } {
    return { context, state: undefined };
  }

  public consumeMessage(context: MessageContext, stream: StreamContext<Event, PublicationOutcome, Error>, _state: ReceiveDurableEventSourceHandlerState, message: ConsumerMessage, result: NATSResultContext<ReceiveDurableEventSourceHandlerState, Event, PublicationOutcome, Error>): void | Promise<void> {
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

  public getMessageId(context: MessageContext, stream: StreamContext<Event, PublicationOutcome, Error>, _state: ReceiveDurableEventSourceHandlerState, value: Readonly<PublicationOutcome>): string {
    return value.EventID;
  }

  public endRequest(_context: MessageContext, _stream: StreamContext<Event, PublicationOutcome, Error>, error: Error | undefined, _state: ReceiveDurableEventSourceHandlerState): void { if (error) process.stderr.write(`request error: ${error.stack}\n`); }
}

/** Construct ReceiveDurableEventSource asynchronously while the service graph is initialized. */
export function makeReceiveDurableEventSource(
  _context: MessageContext,
  _environment: RuntimeEnvironment,
): Promise<ReceiveDurableEventSource> {
  return new Promise((resolve) => {
    resolve(new ReceiveDurableEventSource());
  });
}
