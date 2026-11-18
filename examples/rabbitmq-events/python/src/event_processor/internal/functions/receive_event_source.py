"""User-owned function implementation. The generator never overwrites this file."""

import json
from dataclasses import asdict
from event_processor.models.event import Event
from event_processor.models.publication_outcome import PublicationOutcome

from pyservicelib_gorundebug.runtime.context.context import Context
from pyservicelib_gorundebug.runtime.environment import ServiceEnvironment
from pyservicelib_gorundebug.datasource.rabbitmq.rabbitmqds import (
    ConsumerMessage,
    ResultContext,
)
from pyservicelib_gorundebug.runtime.common import StreamContext
class ReceiveEventSource:
    """Decode Event from native message bytes. Register the result callback before Collect; keep the supplied context and correlate by Event.ID. On outcome, accept only a confirmed successful publication; release publication failures. A missing ACK can cause redelivery; processing must be idempotent. Call Done after handling the outcome. Done itself never settles."""

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
        print(f"RabbitMQ source error: {err!r}", flush=True)
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
        event = Event(**json.loads(bytes(message.data)))
        async def completed(_sc, _state, outcome):
            if outcome.Accepted:
                await message.accept()
            else:
                await message.release()
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
        if err:
            print(f"Request failed: {err!r}", flush=True)
        del sc, err, handler_state



async def make_receive_event_source(
    ctx: Context,
    environment: ServiceEnvironment,

) -> ReceiveEventSource:
    """Construct ReceiveEventSource asynchronously while the graph is initialized."""
    del ctx, environment
    return ReceiveEventSource()
