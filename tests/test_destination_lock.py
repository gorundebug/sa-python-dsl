import subprocess
import sys
import time
from pathlib import Path

import pytest

from sa_dsl.destination_lock import DestinationBusyError, lock_generation_destination


def test_lock_does_not_create_output_and_releases_after_error(tmp_path):
    destination = tmp_path / "missing" / "output"
    with pytest.raises(RuntimeError, match="interrupted"):
        with lock_generation_destination(destination):
            assert not destination.exists()
            with pytest.raises(DestinationBusyError):
                with lock_generation_destination(destination):
                    pytest.fail("same destination was locked twice")
            raise RuntimeError("interrupted")
    with lock_generation_destination(destination):
        assert not destination.exists()


def test_different_destinations_are_independent(tmp_path):
    with lock_generation_destination(tmp_path / "one"):
        with lock_generation_destination(tmp_path / "two"):
            pass


def test_other_process_cannot_acquire_and_exit_releases_lock(tmp_path):
    destination = tmp_path / "output"
    ready = tmp_path / "ready"
    script = (
        "import sys, time\nfrom pathlib import Path\n"
        "from sa_dsl.destination_lock import lock_generation_destination\n"
        "with lock_generation_destination(Path(sys.argv[1])):\n"
        "    Path(sys.argv[2]).touch()\n"
        "    time.sleep(30)\n"
    )
    child = subprocess.Popen([sys.executable, "-c", script, str(destination), str(ready)])
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists(), "child did not acquire the destination lock"
        with pytest.raises(DestinationBusyError):
            with lock_generation_destination(destination):
                pytest.fail("another process acquired the same destination")
    finally:
        child.kill()
        child.wait(timeout=5)
    with lock_generation_destination(destination):
        assert not destination.exists()
