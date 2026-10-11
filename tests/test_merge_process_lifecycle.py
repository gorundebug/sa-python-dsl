import shlex
import sys
import time

import pytest

from sa_dsl import generation_transaction as transaction


def test_merge_timeout_stops_descendants_before_releasing_apply(tmp_path, monkeypatch):
    marker = tmp_path / "merge-still-writing"
    child = tmp_path / "late_writer.py"
    child.write_text(
        "import time\nfrom pathlib import Path\ntime.sleep(0.8)\n"
        + f"Path({str(marker)!r}).write_text('late merge')\n",
        encoding="utf-8",
    )
    script = tmp_path / "merge.generated.sh"
    script.write_text(
        f"#!/bin/sh\n{shlex.quote(sys.executable)} {shlex.quote(str(child))}\nexit 0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(transaction, "MERGE_TIMEOUT_SECONDS", 0.1)
    with pytest.raises(transaction.GenerationTransactionError) as raised:
        transaction._run_merge(
            script, tmp_path / "input.zip", tmp_path, tmp_path / "report.json",
            dry_run=False, remove_stale=False,
        )
    assert raised.value.code == "SA_MERGE_TIMEOUT"
    time.sleep(1)
    assert not marker.exists(), "A timed-out merge continued modifying its destination"
