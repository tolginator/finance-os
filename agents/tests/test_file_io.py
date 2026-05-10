"""Tests for the shared file I/O primitives."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.file_io import FileLockContext, atomic_write

# ---------------------------------------------------------------------------
# FileLockContext tests
# ---------------------------------------------------------------------------


class TestFileLockContext:
    """Tests for the advisory file lock context manager."""

    def test_creates_lock_file(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "test.lock"
        with FileLockContext(lock_path):
            assert lock_path.exists()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "sub" / "dir" / "test.lock"
        with FileLockContext(lock_path):
            assert lock_path.exists()

    def test_fd_closed_after_exit(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "test.lock"
        ctx = FileLockContext(lock_path)
        with ctx:
            assert ctx._fd is not None
        assert ctx._fd is None

    def test_fd_closed_on_flock_failure(self, tmp_path: Path) -> None:
        """File descriptor must be closed if flock() raises."""
        lock_path = tmp_path / "test.lock"
        closed_fds: list[int] = []
        original_close = os.close

        def tracking_close(fd: int) -> None:
            closed_fds.append(fd)
            original_close(fd)

        with (
            patch("src.core.file_io.fcntl") as mock_fcntl,
            patch("src.core.file_io.os.close", side_effect=tracking_close),
        ):
            mock_fcntl.LOCK_EX = 2
            mock_fcntl.flock.side_effect = OSError("flock failed")

            with pytest.raises(OSError):
                with FileLockContext(lock_path):
                    pass

        assert len(closed_fds) == 1

    def test_reentrant_usage(self, tmp_path: Path) -> None:
        """Same lock path can be used in sequential with-blocks."""
        lock_path = tmp_path / "test.lock"
        with FileLockContext(lock_path):
            pass
        with FileLockContext(lock_path):
            pass


# ---------------------------------------------------------------------------
# atomic_write tests
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    """Tests for atomic file writing."""

    def test_writes_content(self, tmp_path: Path) -> None:
        path = tmp_path / "data.json"
        content = b'{"key": "value"}'
        atomic_write(path, content)
        assert path.read_bytes() == content

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        path = tmp_path / "sub" / "dir" / "data.json"
        atomic_write(path, b"hello")
        assert path.read_bytes() == b"hello"

    def test_sets_file_permissions(self, tmp_path: Path) -> None:
        path = tmp_path / "secret.json"
        atomic_write(path, b"data", mode=0o600)
        stat = path.stat()
        assert oct(stat.st_mode & 0o777) == oct(0o600)

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "data.json"
        path.write_bytes(b"old content")
        atomic_write(path, b"new content")
        assert path.read_bytes() == b"new content"

    def test_no_partial_write_on_failure(self, tmp_path: Path) -> None:
        """Original file is preserved if write fails mid-way."""
        path = tmp_path / "data.json"
        path.write_bytes(b"original")

        with patch("src.core.file_io.os.fsync", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                atomic_write(path, b"new content that should not appear")

        assert path.read_bytes() == b"original"

    def test_temp_file_cleaned_on_failure(self, tmp_path: Path) -> None:
        """Temp file is removed on write failure."""
        path = tmp_path / "data.json"

        with patch("src.core.file_io.os.fsync", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                atomic_write(path, b"data")

        # No .tmp files left behind
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == []
