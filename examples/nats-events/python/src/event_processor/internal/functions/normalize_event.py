"""User-owned function implementation. The generator never overwrites this file."""

from event_processor.models.event import Event

from pyservicelib_gorundebug.runtime.context.context import Context
from pyservicelib_gorundebug.runtime.environment import ServiceEnvironment
from pyservicelib_gorundebug.runtime.common import Collect, Stream
class NormalizeEvent:
    """Preserve Event.ID and normalize Event.Value. One input produces one event; no broker I/O."""

    async def map(
        self,
        stream: Stream,
        value: Event,
        out: Collect[Event],
    ) -> None:
        await out.out(Event(value.ID, value.Value.strip().upper()))


async def make_normalize_event(
    ctx: Context,
    environment: ServiceEnvironment,

) -> NormalizeEvent:
    """Construct NormalizeEvent asynchronously while the graph is initialized."""
    del ctx, environment
    return NormalizeEvent()
