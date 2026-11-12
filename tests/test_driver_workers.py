"""Claims and locks of the night driver (plan 07-18; D-06, D-24, D-27 P4): the drive.lock held
for the run's life, one O_EXCL claim file per unit, the stale-claim rule, the gate lock around
every landing and shared write, the git lock, GIT_OPTIONAL_LOCKS=0 and the index.lock retry.

Plan 07-21 adds the workers (D-06, D-07): one coordinator hands passes to N worker threads of
the same driver process. Every session is tests/fakeclaude.py through the Night harness of
test_driver.py (WNight for worker threads); every name and address is made up.
"""

from __future__ import annotations

import _thread
import json
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field, fields, replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from reverseapoc import attempt, driver
from reverseapoc.locks import ProcessLock
from reverseapoc.picker import Pick
from reverseapoc.session import kill_tree, run_session
from test_drive import RUN as DRIVE_RUN
from test_drive import Rig, _canary_rig
from test_driver import (
    CHORE,
    EXE,
    FAKE,
    FUNC,
    LOG,
    MATCH_SUBJECT,
    OTHER_RECORD,
    RUN,
    SCAFFOLD,
    SESSION_TEXT,
    START,
    UNIT,
    UNIT_REL,
    VIEW,
    Launch,
    Night,
    Sess,
    _capture_nights,
    _failed_commit_night,
    _one,
    _run_contained,
    _verb,
    _write,
    check_line,
)

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


# ---- Task 3: the git lock, GIT_OPTIONAL_LOCKS=0, the index.lock retry, the gate lock ----


def test_git_calls_serialised(tmp_path):
    """D-27 P4: every driver git call goes through one git lock: a fake git recording enter and
    exit times from two threads never sees two calls overlap."""
    night = Night(tmp_path)
    times: list[tuple[float, float]] = []
    guard = threading.Lock()

    def git(args):
        enter = time.perf_counter()
        time.sleep(0.02)
        leave = time.perf_counter()
        with guard:
            times.append((enter, leave))
        return subprocess.CompletedProcess(list(args), 0, b"", b"")

    probe = driver._Night(night.config(), night.deps(git=git))

    def calls() -> None:
        for _ in range(5):
            probe._git(["status"])

    threads = [threading.Thread(target=calls) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert len(times) == 10
    ordered = sorted(times)
    assert all(left[1] <= right[0] for left, right in zip(ordered, ordered[1:], strict=False))


def test_every_driver_git_call_holds_the_git_lock(tmp_path, monkeypatch):
    """No driver git call bypasses the git lock: at each one, another thread cannot take it."""
    night = Night(tmp_path, sessions=[Sess(checks=(check_line(1, 50.0),)), Sess()],
                  gate_exits=[1, 0])  # fmt: skip
    nights = _capture_nights(monkeypatch)
    held: list[tuple[str | None, bool]] = []
    night.on_git = lambda args: held.append((_verb(args), _held_elsewhere(nights[-1].git_lock)))
    report = night.run()
    assert report.matched == 1
    assert held and all(ok for _, ok in held), [verb for verb, ok in held if not ok]


def test_optional_locks_off(tmp_path, monkeypatch):
    """GIT_OPTIONAL_LOCKS=0 in the driver's git env (given or inherited) and in every session's
    env, so a `git status` never takes index.lock behind another writer's back."""
    seen: list[dict] = []

    def run(argv, **kw):
        seen.append(kw["env"])
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(driver.subprocess, "run", run)
    driver.git_runner(tmp_path, env={"PATH": "made-up"})(["status"])
    driver.git_runner(tmp_path)(["status"])
    assert [env["GIT_OPTIONAL_LOCKS"] for env in seen] == ["0", "0"]
    assert seen[0]["PATH"] == "made-up"
    monkeypatch.undo()
    night = Night(tmp_path / "night", sessions=[Sess()], gate_exits=[0])
    night.run()
    assert night.launched[0].env["GIT_OPTIONAL_LOCKS"] == "0"


def _feat_commits(night: Night) -> list[list[str]]:
    return [c for c in night.git_calls if _verb(c) == "commit" and "feat(" in _message_of(c)]


def test_index_lock_retry(tmp_path):
    """`git commit` failing once on index.lock is retried and the match lands; no undo."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    night.fail_verbs["commit"] = 1
    report = night.run()
    assert (report.event, report.matched) == ("ENDED", 1)
    assert MATCH_SUBJECT in night.commits()
    assert len(_feat_commits(night)) == 2
    assert [r["outcome"] for r in night.kinds("attempt")] == ["MATCHED"]


def test_index_lock_retry_covers_git_add(tmp_path):
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    night.fail_verbs["add"] = 1
    report = night.run()
    assert (report.event, report.matched) == ("ENDED", 1)
    assert MATCH_SUBJECT in night.commits()


def test_index_lock_twice_undoes_the_match(tmp_path):
    """A second index.lock failure undoes the match as before: STOPPED tool, no feat commit,
    no MATCHED line left in the log."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    night.fail_verbs["commit"] = 2
    report = _run_contained(night)
    assert (report.event, report.reason) == ("STOPPED", "tool")
    assert "index.lock" in report.detail
    assert MATCH_SUBJECT not in night.commits()
    assert _one(night.kinds("attempt"))["outcome"] == "GAVE_UP"
    assert '"outcome":"MATCHED"' not in (night.repo / LOG).read_text(encoding="utf-8")


def test_other_commit_failures_are_not_retried(tmp_path):
    """Only an index.lock message is retried: a refusing commit-msg hook fails once, undone."""
    night = _failed_commit_night(tmp_path)
    report = _run_contained(night)
    assert (report.event, report.reason) == ("STOPPED", "tool")
    assert len(_feat_commits(night)) == 1


def test_partial_gate_under_gate_lock(tmp_path, monkeypatch):
    """`gate --partial` writes status.csv: it runs with the gate lock held."""
    night = Night(tmp_path, sessions=[Sess(checks=(check_line(1, 50.0),))])
    nights = _capture_nights(monkeypatch)
    held: list[bool] = []

    def partial(pick, src, n):
        held.append(_held_elsewhere(nights[-1].gate_lock))
        return night._partial(pick, src, n)

    night.run(config={"attempts_per_function": 1}, partial_gate=partial)
    assert held == [True]
    assert _one(night.kinds("attempt"))["outcome"] == "PARTIAL"


def test_every_record_append_holds_the_gate_lock(tmp_path, monkeypatch):
    """Every attempts.jsonl append (run records, attempt records) happens under the gate lock."""
    night = Night(tmp_path, sessions=[Sess(checks=(check_line(1, 50.0),)), Sess()],
                  gate_exits=[1, 0])  # fmt: skip
    nights = _capture_nights(monkeypatch)
    held: list[tuple[str, bool]] = []
    real = driver.record_line

    def line(record):
        held.append((record["kind"], _held_elsewhere(nights[-1].gate_lock)))
        return real(record)

    monkeypatch.setattr(driver, "record_line", line)
    night.run()
    assert [kind for kind, _ in held] == ["run", "attempt", "attempt", "run"]
    assert all(ok for _, ok in held), held


def test_gate_lock_keeps_other_appends_out_of_the_match_undo_window(tmp_path, monkeypatch):
    """F19 relies on the gate lock: from the MATCHED append to the undo's truncation, another
    worker's record (a thread of the same night, appending through _Night._append) waits. So
    the truncation drops only this landing's MATCHED line and the other record survives."""
    night = _failed_commit_night(tmp_path)
    nights = _capture_nights(monkeypatch)
    others: list[threading.Thread] = []
    blocked: list[bool] = []

    def on_git(args):
        if others or _verb(args) != "commit" or "feat(" not in _message_of(args):
            return
        worker = threading.Thread(target=nights[-1]._append, args=(OTHER_RECORD,))
        others.append(worker)
        worker.start()
        worker.join(timeout=0.5)
        blocked.append(worker.is_alive())

    night.on_git = on_git
    report = _run_contained(night)
    others[0].join(timeout=60)
    assert blocked == [True], "another worker's append ran inside the landing window"
    assert (report.event, report.reason) == ("STOPPED", "tool")
    assert OTHER_RECORD in night.records()
    assert '"outcome":"MATCHED"' not in (night.repo / LOG).read_text(encoding="utf-8")


# ---- Fix round 1: resets of src/ under the gate lock; drive.lock from the top of the verb ----


def _unit_restores_held(night: Night, nights: list) -> list[bool]:
    """Arm `night.on_git` to note, at each `git restore` of the claimed unit, whether the gate
    lock was held (another thread could not take it). Returns the list it fills."""
    held: list[bool] = []

    def on_git(args):
        if _verb(args) == "restore" and UNIT_REL in args:
            held.append(_held_elsewhere(nights[-1].gate_lock))

    night.on_git = on_git
    return held


def test_an_unexpected_landing_error_resets_the_unit_under_the_gate_lock(tmp_path, monkeypatch):
    """A landing that raises something unexpected (here the lint) leaves the failed C in src/
    only while the gate lock is held: the unit is put back before the lock is let go, so no
    other worker's whole-EXE gate can see it."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    nights = _capture_nights(monkeypatch)
    held = _unit_restores_held(night, nights)

    def lint(pick):
        raise RuntimeError("made-up lint crash")

    report = night.run(lint=lint)
    assert (report.event, report.reason) == ("STOPPED", "error")
    assert held and all(held), held
    assert (night.repo / UNIT_REL).read_text(encoding="utf-8") == SCAFFOLD


def test_an_unexpected_landing_error_removes_an_untracked_unit_under_the_gate_lock(
        tmp_path, monkeypatch):  # fmt: skip
    """The same for a unit HEAD does not have: the landed copy is deleted before the gate lock
    is let go."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0], unit_committed=False)
    nights = _capture_nights(monkeypatch)
    gone_while_held: list[bool] = []

    def lint(pick):
        raise RuntimeError("made-up lint crash")

    real = driver._Night._reset

    def reset(self, session):
        real(self, session)
        gone_while_held.append(not (night.repo / UNIT_REL).exists()
                               and _held_elsewhere(nights[-1].gate_lock))  # fmt: skip

    monkeypatch.setattr(driver._Night, "_reset", reset)
    report = night.run(lint=lint)
    assert (report.event, report.reason) == ("STOPPED", "error")
    assert gone_while_held and gone_while_held[0], gone_while_held
    assert not (night.repo / UNIT_REL).exists()


def test_a_transient_reset_runs_under_the_gate_lock(tmp_path, monkeypatch):
    """Every reset of the claimed unit in src/ holds the gate lock, the TRANSIENT one too."""
    night = Night(tmp_path, sessions=[Sess("overloaded", write=None), Sess()])
    nights = _capture_nights(monkeypatch)
    held = _unit_restores_held(night, nights)
    night.run(config={"attempts_per_function": 1})
    assert len(night.launched) == 2
    assert held and all(held), held


def _lock_free(repo: Path) -> bool:
    """True when drive.lock of `repo` can be taken right now (nobody holds it)."""
    probe = ProcessLock(repo / DRIVE_LOCK_REL)
    free = probe.try_acquire()
    probe.release()
    return free


@pytest.mark.parametrize("mode", ["night", "dry_run", "canary"])
def test_a_held_drive_lock_refuses_before_any_preflight_step(tmp_path, capsys, mode):
    """D-06 (orchestrator ruling, fix round 1): a second `reverseapoc drive` (a night, a dry run
    or the canary) runs nothing while a night holds drive.lock: exit 2 before any git call,
    command or file of the preflight."""
    rig = Rig(tmp_path)
    holder = ProcessLock(rig.repo / DRIVE_LOCK_REL)
    assert holder.try_acquire()
    try:
        flags = {mode: True} if mode != "night" else {}
        code, out, _ = rig.drive(capsys, json=True, **flags)
    finally:
        holder.release()
    assert code == 2
    doc = json.loads(out)
    assert (doc["event"], doc["reason"]) == ("REFUSED", "drive lock")
    assert "another reverseapoc drive is running" in doc["detail"]
    assert rig.runner.calls == [] and rig.git_calls == []
    assert not (rig.repo / "build" / "driver" / DRIVE_RUN).exists()


def test_run_drive_holds_the_lock_from_the_preflight_through_the_night(tmp_path, capsys):
    """drive.lock is taken before the preflight and the same lock is the night's: every
    command and git call of the verb sees it held, the night is not refused by its own lock,
    and the lock is free once the verb returns."""
    rig = Rig(tmp_path)
    free_at: list[bool] = []
    runner, git = rig.runner, rig.git

    def run(argv):
        free_at.append(_lock_free(rig.repo))
        return runner(argv)

    def recorded_git(args):
        free_at.append(_lock_free(rig.repo))
        return git(args)

    code, out, _ = rig.drive(capsys, json=True, seams={"run": run, "git": recorded_git})
    doc = json.loads(out)
    assert doc["event"] in ("STOPPED", "ENDED"), doc  # the night ran, under the verb's lock
    assert free_at and not any(free_at), free_at
    assert _lock_free(rig.repo)


def test_the_canary_holds_the_drive_lock(tmp_path, capsys):
    held: list[bool] = []
    rig = _canary_rig(tmp_path, "canary_pass", after=lambda repo: held.append(
        not _lock_free(repo)))  # fmt: skip
    rig.drive(capsys, canary=True, json=True)
    assert held == [True]
    assert _lock_free(rig.repo)


def test_run_canary_called_directly_takes_the_lock_itself(tmp_path):
    rig = _canary_rig(tmp_path, "canary_pass")
    holder = ProcessLock(rig.repo / DRIVE_LOCK_REL)
    assert holder.try_acquire()
    try:
        with pytest.raises(driver.Refused, match="another reverseapoc drive is running"):
            driver.run_canary(rig.options(canary=True, json=True), rig.seams())
    finally:
        holder.release()
    assert rig.launches == []


# ---- 07-21 Task 1: workers (D-06, D-24) ----
#
# F39: overlap and ordering are proven with barriers and events, never with sleeps: a barrier
# of N sessions can only be passed by N sessions running at once, and a session that waits for
# another's event proves the order. Every wait has a generous timeout, so a broken driver fails
# the assertion instead of hanging the suite.

WAIT_S = 30.0  # the longest any barrier or event waits before the test fails
WIDEN_S = 0.05  # a gate's pause that would let an unlocked second gate overlap it


def _unit(i: int) -> str:
    return f"u_{0x10000 * (i + 1):08x}"  # u_00010000 is the committed UNIT


def _wpick(i: int, unit: str | None = None) -> Pick:
    start = START + 0x10000 * i
    return Pick(EXE, start, f"func_{start:08X}", unit or _unit(i), 20, 100 + i)


@dataclass
class WNight(Night):
    """The Night harness for worker threads: each session's script is chosen by the unit its
    prompt claims (`by_unit`, then the shared `sessions`, then a session that writes nothing),
    kept per thread, so concurrent `argv`/`session` calls never mix. `before(unit, index)` and
    `after(unit, index)` run in the session's thread around the stand-in claude; `active` and
    `peak` count the sessions running at once."""

    by_unit: dict[str, list[Sess]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__post_init__()
        self.local = threading.local()
        self.lock = threading.Lock()
        self.before = None
        self.after = None
        self.active: dict[str, int] = {}
        self.peak = 0
        self.overlaps: list[str] = []  # a unit seen in two sessions at once
        self.threads: list[threading.Thread] = []
        self.pids: list[tuple[str, int]] = []  # (unit, pid) as each session reported its pid
        self.on_pid = None  # called with (unit, pid) once the driver has the pid
        self.slow: dict[str, float] = {}  # unit -> fakeclaude --sleep: runs until killed
        self.events: list[tuple[str, int]] = []  # ("start" | "end", launch index), in order
        self.at: list[float] = []  # the fake clock at each launch

    def _argv(self, prompt: str, *, model: str, max_budget_usd: float,
              max_turns: int) -> list[str]:  # fmt: skip
        """Deps.argv's keyword signature (07-30); the stand-in ignores the session values."""
        unit = re.search(r"\(claim [a-z0-9]+/([a-z0-9_]+)\)", prompt)[1]
        with self.lock:
            queue = self.by_unit.get(unit) or self.sessions
            spec = queue.pop(0) if queue else Sess(write=None)
            self.prompts.append(prompt)
        self.local.current = spec
        argv = [sys.executable, str(FAKE), "--scenario", spec.scenario, "--env-unit-paths",
                "--any-unit"]  # fmt: skip
        text = spec.unit_text or (SESSION_TEXT if spec.write == VIEW else None)
        argv += ["--write-env-unit", text] if text else []
        return argv + (["--sleep", str(self.slow[unit])] if unit in self.slow else [])

    def _session(self, argv, *, cwd, env, transcript, timeout_s, **hooks):
        spec = self.local.current
        unit = env[attempt.CLAIM_ENV].split("/")[1]
        with self.lock:
            index = len(self.launched)
            self.launched.append(Launch(list(argv), dict(env), Path(cwd), timeout_s))
            self.threads.append(threading.current_thread())
            if self.active.get(unit):
                self.overlaps.append(unit)
            self.active[unit] = self.active.get(unit, 0) + 1
            self.peak = max(self.peak, sum(self.active.values()))
            self.events.append(("start", index))
            self.at.append(self.now)
            self.now += 45.0
        try:
            if self.before is not None:
                self.before(unit, index)
            result = run_session(argv, cwd=cwd, env=env, transcript=transcript,
                                 timeout_s=timeout_s, **self._hooks(unit, hooks))  # fmt: skip
            for rel, text in spec.files:  # what the "agent" left (a stray), after the stream
                _write(Path(cwd) / rel, text)
            attempt_dir = Path(env[attempt.DIR_ENV])
            for line in spec.checks:
                _write(attempt_dir / line["source"], f"/* made-up C of check {line['n']} */\n")
                with (attempt_dir / attempt.CHECK_LOG).open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(line, sort_keys=True) + "\n")
            if self.after is not None:
                self.after(unit, index)
            return result
        finally:
            with self.lock:
                self.active[unit] -= 1
                self.events.append(("end", index))

    def _hooks(self, unit: str, hooks: dict) -> dict:
        """The driver's on_start/on_end (07-21 Task 2), with each reported pid noted once the
        driver has it, then `on_pid(unit, pid)`."""
        on_start = hooks.get("on_start")
        if on_start is None:
            return hooks

        def started(pid: int) -> None:
            on_start(pid)
            with self.lock:
                self.pids.append((unit, pid))
            if self.on_pid is not None:
                self.on_pid(unit, pid)

        return {**hooks, "on_start": started}

    def _sleep(self, seconds: float) -> None:
        with self.lock:
            self.sleeps.append(seconds)
            self.now += seconds


def _src_changes(night: Night) -> list[str]:
    """The paths under src/ that differ from HEAD (staged, unstaged or untracked), read with
    the test's own git and GIT_OPTIONAL_LOCKS=0, so it never takes index.lock."""
    env = {**night.env, "GIT_OPTIONAL_LOCKS": "0"}
    out = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all", "-z",
                          "--", "src"], cwd=night.repo, env=env, capture_output=True,
                         check=True).stdout  # fmt: skip
    return sorted(entry[3:].decode() for entry in out.split(b"\0") if entry)


def _workers(n: int, **over) -> dict:
    return {"workers": n, **over}


def test_three_workers_overlap(tmp_path):
    """D-06: three picks in three units run three sessions at once. Each session waits at a
    barrier of three, which only three concurrent sessions can pass."""
    night = WNight(tmp_path, picks=tuple(_wpick(i) for i in range(3)))
    barrier = threading.Barrier(3, timeout=WAIT_S)
    night.before = lambda unit, index: barrier.wait()
    report = night.run(config=_workers(3, attempts_per_function=1))
    assert (report.event, report.reason) == ("ENDED", "queue exhausted"), report.detail
    assert len(night.launched) == 3 and night.peak == 3
    assert sorted(r["unit"] for r in night.kinds("attempt")) == [_unit(i) for i in range(3)]


def test_same_unit_never_concurrent(tmp_path):
    """Two picks in one unit never hold sessions at the same time: the second is skipped for
    now (the third pick, in another unit, starts while the first still runs) and still runs
    after the first's landing decision."""
    picks = (_wpick(0), _wpick(1, unit=_unit(0)), _wpick(2))
    night = WNight(tmp_path, picks=picks)
    other_started = threading.Event()

    def before(unit, index):
        if unit == _unit(2):
            other_started.set()
        elif index == 0:
            assert other_started.wait(WAIT_S), "the pick in the free unit never started"

    night.before = before
    report = night.run(config=_workers(3, attempts_per_function=1))
    assert (report.event, report.reason) == ("ENDED", "queue exhausted"), report.detail
    assert night.overlaps == []
    assert [r["function"] for r in night.kinds("attempt")][-1] == picks[1].name
    assert sorted(r["function"] for r in night.kinds("attempt")) == sorted(p.name for p in picks)


def test_gates_never_overlap(tmp_path):
    """DEC-02 concurrency (T-07-63): with three sessions ending together, the fake gate's calls
    never overlap, and at each call src/ differs from HEAD only in the landing unit (each
    session writes its view unit, so every landing changes src/)."""
    night = WNight(tmp_path, picks=tuple(_wpick(i) for i in range(3)), sessions=[Sess()] * 3)
    barrier = threading.Barrier(3, timeout=WAIT_S)
    night.before = lambda unit, index: barrier.wait()
    inside = threading.Lock()
    seen: list[tuple[str, list[str], bool]] = []

    def gate(pick, n):
        alone = inside.acquire(blocking=False)
        try:
            seen.append((pick.unit, _src_changes(night), alone))
            threading.Event().wait(WIDEN_S)  # room for a second, unlocked gate to overlap
        finally:
            if alone:
                inside.release()
        return night._gate(pick, n)

    report = night.run(config=_workers(3, attempts_per_function=1), gate=gate)
    assert report.event == "ENDED", report.detail
    assert len(seen) == 3
    for unit, changed, alone in seen:
        assert alone, f"the gate of {unit} overlapped another gate"
        assert changed == [f"src/{EXE}/{unit}.c"], (unit, changed)


def test_broken_view_does_not_leak(tmp_path):
    """D-24: worker B writes C that would not compile into its view unit and is still running
    when worker A's gate runs: A's gate sees HEAD's version of B's unit in src/."""
    unit_b = _unit(0)  # the committed unit: HEAD holds its scaffold
    picks = (_wpick(0), _wpick(1))
    night = WNight(tmp_path, picks=picks,
                   by_unit={unit_b: [Sess(unit_text="this is not C {\n")]})  # fmt: skip
    a_gated = threading.Event()
    at_gate: list[str] = []

    def after(unit, index):
        if unit == unit_b:
            assert a_gated.wait(WAIT_S), "worker A's gate never ran"

    def gate(pick, n):
        if pick.unit != unit_b:
            at_gate.append((night.repo / UNIT_REL).read_text(encoding="utf-8"))
            a_gated.set()
        return night._gate(pick, n)

    night.after = after
    lint = {unit_b: 1}
    report = night.run(config=_workers(3, attempts_per_function=1), gate=gate,
                       lint=lambda pick: lint.get(pick.unit, 0))  # fmt: skip
    assert report.event == "ENDED", report.detail
    assert at_gate == [SCAFFOLD]
    outcomes = {r["unit"]: (r["outcome"], r["abort_reason"]) for r in night.kinds("attempt")}
    assert outcomes[unit_b] == ("GAVE_UP", "lint")
    assert (night.repo / UNIT_REL).read_text(encoding="utf-8") == SCAFFOLD


def test_workers_one_is_serial(tmp_path):
    """`workers=1` is the Phase 6 driver: one session at a time, on the calling thread, and
    the records in queue order."""
    picks = (_wpick(0), _wpick(1), _wpick(2, unit=_unit(0)))
    night = WNight(tmp_path, picks=picks)
    report = night.run(config=_workers(1, attempts_per_function=1))
    assert (report.event, report.reason) == ("ENDED", "queue exhausted")
    assert night.peak == 1
    assert all(t is threading.main_thread() for t in night.threads)
    kinds = [(r["kind"], r.get("function") or r["event"]) for r in night.records()]
    assert kinds == [("run", "STARTED"), *(("attempt", p.name) for p in picks), ("run", "ENDED")]


# ---- 07-21 Task 2: the shared usage-limit pause, stop-all, KeyboardInterrupt (D-07) ----


def _held(night: driver._Night, n: int) -> bool:
    """True once `n` workers wait at the shared pause (each wait is announced on the pause's
    condition, so no polling sleep is needed)."""
    pause = night.pause
    with pause.cond:
        return pause.cond.wait_for(lambda: pause.waiting >= n, timeout=WAIT_S)


def _limit_night(tmp_path, monkeypatch, *, later: tuple[Sess, ...] = ()):
    """Three workers start together; A's session ends LIMIT while B's and C's still run (they
    end only once the pause has begun, i.e. once A's backoff sleep is called). `later` are the
    scripts of the launches after those three."""
    nights = _capture_nights(monkeypatch)
    by_unit = {_unit(0): [Sess("rate_limit", write=None)], _unit(1): [Sess(write=None)],
               _unit(2): [Sess(write=None)]}  # fmt: skip
    night = WNight(tmp_path, picks=tuple(_wpick(i) for i in range(3)), by_unit=by_unit,
                   sessions=list(later))  # fmt: skip
    start = threading.Barrier(3, timeout=WAIT_S)
    paused = threading.Event()

    def before(unit, index):
        if index < 3:
            start.wait()

    def after(unit, index):
        if index < 3 and unit != _unit(0):
            assert paused.wait(WAIT_S), "the pause never began"

    night.before, night.after = before, after
    return night, nights, paused


def test_limit_pauses_all(tmp_path, monkeypatch):
    """D-07: A's LIMIT pauses every worker. B's and C's running sessions finish and are judged;
    no worker launches until the 60 s backoff has passed on the fake clock."""
    night, nights, paused = _limit_night(tmp_path, monkeypatch)
    seen: dict = {}

    def sleep(seconds):
        paused.set()
        seen["held"] = _held(nights[-1], 2)
        seen["launched"] = len(night.launched)
        seen["judged"] = sorted(r["unit"] for r in night.kinds("attempt"))
        seen["now"] = night.now
        night._sleep(seconds)

    report = night.run(config=_workers(3, attempts_per_function=2), sleep=sleep)
    assert report.event == "ENDED", report.detail
    assert night.sleeps == [60]
    assert seen["held"], "B and C never waited at the pause"
    assert seen["launched"] == 3, "a worker launched during the pause"
    assert seen["judged"] == [_unit(1), _unit(2)]
    later = night.at[3:]
    assert later and all(t >= seen["now"] + 60 for t in later), (seen["now"], later)


def _alone(events: list[tuple[str, int]], index: int) -> bool:
    """No other session started while launch `index` ran."""
    begin, end = events.index(("start", index)), events.index(("end", index))
    return all(kind != "start" for kind, _ in events[begin + 1 : end])


def test_one_probe_after_backoff(tmp_path, monkeypatch):
    """After each backoff exactly one worker launches (the probe). A second LIMIT advances the
    shared streak (120 s); the probe that succeeds clears the pause and the others resume."""
    night, nights, paused = _limit_night(tmp_path, monkeypatch,
                                         later=(Sess("rate_limit", write=None),))  # fmt: skip
    at_sleep: list[tuple[int, bool, int]] = []

    def sleep(seconds):
        paused.set()
        at_sleep.append((seconds, _held(nights[-1], 2), len(night.launched)))
        night._sleep(seconds)

    report = night.run(config=_workers(3, attempts_per_function=2), sleep=sleep)
    assert report.event == "ENDED", report.detail
    assert at_sleep == [(60, True, 3), (120, True, 4)]
    assert _alone(night.events, 3) and _alone(night.events, 4)
    assert night.events.index(("start", 4)) > night.events.index(("end", 3))
    assert len(night.launched) >= 6, "the other workers never resumed"


def _recording_kill(kills: list[int]):
    def kill(pid: int) -> None:
        kills.append(pid)
        kill_tree(pid)

    return kill


def _claims_left(night: Night) -> list[Path]:
    return sorted((night.repo / "build" / "driver" / "claims").glob("*.json"))


def test_stop_kills_all_live_sessions(tmp_path):
    """A STOP signal from worker A kills B's and C's live session trees through the pid
    registry; each of their attempts is contained (C's stray quarantined) and reset, nothing
    of theirs is counted, and the night writes one STOPPED record."""
    unit_a, unit_b, unit_c = (_unit(i) for i in range(3))
    night = WNight(tmp_path, picks=tuple(_wpick(i) for i in range(3)),
                   by_unit={unit_a: [Sess("auth", write=None)],
                            unit_c: [Sess(files=(("tools/x.py", "# made-up stray\n"),))]})
    night.slow = {unit_b: 60.0, unit_c: 60.0}  # they run until killed
    both_live = threading.Event()

    def on_pid(unit, pid):
        if {u for u, _ in night.pids} >= {unit_b, unit_c}:
            both_live.set()

    def before(unit, index):
        if unit == unit_a:
            assert both_live.wait(WAIT_S), "B's and C's sessions never reported their pids"

    night.on_pid, night.before = on_pid, before
    kills: list[int] = []
    report = night.run(config=_workers(3, attempts_per_function=1), kill=_recording_kill(kills))
    assert (report.event, report.reason) == ("STOPPED", "stop signal"), report.detail
    live = {pid for unit, pid in night.pids if unit in (unit_b, unit_c)}
    assert len(live) == 2 and live <= set(kills)
    assert [r["event"] for r in night.kinds("run")] == ["STARTED", "STOPPED"]
    assert night.kinds("attempt") == [] and report.sessions == 0
    assert _src_changes(night) == []
    assert not (night.repo / "tools" / "x.py").exists()
    assert (night.quarantine / "tools" / "x.py").is_file()
    assert "tools/x.py" in report.detail
    assert _claims_left(night) == []


def test_keyboard_interrupt_stops_workers(tmp_path):
    """KeyboardInterrupt reaches only the main thread: it stops every worker, kills each
    registered session pid, and the night records STOPPED `interrupted` before re-raising."""
    night = WNight(tmp_path, picks=(_wpick(0), _wpick(1)))
    night.slow = {_unit(0): 60.0, _unit(1): 60.0}
    fired: list[bool] = []

    def on_pid(unit, pid):
        with night.lock:
            if len(night.pids) < 2 or fired:
                return
            fired.append(True)
        _thread.interrupt_main()  # what Ctrl+C does: KeyboardInterrupt on the main thread

    night.on_pid = on_pid
    kills: list[int] = []
    with pytest.raises(KeyboardInterrupt):
        night.run(config=_workers(2, attempts_per_function=1), kill=_recording_kill(kills))
    pids = {pid for _, pid in night.pids}
    assert len(pids) == 2 and pids <= set(kills)
    stopped = _one([r for r in night.kinds("run") if r["event"] == "STOPPED"])
    assert stopped["reason"] == "interrupted"
    assert night.kinds("attempt") == []
    assert _src_changes(night) == []
    assert _claims_left(night) == []


# ---- 07-21 Task 3: the shared night cap with reservations, the new defaults (D-07) ----


def test_cap_shared_across_workers(tmp_path):
    """max_sessions=5 with three workers: a slot is reserved before each launch, so exactly 5
    sessions launch and count. The first three start together; the fourth waits until those
    three are judged, so without reservations every freed worker would launch again."""
    night = WNight(tmp_path, picks=tuple(_wpick(i) for i in range(8)))
    barrier = threading.Barrier(3, timeout=WAIT_S)
    first_three = threading.Event()

    def before(unit, index):
        if index < 3:
            barrier.wait()
        elif index == 3:
            assert first_three.wait(WAIT_S), "the first three sessions were never judged"

    def gate(pick, n):
        done = night._gate(pick, n)
        with night.lock:
            night.gated = getattr(night, "gated", 0) + 1
            if night.gated == 3:
                first_three.set()
        return done

    night.before = before
    report = night.run(config=_workers(3, attempts_per_function=1, max_sessions=5), gate=gate)
    assert (report.event, report.reason, report.sessions) == ("ENDED", "max sessions", 5)
    assert len(night.launched) == 5
    assert len(night.kinds("attempt")) == 5


def test_transient_launches_spend_the_night_cap(tmp_path):
    """07-26 fix round 1 (orchestrator ruling, D-07: the cap counts sessions): every launched
    session counts toward the night cap, a transient one included (it was given back before).
    Unit 0 has four transient sessions, the other three units one counted session each: with
    max_sessions=6 exactly 6 sessions launch, transient and counted together."""
    transient = [Sess("overloaded", write=None)] * 4
    night = WNight(tmp_path, picks=tuple(_wpick(i) for i in range(4)),
                   by_unit={_unit(0): list(transient)})  # fmt: skip
    report = night.run(config=_workers(2, attempts_per_function=1, max_sessions=6))
    assert (report.event, report.reason) == ("ENDED", "max sessions")
    assert _one(night.kinds("abort"))["unit"] == _unit(0)
    assert report.sessions == len(night.kinds("attempt"))
    assert len(night.launched) == 6


def test_target_matched_zero_is_off(tmp_path):
    """target_matched=0 never ends the night on matches (the night cap governs); 2 still ends
    it after two matches."""
    picks = tuple(_wpick(i) for i in range(3))
    night = WNight(tmp_path / "off", picks=picks, sessions=[Sess()] * 3, gate_exits=[0, 0, 0])
    report = night.run(config=_workers(1, target_matched=0))
    assert (report.event, report.reason, report.matched) == ("ENDED", "queue exhausted", 3)
    night = WNight(tmp_path / "two", picks=picks, sessions=[Sess()] * 3, gate_exits=[0, 0, 0])
    report = night.run(config=_workers(1, target_matched=2))
    assert (report.reason, report.matched, len(night.launched)) == ("target matched", 2, 2)


def test_empty_queue_no_session(tmp_path):
    """Three workers and an empty queue: nothing launches, the night ends `nothing to do`."""
    night = WNight(tmp_path, picks=())
    report = night.run(config=_workers(3))
    assert night.launched == []
    assert (report.event, report.reason, report.exit_code) == ("ENDED", "nothing to do", 0)


def test_drive_config_defaults_follow_d07():
    """D-07: the night cap is 60 sessions and the match target is off (0) by default."""
    defaults = {f.name: f.default for f in fields(driver.DriveConfig)}
    assert (defaults["max_sessions"], defaults["target_matched"]) == (60, 0)
    options = driver.DriveOptions(repo=Path("."), run_id="r")
    assert (options.max_sessions, options.target_matched, options.workers) == (60, 0, 3)


# ---- 07-21 fix round 1 ----

STRAY = b'{"stray": "written by session A (made up)"}\n'


def _until(*events: threading.Event) -> bool:
    """True once any of `events` is set (WAIT_S at most); a short wait per round, never an
    ordering assertion on its own."""
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        if any(event.is_set() for event in events):
            return True
        events[0].wait(0.01)
    return False


def test_a_later_sessions_baseline_never_restores_anothers_stray(tmp_path, monkeypatch):
    """C1 (security S2): A writes a stray to a pinned file outside git's view while it runs;
    B launches after that, so B's launch snapshot holds the stray. Every launch and every
    containment compares with the night's pinned baseline: B's launch (or, without that
    check, B's audit after stop-all) contains the stray, and the file ends with its pre-night
    bytes, never the stray again."""
    nights = _capture_nights(monkeypatch)
    unit_a, unit_b = _unit(0), _unit(1)
    night = WNight(tmp_path, picks=(_wpick(0), _wpick(1)))
    settings = night.repo / ".claude" / "settings.local.json"
    _write(settings, '{"made": "up"}\n')
    original = settings.read_bytes()
    night.slow = {unit_b: 60.0}  # B runs until stop-all kills it
    a_strayed, b_live = threading.Event(), threading.Event()

    def pack(pick, attempt_dir, src=None):
        if pick.unit == unit_b:  # B's launch snapshot comes after A's stray
            assert a_strayed.wait(WAIT_S), "A never wrote its stray"
        return night._pack(pick, attempt_dir, src)

    def before(unit, index):
        if unit == unit_a:
            settings.write_bytes(STRAY)
            a_strayed.set()
            assert _until(b_live, nights[-1].stop), "B neither started nor stopped the night"

    def on_pid(unit, pid):
        if unit == unit_b:
            b_live.set()

    night.before, night.on_pid = before, on_pid
    report = night.run(config=_workers(2, attempts_per_function=1), pack=pack,
                       kill=_recording_kill([]))  # fmt: skip
    assert (report.event, report.reason) == ("STOPPED", "guardrail"), report.detail
    assert settings.read_bytes() == original, "a halted session wrote the stray back"
    # The stray is kept; A's audit may also keep a copy of the restored file (its mtime, a
    # fingerprint, changed during A's session), never anything but these two byte strings.
    kept = [path.read_bytes() for path in night.quarantine.rglob("settings.local.json*")]
    assert STRAY in kept and set(kept) <= {STRAY, original}


def test_containment_restores_the_night_baseline_not_the_launch_snapshot(tmp_path):
    """C1, the audit half: a session whose launch snapshot held another's stray (now
    contained) has no pinned change of its own, and a change it does make goes back to the
    night's baseline, not to its launch bytes."""
    night = Night(tmp_path)
    settings = night.repo / ".claude" / "settings.local.json"
    rel = ".claude/settings.local.json"
    _write(settings, '{"made": "up"}\n')
    original = settings.read_bytes()
    probe = driver._Night(night.config(), night.deps())
    probe.pinned_base = probe._pinned_state()  # the night's baseline, before any session
    settings.write_bytes(STRAY)
    launch = probe._snapshot()  # a later session's launch snapshot holds the stray
    settings.write_bytes(original)  # the stray's owner was contained
    claim = driver._Claim(_wpick(0), RUN, night.repo, 1)
    calm = probe._measure(claim, None, driver.PackInfo(0), 0.0, launch, False, b"", "", {})
    assert rel not in calm.pinned_changed
    settings.write_bytes(b"{}\n")  # a change of its own
    session = probe._measure(claim, None, driver.PackInfo(0), 0.0, launch, False, b"", "", {})
    assert rel in session.pinned_changed
    probe._contain(session, [rel])
    assert settings.read_bytes() == original


def _match_commit_add(args: list[str]) -> bool:
    return _verb(args) == "add" and UNIT_REL in args


@pytest.mark.parametrize("rel", [UNIT_REL, f"config/{EXE}/status.csv"])
def test_a_write_between_the_landing_check_and_the_commit_is_never_committed(tmp_path, rel):
    """I1 (security S1): another live session writes the landing unit or status.csv after
    `_verify_landing` but before `git commit` reads it. The driver checks the committed blobs,
    moves HEAD back off its own commit and undoes the match: nothing tampered stays committed
    or in the worktree, and the night stops `guardrail`."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    marker = "/* made-up write of another live session */\n"
    done: list[str] = []

    def on_git(args):
        if not done and _match_commit_add(args):
            with (night.repo / rel).open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(marker)
            done.append(rel)

    night.on_git = on_git
    report = _run_contained(night)
    assert done == [rel]
    assert (report.event, report.reason) == ("STOPPED", "guardrail"), report.detail
    assert MATCH_SUBJECT not in night.commits()
    assert marker not in night.git("show", f"HEAD:{rel}")
    assert marker not in (night.repo / rel).read_text(encoding="utf-8")
    assert _one(night.kinds("attempt"))["outcome"] == "GAVE_UP"
    kept = night.quarantine.joinpath(*rel.split("/"))
    assert kept.is_file() and marker in kept.read_text(encoding="utf-8")


@pytest.mark.parametrize(("rel", "tracked"), [(f"src/{EXE}/u_00099990.c", False),
                                              ("tools/keep.py", True)])  # fmt: skip
def test_another_dirty_path_at_the_match_commit_is_a_breach(tmp_path, rel, tracked):
    """The reviewer's open point (orchestrator ruling): right before the match commit every
    git-visible path but the landing unit and the ledgered outputs must equal HEAD. Another
    unit's src/ file (or any tracked file) written during A's gate stops the night before
    anything is committed; the path is quarantined and put back."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    head = (night.repo / rel).read_bytes() if tracked else None

    def gate(pick, n):
        _write(night.repo / rel, "/* made-up file another live session wrote */\n")
        return night._gate(pick, n)

    report = _run_contained(night, gate=gate)
    assert (report.event, report.reason) == ("STOPPED", "guardrail"), report.detail
    assert MATCH_SUBJECT not in night.commits()
    assert rel in report.detail
    assert (night.repo / rel).read_bytes() == head if tracked else not (night.repo / rel).exists()
    assert night.quarantine.joinpath(*rel.split("/")).is_file()


def test_an_interrupt_record_lists_a_halted_workers_strays(tmp_path):
    """I2: after Ctrl+C a halted worker's audit finds a stray and contains it; the STOPPED
    `interrupted` record names that path (the security ruling: the record lists every path)."""
    night = WNight(tmp_path, picks=(_wpick(0), _wpick(1)),
                   by_unit={_unit(1): [Sess(files=(("tools/x.py", "# made-up stray\n"),))]})
    night.slow = {_unit(0): 60.0, _unit(1): 60.0}
    fired: list[bool] = []

    def on_pid(unit, pid):
        with night.lock:
            if len(night.pids) < 2 or fired:
                return
            fired.append(True)
        _thread.interrupt_main()

    night.on_pid = on_pid
    with pytest.raises(KeyboardInterrupt):
        night.run(config=_workers(2, attempts_per_function=1), kill=_recording_kill([]))
    stopped = _one([r for r in night.kinds("run") if r["event"] == "STOPPED"])
    assert stopped["reason"] == "interrupted"
    assert "tools/x.py" in (stopped["detail"] or ""), stopped["detail"]
    assert not (night.repo / "tools" / "x.py").exists()
    assert (night.quarantine / "tools" / "x.py").is_file()


# ---- 07-21 fix round 2 ----

CRLF_TEXT = "/* made-up unit with CRLF line endings */\r\nint fake_written;\r\n"
FOREIGN = "chore: a made-up commit of another writer"
PINNED_TRACKED = "config/driver/claude-settings.json"


def _commit_files(night: Night, files: dict[str, str]) -> None:
    """Write and commit `files` in the night's repo before the night starts."""
    for rel, text in files.items():
        _write(night.repo / rel, text)
    night.git("add", "--", *files)
    night.git("commit", "-q", "-m", "made-up setup")


def test_a_crlf_unit_under_an_eol_rule_is_committed_without_a_guardrail_stop(tmp_path):
    """N1: under `* text=auto eol=lf` git stores the LF form of a CRLF landed unit. The
    post-commit check compares object ids hashed with the same attributes, so a genuine match
    is committed, not undone as a breach. The rule is set in the test repo itself (the test
    git env has no system config and core.autocrlf=false), so this holds on every host."""
    night = Night(tmp_path, sessions=[Sess(write=None, unit_text=CRLF_TEXT)], gate_exits=[0])
    _commit_files(night, {".gitattributes": "* text=auto eol=lf\n"})
    report = _run_contained(night)
    assert report.reason != "guardrail", report.detail
    assert MATCH_SUBJECT in night.commits(), report.detail
    assert night.file_at(MATCH_SUBJECT, UNIT_REL) == CRLF_TEXT.replace("\r\n", "\n")


def _after_match_commit(action):
    """An on_git hook running `action` once, at the first git call after the match commit's
    `git commit`."""
    state: list[str] = []

    def on_git(args):
        if state == ["committed"]:
            state.append("done")
            action()
        elif not state and _verb(args) == "commit" and UNIT_REL in args:
            state.append("committed")

    return on_git


def _at_match_commit_add(action):
    """An on_git hook running `action` once, right before the match commit's `git add` (after
    the driver read HEAD)."""
    done: list[bool] = []

    def on_git(args):
        if not done and _match_commit_add(args):
            done.append(True)
            action()

    return on_git


def _both(*hooks):
    def on_git(args):
        for hook in hooks:
            hook(args)

    return on_git


@pytest.mark.parametrize("tamper", [False, True], ids=["clean", "tampered"])
@pytest.mark.parametrize("when", ["before the driver's commit", "after the driver's commit"])
def test_a_foreign_commit_during_the_match_commit_never_moves_head(tmp_path, when, tamper):
    """N2: another writer commits while the driver makes its match commit, (a) between the
    driver's HEAD read and its commit, or (b) after its commit but before the post-commit
    check. The driver's commit is then not anchored on the HEAD it read: HEAD is never moved
    back (that would drop the other commit), the night stops `guardrail` and the record names
    the foreign commit."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    status_rel = f"config/{EXE}/status.csv"
    marker = "/* made-up write of another live session */\n"

    def foreign() -> None:
        night.git("commit", "--allow-empty", "-q", "-m", FOREIGN)

    def tampered() -> None:
        with (night.repo / status_rel).open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(marker)

    at_add = [foreign] if when.startswith("before") else []
    at_add += [tampered] if tamper else []
    later = [] if when.startswith("before") else [foreign]
    night.on_git = _both(*(_at_match_commit_add(f) for f in at_add),
                         *(_after_match_commit(f) for f in later))  # fmt: skip
    report = _run_contained(night)
    assert (report.event, report.reason) == ("STOPPED", "guardrail"), report.detail
    subjects = night.commits()
    assert FOREIGN in subjects and MATCH_SUBJECT in subjects, "HEAD was moved back"
    foreign_sha = night.sha(FOREIGN)
    assert foreign_sha[:12] in (report.detail or ""), report.detail
    if tamper:
        assert status_rel in report.detail
        assert marker not in (night.repo / status_rel).read_text(encoding="utf-8")


def test_a_launch_check_puts_a_tracked_pinned_file_back_to_the_night_baseline(tmp_path):
    """N3: a stray write to a TRACKED pinned path (no session owns it, so no later audit
    puts it right) is caught at the launch check. It goes back to the night's baseline, never
    to the launch snapshot that holds the stray, and the record never calls it restored while
    it is still changed."""
    night = Night(tmp_path, sessions=[Sess()])
    _commit_files(night, {PINNED_TRACKED: '{"made": "up"}\n'})
    settings = night.repo / PINNED_TRACKED
    original = settings.read_bytes()

    def pack(pick, attempt_dir, src=None):  # after the night's baseline, before the launch
        settings.write_bytes(STRAY)
        return night._pack(pick, attempt_dir, src)

    report = _run_contained(night, pack=pack)
    assert (report.event, report.reason) == ("STOPPED", "guardrail"), report.detail
    assert night.launched == []
    assert settings.read_bytes() == original, report.detail
    assert "still changed after containment" not in report.detail, report.detail
    assert night.git("status", "--porcelain", "--", PINNED_TRACKED) == ""
    kept = [path.read_bytes() for path in night.quarantine.rglob("claude-settings.json*")]
    assert STRAY in kept


def test_a_failed_check_after_the_match_commit_keeps_the_commit_and_reverts_nothing(tmp_path):
    """N4: the match commit exists, then the post-commit check itself fails (here its
    `rev-parse`). That is a guardrail stop with the error in the detail: status.csv and the
    log are never put back to their pre-match bytes under the kept commit, and no chore
    commit follows."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    status_rel = f"config/{EXE}/status.csv"

    def broken() -> None:
        raise RuntimeError("made-up rev-parse failure")

    night.on_git = _after_match_commit(broken)
    report = _run_contained(night)
    assert (report.event, report.reason) == ("STOPPED", "guardrail"), report.detail
    assert "made-up rev-parse failure" in report.detail
    assert night.commits() == [MATCH_SUBJECT]
    head_status = night.git("show", f"HEAD:{status_rel}")
    assert (night.repo / status_rel).read_text(encoding="utf-8") == head_status
    head_log = night.git("show", f"HEAD:{LOG}")
    assert (night.repo / LOG).read_text(encoding="utf-8").startswith(head_log)


# ---- 07.2-16 (D-22, D-26): several arms in one drive ----

HAIKU = "claude-haiku-5-5"
SONNET = "claude-sonnet-5-5"
DEEPSEEK = "deepseek-flash"
TWO_ARMS = ((HAIKU, 1), (SONNET, 1))


@dataclass
class ArmNight(WNight):
    """WNight whose stand-in claude echoes the requested model into its init event, as the
    real CLI does, so a session of any Claude or hosted arm passes the init check. A model's
    scripts in `by_model` come before the unit's (07.2-16 Task 2: one arm's LIMIT)."""

    by_model: dict[str, list[Sess]] = field(default_factory=dict)

    def _argv(self, prompt: str, *, model: str, max_budget_usd: float,
              max_turns: int) -> list[str]:  # fmt: skip
        with self.lock:
            scripted = self.by_model.get(model)
            spec = scripted.pop(0) if scripted else None
        if spec is None:
            argv = super()._argv(prompt, model=model, max_budget_usd=max_budget_usd,
                                 max_turns=max_turns)  # fmt: skip
        else:
            with self.lock:
                self.prompts.append(prompt)
            self.local.current = spec
            argv = [sys.executable, str(FAKE), "--scenario", spec.scenario, "--env-unit-paths",
                    "--any-unit"]  # fmt: skip
        return argv + (["--model", model] if model != driver.OPUS_MODEL else [])


def _arm_run(arm: str) -> str:
    return f"{RUN}-{arm}"


def _driver_dir(night: Night) -> Path:
    return night.repo / "build" / "driver"


def _run_of(night: Night, launch: Launch) -> str:
    """The run directory a launch's attempt dir lies in (build/driver/<run>/...)."""
    return Path(launch.env[attempt.DIR_ENV]).relative_to(_driver_dir(night)).parts[0]


def test_two_arms_one_process(tmp_path):
    """D-22, D-26: two arms of one worker each over three picks under --hold: six sessions,
    three per arm, each arm's records under its own run id with its model, backend and harness,
    one attempt directory per function per arm under build/driver/<run>-<arm>/, none shared or
    moved aside as uncounted; the night's own run records keep the base run id and count every
    arm's attempts."""
    picks = tuple(_wpick(i) for i in range(3))
    night = ArmNight(tmp_path, picks=picks)
    report = night.run(config={"arms": TWO_ARMS, "hold": True})
    assert report.event == "ENDED", report.detail
    assert len(night.launched) == 6 and report.sessions == 6
    attempts = night.kinds("attempt")
    for arm in (HAIKU, SONNET):
        mine = [r for r in attempts if r["run"] == _arm_run(arm)]
        assert sorted(r["function"] for r in mine) == sorted(p.name for p in picks), arm
        assert {(r["model_requested"], r["backend"], r["harness"], r["hold_run"])
                for r in mine} == {(arm, "anthropic", "claude", True)}  # fmt: skip
        for pick in picks:
            assert (_driver_dir(night) / _arm_run(arm) / EXE / pick.name / "attempt-1").is_dir()
        assert (_driver_dir(night) / _arm_run(arm) / driver.HOLD_RUN_MARKER).is_file()
    assert {r["run"] for r in attempts} == {_arm_run(HAIKU), _arm_run(SONNET)}
    runs = sorted(p.name for p in _driver_dir(night).iterdir() if p.name.startswith(f"{RUN}-"))
    assert runs == [_arm_run(HAIKU), _arm_run(SONNET)]
    assert list(_driver_dir(night).rglob("*-uncounted-*")) == []
    run_records = night.kinds("run")
    assert [r["run"] for r in run_records] == [RUN, RUN]
    assert run_records[-1]["workers"] == 2
    totals = run_records[-1]["totals"]
    assert sum(totals["sessions"].values()) == 6
    assert {name: share["sessions"] for name, share in totals["by_model"].items()} == {
        HAIKU: 3, SONNET: 3}  # fmt: skip


def test_two_arms_one_lock(tmp_path, monkeypatch):
    """D-22: one drive lock for the whole process, whatever the arms; while it runs, a second
    drive on the same checkout is refused as today."""
    taken: list[object] = []
    real = driver.take_drive_lock

    def counted(repo):
        lock = real(repo)
        taken.append(lock)
        return lock

    monkeypatch.setattr(driver, "take_drive_lock", counted)
    night = ArmNight(tmp_path, picks=tuple(_wpick(i) for i in range(2)))
    second: list[driver.DriveReport] = []

    def before(unit, index):
        if index == 0:
            second.append(driver.drive(night.config(arms=TWO_ARMS), night.deps()))

    night.before = before
    report = night.run(config={"arms": TWO_ARMS, "hold": True})
    assert report.event == "ENDED", report.detail
    assert len(taken) == 1, "the night took more than one drive lock"
    assert [(r.event, r.exit_code) for r in second] == [("REFUSED", 2)]
    assert "another reverseapoc drive is running" in second[0].detail


def test_two_arms_never_share_a_unit(tmp_path):
    """Claims stay per unit across arms: two arms' sessions on functions of one unit never run
    at the same time, and each arm still attempts every function once."""
    picks = tuple(_wpick(i, unit=_unit(0)) for i in range(3))
    night = ArmNight(tmp_path, picks=picks)
    report = night.run(config={"arms": TWO_ARMS, "hold": True})
    assert report.event == "ENDED", report.detail
    assert night.overlaps == [] and night.peak == 1
    assert len(night.launched) == 6
    runs = sorted(r["run"] for r in night.kinds("attempt"))
    assert runs == [_arm_run(HAIKU)] * 3 + [_arm_run(SONNET)] * 3


def _shape(night: Night) -> list[tuple]:
    return sorted((r["run"], r["function"], r["model_requested"], r["outcome"], r["attempt"])
                  for r in night.kinds("attempt"))  # fmt: skip


def test_night_model_is_one_arm(tmp_path):
    """D-22: `--night-model X --workers 2` is the one-arm shorthand: the same night as
    `--arm X=2`, under the base run id."""
    picks = tuple(_wpick(i) for i in range(2))
    short = ArmNight(tmp_path / "short", picks=picks)
    short.run(config={"night_model": HAIKU, "workers": 2, "hold": True})
    arm = ArmNight(tmp_path / "arm", picks=picks)
    report = arm.run(config={"arms": ((HAIKU, 2),), "hold": True})
    assert report.event == "ENDED", report.detail
    assert _shape(short) == _shape(arm)
    assert {r["run"] for r in arm.kinds("attempt")} == {RUN}


def test_each_arm_gets_its_own_session_env(tmp_path):
    """RULINGS token-leak guard, inside a multi-arm night: the hosted arm's session gets its
    endpoint, its own key as the bearer token and REVERSEAPOC_EGRESS; the Claude arm's session
    beside it gets none of them and no arm's key variable."""
    from reverseapoc import hooks
    from test_drive import DEEPSEEK_URL, FAKE_KEY, _keyed

    night = ArmNight(tmp_path, picks=tuple(_wpick(i) for i in range(2)))
    env = _keyed(night.env, OPENROUTER_API_KEY=FAKE_KEY)
    report = night.run(config={"arms": ((HAIKU, 1), (DEEPSEEK, 1)), "hold": True,
                               "base_env": env})  # fmt: skip
    assert report.event == "ENDED", report.detail
    by_run: dict[str, dict] = {}
    for launch in night.launched:
        by_run.setdefault(_run_of(night, launch), launch.env)
    hosted, claude = by_run[_arm_run(DEEPSEEK)], by_run[_arm_run(HAIKU)]
    assert hosted.get("ANTHROPIC_BASE_URL") == DEEPSEEK_URL
    assert hosted.get("ANTHROPIC_AUTH_TOKEN") == FAKE_KEY
    assert hosted.get(hooks.EGRESS_ENV) == "1"
    for name in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "OPENROUTER_API_KEY",
                 hooks.EGRESS_ENV):  # fmt: skip
        assert name not in set(claude), name
    assert "OPENROUTER_API_KEY" not in set(hosted)


# ---- 07.2-16 Task 2 (D-22): each arm's own usage pause and limits ----

LOCAL = "qwen-local"


def _runs_launched(night: Night, run: str) -> int:
    with night.lock:
        return sum(_run_of(night, launch) == run for launch in night.launched)


def _poll(predicate) -> bool:
    """True once `predicate()` holds, False after WAIT_S."""
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def _one_arm_limited(tmp_path, monkeypatch):
    """Two arms over four picks under --hold. The Sonnet arm's first session ends LIMIT while
    the Haiku arm's first session runs; that Haiku session ends only once Sonnet's pause has
    begun (its backoff sleep was called), and the backoff lasts until the Haiku arm has
    launched again twice (or WAIT_S passed)."""
    nights = _capture_nights(monkeypatch)
    picks = tuple(_wpick(i) for i in range(4))
    night = ArmNight(tmp_path, picks=picks, by_model={SONNET: [Sess("rate_limit", write=None)]})
    paused = threading.Event()
    seen: dict = {}

    def after(unit, index):
        if _run_of(night, night.launched[index]) == _arm_run(HAIKU) and not paused.is_set():
            assert paused.wait(WAIT_S), "the Sonnet arm's pause never began"

    def sleep(seconds):
        paused.set()
        seen["haiku_launched_while_paused"] = _poll(
            lambda: _runs_launched(night, _arm_run(HAIKU)) >= 3)
        seen["sonnet_launched_while_paused"] = _runs_launched(night, _arm_run(SONNET))
        night._sleep(seconds)

    night.after = after
    report = night.run(config={"arms": ((SONNET, 1), (HAIKU, 1)), "hold": True}, sleep=sleep)
    return night, nights, seen, report


def test_limit_pauses_only_its_arm(tmp_path, monkeypatch):
    """D-22: one arm's LIMIT (a Codex Plus window, an Antigravity quota) starts that arm's pause
    only: the other arm keeps launching while it holds, the paused arm launches nothing until
    its backoff passed, and its probe clears its own pause."""
    night, nights, seen, report = _one_arm_limited(tmp_path, monkeypatch)
    assert report.event == "ENDED", report.detail
    assert seen["haiku_launched_while_paused"], "Sonnet's pause stopped the Haiku arm"
    assert seen["sonnet_launched_while_paused"] == 1
    assert night.sleeps == [60]
    assert _runs_launched(night, _arm_run(SONNET)) == 5  # the LIMIT launch, then four attempts
    assert _runs_launched(night, _arm_run(HAIKU)) == 4
    lanes = nights[-1].lanes
    assert [lane.pause.paused for lane in lanes] == [False, False]
    assert lanes[0].pause is not lanes[1].pause


def test_limit_record_names_its_arm(tmp_path, monkeypatch):
    """The limit record of an arm's wait carries that arm's run id and its worker."""
    night, _, _, report = _one_arm_limited(tmp_path, monkeypatch)
    assert report.event == "ENDED", report.detail
    (limit,) = night.kinds("limit")
    assert (limit["run"], limit["worker"], limit["seconds"]) == (_arm_run(SONNET), 0, 60)
    driver.validate_record(limit)


def test_arm_caps(tmp_path, capsys):
    """D-22: an arm's workers above its max_workers are refused before any session; an arm's
    max_sessions stops that arm's launches at its cap while the other arm goes on; the night's
    --max-sessions still caps the total."""
    rig = Rig(tmp_path / "rig")
    code, out, _ = rig.drive(capsys, json=True, arms=((HAIKU, 1), (SONNET, 11)))
    assert code == 2 and "max_workers" in json.loads(out)["detail"]
    assert rig.runner.calls == []
    table = driver.backends.load_arms()
    table[HAIKU] = replace(table[HAIKU], max_sessions=2)
    picks = tuple(_wpick(i) for i in range(3))
    capped = ArmNight(tmp_path / "capped", picks=picks)
    report = capped.run(config={"arms": TWO_ARMS, "hold": True, "arm_table": table})
    assert report.event == "ENDED", report.detail
    assert _runs_launched(capped, _arm_run(HAIKU)) == 2
    assert _runs_launched(capped, _arm_run(SONNET)) == 3
    total = ArmNight(tmp_path / "total", picks=picks)
    report = total.run(config={"arms": TWO_ARMS, "hold": True, "max_sessions": 4})
    assert (report.event, report.reason) == ("ENDED", driver.MAX_SESSIONS), report.detail
    assert len(total.launched) == 4


def test_local_arm_beside_cloud(tmp_path, capsys):
    """D-22: the local arm (max_workers 1) runs beside a cloud arm of two workers, three
    sessions at once, but never two local sessions at once; `qwen-local=2` is refused."""
    from test_drive import _keyed

    rig = Rig(tmp_path / "rig")
    code, out, _ = rig.drive(capsys, json=True, seams={"base_env": _keyed(rig.env)},
                             arms=((LOCAL, 2), (HAIKU, 1)))  # fmt: skip
    assert code == 2 and "max_workers" in json.loads(out)["detail"]
    picks = tuple(_wpick(i) for i in range(4))
    night = ArmNight(tmp_path / "night", picks=picks)
    together = threading.Barrier(3, timeout=WAIT_S)
    night.before = lambda unit, index: together.wait() if index < 3 else None
    report = night.run(config={"arms": ((LOCAL, 1), (HAIKU, 2)), "hold": True,
                               "base_env": _keyed(night.env)})  # fmt: skip
    assert report.event == "ENDED", report.detail
    assert night.peak == 3
    local = {i for i, launch in enumerate(night.launched)
             if _run_of(night, launch) == _arm_run(LOCAL)}  # fmt: skip
    active = peak = 0
    for event, index in night.events:
        if index in local:
            active += 1 if event == "start" else -1
            peak = max(peak, active)
    assert peak == 1 and len(local) == 4


# ---- owner ruling 2026-11-10: a hook-denied write stops its arm only ----

DENIED = Sess("denied_write", write=None)  # a Write to tools/x.py the hook denied
DENIED_PATH = "/repo/tools/x.py"


def test_a_denied_write_stops_its_arm_only(tmp_path):
    """Owner ruling 2026-11-10: a session whose only stray is a write the hook denied (in the
    result event's permission_denials) with nothing changed is recorded GAVE_UP guardrail as
    today and stops its arm only: that arm launches nothing more, the other arm attempts every
    pick, the night ENDS and commits its log, and the run record and one console line name the
    arm, the attempt and the denied path. Nothing is quarantined."""
    picks = tuple(_wpick(i) for i in range(3))
    night = ArmNight(tmp_path, picks=picks, by_model={HAIKU: [DENIED]})
    lines: list[str] = []
    report = night.run(config={"arms": TWO_ARMS, "hold": True}, say=lines.append)
    assert (report.event, report.reason) == ("ENDED", driver.QUEUE_EXHAUSTED), report.detail
    assert _runs_launched(night, _arm_run(HAIKU)) == 1
    assert _runs_launched(night, _arm_run(SONNET)) == 3
    (stopped,) = [r for r in night.kinds("attempt") if r["run"] == _arm_run(HAIKU)]
    assert (stopped["outcome"], stopped["abort_reason"]) == ("GAVE_UP", "guardrail")
    final = night.kinds("run")[-1]
    assert (final["event"], final["schema"]) == ("ENDED", 3)
    for text in (final["detail"], report.detail):
        assert HAIKU in text and picks[0].name in text and DENIED_PATH in text, text
    said = [line for line in lines if "stopped" in line and HAIKU in line]
    assert len(said) == 1 and DENIED_PATH in said[0] and picks[0].name in said[0], lines
    assert night.commits() == [CHORE]
    quarantine = _driver_dir(night) / _arm_run(HAIKU) / "quarantine"
    assert not quarantine.exists() or list(quarantine.rglob("*")) == []
    for record in night.records():
        driver.validate_record(record)


def test_a_stopped_arm_relaunches_nothing(tmp_path, monkeypatch):
    """A session of the stopped arm still in flight finishes, but its LIMIT relaunch is a launch
    the stopped arm no longer makes; the other arm goes on."""
    nights = _capture_nights(monkeypatch)
    picks = tuple(_wpick(i) for i in range(3))
    night = ArmNight(tmp_path, picks=picks,
                     by_model={HAIKU: [DENIED, Sess("rate_limit", write=None)]})  # fmt: skip

    def after(unit, index):  # the LIMIT session ends only once the denied write stopped its arm
        if "rate_limit" in night.launched[index].argv:
            assert _poll(lambda: nights[-1].lanes[0].stopped), "the Haiku arm never stopped"

    night.after = after
    report = night.run(config={"arms": ((HAIKU, 2), (SONNET, 1)), "hold": True})
    assert (report.event, report.reason) == ("ENDED", driver.QUEUE_EXHAUSTED), report.detail
    assert _runs_launched(night, _arm_run(HAIKU)) == 2
    assert _runs_launched(night, _arm_run(SONNET)) == 3


def test_a_denied_write_with_one_arm_stops_the_night(tmp_path):
    """With one arm, stopping the arm is stopping the night, exactly as before the ruling."""
    night = ArmNight(tmp_path, picks=tuple(_wpick(i) for i in range(2)),
                     by_model={HAIKU: [DENIED]})  # fmt: skip
    report = night.run(config={"arms": ((HAIKU, 1),), "hold": True})
    assert (report.event, report.reason) == ("STOPPED", "guardrail"), report.detail
    assert DENIED_PATH in report.detail
    assert len(night.launched) == 1


def test_a_hold_run_resumes(tmp_path):
    """Owner approval 2026-11-10: the same `--hold --run` drive again resumes it. Each arm skips
    the functions its run already attempted with a counted session in the committed log, and
    attempts again the rest: one whose record is a GAVE_UP guardrail (the stop cut it short)
    in a fresh attempt-2 directory beside its attempt-1, one with no record in attempt-1. An
    arm with every pick done launches nothing."""
    picks = tuple(_wpick(i) for i in range(3))
    night = ArmNight(tmp_path, picks=picks, by_model={HAIKU: [DENIED]})
    first = night.run(config={"arms": TWO_ARMS, "hold": True})
    assert first.event == "ENDED", first.detail
    before = len(night.launched)
    report = night.run(config={"arms": TWO_ARMS, "hold": True})
    assert (report.event, report.reason) == ("ENDED", driver.QUEUE_EXHAUSTED), report.detail
    again = night.launched[before:]
    assert sorted(_run_of(night, launch) for launch in again) == [_arm_run(HAIKU)] * 3
    haiku = sorted((r["function"], r["attempt"], r["abort_reason"]) for r in night.kinds("attempt")
                   if r["run"] == _arm_run(HAIKU))  # fmt: skip
    assert haiku == [(picks[0].name, 1, "guardrail"), (picks[0].name, 2, None),
                     (picks[1].name, 1, None), (picks[2].name, 1, None)]  # fmt: skip
    sonnet = [r for r in night.kinds("attempt") if r["run"] == _arm_run(SONNET)]
    assert len(sonnet) == 3
    redo = _driver_dir(night) / _arm_run(HAIKU) / EXE / picks[0].name
    assert sorted(p.name for p in redo.iterdir()) == ["attempt-1", "attempt-2"]
    assert list(_driver_dir(night).rglob("*-uncounted-*")) == []
    assert night.kinds("run")[-1]["sessions"] == 3
    for record in night.records():
        driver.validate_record(record)


def test_a_finished_hold_run_resumes_to_nothing(tmp_path):
    """Every arm's every pick counted: the same hold drive again launches nothing."""
    night = ArmNight(tmp_path, picks=tuple(_wpick(i) for i in range(2)))
    assert night.run(config={"arms": TWO_ARMS, "hold": True}).event == "ENDED"
    before = len(night.launched)
    report = night.run(config={"arms": TWO_ARMS, "hold": True})
    assert report.event == "ENDED", report.detail
    assert len(night.launched) == before


GEMINI = "gemini-flash"  # an agy arm (07.2-15)
AGY_DENIED_PATH = "C:\\made-up\\tools\\x.py"  # soft_denied_write's write, agy refused it


@dataclass
class AgyArmNight(ArmNight):
    """ArmNight with agy arms: each agy session is tests/fakeagy.py through the real argv
    builder (test_agy.fake_agy_argv), replaying the next of `agy_scenarios`, then
    gemini_success (a clean wrapper session)."""

    agy_scenarios: list[str] = field(default_factory=list)

    def _agy_argv(self, prompt: str, **values) -> list[str]:
        from test_agy import fake_agy_argv

        with self.lock:
            self.prompts.append(prompt)
            scenario = self.agy_scenarios.pop(0) if self.agy_scenarios else "gemini_success"
        self.local.current = Sess(write=None)
        self.local.scenario = scenario
        return fake_agy_argv(prompt, **values)

    def _session(self, argv, *, env, **values):
        scenario, self.local.scenario = getattr(self.local, "scenario", None), None
        env = {**env, "FAKEAGY_SCENARIO": scenario} if scenario else env
        return super()._session(argv, env=env, **values)

    def deps(self, **over) -> driver.Deps:
        return super().deps(**{"agy_argv": self._agy_argv, **over})


def test_an_agy_soft_denied_write_stops_its_arm_only(tmp_path):
    """Owner ruling 2026-11-10 ("extend it"): the arm-only stop covers agy arms. An agy
    session's write that agy's permission check provably refused (agyjson.denials: its exact
    refusal of the step's own request) counts as a denied write in the same decision as a
    Claude hook-denied one: with nothing else stray and nothing changed after the reset, the
    attempt is GAVE_UP guardrail, only that arm stops (it launches nothing more), the Claude
    arm attempts every pick, the night ENDS, and the console line names the arm, the attempt
    and the refused path."""
    picks = tuple(_wpick(i) for i in range(3))
    night = AgyArmNight(tmp_path, picks=picks, agy_scenarios=["soft_denied_write"])
    lines: list[str] = []
    report = night.run(config={"arms": ((HAIKU, 1), (GEMINI, 1)), "hold": True},
                       say=lines.append)  # fmt: skip
    assert (report.event, report.reason) == ("ENDED", driver.QUEUE_EXHAUSTED), report.detail
    assert _runs_launched(night, _arm_run(GEMINI)) == 1
    assert _runs_launched(night, _arm_run(HAIKU)) == 3
    (stopped,) = [r for r in night.kinds("attempt") if r["run"] == _arm_run(GEMINI)]
    assert (stopped["outcome"], stopped["abort_reason"]) == ("GAVE_UP", "guardrail")
    said = [line for line in lines if "stopped" in line and GEMINI in line]
    assert len(said) == 1 and AGY_DENIED_PATH in said[0], lines
    assert stopped["function"] in said[0] and "agy's permission check denied" in said[0], said
    for record in night.records():
        driver.validate_record(record)


@pytest.mark.parametrize("scenario", ["stray_write", "soft_denied_write_beside_ran"])
def test_an_agy_write_that_ran_stops_every_arm(tmp_path, scenario):
    """A write an agy session ran (no denial), even beside a write agy refused, stops the
    whole multi-arm drive at the guardrail as before."""
    night = AgyArmNight(tmp_path, picks=tuple(_wpick(i) for i in range(3)),
                        agy_scenarios=[scenario])  # fmt: skip
    report = night.run(config={"arms": ((HAIKU, 1), (GEMINI, 1)), "hold": True})
    assert (report.event, report.reason) == ("STOPPED", "guardrail"), report.detail
    assert "tools/x.py" in report.detail.replace("\\", "/")


@pytest.mark.parametrize(
    "spec",
    [Sess("undenied_write", write=None),
     Sess("denied_write", write=None, files=(("tools/y.py", "# made up\n"),)),
     Sess("denied_write_shared_id", write=None), Sess("denied_other_tool", write=None),
     Sess("denied_other_path", write=None)],
    ids=["write-not-denied", "denied-and-a-changed-file", "id-shared-by-two-writes",
         "denial-names-another-tool", "denial-names-another-path"],
)  # fmt: skip
def test_any_other_stray_still_stops_every_arm(tmp_path, spec):
    """A write the hook did not deny, or a denied write beside a file the session changed, stops
    the whole multi-arm drive as today. Security review of the arm-only stop: tool_use ids on
    hosted arms come from the provider, so a write counts as denied only when its id is the
    transcript's only tool_use with that id and the denial names the same tool and target; two
    writes sharing an id (one denied, one not) or a denial naming another tool or path stop
    every arm."""
    night = ArmNight(tmp_path, picks=tuple(_wpick(i) for i in range(3)),
                     by_model={HAIKU: [spec]})  # fmt: skip
    report = night.run(config={"arms": TWO_ARMS, "hold": True})
    assert (report.event, report.reason) == ("STOPPED", "guardrail"), report.detail
    assert DENIED_PATH in report.detail


# ---- quick 261112-fds (backlog 999.12a): the size-routed cascade ----

ROW_LABELS = (("[0, 64)", (0,)), ("[64, 256)", (1,)), ("[256, inf)", (2, 3)))


def _rows(*arms: tuple[str, ...]) -> tuple[driver.backends.Route, ...]:
    """Routing rows for the three committed keys, the n-th row's arms `arms[n]`."""
    return tuple(driver.backends.Route(label, buckets, tuple(row))
                 for (label, buckets), row in zip(ROW_LABELS, arms, strict=True))  # fmt: skip


def _every(*arms: str) -> tuple[driver.backends.Route, ...]:
    """Every row the same ladder."""
    return _rows(arms, arms, arms)


def _sized(i: int, size: int) -> Pick:
    start = START + 0x10000 * i
    return Pick(EXE, start, f"func_{start:08X}", _unit(i), size, 100 + i)


def _climb(night: Night) -> list[tuple]:
    return [(r["attempt"], r["model_requested"], r["run"]) for r in night.kinds("attempt")]


def test_cascade_climbs_the_row(tmp_path):
    """999.12a: one function's three attempts climb its row (HAIKU, SONNET): HAIKU, then SONNET,
    then SONNET (the row's last arm takes every later attempt), each under `<run>-<arm>` in its
    own attempt directory; the night's run records keep the base run id and count each arm."""
    pick = _wpick(0)
    night = ArmNight(tmp_path, picks=(pick,))
    lines: list[str] = []
    report = night.run(config={"routing": _every(HAIKU, SONNET)}, say=lines.append)
    assert (report.event, report.reason) == ("ENDED", driver.QUEUE_EXHAUSTED), report.detail
    assert _climb(night) == [(1, HAIKU, _arm_run(HAIKU)), (2, SONNET, _arm_run(SONNET)),
                             (3, SONNET, _arm_run(SONNET))]  # fmt: skip
    for n, arm in ((1, HAIKU), (2, SONNET), (3, SONNET)):
        assert (_driver_dir(night) / _arm_run(arm) / EXE / pick.name / f"attempt-{n}").is_dir()
    assert list(_driver_dir(night).rglob("*-uncounted-*")) == []
    run_records = night.kinds("run")
    assert [r["run"] for r in run_records] == [RUN, RUN]
    totals = run_records[-1]["totals"]
    assert {name: share["sessions"] for name, share in totals["by_model"].items()} == {
        HAIKU: 1, SONNET: 2}  # fmt: skip
    assert any(f"attempt 1/3 ({HAIKU})" in line for line in lines), lines
    assert any(f"attempt 2/3 ({SONNET})" in line for line in lines), lines


def test_cascade_routes_by_size(tmp_path):
    """999.12a: each pick's attempt runs on its own size bucket's row."""
    picks = (_sized(0, 20), _sized(1, 100), _sized(2, 300))
    night = ArmNight(tmp_path, picks=picks)
    report = night.run(config={"routing": _rows((HAIKU,), (SONNET,), (driver.OPUS_MODEL,)),
                               "attempts_per_function": 1})  # fmt: skip
    assert report.event == "ENDED", report.detail
    got = {r["function"]: (r["model_requested"], r["run"]) for r in night.kinds("attempt")}
    assert got == {picks[0].name: (HAIKU, _arm_run(HAIKU)),
                   picks[1].name: (SONNET, _arm_run(SONNET)),
                   picks[2].name: (driver.OPUS_MODEL, _arm_run(driver.OPUS_MODEL))}  # fmt: skip


@pytest.mark.parametrize(("config", "expected"), [
    ({}, {(driver.OPUS_MODEL, RUN)}),
    ({"fable_trial": True}, {(driver.FABLE_MODEL, RUN)}),
    ({"night_model": HAIKU}, {(HAIKU, RUN)}),
    ({"arms": TWO_ARMS, "hold": True}, {(HAIKU, _arm_run(HAIKU)), (SONNET, _arm_run(SONNET))}),
], ids=["d09", "fable-trial", "night-model", "arms-hold"])  # fmt: skip
def test_a_night_without_routing_picks_its_arm_as_before(tmp_path, config, expected):
    """RULINGS fds invariant: on every night without --cascade each attempt's arm is the
    lane's (or D-09's on the default night), under the run id it had before; the one-lane
    nights' console labels carry no arm suffix."""
    night = ArmNight(tmp_path, picks=tuple(_wpick(i) for i in range(2)))
    lines: list[str] = []
    report = night.run(config=config, say=lines.append)
    assert report.event == "ENDED", report.detail
    assert {(r["model_requested"], r["run"]) for r in night.kinds("attempt")} == expected
    if "arms" not in config:
        started = [line for line in lines if line.endswith(": started")]
        assert started and not any("(" in line for line in started), started


# ---- 261112-fds Task 2: caps, max_workers and no worker held on an arm that cannot launch ----


def _one_worker(arm: str) -> dict[str, driver.backends.Arm]:
    """The committed arm table with `arm`'s max_workers 1."""
    table = driver.backends.load_arms()
    table[arm] = replace(table[arm], max_workers=1)
    return table


def _peak_of(night: Night, run: str) -> int:
    """The most sessions of run `run` that were running at once."""
    mine = {i for i, launch in enumerate(night.launched) if _run_of(night, launch) == run}
    active = peak = 0
    for event, index in night.events:
        if index in mine:
            active += 1 if event == "start" else -1
            peak = max(peak, active)
    return peak


def _deferred_on_release(monkeypatch) -> list[tuple[str, str | None, bool]]:
    """Each released pass as (function, outcome, the pick is back on its lane's deferred)."""
    seen: list = []
    real = driver._Coordinator.release

    def release(self, worker):
        real(self, worker)
        with self.night.cond:
            seen.append((worker.pick.name, worker.outcome, worker.pick in worker.lane.deferred))

    monkeypatch.setattr(driver._Coordinator, "release", release)
    return seen


def test_cascade_never_holds_a_worker_on_a_full_or_paused_arm(tmp_path, monkeypatch):
    """999.12a (T-261112-fds-04): two workers; HAIKU (max_workers 1) takes the small picks,
    SONNET the medium ones, and SONNET's first session ends LIMIT. The paused pass ends at once
    (ARM_WAITING, back on the pool's deferred list), no worker sleeps a backoff, HAIKU keeps
    working while SONNET is paused and never runs two sessions at once, the first SONNET launch
    after the backoff has passed on the clock relaunches the waiting attempt 1, and every pick
    gets its counted attempt."""
    nights = _capture_nights(monkeypatch)
    released = _deferred_on_release(monkeypatch)
    small = [_wpick(i) for i in (0, 2, 3, 4)]
    medium = [_sized(1, 100), _sized(5, 100)]
    picks = (small[0], medium[0], *small[1:], medium[1])
    night = ArmNight(tmp_path, picks=picks, by_model={SONNET: [Sess("rate_limit", write=None)]})
    first_haiku: list[int] = []

    def after(unit, index):  # the first HAIKU session ends only once SONNET's pause began
        if _run_of(night, night.launched[index]) == _arm_run(HAIKU) and not first_haiku:
            first_haiku.append(index)
            assert _poll(lambda: nights[-1].arm_lanes[SONNET].pause.paused), "no SONNET pause"

    night.after = after
    sleeps: list[float] = []
    lines: list[str] = []
    report = night.run(config={"workers": 2, "attempts_per_function": 1,
                               "arm_table": _one_worker(HAIKU),
                               "routing": _rows((HAIKU,), (SONNET,), (HAIKU,))},
                       sleep=sleeps.append, say=lines.append)  # fmt: skip
    assert (report.event, report.reason) == ("ENDED", driver.QUEUE_EXHAUSTED), report.detail
    attempts = night.kinds("attempt")
    assert sorted(r["function"] for r in attempts) == sorted(p.name for p in picks)
    assert {(r["function"], r["attempt"], r["run"]) for r in attempts if r["model_requested"]
            == SONNET} == {(p.name, 1, _arm_run(SONNET)) for p in medium}  # fmt: skip
    (limit,) = night.kinds("limit")
    assert limit["run"] == _arm_run(SONNET)
    runs = [_run_of(night, launch) for launch in night.launched]
    sonnet = [i for i, run in enumerate(runs) if run == _arm_run(SONNET)]
    assert len(sonnet) == 3  # the LIMIT launch, its relaunch after the pause, the other pick
    limited, relaunch = sonnet[0], sonnet[1]
    assert any(runs[i] == _arm_run(HAIKU) for i in range(limited + 1, relaunch))
    assert _peak_of(night, _arm_run(HAIKU)) == 1
    assert sleeps == []
    assert len([line for line in lines if f"arm {SONNET} pauses" in line]) == 1, lines
    waiting = [entry for entry in released if entry[1] == driver.ARM_WAITING]
    assert waiting and all(back for _, _, back in waiting), released


def test_cascade_arm_runs_at_most_its_max_workers(tmp_path):
    """A cascade arm runs at most its backends.toml max_workers sessions at once, whatever the
    night's --workers. The first session holds on until a second one starts (or a short while
    passed), so a second launch beside it would show in `peak`."""
    night = ArmNight(tmp_path, picks=tuple(_wpick(i) for i in range(3)))

    def before(unit, index):
        if index == 0:
            deadline = time.monotonic() + 2.0
            while len(night.launched) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)

    night.before = before
    report = night.run(config={"workers": 3, "attempts_per_function": 1,
                               "arm_table": _one_worker(HAIKU), "routing": _every(HAIKU)})
    assert (report.event, report.reason) == ("ENDED", driver.QUEUE_EXHAUSTED), report.detail
    assert len(night.launched) == 3 and night.peak == 1


def test_cascade_arm_cap_holds_the_function_for_tonight(tmp_path):
    """--arm-cap HAIKU=1: the second pick's attempt finds HAIKU at its cap, so its pass ends
    ARM_CAPPED with one console line, and it gets no difficult-list entry."""
    picks = (_wpick(0), _wpick(1))
    night = ArmNight(tmp_path, picks=picks)
    lines: list[str] = []
    report = night.run(config={"attempts_per_function": 1, "routing": _every(HAIKU),
                               "arm_caps": ((HAIKU, 1),)}, say=lines.append)  # fmt: skip
    assert (report.event, report.reason) == ("ENDED", driver.QUEUE_EXHAUSTED), report.detail
    assert len(night.launched) == 1
    capped = [line for line in lines if "cap" in line and HAIKU in line and picks[1].name in line]
    assert len(capped) == 1 and " 1 " in capped[0], lines
    difficult = driver.load_difficult(night.repo / driver.DIFFICULT)
    assert (picks[1].exe, picks[1].start) not in difficult


def test_cascade_arm_cap_mid_pass_leaves_the_tier_queue(tmp_path):
    """Quick 261112-fdt (rewritten from fds' one-arm cap): --arm-cap HAIKU=2 and SONNET=1 on a
    tier night over row (HAIKU, SONNET). F runs HAIKU, SONNET, then HAIKU (its third attempt's
    rung SONNET is capped, so the rotated row wraps to HAIKU). Every later pass, of F or of S,
    finds the whole row capped: it launches nothing, ends ARM_CAPPED with one ARM_CAP_LINE
    naming both arms and their caps, and leaves the tier queue for tonight. S gets no
    difficult-list entry (F one, for its full capped pass), and the night ends."""
    from test_driver_pick import _tier_night

    a, b = START, START + 0x10
    night, deps = _tier_night(tmp_path, (a, b), unit=UNIT, night_cls=ArmNight)
    lines: list[str] = []
    report = night.run(config={"attempts_per_function": 3, "routing": _every(HAIKU, SONNET),
                               "arm_caps": ((HAIKU, 2), (SONNET, 1))},
                       queue=deps.queue, requeue=deps.requeue, say=lines.append)  # fmt: skip
    assert report.event == "ENDED", report.detail
    got = [(int(r["start"], 16), r["attempt"], r["model_requested"])
           for r in night.kinds("attempt")]  # fmt: skip
    first = got[0][0]
    second = b if first == a else a
    assert got == [(first, 1, HAIKU), (first, 2, SONNET), (first, 3, HAIKU)]
    capped = [line for line in lines if "has launched its cap" in line]
    assert capped and all(f"{HAIKU}: 2 sessions" in line and f"{SONNET}: 1 sessions" in line
                          for line in capped), capped  # fmt: skip
    assert any(f"func_{second:08X}" in line for line in capped), capped
    difficult = driver.load_difficult(night.repo / driver.DIFFICULT)
    assert [start for _, start in difficult] == [first]


def _ticking(night: Night, step: float = 10.0):
    """A clock seam that moves the night's fake clock on every reading."""

    def clock() -> float:
        night.now += step
        return night.now

    return clock


def test_a_cascade_pass_resumes_at_its_waiting_attempt(tmp_path):
    """SONNET's first session ends LIMIT at attempt 2: the pass ends ARM_WAITING, the tier queue
    keeps the function eligible, and once the backoff has passed on the clock its pass resumes
    at attempt 2 (the probe), then attempt 3. No second attempt 1, one limit record, and no
    worker slept the backoff: the pick waited in the queue instead. Quick 261112-fdt: HAIKU is
    capped at 1, so the paused SONNET has no free arm in its row to pass attempt 2 to."""
    from test_driver_pick import _tier_night

    night, deps = _tier_night(tmp_path, (START,), unit=UNIT, night_cls=ArmNight,
                              by_model={SONNET: [Sess("rate_limit", write=None)]})  # fmt: skip
    report = night.run(config={"attempts_per_function": 3, "max_sessions": 3,
                               "routing": _every(HAIKU, SONNET), "arm_caps": ((HAIKU, 1),)},
                       queue=deps.queue, requeue=deps.requeue, clock=_ticking(night))
    assert report.event == "ENDED", report.detail
    assert [(r["attempt"], r["model_requested"]) for r in night.kinds("attempt")] == [
        (1, HAIKU), (2, SONNET), (3, SONNET)]  # fmt: skip
    assert [r["run"] for r in night.kinds("limit")] == [_arm_run(SONNET)]
    assert night.sleeps == []


def test_a_cascade_probe_that_ends_without_a_verdict_is_handed_back(tmp_path, monkeypatch):
    """RULINGS amendment: the probe attempt after SONNET's pause fails before its session (its
    claim raises), so it ends with no on_limit/on_clear verdict: the night still ends, and the
    probe is handed back (probe_taken reset), not lost."""
    from test_driver_pick import _tier_night

    nights = _capture_nights(monkeypatch)
    real = driver._Night._claim

    def claim(self, pick, n):
        if getattr(self.local, "probe", False):
            raise RuntimeError("made-up claim failure of the probe")
        return real(self, pick, n)

    monkeypatch.setattr(driver._Night, "_claim", claim)
    night, deps = _tier_night(tmp_path, (START,), unit=UNIT, night_cls=ArmNight,
                              by_model={SONNET: [Sess("rate_limit", write=None)]})  # fmt: skip
    report = night.run(config={"attempts_per_function": 3, "routing": _every(SONNET)},
                       queue=deps.queue, requeue=deps.requeue, clock=_ticking(night))
    assert report.event == "STOPPED" and "made-up claim failure" in report.detail, report.detail
    pause = nights[-1].arm_lanes[SONNET].pause
    assert pause.paused and not pause.probe_taken


# ---- quick 261112-fdt (backlog 999.12b): a capped, paused or limited arm hands the attempt on ----

OPUS = driver.OPUS_MODEL


def _model_of(argv: list[str]) -> str:
    """The model a stand-in session was launched for (ArmNight passes --model but for Opus)."""
    return argv[argv.index("--model") + 1] if "--model" in argv else OPUS


def _leaves_work(night: Night, models: set[str] | None = None):
    """A session seam: after the stand-in run, a session of a model in `models` (None: every
    model) leaves its work in its attempt dir: notes.md naming its model, a valid giveup.json
    and checks/0001.c holding a definition of its function (the driver's PARTIAL path copies
    it to best/<unit>.c)."""
    from test_driver_records import GIVEUP

    def session(argv, **kw):
        result = night._session(argv, **kw)
        model = _model_of(list(argv))
        if models is not None and model not in models:
            return result
        attempt_dir = Path(kw["env"][attempt.DIR_ENV])
        func = attempt_dir.parent.name
        _write(attempt_dir / "notes.md", f"made-up note of {model}\n")
        _write(attempt_dir / "giveup.json", json.dumps(GIVEUP))
        _write(attempt_dir / "checks" / "0001.c", f"int {func}(void)\n{{\n    return 1;\n}}\n")
        return result

    return session


def _packs_seen(night: Night) -> tuple[list, object]:
    """A pack seam that records attempt.earlier_notes at each launch as (attempt dir, Notes)."""
    seen: list = []

    def pack(pick, attempt_dir, src=None):
        seen.append((Path(attempt_dir), attempt.earlier_notes(night.repo, pick.exe, pick.name)))
        return night._pack(pick, attempt_dir, src)

    return seen, pack


def _notes_at(night: Night, seen: list, run: str, pick: Pick, n: int):
    """The earlier notes the launch of `pick`'s attempt `n` under `run` was packed with."""
    want = _driver_dir(night) / run / EXE / pick.name / f"attempt-{n}"
    (notes,) = [notes for path, notes in seen if path == want]
    return notes


def _assert_carries(notes, run: str, pick: Pick, n: int) -> None:
    """`notes` hold attempt `n` of `pick` under `run`: its notes.md text, its give-up line and
    its best C (07.2-02, 999.5)."""
    assert notes is not None, "the launch was packed with no earlier notes"
    header = f"--- {run}/{EXE}/{pick.name}/attempt-{n}/notes.md"
    assert any(text.startswith(header) for text in notes.texts), notes.texts
    assert any(line.startswith(f"{run} attempt {n}: stack_layout")
               for line in notes.giveups), notes.giveups  # fmt: skip
    assert notes.best_c is not None and f"int {pick.name}(void)" in notes.best_c, notes.best_c


def _skip_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if ": skipped " in line]


def _handoff_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if "passes this attempt to" in line]


def _wait_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if "goes back to the queue at attempt" in line]


def test_cascade_skips_a_capped_arm(tmp_path):
    """The tracer (999.12b): row (HAIKU, SONNET, OPUS) with SONNET capped at 1. F runs HAIKU,
    SONNET, OPUS; S's attempt 2 finds SONNET capped and goes to OPUS, so S runs HAIKU, OPUS,
    OPUS (the skip is for that attempt only: attempt 3's rung is still OPUS). Every record names
    the arm it ran on, one ARM_SKIP_LINE names SONNET as capped, and S's attempt 2 on OPUS is
    packed with Haiku's attempt 1 notes, give-up and best C (07.2-02, unchanged)."""
    from reverseapoc import stats

    f, s = _wpick(0), _wpick(1)
    night = ArmNight(tmp_path, picks=(f, s),
                     sessions=[Sess(write=None, checks=(check_line(1, 40.0),))] * 6)  # fmt: skip
    seen, pack = _packs_seen(night)
    lines: list[str] = []
    report = night.run(config={"attempts_per_function": 3, "routing": _every(HAIKU, SONNET, OPUS),
                               "arm_caps": ((SONNET, 1),)},
                       session=_leaves_work(night), pack=pack, say=lines.append)  # fmt: skip
    assert (report.event, report.reason) == ("ENDED", driver.QUEUE_EXHAUSTED), report.detail
    attempts = night.kinds("attempt")
    got = [(r["function"], r["attempt"], r["model_requested"], r["run"]) for r in attempts]
    assert got == [(f.name, 1, HAIKU, _arm_run(HAIKU)), (f.name, 2, SONNET, _arm_run(SONNET)),
                   (f.name, 3, OPUS, _arm_run(OPUS)), (s.name, 1, HAIKU, _arm_run(HAIKU)),
                   (s.name, 2, OPUS, _arm_run(OPUS)), (s.name, 3, OPUS, _arm_run(OPUS))]
    for record in attempts:
        assert (record["harness"], record["backend"]) == ("claude", "anthropic")
        assert stats.arm_key(record) == f"anthropic/claude/{record['model_requested']}"
        driver.validate_record(record)
    totals = night.kinds("run")[-1]["totals"]
    assert {name: share["sessions"] for name, share in totals["by_model"].items()} == {
        HAIKU: 2, SONNET: 1, OPUS: 3}  # fmt: skip
    (skip,) = _skip_lines(lines)
    assert s.name in skip and f"attempt 2/3 ({OPUS})" in skip and f"{SONNET} (capped)" in skip
    _assert_carries(_notes_at(night, seen, _arm_run(OPUS), s, 2), _arm_run(HAIKU), s, 1)


def test_cascade_wraps_to_the_rows_start(tmp_path):
    """Row (HAIKU, SONNET), SONNET capped at 1: attempt 3's rung is SONNET (capped), so the
    rotated row (SONNET, HAIKU) sends it back to HAIKU, and the skip line names SONNET."""
    night = ArmNight(tmp_path, picks=(_wpick(0),))
    lines: list[str] = []
    report = night.run(config={"attempts_per_function": 3, "routing": _every(HAIKU, SONNET),
                               "arm_caps": ((SONNET, 1),)}, say=lines.append)  # fmt: skip
    assert (report.event, report.reason) == ("ENDED", driver.QUEUE_EXHAUSTED), report.detail
    assert _climb(night) == [(1, HAIKU, _arm_run(HAIKU)), (2, SONNET, _arm_run(SONNET)),
                             (3, HAIKU, _arm_run(HAIKU))]  # fmt: skip
    (skip,) = _skip_lines(lines)
    assert "attempt 3/3" in skip and f"{SONNET} (capped)" in skip


def _state_night(tmp_path) -> tuple[driver._Night, Pick]:
    """A cascade _Night over row (HAIKU, SONNET), both capped at 1, and one pick."""
    pick = _wpick(0)
    night = ArmNight(tmp_path, picks=(pick,))
    config = night.config(routing=_every(HAIKU, SONNET), arm_caps=((HAIKU, 1), (SONNET, 1)))
    return driver._Night(config, night.deps()), pick


def _cap(lane) -> None:
    lane.sessions = lane.max_sessions


def _busy(lane) -> None:
    lane.reserved = lane.live_cap


def _pause(lane, *, probe_taken: bool = False) -> None:
    """A holding pause; with `probe_taken` its backoff has run out on the clock but another
    worker holds its probe (coordinator amendment: still paused, not busy)."""
    lane.pause.paused = True
    lane.pause.probe_taken = probe_taken
    lane.pause.paused_until = lane.pause.clock() + (-1.0 if probe_taken else 100.0)


def _probe_held(lane) -> None:
    _pause(lane, probe_taken=True)


@pytest.mark.parametrize(("haiku", "sonnet", "state"), [
    (None, None, driver.RESERVED),
    (_cap, None, driver.RESERVED),
    (_cap, _busy, driver.ARM_WAITING),
    (_busy, None, driver.ARM_WAITING),
    (_pause, None, driver.RESERVED),
    (_probe_held, None, driver.RESERVED),
    (_pause, _pause, driver.ARM_WAITING),
    (_cap, _pause, driver.ARM_WAITING),
    (_cap, _cap, driver.ARM_CAPPED),
], ids=["free", "capped-rung", "capped-then-busy", "busy-rung", "paused-rung",
        "probe-held-rung", "both-paused", "capped-then-paused", "both-capped"])  # fmt: skip
def test_arm_state_reads_the_whole_row(tmp_path, haiku, sonnet, state):
    """999.12b: the dispatch filter folds the rotated row by the routing's rule: RESERVED at
    the first arm that can launch; a busy arm (pause ready, its slots taken) makes the pick wait
    (coordinator ruling 2026-11-12); a capped or paused arm (a probe another worker holds counts
    as paused, coordinator amendment) passes to the next; ARM_CAPPED only when every arm is
    capped."""
    night, pick = _state_night(tmp_path)
    with night.cond:
        for setup, arm in ((haiku, HAIKU), (sonnet, SONNET)):
            if setup is not None:
                setup(night.arm_lanes[arm])
    assert night._arm_state(pick) == state


def test_route_order_starts_at_the_resumed_attempts_rung(tmp_path):
    """_route_order is the rotated row; with a resume entry of 2 the order starts at SONNET, so
    a busy HAIKU behind a free SONNET does not hold the pick."""
    night, pick = _state_night(tmp_path)
    assert night._route_order(pick, 1) == (night.arm_lanes[HAIKU], night.arm_lanes[SONNET])
    assert night._route_order(pick, 2) == (night.arm_lanes[SONNET], night.arm_lanes[HAIKU])
    with night.cond:
        _busy(night.arm_lanes[HAIKU])
        night.lane.resume[(pick.exe, pick.start)] = 2
    assert night._arm_state(pick) == driver.RESERVED


@pytest.mark.parametrize(("lane_setup", "arm", "line"), [
    (_cap, HAIKU, f"{HAIKU} (capped)"),
    (_pause, HAIKU, f"{HAIKU} (paused)"),
    (_probe_held, HAIKU, f"{HAIKU} (paused)"),
], ids=["capped", "paused", "probe-held"])  # fmt: skip
def test_cascade_route_skips_a_capped_or_paused_rung(tmp_path, lane_setup, arm, line):
    """_cascade_route binds the first lane that reserves, skipping a capped or paused rung (a
    probe another worker holds counts as paused), and prints one skip line naming it."""
    night, pick = _state_night(tmp_path)
    lines: list[str] = []
    night.deps = replace(night.deps, say=lines.append)
    with night.cond:
        lane_setup(night.arm_lanes[arm])
    assert night._cascade_route(pick, 1) == driver.RESERVED
    assert night.arm_lane is night.arm_lanes[SONNET]
    assert not night.arm_lanes[HAIKU].pause.probe_taken or lane_setup is _probe_held
    (skip,) = _skip_lines(lines)
    assert line in skip


def test_cascade_route_waits_on_a_busy_rung(tmp_path):
    """A busy rung is not skipped (coordinator ruling 2026-11-12): ARM_WAITING, no slot taken
    on SONNET, no skip line."""
    night, pick = _state_night(tmp_path)
    lines: list[str] = []
    night.deps = replace(night.deps, say=lines.append)
    with night.cond:
        _busy(night.arm_lanes[HAIKU])
    assert night._cascade_route(pick, 1) == driver.ARM_WAITING
    assert night.arm_lanes[SONNET].reserved == 0 and lines == []


@pytest.mark.parametrize("first", ["partial", "gave-up", "matched"])
def test_cascade_escalates_on_partial_and_gave_up(tmp_path, first):
    """fds' ladder, pinned under 999.12b: PARTIAL or GAVE_UP send attempt 2 to the next rung
    (SONNET); MATCHED ends the pass after one record."""
    sessions = {"partial": [Sess(write=None, checks=(check_line(1, 40.0),))],
                "gave-up": [Sess(write=None)], "matched": [Sess()]}[first]  # fmt: skip
    night = ArmNight(tmp_path, picks=(_wpick(0),), sessions=sessions,
                     gate_exits=[0] if first == "matched" else [])  # fmt: skip
    report = night.run(config={"attempts_per_function": 2, "routing": _every(HAIKU, SONNET)})
    assert report.event == "ENDED", report.detail
    outcome = night.kinds("attempt")[0]["outcome"]
    if first == "matched":
        assert _climb(night) == [(1, HAIKU, _arm_run(HAIKU))] and outcome == driver.MATCHED
        return
    assert _climb(night) == [(1, HAIKU, _arm_run(HAIKU)), (2, SONNET, _arm_run(SONNET))]
    assert outcome == {"partial": driver.PARTIAL, "gave-up": driver.GAVE_UP}[first]
