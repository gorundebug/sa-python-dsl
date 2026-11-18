/** User-owned endpoint implementation. The generator preserves this file. */

import type {
  MessageContext,
  RuntimeEnvironment,
} from "@gorundebug/tsservicelib/runtime/graph";
import type {
  EndpointHandler as RedisStreamsSinkEndpointHandler,

  SinkMessage,
  StreamContext as RedisStreamsSinkStreamContext,
} from "@gorundebug/tsservicelib/datasink/redisstreams";

import type { Event, PublicationOutcome } from "#internal/types/index.generated.js";

export type PublishEventSinkHandlerState = undefined;

/** Encode Event and publish through the native endpoint. Emit exactly one PublicationOutcome for each event, preserving EventID and the caller context. Use asynchronous publication with its callback; represent failed or unknown delivery as Accepted=false with a reason. Do not open a second broker client. */
export class PublishEventSink implements RedisStreamsSinkEndpointHandler<PublishEventSinkHandlerState, Event, PublicationOutcome, Error> {
  public getStreamId(context: MessageContext, value: Readonly<Event>): string { return context.streamId() ?? value.ID; }


  public beginRequest(context: MessageContext, _stream: RedisStreamsSinkStreamContext<Event, PublicationOutcome, Error>): { readonly context: MessageContext; readonly state: PublishEventSinkHandlerState } {
    return { context, state: undefined };
  }

  public consumeMessage(context: MessageContext, _stream: RedisStreamsSinkStreamContext<Event, PublicationOutcome, Error>, _state: PublishEventSinkHandlerState, value: Readonly<Event>, message: SinkMessage<PublicationOutcome>): void {
    message.fields = [["ID",value.ID],["Value",value.Value]];
    message.send(context, (delivery, error) => ({EventID: value.ID, EntryID: delivery?.id ?? "", Accepted: error === undefined && delivery?.outcome === "published", Reason: error?.message ?? delivery?.error?.message ?? ""}));
  }

  public endRequest(context: MessageContext, _stream: RedisStreamsSinkStreamContext<Event, PublicationOutcome, Error>, _error: Error | undefined, _state: PublishEventSinkHandlerState): void {}
}

/** Construct PublishEventSink asynchronously while the service graph is initialized. */
export function makePublishEventSink(
  _context: MessageContext,
  _environment: RuntimeEnvironment,
): Promise<PublishEventSink> {
  return new Promise((resolve) => {
    resolve(new PublishEventSink());
  });
}
