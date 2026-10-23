"""Parallel `cc` processes keep one intact build/logs/cc.log line per call (gap G-04-2, 04-UAT.md).

The 1600-compile UAT run lost and tore cc.log lines: on the Docker Desktop 9p bind mount and in
the Windows UCRT, append is read-EOF-then-write, so two writers land on the same offset. Writers
here are subprocesses that call the real `compiler._append_log`.

The shared log lives under REPO_ROOT/build, because that is the 9p bind mount inside
`docker compose run` and NTFS on the host, where the loss happens. A tmp_path-only test passes in
the container even with the bug (overlay fs appends atomically), so it is kept only as a second
case. The new lock helpers are reached as `compiler.<name>` at call time, never imported by
name, so every test fails for its own reason when one is missing.
"""

from __future__ import annotations

import errno
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from reverseapoc import compiler
from reverseapoc.cflags import Rule

WRITERS = 16
LINES = 25
SHARED_ROOT = REPO_ROOT / "build" / "test-cclog"
HOLD_SECONDS = 60  # the holder sleeps this long inside the lock unless it is killed
BLOCKED_CHECK_SECONDS = 0.5  # how long a waiting writer must still be waiting
FREED_TIMEOUT_SECONDS = 10  # how long the writer may take once the holder is dead
BUSY_CALLS = 3  # contended msvcrt.locking calls before the lock is granted

LINE_START = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00  .*")
OBJ_ARG = re.compile(r"-fo=\S+")

# argv: log path, writer number w, count. Prints `start` before its first append. Each tag has a
# width that varies with w (like o9 vs o10), so an overwrite tears a line visibly.
WRITER = """
import sys
from pathlib import Path
from reverseapoc import compiler
from reverseapoc.cflags import Rule
log, w, count = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
rule = Rule("*", "wcc386", "10.6", ("-5r", "-s"), 1)
gate = compiler.Gate("10.6", Path("w/10.6"), (("BINNT/WCC386.EXE", "0" * 40),), "Version 10.6")
print("start", flush=True)
for j in range(count):
    tag = f"w{w}-{'x' * (w % 3)}{j}"
    result = compiler.CompileResult(
        Path("a.c"), Path(f"o/{tag}.obj"), rule, gate, ("wcc386", f"-fo=o/{tag}.obj"), 0, "",
        "1" * 40, "2" * 40,
    )
    compiler._append_log(log, result)
"""

# argv: log path. Holds the log lock, says `held`, and sleeps until it is killed.
HOLDER = f"""
import sys, time
from pathlib import Path
from reverseapoc import compiler
with compiler._log_lock(Path(sys.argv[1])):
    print("held", flush=True)
    time.sleep({HOLD_SECONDS})
"""


def _tag(w: int, j: int) -> str:
    return f"w{w}-{'x' * (w % 3)}{j}"


def _result(tag: str) -> compiler.CompileResult:
    """The CompileResult the WRITER program builds for `tag`, in process."""
    rule = Rule("*", "wcc386", "10.6", ("-5r", "-s"), 1)
    gate = compiler.Gate("10.6", Path("w/10.6"), (("BINNT/WCC386.EXE", "0" * 40),), "Version 10.6")
    argv = ("wcc386", f"-fo=o/{tag}.obj")
    return compiler.CompileResult(
        Path("a.c"), Path(f"o/{tag}.obj"), rule, gate, argv, 0, "", "1" * 40, "2" * 40
    )


def _expected_tags() -> set[str]:
    return {f"-fo=o/{_tag(w, j)}.obj" for w in range(WRITERS) for j in range(LINES)}


def _assert_line_intact(line: str) -> None:
    assert LINE_START.fullmatch(line), f"torn line start: {line!r}"
    assert line.endswith("  exit 0"), f"torn line end: {line!r}"
    assert line.count("Version 10.6") == 1, f"merged line: {line!r}"
    assert line.count("-fo=") == 1, f"merged line: {line!r}"


def assert_every_line_intact(lines: list[str]) -> None:
    for line in lines:
        _assert_line_intact(line)
    assert len(lines) == WRITERS * LINES, f"{len(lines)} lines for {WRITERS * LINES} appends"
    tags = [OBJ_ARG.search(line).group(0) for line in lines]
    assert len(set(tags)) == len(tags), "a tag was logged twice"
    assert set(tags) == _expected_tags()


def _log_lines(log: Path) -> list[str]:
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def _start_writer(log: Path, w: int, count: int, stdout=subprocess.DEVNULL) -> subprocess.Popen:
    argv = [sys.executable, "-c", WRITER, str(log), str(w), str(count)]
    return subprocess.Popen(argv, stdout=stdout, text=True)


@pytest.fixture
def shared_dir(request) -> Path:
    """build/test-cclog/<test name>, empty at the start and removed at the end."""
    path = SHARED_ROOT / re.sub(r"[^A-Za-z0-9._-]", "_", request.node.name)
    shutil.rmtree(path, ignore_errors=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.mark.parametrize("where", ["repo-build", "tmp-path"])
def test_concurrent_appends_keep_every_line(where, shared_dir, tmp_path):
    base = shared_dir if where == "repo-build" else tmp_path
    log = base / "logs" / "cc.log"
    writers = [_start_writer(log, w, LINES) for w in range(WRITERS)]
    assert [p.wait() for p in writers] == [0] * WRITERS
    assert_every_line_intact(log.read_text(encoding="utf-8").splitlines())


class _FrozenDatetime:
    @staticmethod
    def now(tz=None) -> datetime:
        return datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


def test_append_writes_the_log_line_and_an_empty_sidecar_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(compiler, "datetime", _FrozenDatetime)
    log = tmp_path / "elsewhere" / "my.log"
    result = _result("w0-0")
    compiler._append_log(log, result)
    compiler._append_log(log, result)
    assert log.read_text(encoding="utf-8") == compiler._log_line(result) * 2
    found = {path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")}
    assert found == {"elsewhere", "elsewhere/my.log", "elsewhere/my.log.lock"}
    assert (tmp_path / "elsewhere" / "my.log.lock").stat().st_size == 0


def test_default_log_and_its_lock():
    assert REPO_ROOT / "build" / "logs" / "cc.log" == compiler.DEFAULT_LOG
    lock = compiler._lock_path(compiler.DEFAULT_LOG)
    assert lock == REPO_ROOT / "build" / "logs" / "cc.log.lock"


def _no_lock(log: Path):
    raise AssertionError(f"took the sidecar lock for {log}")


def test_a_device_log_is_appended_without_the_lock(monkeypatch):
    """os.devnull (`/dev/null`, `nul`) is a device: it needs no append serialisation, and its
    directory may not take a `<log>.lock` (the container's /dev for user dev)."""
    monkeypatch.setattr(compiler, "_log_lock", _no_lock)
    compiler._append_log(Path(os.devnull), _result("w0-0"))


posix_only = pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX-only: /dev/null and its directory /dev"
)


@posix_only
def test_dev_null_log_works_and_leaves_no_sidecar():
    sidecar = Path("/dev/null" + compiler.LOCK_SUFFIX)
    if sidecar.exists():
        pytest.skip(f"{sidecar} already exists, left by something else")
    compiler._append_log(Path("/dev/null"), _result("w0-0"))
    assert not sidecar.exists()


def test_a_killed_lock_holder_does_not_block_later_appends(shared_dir):
    log = shared_dir / "logs" / "cc.log"
    log.parent.mkdir(parents=True)
    procs: list[subprocess.Popen] = []
    try:
        holder = subprocess.Popen(
            [sys.executable, "-c", HOLDER, str(log)], stdout=subprocess.PIPE, text=True
        )
        procs.append(holder)
        assert holder.stdout.readline().strip() == "held"
        writer = _start_writer(log, 0, 1, stdout=subprocess.PIPE)
        procs.append(writer)
        assert writer.stdout.readline().strip() == "start"
        time.sleep(BLOCKED_CHECK_SECONDS)
        assert writer.poll() is None, "the writer did not wait for the lock"
        assert _log_lines(log) == []
        holder.kill()
        holder.wait()
        assert writer.wait(timeout=FREED_TIMEOUT_SECONDS) == 0
        lines = _log_lines(log)
        assert len(lines) == 1
        _assert_line_intact(lines[0])
        assert OBJ_ARG.search(lines[0]).group(0) == "-fo=o/w0-0.obj"
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only: msvcrt lock path")


@windows_only
def test_lock_retries_while_busy(tmp_path, monkeypatch):
    import msvcrt

    real = msvcrt.locking
    calls = []

    def locking(fd, mode, nbytes):
        if mode == msvcrt.LK_NBLCK:
            calls.append(mode)
            if len(calls) <= BUSY_CALLS:
                raise OSError(errno.EACCES, "busy")
        return real(fd, mode, nbytes)

    monkeypatch.setattr(msvcrt, "locking", locking)
    log = tmp_path / "logs" / "cc.log"
    compiler._append_log(log, _result("w0-0"))
    assert len(_log_lines(log)) == 1
    assert len(calls) >= BUSY_CALLS + 1


@windows_only
def test_lock_does_not_swallow_other_errors(tmp_path, monkeypatch):
    import msvcrt

    real = msvcrt.locking
    calls = []

    def locking(fd, mode, nbytes):
        if mode == msvcrt.LK_NBLCK:
            calls.append(mode)
            if len(calls) == 1:
                raise OSError(errno.EBADF, "bad")
        return real(fd, mode, nbytes)

    monkeypatch.setattr(msvcrt, "locking", locking)
    log = tmp_path / "logs" / "cc.log"
    with pytest.raises(OSError) as excinfo:
        compiler._append_log(log, _result("w0-0"))
    assert excinfo.value.errno == errno.EBADF
    assert _log_lines(log) == []
