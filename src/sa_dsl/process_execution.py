"""Bounded capture and process-tree cleanup for local generated commands."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Mapping


MAX_CAPTURED_OUTPUT = 64 * 1024


def run_bounded_process(
    command: list[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    capture_output: bool,
    text: bool,
    timeout: float,
    check: bool,
) -> subprocess.CompletedProcess[str]:
    """Drain both pipes, retain bounded prefixes, and own the process group.

    The keyword signature matches the injected subprocess runner used by the
    verification API. Callers request captured text and inspect the exit code.
    Timeout includes descendants retaining pipes after the direct child exits.
    """
    deadline = time.monotonic() + timeout
    process = subprocess.Popen(
        command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=os.name == "posix",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    output = ["", ""]
    errors: list[OSError] = []

    def drain(pipe: Any, index: int) -> None:
        prefix = bytearray()
        truncated = False
        try:
            with pipe:
                while chunk := pipe.read(64 * 1024):
                    remaining = MAX_CAPTURED_OUTPUT - len(prefix)
                    prefix.extend(chunk[:remaining])
                    truncated |= len(chunk) > remaining
        except OSError as error:
            errors.append(error)
        finally:
            output[index] = prefix.decode("utf-8", errors="replace")
            if truncated:
                output[index] += "\n... output truncated ...\n"

    readers = [
        threading.Thread(target=drain, args=(pipe, index), daemon=True)
        for index, pipe in enumerate((process.stdout, process.stderr))
    ]
    try:
        for reader in readers:
            reader.start()
        process.wait(timeout=max(0, deadline - time.monotonic()))
        for reader in readers:
            reader.join(timeout=max(0, deadline - time.monotonic()))
        if any(reader.is_alive() for reader in readers):
            raise subprocess.TimeoutExpired(command, timeout)
        if errors:
            raise errors[0]
    except BaseException:
        _stop_process_group(process)
        for reader in readers:
            if reader.ident is not None:
                reader.join(timeout=1)
        raise
    return subprocess.CompletedProcess(command, process.returncode, *output)


def _stop_process_group(process: subprocess.Popen[bytes]) -> None:
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=5, check=False,
            )
        finally:
            if process.poll() is None:
                process.kill()
    elif process.poll() is None:
        process.kill()
    process.wait(timeout=5)
