/** User-owned endpoint implementation. The generator preserves this file. */

import type {
  MessageContext,
  RuntimeEnvironment,
  StreamContext,
} from "@gorundebug/tsservicelib/runtime/graph";
import type {
  ConsumerMessage,
  EndpointHandler as RabbitMQSourceEndpointHandler,
  ResultContext as RabbitMQResultContext,
} from "@gorundebug/tsservicelib/datasource/rabbitmq";

import type { Event, PublicationOutcome } from "#internal/types/index.generated.js";

export type ReceiveEventSourceHandlerState = undefined;

/** Decode Event from native message bytes. Register the result callback before Collect; keep the supplied context and correlate by Event.ID. On outcome, ACK only a confirmed successful publication; NAK publication failures. A missing ACK can cause redelivery; processing must be idempotent. Call Done after handling the outcome. Done itself never ACKs. */
export class ReceiveEventSource implements RabbitMQSourceEndpointHandler<ReceiveEventSourceHandlerState, Event, PublicationOutcome, Error> {


  public onError(context: MessageContext, stream: StreamContext<Event, PublicationOutcome, Error>, error: Error): void | Promise<void> {
    // Transport errors have no message state and do not select retry policy.
    process.stderr.write(`source error: ${error.stack}\n`);
    return stream.errorCollect(context, error);
  }

  public beginRequest(context: MessageContext, _stream: StreamContext<Event, PublicationOutcome, Error>): { readonly context: MessageContext; readonly state: ReceiveEventSourceHandlerState } {
    return { context, state: undefined };
  }

  public consumeMessage(context: MessageContext, stream: StreamContext<Event, PublicationOutcome, Error>, _state: ReceiveEventSourceHandlerState, message: ConsumerMessage, result: RabbitMQResultContext<ReceiveEventSourceHandlerState, Event, PublicationOutcome, Error>): void | Promise<void> {
    const event = JSON.parse(Buffer.from((message.message.body as {content?: Uint8Array}).content ?? message.message.body as Uint8Array).toString("utf8")) as Event;
    if (typeof event.ID !== "string" || typeof event.Value !== "string") throw new Error("Invalid event");
    result.setResultCallback(event.ID, async (_context, _stream, _state, outcome) => {
      if (outcome.Accepted) await message.accept(); else await message.release();
      process.stdout.write(JSON.stringify(outcome) + "\n");
      result.done();
      return true;
    });
    return stream.collect(context, event);
  }

  public getMessageId(context: MessageContext, stream: StreamContext<Event, PublicationOutcome, Error>, _state: ReceiveEventSourceHandlerState, value: Readonly<PublicationOutcome>): string {
    return value.EventID;
  }

  public endRequest(_context: MessageContext, _stream: StreamContext<Event, PublicationOutcome, Error>, error: Error | undefined, _state: ReceiveEventSourceHandlerState): void { if (error) process.stderr.write(`request error: ${error.stack}\n`); }
}

/** Construct ReceiveEventSource asynchronously while the service graph is initialized. */
export function makeReceiveEventSource(
  _context: MessageContext,
  _environment: RuntimeEnvironment,
): Promise<ReceiveEventSource> {
  return new Promise((resolve) => {
    resolve(new ReceiveEventSource());
  });
}
