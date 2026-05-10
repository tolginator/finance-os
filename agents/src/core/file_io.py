"""Shared file I/O primitives — advisory locking and atomic writes.

Provides OS-level advisory file locking via ``fcntl.flock`` and an
atomic-write helper (temp file → fsync → rename) used by persistence
services that share the ``~/.config/finance-os/`` directory across
the Web API, MCP server, and CLI processes.
"""

import fcntl
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class FileLockContext:
    """OS-level advisory lock via ``fcntl.flock``.

    Usage::

        with FileLockContext(lock_path):
            # exclusive access to the protected resource
            ...

    The file descriptor is always closed on exit, even if unlocking
    raises an exception.
    """

    def __init__(self, lock_path: Path) -> None:
        self._lock_path = lock_path
        self._fd: int | None = None

    def __enter__(self) -> "FileLockContext":
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self._lock_path), os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX)
        except BaseException:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
            raise
        return self

    def __exit__(self, *_: object) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None


def atomic_write(path: Path, content: bytes, *, mode: int = 0o600) -> None:
    """Write *content* to *path* atomically via temp-file + rename.

    1. Create a temp file in the same directory as *path*.
    2. Write *content*, ``fsync`` the data.
    3. ``chmod`` to *mode*, then ``replace`` the temp file over *path*.
    4. Best-effort ``fsync`` on the parent directory.

    On failure the temp file is removed and the original *path* is
    left untouched.

    Args:
        path: Destination file path.
        content: Raw bytes to write.
        mode: File permission bits (default ``0o600``).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd_num, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd_num, "wb") as tmp_file:
            tmp_file.write(content)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.chmod(str(tmp_path), mode)
        tmp_path.replace(path)
    except BaseException:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError as cleanup_exc:
            logger.warning(
                "Could not remove temp file %s: %s",
                tmp_path, cleanup_exc,
            )
        raise
    # Best-effort directory fsync
    dir_fd: int | None = None
    try:
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        if dir_fd is not None:
            os.close(dir_fd)
