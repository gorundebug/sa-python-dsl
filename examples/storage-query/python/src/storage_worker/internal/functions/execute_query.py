"""User-owned function implementation. The generator never overwrites this file."""

from typing import Any
from .query_state import RequestState, finish

from storage_worker.models.storage_request import StorageRequest
from storage_worker.models.storage_result import StorageResult
from sqlalchemy.engine import CursorResult
from sqlalchemy import bindparam
from sqlalchemy.dialects.postgresql import insert
from .storage_schema import items

from pyservicelib_gorundebug.runtime.context.context import Context
from pyservicelib_gorundebug.runtime.environment import ServiceEnvironment
from pyservicelib_gorundebug.dataquery import BeginRequest
from pyservicelib_gorundebug.dataquery.postgresqlsqlalchemy import Query
from pyservicelib_gorundebug.runtime.common import Collect, Stream

class ExecuteQuery:
    """Build and execute Execute using the connector's native request contract. Use the supplied context and maker-owned shared client. Map native results to StorageResult, preserving RequestID. EndRequest emits Kind=completed only on success; failures go to the error collector. Never retry unknown writes or partial output. No schema/bucket creation."""

    async def begin_request(self, stream: Stream) -> BeginRequest[RequestState]:
        return BeginRequest(RequestState())

    async def build_query(self, state: RequestState, value: StorageRequest) -> Query:
        state.request_id = value.request_id
        statement = insert(items).values(key=bindparam("key"), value=bindparam("value"))
        statement = statement.on_conflict_do_update(index_elements=[items.c.key], set_={"value": statement.excluded.value})
        return Query(statement, {"key": value.key, "value": value.value})

    async def handle_result(self, state: RequestState, result: CursorResult[Any], out: Collect[StorageResult]) -> None:
        await out.out(StorageResult(state.request_id, "command", str(result.rowcount).encode()))

    async def end_request(self, stream: Stream, state: RequestState | None, error: BaseException | None,
                          out: Collect[StorageResult], errors: Collect[Exception]) -> None:
        await finish(state, error, out, errors)


async def make_execute_query(
    ctx: Context,
    environment: ServiceEnvironment,

) -> ExecuteQuery:
    """Construct ExecuteQuery asynchronously while the graph is initialized."""
    del ctx, environment
    return ExecuteQuery()
