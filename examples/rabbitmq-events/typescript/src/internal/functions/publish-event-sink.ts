/** User-owned endpoint implementation. The generator preserves this file. */

import type {
  MessageContext,
  RuntimeEnvironment,
} from "@gorundebug/tsservicelib/runtime/graph";
import type {
  EndpointHandler as RabbitMQSinkEndpointHandler,

  SinkMessage,
  StreamContext as RabbitMQSinkStreamContext,
} from "@gorundebug/tsservicelib/datasink/rabbitmq";

import type { Event, PublicationOutcome } from "#internal/types/index.generated.js";

export type PublishEventSinkHandlerState = undefined;

/** Encode Event and publish through the native endpoint. Emit exactly one PublicationOutcome for each event, preserving EventID and the caller context. Use asynchronous publication with its callback; represent failed or unknown delivery as Accepted=false with a reason. Do not open a second broker client. */
export class PublishEventSink implements RabbitMQSinkEndpointHandler<PublishEventSinkHandlerState, Event, PublicationOutcome, Error> {
  public getStreamId(context: MessageContext, value: Readonly<Event>): string { return context.streamId() ?? value.ID; }


  public beginRequest(context: MessageContext, _stream: RabbitMQSinkStreamContext<Event, PublicationOutcome, Error>): { readonly context: MessageContext; readonly state: PublishEventSinkHandlerState } {
    return { context, state: undefined };
  }

  public consumeMessage(context: MessageContext, _stream: RabbitMQSinkStreamContext<Event, PublicationOutcome, Error>, _state: PublishEventSinkHandlerState, value: Readonly<Event>, message: SinkMessage<PublicationOutcome>): void {
    message.message.body = new TextEncoder().encode(JSON.stringify(value));
    message.send(context, (_delivery, error) => ({EventID: value.ID, Accepted: error === undefined, Reason: error?.message ?? ""}));
  }

  public endRequest(context: MessageContext, _stream: RabbitMQSinkStreamContext<Event, PublicationOutcome, Error>, _error: Error | undefined, _state: PublishEventSinkHandlerState): void {}
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
