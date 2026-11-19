"""User-owned function implementation. The generator never overwrites this file."""

from collections.abc import Mapping
from typing import Any
from .query_state import RequestState, finish

from storage_worker.models.storage_request import StorageRequest
from storage_worker.models.storage_result import StorageResult

from pyservicelib_gorundebug.runtime.context.context import Context
from pyservicelib_gorundebug.runtime.environment import ServiceEnvironment
from pyservicelib_gorundebug.dataquery import BeginRequest
from pyservicelib_gorundebug.runtime.common import Collect, Stream

class GetObjectQuery:
    """Build and execute GetObject using the connector's native request contract. Use the supplied context and maker-owned shared client. Map native results to StorageResult, preserving RequestID. EndRequest emits Kind=completed only on success; failures go to the error collector. Never retry unknown writes or partial output. No schema/bucket creation."""

    async def begin_request(self, stream: Stream) -> BeginRequest[RequestState]:
        return BeginRequest(RequestState())

    async def build_request(self, state: RequestState, value: StorageRequest) -> Mapping[str, Any]:
        state.request_id = value.request_id
        return {"Bucket": "query-example", "Key": value.key}

    async def handle_result(self, state: RequestState, result: Mapping[str, Any], out: Collect[StorageResult]) -> None:
        body = result["Body"]
        while chunk := await body.read(65536):
            await out.out(StorageResult(state.request_id, "object", bytes(chunk)))

    async def end_request(self, stream: Stream, state: RequestState | None, error: BaseException | None,
                          out: Collect[StorageResult], errors: Collect[Exception]) -> None:
        await finish(state, error, out, errors)


async def make_get_object_query(
    ctx: Context,
    environment: ServiceEnvironment,

) -> GetObjectQuery:
    """Construct GetObjectQuery asynchronously while the graph is initialized."""
    del ctx, environment
    return GetObjectQuery()
