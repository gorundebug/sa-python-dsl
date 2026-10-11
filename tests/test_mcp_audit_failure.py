import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

from sa_dsl import mcp_server
from tests.test_generation_transaction import project_workspace


def test_completed_verification_survives_an_unwritable_audit_log(tmp_path: Path, monkeypatch):
    project_workspace(tmp_path)
    (tmp_path / ".service-architect" / "audit.jsonl").mkdir()
    monkeypatch.setattr(mcp_server, "_workspace", type(mcp_server._workspace)(tmp_path))
    calls = []

    def execute(workspace, verification):
        calls.append((workspace, verification))
        return {"status": "success", "exitCode": 0, "stdout": "completed", "stderr": ""}

    monkeypatch.setattr(mcp_server, "execute_verification", execute)
    result = asyncio.run(mcp_server.run_verification(AsyncMock(), verification="test"))
    assert len(calls) == 1
    assert result["status"] == "success"
    assert result["result"]["stdout"] == "completed"
    assert result["diagnostics"] == [{
        "code": "SA_AUDIT_WRITE_FAILED",
        "severity": "warning",
        "path": "$.audit",
        "message": "The operation result is available, but its local audit record could not be written. Do not repeat the operation solely to repair the audit log.",
    }]
