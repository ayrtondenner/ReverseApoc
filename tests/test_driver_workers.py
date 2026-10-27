"""Claims and locks of the night driver (plan 07-18; D-06, D-24, D-27 P4): the drive.lock held
for the run's life, one O_EXCL claim file per unit, the stale-claim rule, the gate lock around
every landing and shared write, the git lock, GIT_OPTIONAL_LOCKS=0 and the index.lock retry.

The driver still runs one session at a time; "another worker" here is a thread of the same
driver process, as plan 07-21's workers will be. Every session is tests/fakeclaude.py through
the Night harness of test_driver.py; every name and address is made up.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from reverseapoc import driver
from test_driver import EXE, FUNC, RUN, UNIT, Night, Sess, _capture_nights

CLAIM_KEYS = {"run", "worker", "exe", "unit", "function", "start", "kind", "pass", "model",
              "claimed_at"}  # fmt: skip
DRIVE_LOCK_REL = Path("build", "driver", "drive.lock")


def _claim_path(night: Night, exe: str = EXE, unit: str = UNIT) -> Path:
    return night.repo / "build" / "driver" / "claims" / f"{exe}__{unit}.json"


def _held_elsewhere(lock) -> bool:
    """True when another thread cannot take `lock` right now (someone holds it)."""
    got: list[bool] = []

    def probe() -> None:
        ok = lock.acquire(blocking=False)
        got.append(ok)
        if ok:
            lock.release()

    thread = threading.Thread(target=probe)
    thread.start()
    thread.join(timeout=30)
    return got == [False]


# ---- Task 1: the tracer ----


def test_drive_claims_and_releases(tmp_path):
    """A one-session night: the unit's claim file exists while the session runs and while the
    gate runs, holds the ten keys, and is gone after the landing decision."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    claim = _claim_path(night)
    at_session: list[dict | None] = []
    at_gate: list[dict | None] = []

    def read() -> dict | None:
        return json.loads(claim.read_text(encoding="utf-8")) if claim.is_file() else None

    def session(argv, **kw):
        at_session.append(read())
        return night._session(argv, **kw)

    def gate(pick, n):
        at_gate.append(read())
        return night._gate(pick, n)

    report = night.run(session=session, gate=gate)
    assert (report.event, report.matched) == ("ENDED", 1)
    assert at_session and at_session[0] is not None, "no claim while the session ran"
    assert at_gate == at_session
    record = at_session[0]
    assert set(record) == CLAIM_KEYS
    assert (record["run"], record["exe"], record["unit"], record["function"], record["start"],
            record["kind"], record["pass"]) == (RUN, EXE, UNIT, FUNC, "0x00010010", "matching",
                                                1)  # fmt: skip
    assert isinstance(record["worker"], int)
    assert datetime.fromisoformat(record["claimed_at"]).utcoffset() == timedelta(0)
    assert not claim.exists(), "the claim outlived the landing decision"


def test_claim_is_released_when_the_night_stops(tmp_path):
    """A guardrail stop resets the attempt and still releases the unit's claim."""
    night = Night(tmp_path, sessions=[Sess(write="tools/x.py")])
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    assert not _claim_path(night).exists()


def test_second_drive_refused(tmp_path):
    """drive.lock held by another holder: the night is REFUSED (exit 2) naming the lock, and
    no run record is written, no session launched."""
    from reverseapoc.locks import ProcessLock

    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    holder = ProcessLock(night.repo / DRIVE_LOCK_REL)
    assert holder.try_acquire()
    try:
        report = night.run()
    finally:
        holder.release()
    assert (report.event, report.exit_code) == ("REFUSED", 2)
    assert "another reverseapoc drive is running" in report.detail
    assert "drive.lock" in report.detail
    assert (night.repo / "progress" / "attempts.jsonl").read_text(encoding="utf-8") == ""
    assert night.launched == []


def test_drive_lock_is_held_for_the_night_and_freed_after(tmp_path):
    from reverseapoc.locks import ProcessLock

    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    during: list[bool] = []

    def gate(pick, n):
        probe = ProcessLock(night.repo / DRIVE_LOCK_REL)
        during.append(probe.try_acquire())
        probe.release()
        return night._gate(pick, n)

    night.run(gate=gate)
    assert during == [False]
    after = ProcessLock(night.repo / DRIVE_LOCK_REL)
    assert after.try_acquire()
    after.release()


def test_landing_runs_under_the_gate_lock(tmp_path, monkeypatch):
    """The landing section (copy, lint, gate, commit) runs with the gate lock held: another
    thread cannot take it at the lint, the gate or the match commit."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    nights = _capture_nights(monkeypatch)
    held: dict[str, bool] = {}

    def lint(pick):
        held["lint"] = _held_elsewhere(nights[-1].gate_lock)
        return night._lint(pick)

    def gate(pick, n):
        held["gate"] = _held_elsewhere(nights[-1].gate_lock)
        return night._gate(pick, n)

    def on_git(args):
        if "commit" in args and "feat(" in _message_of(args):
            held["commit"] = _held_elsewhere(nights[-1].gate_lock)

    night.on_git = on_git
    report = night.run(lint=lint, gate=gate)
    assert report.matched == 1
    assert held == {"lint": True, "gate": True, "commit": True}
    assert not _held_elsewhere(nights[-1].gate_lock), "the gate lock outlived the night"


def _message_of(args: list[str]) -> str:
    """The commit message file's text of a `git commit -F <file>` argv, else ""."""
    if "-F" not in args:
        return ""
    return Path(args[args.index("-F") + 1]).read_text(encoding="utf-8")


# ---- Task 2: stale claims, the O_EXCL race, no PID probe ----

TOOLS = Path(__file__).resolve().parent.parent / "tools" / "reverseapoc"


def _claim_record(run: str, unit: str = "u_x", worker: int = 0) -> dict:
    return {"run": run, "worker": worker, "exe": EXE, "unit": unit, "function": "func_00099990",
            "start": "0x00099990", "kind": "matching", "pass": 1, "model": None,
            "claimed_at": "2026-10-26T23:59:00+00:00"}  # fmt: skip


def _plant_claim(night: Night, record: dict) -> Path:
    path = _claim_path(night, record["exe"], record["unit"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def test_stale_claim_recovered(tmp_path):
    """A claim left by run "old" (a crashed drive): with drive.lock held the new run moves it to
    build/driver/<run>/stale-claims/ and its STARTED record names ufo2p/u_x and run old."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    planted = _plant_claim(night, _claim_record("old"))
    body = planted.read_bytes()
    report = night.run()
    assert report.event == "ENDED"
    started = night.kinds("run")[0]
    assert started["event"] == "STARTED"
    detail = started["detail"] or ""
    assert "ufo2p/u_x" in detail and "run old" in detail
    moved = night.repo / "build" / "driver" / RUN / "stale-claims" / planted.name
    assert moved.read_bytes() == body
    assert not planted.exists()


def test_unreadable_stale_claim_is_recovered_too(tmp_path):
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    planted = _claim_path(night, EXE, "u_y")
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_bytes(b"not json")
    night.run()
    assert "ufo2p/u_y" in (night.kinds("run")[0]["detail"] or "")
    assert (night.repo / "build" / "driver" / RUN / "stale-claims" / planted.name).is_file()
    assert not planted.exists()


def test_no_stale_claim_leaves_the_started_detail_empty(tmp_path):
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    night.run()
    assert night.kinds("run")[0]["detail"] is None


def test_stale_recover_needs_the_drive_lock(tmp_path):
    """Claims.recover is only callable with drive.lock held: without it, nothing moves."""
    night = Night(tmp_path)
    planted = _plant_claim(night, _claim_record("old"))
    with pytest.raises(driver.DriverError, match="drive.lock"):
        driver.Claims(night.repo, "new").recover()
    assert planted.is_file()


def test_stale_recover_returns_old_claims_and_keeps_the_current_runs(tmp_path):
    from reverseapoc.locks import ProcessLock

    night = Night(tmp_path)
    _plant_claim(night, _claim_record("old"))
    mine = _plant_claim(night, _claim_record("new", unit="u_z"))
    with ProcessLock(night.repo / DRIVE_LOCK_REL):
        found = driver.Claims(night.repo, "new").recover()
    assert found == [{"exe": EXE, "unit": "u_x", "run": "old"}]
    assert mine.is_file()


def test_claim_race_one_winner(tmp_path):
    """DEC-02 adjacency: 8 threads claim one unit at once behind a barrier: exactly one O_EXCL
    create wins, the losers get False and the file holds the winner's worker id."""
    claims = driver.Claims(tmp_path, "night1")
    barrier = threading.Barrier(8)
    results: dict[int, bool] = {}

    def take(worker: int) -> None:
        barrier.wait(timeout=30)
        results[worker] = claims.take(_claim_record("night1", worker=worker))

    threads = [threading.Thread(target=take, args=(w,)) for w in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    winners = [w for w, won in results.items() if won]
    assert len(results) == 8 and len(winners) == 1
    path = claims.path(EXE, "u_x")
    assert json.loads(path.read_text(encoding="utf-8"))["worker"] == winners[0]


def test_no_pid_probe():
    """D-24: liveness is the OS lock only. Neither driver.py nor locks.py calls the os module's
    kill function (on Windows it terminates the process it names). The pattern is built from
    parts, so this file does not hold the call either."""
    name = "ki" + "ll"
    call = re.compile(r"\bos\s*\.\s*" + name + r"\s*\(")
    imported = re.compile(r"\bfrom\s+os\s+import\b[^\n]*\b" + name + r"\b")
    for module in ("driver.py", "locks.py"):
        text = (TOOLS / module).read_text(encoding="utf-8")
        assert not call.search(text), module
        assert not imported.search(text), module
