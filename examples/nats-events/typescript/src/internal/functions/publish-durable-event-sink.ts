/** User-owned endpoint implementation. The generator preserves this file. */

import type {
  MessageContext,
  RuntimeEnvironment,
} from "@gorundebug/tsservicelib/runtime/graph";
import type {
  EndpointHandler as NATSSinkEndpointHandler,

  SinkMessage,
  StreamContext as NATSSinkStreamContext,
} from "@gorundebug/tsservicelib/datasink/nats";

import type { Event, PublicationOutcome } from "#internal/types/index.generated.js";

export type PublishDurableEventSinkHandlerState = undefined;

/** Encode Event and publish through the native endpoint. Emit exactly one PublicationOutcome for each event, preserving EventID and the caller context. Use asynchronous publication with its callback; represent failed or unknown delivery as Accepted=false with a reason. Do not open a second broker client. */
export class PublishDurableEventSink implements NATSSinkEndpointHandler<PublishDurableEventSinkHandlerState, Event, PublicationOutcome, Error> {
  public getStreamId(context: MessageContext, value: Readonly<Event>): string { return context.streamId() ?? value.ID; }


  public beginRequest(context: MessageContext, _stream: NATSSinkStreamContext<Event, PublicationOutcome, Error>): { readonly context: MessageContext; readonly state: PublishDurableEventSinkHandlerState } {
    return { context, state: undefined };
  }

  public consumeMessage(context: MessageContext, _stream: NATSSinkStreamContext<Event, PublicationOutcome, Error>, _state: PublishDurableEventSinkHandlerState, value: Readonly<Event>, message: SinkMessage<PublicationOutcome>): void {
    message.data = new TextEncoder().encode(JSON.stringify(value));
    message.send(context, (_delivery, error) => ({EventID: value.ID, Accepted: error === undefined, Reason: error?.message ?? ""}));
  }

  public endRequest(context: MessageContext, _stream: NATSSinkStreamContext<Event, PublicationOutcome, Error>, _error: Error | undefined, _state: PublishDurableEventSinkHandlerState): void {}
}

/** Construct PublishDurableEventSink asynchronously while the service graph is initialized. */
export function makePublishDurableEventSink(
  _context: MessageContext,
  _environment: RuntimeEnvironment,
): Promise<PublishDurableEventSink> {
  return new Promise((resolve) => {
    resolve(new PublishDurableEventSink());
  });
}
