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
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from reverseapoc import driver
from reverseapoc.locks import ProcessLock
from test_drive import RUN as DRIVE_RUN
from test_drive import Rig, _canary_rig
from test_driver import (
    EXE,
    FUNC,
    LOG,
    MATCH_SUBJECT,
    OTHER_RECORD,
    RUN,
    SCAFFOLD,
    UNIT,
    UNIT_REL,
    Night,
    Sess,
    _capture_nights,
    _failed_commit_night,
    _one,
    _run_contained,
    _verb,
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
    assert "MATCHED" not in (night.repo / LOG).read_text(encoding="utf-8")


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
    assert "MATCHED" not in (night.repo / LOG).read_text(encoding="utf-8")


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
