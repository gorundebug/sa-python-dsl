"""Per-invocation application state; no clients, registry or retained collectors."""
from dataclasses import dataclass
from pyservicelib_gorundebug.runtime.common import Collect
from storage_worker.models.storage_result import StorageResult

@dataclass(slots=True)
class RequestState:
    request_id: str = ""

async def finish(state: RequestState | None, error: BaseException | None,
                 out: Collect[StorageResult], errors: Collect[Exception]) -> None:
    if error is not None:
        await errors.out(error if isinstance(error, Exception) else RuntimeError(str(error)))
    else:
        assert state is not None  # A successful begin_request always creates state.
        await out.out(StorageResult(state.request_id, "completed"))
