import shlex
import subprocess
import sys
import time
from pathlib import Path

import pytest

from sa_dsl.business_tasks import (
    BusinessTaskError, MAX_VERIFICATION_OUTPUT, run_verification,
)


def _make_test(root: Path, program: str) -> None:
    script = root / "verification.py"
    script.write_text(program, encoding="utf-8")
    (root / "Makefile").write_text(
        f"test:\n\t@{shlex.quote(sys.executable)} {shlex.quote(str(script))}\n",
        encoding="utf-8",
    )


def test_timeout_terminates_make_and_its_child(tmp_path):
    marker = tmp_path / "survived"
    _make_test(tmp_path, "import time\nfrom pathlib import Path\ntime.sleep(0.8)\n"
               + f"Path({str(marker)!r}).touch()\n")
    with pytest.raises(BusinessTaskError) as raised:
        run_verification(tmp_path, "test", timeout_seconds=0.1)
    assert raised.value.code == "SA_VERIFICATION_TIMEOUT"
    time.sleep(1)
    assert not marker.exists()


def test_noisy_command_is_drained_without_unbounded_capture(tmp_path):
    _make_test(tmp_path, "import sys\n"
               "sys.stdout.write('x' * (4 * 1024 * 1024))\n"
               "sys.stderr.write('y' * (4 * 1024 * 1024))\n")
    result = run_verification(tmp_path, "test", timeout_seconds=5)
    assert result["status"] == "success"
    suffix = "\n... output truncated ...\n"
    assert result["stdout"] == "x" * MAX_VERIFICATION_OUTPUT + suffix
    assert result["stderr"] == "y" * MAX_VERIFICATION_OUTPUT + suffix


def test_nonzero_and_unicode_output_are_preserved(tmp_path):
    _make_test(tmp_path, "import sys\nprint('\\u041f\\u0440\\u0438\\u0432\\u0435\\u0442')\n"
               "print('failed', file=sys.stderr)\nsys.exit(7)\n")
    result = run_verification(tmp_path, "test", timeout_seconds=5)
    assert result["status"] == "failed"
    assert result["exitCode"] != 0
    assert result["stdout"] == "\u041f\u0440\u0438\u0432\u0435\u0442\n"
    assert "failed" in result["stderr"]


def test_injected_runner_contract_is_unchanged(tmp_path):
    _make_test(tmp_path, "pass\n")
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, "ok", "")

    result = run_verification(tmp_path, "test", runner=runner)
    assert calls[0][0] == ["make", "test"]
    assert calls[0][1]["capture_output"] is True
    assert result["stdout"] == "ok"
