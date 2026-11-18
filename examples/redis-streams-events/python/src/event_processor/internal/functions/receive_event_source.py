"""User-owned function implementation. The generator never overwrites this file."""

import json
from dataclasses import asdict

from event_processor.models.event import Event
from event_processor.models.publication_outcome import PublicationOutcome
from pyservicelib_gorundebug.datasource.redisstreams.redisstreamsds import (
    ConsumerMessage,
    ResultContext,
)
from pyservicelib_gorundebug.runtime.common import StreamContext
from pyservicelib_gorundebug.runtime.context.context import Context
from pyservicelib_gorundebug.runtime.environment import ServiceEnvironment


class ReceiveEventSource:
    """Decode native fields, register before collect, and XACK only confirmed XADD outcomes."""

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
        print(f"Redis Streams source error: {err!r}", flush=True)
        await sc.error_collect(err)

    async def begin_request(
        self,
        sc: StreamContext[Event, PublicationOutcome, Exception],
    ) -> None:
        del sc

    async def consume_message(
        self,
        sc: StreamContext[Event, PublicationOutcome, Exception],
        handler_state: None,
        message: ConsumerMessage,
        result_ctx: ResultContext[None, Event, PublicationOutcome, Exception],
    ) -> None:
        business = {}
        for key, value in message.message.fields:
            if key in (b"ID", b"Value"):
                name = key.decode("utf-8")
                if name in business:
                    raise ValueError(f"duplicate Event field: {name}")
                business[name] = value.decode("utf-8")
        event = Event(**business)

        async def completed(_sc, _state, outcome):
            if outcome.Accepted and await message.ack() != 1:
                raise RuntimeError("input entry was not acknowledged")
            # Failed/unknown publication leaves input pending; Done is only local completion.
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
