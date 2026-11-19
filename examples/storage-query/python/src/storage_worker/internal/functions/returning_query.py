"""User-owned function implementation. The generator never overwrites this file."""

from typing import Any
from .query_state import RequestState, finish

from storage_worker.models.storage_request import StorageRequest
from storage_worker.models.storage_result import StorageResult
from sqlalchemy.engine import Row
from sqlalchemy import bindparam, insert
from .storage_schema import items

from pyservicelib_gorundebug.runtime.context.context import Context
from pyservicelib_gorundebug.runtime.environment import ServiceEnvironment
from pyservicelib_gorundebug.dataquery import BeginRequest
from pyservicelib_gorundebug.dataquery.postgresqlsqlalchemy import Query
from pyservicelib_gorundebug.runtime.common import Collect, Stream

class ReturningQuery:
    """Insert a bound key/value and return its stored value using PostgreSQL Rows. Use the supplied context and maker-owned shared client. Map native results to StorageResult, preserving RequestID. EndRequest emits Kind=completed only on success; failures go to the error collector. Never retry unknown writes or partial output. No schema/bucket creation."""

    async def begin_request(self, stream: Stream) -> BeginRequest[RequestState]:
        return BeginRequest(RequestState())

    async def build_query(self, state: RequestState, value: StorageRequest) -> Query:
        state.request_id = value.request_id
        return Query(insert(items).values(key=bindparam("key"), value=bindparam("value")).returning(items.c.value), {"key": value.key, "value": value.value})

    async def handle_row(self, state: RequestState, row: Row[Any], out: Collect[StorageResult]) -> None:
        await out.out(StorageResult(state.request_id, "record", bytes(row._mapping["value"])))

    async def end_request(self, stream: Stream, state: RequestState | None, error: BaseException | None,
                          out: Collect[StorageResult], errors: Collect[Exception]) -> None:
        await finish(state, error, out, errors)


async def make_returning_query(
    ctx: Context,
    environment: ServiceEnvironment,

) -> ReturningQuery:
    """Construct ReturningQuery asynchronously while the graph is initialized."""
    del ctx, environment
    return ReturningQuery()
