"""ProcessLock: the non-blocking OS lock `reverseapoc drive` holds for its life (plan 07-18; D-06,
D-24). Liveness is the OS lock alone: no test, and no code under test, probes a process id."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CHILD = """
import os, sys
from reverseapoc.locks import ProcessLock
lock = ProcessLock(sys.argv[1])
print("held" if lock.try_acquire() else "busy", flush=True)
sys.stdin.readline()
os._exit(0)  # no release, no finalizer: only the kernel can free the lock
"""


def test_process_lock_is_exclusive(tmp_path):
    from reverseapoc.locks import ProcessLock

    path = tmp_path / "build" / "driver" / "drive.lock"
    first, second = ProcessLock(path), ProcessLock(path)
    assert first.try_acquire()
    try:
        assert not second.try_acquire()
        assert not second.held
    finally:
        first.release()
    assert second.try_acquire()
    second.release()


def test_process_lock_context_raises_lock_held(tmp_path):
    from reverseapoc.locks import LockHeld, ProcessLock

    path = tmp_path / "drive.lock"
    with ProcessLock(path):
        with pytest.raises(LockHeld, match="drive.lock"):
            with ProcessLock(path):
                pass
    with ProcessLock(path) as again:  # released on leaving the block
        assert again.held


def test_process_lock_release_is_idempotent_and_keeps_the_file(tmp_path):
    from reverseapoc.locks import ProcessLock

    path = tmp_path / "drive.lock"
    lock = ProcessLock(path)
    lock.release()  # never held: nothing to do
    assert lock.try_acquire()
    assert lock.try_acquire()  # already held by this object
    lock.release()
    lock.release()
    assert path.is_file() and path.read_bytes() == b""  # created, never written or deleted


def test_drive_lock_path():
    from reverseapoc.locks import DRIVE_LOCK

    assert DRIVE_LOCK == Path("build", "driver", "drive.lock")


def test_process_lock_freed_on_exit(tmp_path):
    from reverseapoc.locks import ProcessLock

    path = tmp_path / "drive.lock"
    child = subprocess.Popen([sys.executable, "-c", CHILD, str(path)], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, text=True)  # fmt: skip
    try:
        assert child.stdout.readline().strip() == "held"
        mine = ProcessLock(path)
        assert not mine.try_acquire()
        child.stdin.close()  # the child exits without releasing
        assert child.wait(timeout=60) == 0
        assert mine.try_acquire()
        mine.release()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=60)


# --- is_held: the drive write guard's liveness probe (todo drive-write-guard) ----------------


def test_is_held_is_false_for_a_missing_file_and_never_creates_it(tmp_path):
    from reverseapoc.locks import is_held

    path = tmp_path / "build" / "driver" / "drive.lock"
    assert not is_held(path)
    assert not path.exists() and not path.parent.exists()


def test_is_held_is_false_for_a_stale_file_and_frees_it_again(tmp_path):
    """A lock file left behind by a drive that exited is not a live drive, and the probe gives
    the lock straight back, so the next drive can take it."""
    from reverseapoc.locks import ProcessLock, is_held

    path = tmp_path / "drive.lock"
    path.write_bytes(b"")
    assert not is_held(path)
    assert path.read_bytes() == b""
    with ProcessLock(path) as lock:
        assert lock.held


def test_is_held_while_another_handle_holds_it(tmp_path):
    from reverseapoc.locks import ProcessLock, is_held

    path = tmp_path / "drive.lock"
    with ProcessLock(path):
        assert is_held(path)
    assert not is_held(path)


def test_is_held_follows_a_holding_child_process(tmp_path):
    from reverseapoc.locks import is_held

    path = tmp_path / "drive.lock"
    child = subprocess.Popen([sys.executable, "-c", CHILD, str(path)], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, text=True)  # fmt: skip
    try:
        assert child.stdout.readline().strip() == "held"
        assert is_held(path)
        child.stdin.close()  # the child exits without releasing
        assert child.wait(timeout=60) == 0
        assert not is_held(path)  # the file stays behind, stale
        assert path.is_file()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=60)


def test_is_held_is_false_below_a_file(tmp_path):
    """An ancestor that is a file (a `build` file) holds no lock below it; the probe walks every
    ancestor of the hook's cwd, so this must not raise."""
    from reverseapoc.locks import is_held

    (tmp_path / "build").write_bytes(b"")
    assert not is_held(tmp_path / "build" / "driver" / "drive.lock")


def test_a_momentary_probe_does_not_refuse_the_lock(tmp_path, monkeypatch):
    """Review: is_held takes the lock for an instant, so a drive starting in that instant must
    not see it held. One busy try is retried after a short wait, for both callers."""
    from reverseapoc import locks

    path = tmp_path / "drive.lock"
    path.write_bytes(b"")
    real, busy = locks._try, [True]

    def once_busy(fh):
        if busy:
            busy.pop()
            return False
        return real(fh)

    monkeypatch.setattr(locks, "_try", once_busy)
    lock = locks.ProcessLock(path)
    assert lock.try_acquire()
    lock.release()
    busy.append(True)
    assert not locks.is_held(path)
