# SPDX-License-Identifier: GPL-3.0-or-later
"""Process-lifetime OS locks (D-06, D-24).

`ProcessLock(path)` takes one non-blocking OS lock on `path`: msvcrt's `LK_NBLCK` on byte 0
on Windows, `fcntl.flock(LOCK_EX | LOCK_NB)` elsewhere, on the file opened "a+b" (created when
missing, never truncated or written), the pattern compiler.py's log lock uses. The kernel
frees the lock when its holder exits, however it exits, so holding the lock proves that every
earlier holder is dead. No process id is ever probed: on Windows the os module's kill with
signal 0 terminates the process it names (D-24).

`is_held(path)` asks the same question without keeping the answer: the hooks' drive write guard
uses it, so a lock file left behind by an exited drive does not count as a running one.

Two ProcessLock objects on one path conflict even inside one process: each opens its own
handle (Windows locks a byte range per handle, flock locks per open file description).
"""

from __future__ import annotations

import errno
import sys
from pathlib import Path

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

DRIVE_LOCK = Path("build", "driver", "drive.lock")  # held by `reverseapoc drive` for its life


class LockHeld(RuntimeError):
    """Another holder has the lock."""


if sys.platform == "win32":

    def _try(fh) -> bool:
        """One non-blocking try for byte 0. EACCES is contention (the C runtime also sets it
        for access-denied and sharing violations, which equally mean "not ours"); any other
        error is raised."""
        fh.seek(0)
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno != errno.EACCES:
                raise
            return False
        return True

    def _unlock(fh) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)

else:

    def _try(fh) -> bool:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True

    def _unlock(fh) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def is_held(path: Path) -> bool:
    """Whether some live holder has the lock on `path` (todo drive-write-guard): one
    non-blocking try, given straight back when it succeeds. A missing file, or one left behind
    by a holder that exited, is not held. The file is opened for reading only, so the probe
    never creates or writes it."""
    try:
        fh = open(path, "rb")  # noqa: SIM115 - closed below, after the unlock
    except FileNotFoundError:
        return False
    with fh:
        if not _try(fh):
            return True
        _unlock(fh)
        return False


class ProcessLock:
    """A non-blocking OS lock on `path` (see the module docstring). `try_acquire()` is True
    when this object now holds it; `release()` gives it back (a no-op when not held); `with`
    holds it for the block or raises LockHeld."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._fh = None

    @property
    def held(self) -> bool:
        return self._fh is not None

    def try_acquire(self) -> bool:
        if self._fh is not None:
            return True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+b")  # noqa: SIM115 - kept open for the lock's whole life
        try:
            got = _try(fh)
        except BaseException:
            fh.close()
            raise
        if not got:
            fh.close()
            return False
        self._fh = fh
        return True

    def release(self) -> None:
        fh, self._fh = self._fh, None
        if fh is None:
            return
        try:
            _unlock(fh)
        finally:
            fh.close()  # closing frees the lock too

    def __enter__(self) -> ProcessLock:
        if not self.try_acquire():
            raise LockHeld(f"{self.path} is held by another process")
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()
