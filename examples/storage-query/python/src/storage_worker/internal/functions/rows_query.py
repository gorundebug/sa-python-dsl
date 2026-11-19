"""User-owned function implementation. The generator never overwrites this file."""

from typing import Any
from .query_state import RequestState, finish

from storage_worker.models.storage_request import StorageRequest
from storage_worker.models.storage_result import StorageResult
from sqlalchemy.engine import Row
from sqlalchemy import bindparam, select
from .storage_schema import items

from pyservicelib_gorundebug.runtime.context.context import Context
from pyservicelib_gorundebug.runtime.environment import ServiceEnvironment
from pyservicelib_gorundebug.dataquery import BeginRequest
from pyservicelib_gorundebug.dataquery.postgresqlsqlalchemy import Query
from pyservicelib_gorundebug.runtime.common import Collect, Stream

class RowsQuery:
    """Build and execute Rows using the connector's native request contract. Use the supplied context and maker-owned shared client. Map native results to StorageResult, preserving RequestID. EndRequest emits Kind=completed only on success; failures go to the error collector. Never retry unknown writes or partial output. No schema/bucket creation."""

    async def begin_request(self, stream: Stream) -> BeginRequest[RequestState]:
        return BeginRequest(RequestState())

    async def build_query(self, state: RequestState, value: StorageRequest) -> Query:
        state.request_id = value.request_id
        return Query(select(items.c.value).where(items.c.key == bindparam("key")), {"key": value.key})

    async def handle_row(self, state: RequestState, row: Row[Any], out: Collect[StorageResult]) -> None:
        await out.out(StorageResult(state.request_id, "record", bytes(row._mapping["value"])))

    async def end_request(self, stream: Stream, state: RequestState | None, error: BaseException | None,
                          out: Collect[StorageResult], errors: Collect[Exception]) -> None:
        await finish(state, error, out, errors)


async def make_rows_query(
    ctx: Context,
    environment: ServiceEnvironment,

) -> RowsQuery:
    """Construct RowsQuery asynchronously while the graph is initialized."""
    del ctx, environment
    return RowsQuery()
