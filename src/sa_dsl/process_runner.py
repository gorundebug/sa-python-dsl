"""Bounded process output and process-group termination for generated commands."""
from __future__ import annotations

import os
import signal
import subprocess
import tempfile
from pathlib import Path

OUTPUT_LIMIT = 64 * 1024


def run_bounded(command, *, cwd, env, timeout, capture_output=True, text=True,
                check=False, log_directory=None):
    # Files drain output without keeping an unbounded communicate() buffer in memory.
    with tempfile.TemporaryDirectory(prefix="sa-command-") as temporary:
        directory = Path(log_directory) if log_directory else Path(temporary)
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=directory, prefix="stdout-", delete=False) as out, \
             tempfile.NamedTemporaryFile(dir=directory, prefix="stderr-", delete=False) as err:
            paths = {"stdout": Path(out.name), "stderr": Path(err.name)}
            process = subprocess.Popen(command, cwd=cwd, env=env, stdout=out, stderr=err,
                                       start_new_session=os.name == "posix")
            try:
                process.wait(timeout=timeout)
            except BaseException:
                terminate_group(process)
                raise
        def read_tail(path):
            with path.open("rb") as stream:
                size = stream.seek(0, os.SEEK_END)
                stream.seek(max(0, size - OUTPUT_LIMIT))
                value = stream.read(OUTPUT_LIMIT).decode("utf-8", errors="replace")
                return ("... earlier output truncated ...\n" if size > OUTPUT_LIMIT else "") + value
        result = subprocess.CompletedProcess(command, process.returncode,
                                             read_tail(paths["stdout"]), read_tail(paths["stderr"]))
        if log_directory:
            result.log_paths = {key: str(path) for key, path in paths.items()}
        if check:
            result.check_returncode()
        return result


def terminate_group(process):
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if process.poll() is None:
                process.kill()
    except ProcessLookupError:
        pass
    process.wait()
