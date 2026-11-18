"""User-owned function implementation. The generator never overwrites this file."""

import json
import base64
from dataclasses import asdict
from pyservicelib_gorundebug.datasink.pulsar import ProducerMessage

from event_processor.models.event import Event
from event_processor.models.publication_outcome import PublicationOutcome
from pyservicelib_gorundebug.datasink.pulsar.pulsards import SinkMessage
from pyservicelib_gorundebug.runtime.common import Stream
from pyservicelib_gorundebug.runtime.context.context import Context
from pyservicelib_gorundebug.runtime.environment import ServiceEnvironment


class PublishEventSink:
    """Encode Event and publish through the native endpoint. Emit exactly one PublicationOutcome for each event, preserving EventID and the caller context. Use asynchronous publication with its callback; represent failed or unknown delivery as Accepted=false with a reason. Do not open a second broker client."""

    def get_stream_id(self, value: Event) -> str:
        return value.ID

    def begin_request(self, stream: Stream) -> None:
        del stream

    async def consume_message(
        self,
        stream: Stream,
        handler_state: None,
        value: Event,
        message: SinkMessage[PublicationOutcome],
    ) -> None:
        message.message = ProducerMessage(json.dumps(asdict(value)).encode(), key=value.ID)
        message.send(
            lambda delivery: PublicationOutcome(
                value.ID,
                base64.b64encode(delivery.id.serialize()).decode() if delivery.id is not None else "",
                delivery.outcome == "Accepted",
                str(delivery.error or ""),
            )
        )

    async def end_request(
        self,
        stream: Stream,
        err: Exception | None,
        handler_state: None,
    ) -> None:
        if err:
            print(f"Publication failed: {err!r}", flush=True)
        del stream, err, handler_state


async def make_publish_event_sink(
    ctx: Context,
    environment: ServiceEnvironment,
) -> PublishEventSink:
    """Construct PublishEventSink asynchronously while the graph is initialized."""
    del ctx, environment
    return PublishEventSink()
