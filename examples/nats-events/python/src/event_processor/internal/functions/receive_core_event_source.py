"""User-owned function implementation. The generator never overwrites this file."""

import json
from dataclasses import asdict
from event_processor.models.event import Event
from event_processor.models.publication_outcome import PublicationOutcome

from pyservicelib_gorundebug.runtime.context.context import Context
from pyservicelib_gorundebug.runtime.environment import ServiceEnvironment
from pyservicelib_gorundebug.datasource.nats.natsds import (
    ConsumerMessage, JetStreamMessage,
    ResultContext,
)
from pyservicelib_gorundebug.runtime.common import StreamContext
class ReceiveCoreEventSource:
    """Decode Event from native message bytes. Register the result callback before Collect; keep the supplied context and correlate by Event.ID. On outcome, record local publication acceptance or failure; Core has no ACK or replay. Call Done after handling the outcome. Done itself never ACKs."""

    def concurrency(
        self,
        sc: StreamContext[Event, PublicationOutcome, Exception],
    ) -> int:
        del sc
        return 1

    async def on_error(
        self,
        sc: StreamContext[Event, PublicationOutcome, Exception],
        err: Exception,
    ) -> None:
        # Transport errors have no message state and do not select retry policy.
        await sc.error_collect(err)


    async def begin_request(
        self,
        sc: StreamContext[Event, PublicationOutcome, Exception],
    ) -> None:
        del sc
        return None

    async def consume_message(
        self,
        sc: StreamContext[Event, PublicationOutcome, Exception],
        handler_state: None,
        message: ConsumerMessage,
        result_ctx: ResultContext[
            None, Event, PublicationOutcome, Exception
        ],
    ) -> None:
        event = Event(**json.loads(message.data))
        async def completed(_sc, _state, outcome):
            if isinstance(message, JetStreamMessage):
                if outcome.Accepted:
                    await message.ack()
                else:
                    await message.nak()
            print(json.dumps(asdict(outcome)), flush=True)
            result_ctx.done()
            return True
        result_ctx.set_result_callback(event.ID, completed)
        await sc.collect(event)

    def get_message_id(
        self,
        sc: StreamContext[Event, PublicationOutcome, Exception],
        handler_state: None,
        value: PublicationOutcome,
    ) -> str:
        return value.EventID

    async def end_request(
        self,
        sc: StreamContext[Event, PublicationOutcome, Exception],
        err: Exception | None,
        handler_state: None,
    ) -> None:
        del sc, err, handler_state



async def make_receive_core_event_source(
    ctx: Context,
    environment: ServiceEnvironment,

) -> ReceiveCoreEventSource:
    """Construct ReceiveCoreEventSource asynchronously while the graph is initialized."""
    del ctx, environment
    return ReceiveCoreEventSource()
