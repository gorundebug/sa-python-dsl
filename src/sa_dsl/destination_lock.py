"""Host-local merge locks shared by MCP processes and authoring projects."""

from __future__ import annotations

import errno
import hashlib
import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class DestinationBusyError(RuntimeError):
    pass


@contextmanager
def lock_generation_destination(destination: Path) -> Iterator[None]:
    """Fail fast if another local process is applying to this resolved directory.

    Lock files live outside the project, so acquisition does not invalidate a
    preview revision or create a not-yet-existing generation destination. Keep
    each file's inode stable: unlinking after unlock would allow two independent
    locks on the same pathname. The OS releases the lock if the holder exits.
    """
    identity = str(os.getuid()) if hasattr(os, "getuid") else hashlib.sha256(
        os.fsencode(Path.home().resolve())
    ).hexdigest()[:16]
    directory = Path(tempfile.gettempdir()) / f"service-architect-merge-locks-{identity}"
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise OSError("generation lock directory must be a real directory")
    if os.name == "posix" and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077):
        raise OSError("generation lock directory must be private to the current user")
    name = hashlib.sha256(os.fsencode(os.path.normcase(str(destination.resolve())))).hexdigest()
    path = directory / (name + ".lock")
    if path.is_symlink():
        raise OSError("generation lock must not be a symlink")
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("generation lock must be a regular file")
        try:
            if os.name == "posix":
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            elif os.name == "nt":
                import msvcrt

                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                raise OSError("generation locking is unsupported on this platform")
        except OSError as error:
            if error.errno in {errno.EACCES, errno.EAGAIN}:
                raise DestinationBusyError("another generation apply is using this output directory") from error
            raise
        yield
    finally:
        os.close(descriptor)
