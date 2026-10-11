"""A timed-out verification must not leave its compiler/test process running."""

import asyncio
import inspect
import shlex
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock

from sa_dsl import mcp_server
from tests.test_generation_transaction import project_workspace


def test_verification_timeout_stops_child_process(tmp_path: Path, monkeypatch):
    project_workspace(tmp_path)
    marker = tmp_path / "child-survived-timeout"
    child = tmp_path / "slow_verification.py"
    child.write_text(
        "import time\nfrom pathlib import Path\n"
        "time.sleep(0.8)\n"
        f"Path({str(marker)!r}).write_text('still running')\n",
        encoding="utf-8",
    )
    (tmp_path / "Makefile").write_text(
        f"test:\n\t{shlex.quote(sys.executable)} {shlex.quote(str(child))}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mcp_server, "_workspace", type(mcp_server._workspace)(tmp_path))
    original_run = mcp_server.execute_verification

    def short_timeout(*args, **kwargs):
        kwargs["timeout_seconds"] = 0.1
        return original_run(*args, **kwargs)

    monkeypatch.setattr(mcp_server, "execute_verification", short_timeout)
    result = mcp_server.run_verification(AsyncMock(), verification="test")
    if inspect.isawaitable(result):
        result = asyncio.run(result)
    assert result["status"] == "failed", result
    assert result["diagnostics"][0]["code"] == "SA_VERIFICATION_TIMEOUT", result
    time.sleep(1)
    assert not marker.exists(), "Verification timed out, but its child kept running"
