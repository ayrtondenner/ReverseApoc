"""The driver's v2 attempts.jsonl records (plan 07-23; DEC-06, DEC-07, D-08, D-09; research
section J, P10): per-attempt hook blocks, gate verdicts, pass, requested model and budget, sweep
evidence, usage-limit records, recovered claims, nightly totals, and the pass count read from
the committed log.

Every session is tests/fakeclaude.py through the Night harness of test_driver.py (WNight for
worker threads); every name, address and flag spec below is made up.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from reverseapoc import attempt, driver
from reverseapoc.picker import Pick
from reverseapoc.session import MAX_BUDGET_USD, MODEL
from test_attempts_schema import _attempt as _v1_template
from test_attempts_schema import _attempt_v2 as _v2_template
from test_driver import (
    EXE,
    FUNC,
    LOG,
    PICK,
    START,
    UNIT,
    Night,
    Sess,
    _one,
    _write,
    check_line,
)

OTHER_START = START + 0x10  # a made-up function of the same unit, matched before the night
OTHER_ROW = f"0x{OTHER_START:08X},func_{OTHER_START:08X},{UNIT},matched,100.00,1\n"


def _commit(night: Night, files: dict[str, str], message: str = "made-up setup") -> None:
    """Write and commit `files` in the night's tmp repo, then make that commit the base."""
    for rel, text in files.items():
        _write(night.repo / rel, text)
    night.git("add", "--", *files)
    night.git("commit", "-q", "-m", message)
    night.base = night.git("rev-parse", "HEAD").strip()


def _with_result(night: Night, **fields):
    """A session fake that runs the harness's session, then sets `fields` on its result event."""

    def session(argv, **kw):
        result = night._session(argv, **kw)
        events = tuple({**e, **fields} if e.get("type") == "result" else e for e in result.events)
        return dataclasses.replace(result, events=events)

    return session


# ---- Task 1: the v2 attempt record ----


def test_attempt_record_is_v2(tmp_path):
    """DEC-07: a matched night's attempt record is schema 2 with the session kind, the pass,
    the requested model and budget, the worker, the hook blocks and the gate's verdict, and it
    passes validate_record."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    report = night.run()
    assert report.matched == 1, report.detail
    record = _one(night.kinds("attempt"))
    driver.validate_record(record)
    assert record["schema"] == driver.SCHEMA_V2 == 2
    assert (record["session"], record["pass"], record["worker"]) == ("matching", 1, 0)
    assert (record["model_requested"], record["budget_usd"]) == (MODEL, MAX_BUDGET_USD)
    assert (MODEL, MAX_BUDGET_USD) == ("claude-opus-5-5", 5)
    assert record["gate"] == {"exit": 0, "claimed_ok": True, "regressions": 0, "problems": []}
    assert record["hook_blocks"] == 0
    assert (record["sweep_source"], record["sweep_cells_100"]) == (None, [])
    assert (record["outcome"], record["function"], record["start"]) == (
        "MATCHED", FUNC, f"0x{START:08X}")  # fmt: skip


def test_every_attempt_record_of_a_night_is_v2(tmp_path):
    """From this plan on the driver writes only v2 attempt records (the run records follow in
    Task 3, test_every_record_of_a_night_is_v2)."""
    night = Night(tmp_path, sessions=[Sess(checks=(check_line(1, 30.0),))] * 3)
    night.run()
    attempts = [r for r in night.records() if r["kind"] != "run"]
    assert len(attempts) == 3
    for record in attempts:
        driver.validate_record(record)
        assert record["schema"] == 2, record["kind"]


def test_function_is_the_rows_c_name(tmp_path):
    """DEC-07 with D-19: `function` is the pick's C name (the EXE's symbol table names it), while
    `start` keeps the address and the attempt directory keeps the placeholder."""
    pick = Pick(EXE, START, "GetMadeUpVolume", UNIT, 20, 100)
    night = Night(tmp_path, sessions=[Sess(checks=(check_line(1, 40.0),))], picks=(pick,))
    night.run(config={"attempts_per_function": 1})
    record = _one(night.kinds("attempt"))
    assert (record["function"], record["start"]) == ("GetMadeUpVolume", f"0x{START:08X}")
    assert night.attempt_dir(1).is_dir()  # build/driver/<run>/ufo2p/func_00010010/attempt-1


def test_hook_blocks_counted(tmp_path):
    """hook_blocks is the length of the result event's permission_denials (research section 3)."""
    denials = [{"tool_name": "Bash", "tool_use_id": "toolu_made_up_1", "tool_input": {}},
               {"tool_name": "Write", "tool_use_id": "toolu_made_up_2", "tool_input": {}}]
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[1])
    night.run(config={"attempts_per_function": 1},
              session=_with_result(night, permission_denials=denials))  # fmt: skip
    assert _one(night.kinds("attempt"))["hook_blocks"] == 2
    events = [{"type": "result", "permission_denials": denials}]
    assert driver._hook_blocks(events) == 2
    assert driver._hook_blocks([{"type": "result"}]) == 0
    assert driver._hook_blocks([]) == 0


def test_gate_null_on_lint_failure(tmp_path):
    """No gate ran (the lint failed): gate is null and abort_reason lint."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0], lint_exits=[1])
    night.run(config={"attempts_per_function": 1})
    record = _one(night.kinds("attempt"))
    assert (record["gate"], record["abort_reason"], record["outcome"]) == (None, "lint", "GAVE_UP")
    assert night.gate_calls == []


def test_gate_counts_regressions_and_keeps_problems(tmp_path):
    """A failing gate: claimed_ok false, every previously matched function of the unit the gate
    found failing is one regression, and the gate's problems are kept (as text)."""
    night = Night(tmp_path, sessions=[Sess()])
    status = f"config/{EXE}/status.csv"
    _commit(night, {status: (night.repo / status).read_text(encoding="utf-8") + OTHER_ROW})

    def gate(pick, n):
        night.gate_calls.append((pick, n))
        failing = {"objdiff_percent": 90.0, "reloc": {"ok": True}, "bytes": {"ok": False}}
        doc = {"ok": False, "written": [], "problems": ["made-up problem of the gate"],
               "checks": [{"exe": "UFO2P", "functions": [
                   {"va": f"0x{START:08X}", **failing},
                   {"va": f"0x{OTHER_START:08X}", **failing}]}]}  # fmt: skip
        return driver.GateRun(1, doc)

    night.run(config={"attempts_per_function": 1}, gate=gate)
    record = _one(night.kinds("attempt"))
    assert record["gate"] == {"exit": 1, "claimed_ok": False, "regressions": 1,
                              "problems": ["made-up problem of the gate"]}  # fmt: skip


SPEC_A = "wcc386@10.6 -5r -s -made-up-a"
SPEC_B = "wcc386@10.6 -4r -s -made-up-b"


def _cell(n: int, spec: str, percent: float | None, *, reloc: bool = True, differing: int = 0,
          status: str = "measured") -> dict:  # fmt: skip
    compiler, *flags = spec.split(" ")
    return {"cell": n, "compiler": compiler, "flags": flags, "status": status,
            "objdiff_percent": percent, "reloc_ok": reloc, "differing": differing}  # fmt: skip


def test_sweep_evidence(tmp_path):
    """P10: the first hitting sweep line's snapshot is sweep_source, and every 100% cell of its
    saved JSON (stage 1, then stage 2) is in sweep_cells_100; a sweep line without a hit and a
    cell below 100% or with a failing relocation check are not."""
    checks = (check_line(1, 50.0), check_line(2, 70.0, sweep=True, exit_code=0),
              check_line(3, 55.0),
              check_line(4, 80.0, sweep=True, exit_code=0, sweep_hit=SPEC_A))  # fmt: skip
    night = Night(tmp_path, sessions=[Sess(checks=checks)])
    doc = {"cells": [_cell(1, "wcc386@10.6 -4r -s", 80.0), _cell(2, "wcc386@10.6 -3r", None,
                                                                 status="error")],
           "stage2": {"from": [1], "best": [3],
                      "cells": [_cell(3, SPEC_A, 100.0), _cell(4, SPEC_B, 100.0),
                                _cell(5, "wcc386@10.6 -6r", 100.0, reloc=False),
                                _cell(6, "wcc386@10.6 -os", 100.0, differing=2)]}}  # fmt: skip

    def session(argv, **kw):
        result = night._session(argv, **kw)
        saved = Path(kw["env"][attempt.DIR_ENV]) / "checks" / "0004.json"
        saved.write_text(json.dumps(doc), encoding="utf-8")
        return result

    night.run(config={"attempts_per_function": 1}, session=session)
    record = _one(night.kinds("attempt"))
    assert record["sweep_source"] == "checks/0004.c"
    assert record["sweep_cells_100"] == [SPEC_A, SPEC_B]
    assert record["check"]["sweep_hit"] == SPEC_A
    driver.validate_record(record)


def test_sweep_evidence_without_a_saved_json_keeps_the_source(tmp_path):
    """The hitting line's JSON is gone (or unreadable): the source is still named, no cells."""
    checks = (check_line(1, 80.0, sweep=True, exit_code=0, sweep_hit=SPEC_A),)
    night = Night(tmp_path, sessions=[Sess(checks=checks)])
    night.run(config={"attempts_per_function": 1})
    record = _one(night.kinds("attempt"))
    assert (record["sweep_source"], record["sweep_cells_100"]) == ("checks/0001.c", [])


def test_abort_record_is_v2_with_the_c_name(tmp_path):
    """Orchestrator ruling F12: a v2 abort takes the same C-name rule as an attempt."""
    pick = Pick(EXE, START, "GetMadeUpVolume", UNIT, 20, 100)
    sessions = [Sess("overloaded", write=None)] * 4
    night = Night(tmp_path, sessions=sessions, picks=(pick,))
    night.run(config={"attempts_per_function": 1})
    abort = _one(night.kinds("abort"))
    driver.validate_record(abort)
    assert (abort["schema"], abort["function"], abort["session"], abort["pass"],
            abort["worker"], abort["retries"]) == (2, "GetMadeUpVolume", "matching", 1, 0, 3)


# ---- Task 2: pass counting from the committed log (D-08, D-09) ----

PILOT_RUN = "20261026-005209"  # the Phase 6 pilot's run id in the committed log
KEY = (EXE, START)


def _v1(run: str, n: int, *, start: int = START, outcome: str = "PARTIAL") -> dict:
    record = _v1_template()
    record.update(run=run, attempt=n, outcome=outcome, start=f"0x{start:08X}",
                  function=f"func_{start:08X}")  # fmt: skip
    return record


def _v2(run: str, pass_n: int, n: int, *, start: int = START, outcome: str = "PARTIAL") -> dict:
    record = _v2_template()
    record.update(run=run, attempt=n, outcome=outcome, start=f"0x{start:08X}",
                  function=f"func_{start:08X}", **{"pass": pass_n})  # fmt: skip
    return record


def _lines(records: list[dict]) -> str:
    for record in records:
        driver.validate_record(record)
    return "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in records)


def _log(tmp_path: Path, records: list[dict]) -> Path:
    path = tmp_path / "attempts.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_lines(records), encoding="ascii", newline="\n")
    return path


def test_passes_v1(tmp_path):
    """A v1 run's attempts on a function are one pass: three in one run without MATCHED are 1,
    the same in two runs are 2; another function or another EXE's start counts nothing."""
    one = _log(tmp_path / "a", [_v1("night0", n) for n in (1, 2, 3)])
    assert driver.passes_of(one, KEY) == 1
    two = _log(tmp_path / "b", [*(_v1("night0", n) for n in (1, 2, 3)),
                                *(_v1("night9", n) for n in (1, 2, 3))])  # fmt: skip
    assert driver.passes_of(two, KEY) == 2
    assert driver.passes_of(two, (EXE, START + 0x10)) == 0
    assert driver.passes_of(two, ("tacp", START)) == 0


def test_passes_v2(tmp_path):
    """A v2 record names its pass: pass 1 (three sessions) and pass 2 (three) are 2 passes."""
    log = _log(tmp_path, [*(_v2("night0", 1, n) for n in (1, 2, 3)),
                          *(_v2("night1", 2, n) for n in (1, 2, 3))])  # fmt: skip
    assert driver.passes_of(log, KEY) == 2
    assert driver.pass_index(log) == {KEY: 2}


def test_passes_mixed_v1_then_v2(tmp_path):
    """The pilot's v1 run is pass 1, so the first v2 night writes pass 2: together 2 passes."""
    log = _log(tmp_path, [*(_v1("night0", n) for n in (1, 2, 3)), _v2("night1", 2, 1)])
    assert driver.passes_of(log, KEY) == 2


def test_passes_ignore_abort_records_and_a_missing_log(tmp_path):
    """Only attempt records are sessions of a pass; a missing log has no pass."""
    abort = {"kind": "abort", "schema": 2, "run": "night0", "exe": EXE, "function": FUNC,
             "unit": UNIT, "start": f"0x{START:08X}", "attempt": 1, "abort_reason": "transient",
             "retries": 3, "session": "matching", "pass": 1, "worker": 0,
             "date": "2026-10-25"}  # fmt: skip
    log = _log(tmp_path, [abort])
    assert driver.pass_index(log) == {}
    assert driver.pass_index(tmp_path / "missing.jsonl") == {}


def test_a_corrupt_log_line_is_named_when_passes_are_counted(tmp_path):
    log = _log(tmp_path, [_v1("night0", 1)])
    with log.open("a", encoding="ascii", newline="\n") as fh:
        fh.write("not json\n")
    with pytest.raises(driver.DriverError, match="line 2"):
        driver.pass_index(log)


def test_committed_log_pilot_passes(tmp_path):
    """D-08/D-09 on the committed log: the pilot run gave each of its 12 never-matched functions
    one capped Opus pass (so their next pass is 2), and its matched functions are matched rows
    of the committed status.csv, which the picker never re-queues."""
    committed = (REPO_ROOT / LOG).read_text(encoding="utf-8").splitlines()
    pilot = [r for r in map(json.loads, committed) if r["run"] == PILOT_RUN]
    log = _log(tmp_path, pilot)
    attempts = [r for r in pilot if r["kind"] == "attempt"]
    keys = {(r["exe"], int(r["start"], 16)) for r in attempts}
    matched = {(r["exe"], int(r["start"], 16)) for r in attempts if r["outcome"] == "MATCHED"}
    never = keys - matched
    assert (len(never), len(matched)) == (12, 3)
    index = driver.pass_index(log)
    assert {key: index[key] for key in never} == dict.fromkeys(never, 1)
    assert matched <= driver.matched_keys(REPO_ROOT / "config")


def test_next_pass_number(tmp_path, monkeypatch):
    """The driver's next attempt record (and its claim) for a function with 2 finished passes
    carries pass 3; a function without one is on pass 1. The log is read once per night."""
    night = Night(tmp_path, sessions=[Sess(), Sess()], gate_exits=[1, 1])
    log = [*(_v2("night0", 1, n) for n in (1, 2, 3)), *(_v2("night0b", 2, n) for n in (1, 2, 3))]
    _commit(night, {LOG: _lines(log)})
    claims: list[dict] = []
    reads: list[Path] = []
    real = driver.pass_index

    def counted(path):
        reads.append(Path(path))
        return real(path)

    def session(argv, **kw):
        unit = kw["env"][attempt.CLAIM_ENV].split("/")[1]
        claim = night.repo / "build" / "driver" / "claims" / f"{EXE}__{unit}.json"
        claims.append(json.loads(claim.read_text(encoding="utf-8")))
        return night._session(argv, **kw)

    monkeypatch.setattr(driver, "pass_index", counted)
    second = Pick(EXE, START + 0x10, f"func_{START + 0x10:08X}", UNIT, 20, 101)
    night.picks = (PICK, second)
    night.run(config={"attempts_per_function": 1}, session=session)
    passes = {r["start"]: r["pass"] for r in night.kinds("attempt") if r["run"] == "night1"}
    assert passes == {f"0x{START:08X}": 3, f"0x{START + 0x10:08X}": 1}
    assert [c["pass"] for c in claims] == [3, 1]
    assert len(reads) == 1


# ---- Task 3: run records, limit records, totals, the log commit after the drain (DEC-06) ----

DENIAL = {"tool_name": "Bash", "tool_use_id": "toolu_made_up", "tool_input": {}}
OUTCOMES = ("MATCHED", "PARTIAL", "GAVE_UP", "LANDED", "REFUSED")


def _run_records(night: Night, event: str) -> list[dict]:
    return [r for r in night.kinds("run") if r["event"] == event]


def test_every_record_of_a_night_is_v2(tmp_path):
    """From this plan on the driver writes only v2 records: attempts, limits and run records."""
    sessions = [Sess("rate_limit", write=None), Sess(checks=(check_line(1, 30.0),)), Sess()]
    night = Night(tmp_path, sessions=sessions, gate_exits=[1, 0])
    night.run()
    kinds = [r["kind"] for r in night.records()]
    assert kinds == ["run", "limit", "attempt", "attempt", "run"]
    for record in night.records():
        driver.validate_record(record)
        assert record["schema"] == 2, record["kind"]


def test_started_record_v2(tmp_path):
    """STARTED carries the night's workers and every stale claim moved at start as {exe, unit,
    run}; its totals are null (the detail still names the claims)."""
    from test_driver_workers import _claim_record, _plant_claim

    night = Night(tmp_path, sessions=[Sess()], gate_exits=[1])
    _plant_claim(night, _claim_record("old"))
    night.run(config={"workers": 3, "attempts_per_function": 1})
    started = _one(_run_records(night, "STARTED"))
    assert (started["workers"], started["totals"]) == (3, None)
    assert started["recovered"] == [{"exe": EXE, "unit": "u_x", "run": "old"}]
    assert "ufo2p/u_x" in started["detail"]
    ended = _one(_run_records(night, "ENDED"))
    assert (ended["workers"], ended["recovered"]) == (3, [])
    assert ended["totals"] is not None


def test_limit_record_per_wait(tmp_path):
    """Every usage-limit wait writes one limit record: the worker, the backoff it waits and the
    pause's streak (1 for the first wait: the 07-07 schema counts from 1)."""
    sessions = [Sess("rate_limit", write=None), Sess("rate_limit", write=None), Sess()]
    night = Night(tmp_path, sessions=sessions, gate_exits=[0])
    night.run()
    assert night.sleeps == [60, 120]
    limits = night.kinds("limit")
    assert [(r["worker"], r["seconds"], r["streak"]) for r in limits] == [(0, 60, 1), (0, 120, 2)]
    for record in limits:
        driver.validate_record(record)


def _sums(records: list[dict]) -> dict:
    """DEC-06's totals recomputed by the test from the night's own attempt, abort and limit
    records (wall_seconds aside)."""
    attempts = [r for r in records if r["kind"] == "attempt"]
    limits = [r for r in records if r["kind"] == "limit"]

    def share(group: list[dict]) -> dict:
        return {"sessions": len(group), "matched": sum(r["outcome"] == "MATCHED" for r in group),
                "cost_usd": pytest.approx(sum(r["cost_usd"] for r in group))}  # fmt: skip

    models = {r["model_requested"] for r in attempts}
    kinds = {r["session"] for r in attempts}
    return {
        "sessions": {o: sum(r["outcome"] == o for r in attempts) for o in OUTCOMES},
        "turns": sum(r["turns"] for r in attempts),
        "tokens": {k: sum(r["tokens"][k] for r in attempts)
                   for k in ("input", "output", "cache_read", "cache_creation")},
        "cost_usd": pytest.approx(sum(r["cost_usd"] for r in attempts)),
        "session_seconds": pytest.approx(sum(r["seconds"] for r in attempts)),
        "hook_blocks": sum(r["hook_blocks"] for r in attempts),
        "regressions_stopped": sum((r["gate"] or {}).get("regressions", 0) for r in attempts),
        "limit_waits": {"count": len(limits),
                        "seconds": pytest.approx(sum(r["seconds"] for r in limits))},
        "aborts": sum(r["kind"] == "abort" for r in records),
        "by_model": {m: share([r for r in attempts if r["model_requested"] == m]) for m in models},
        "by_session": {k: share([r for r in attempts if r["session"] == k]) for k in kinds},
    }  # fmt: skip


def test_totals_equal_sums(tmp_path):
    """DEC-06 (T-07-68): a night of 4 attempts on 2 workers and one usage-limit wait ends with
    totals equal to the sums over its own records, per model and per session kind too; the
    wall clock is the night's own."""
    from test_driver_workers import WNight, _unit, _wpick

    by_unit = {_unit(0): [Sess("rate_limit", write=None), Sess(checks=(check_line(1, 40.0),)),
                          Sess()],
               _unit(1): [Sess(), Sess()]}  # fmt: skip
    night = WNight(tmp_path, picks=(_wpick(0), _wpick(1)), by_unit=by_unit)

    def gate(pick, n):  # unit 1's second attempt matches; every other gate fails
        night.gate_exits = [0 if (pick.unit, n) == (_unit(1), 2) else 1]
        return night._gate(pick, n)

    def session(argv, **kw):
        result = WNight._session(night, argv, **kw)
        events = tuple({**e, "permission_denials": [DENIAL]} if e.get("type") == "result" else e
                       for e in result.events)  # fmt: skip
        return dataclasses.replace(result, events=events)

    begin = night.now
    report = night.run(config={"workers": 2, "attempts_per_function": 2}, gate=gate,
                       session=session)  # fmt: skip
    assert (report.event, report.matched) == ("ENDED", 1), report.detail
    records = [r for r in night.records() if r["run"] == "night1"]
    assert [r["kind"] for r in records].count("attempt") == 4
    assert [r["kind"] for r in records].count("limit") == 1
    totals = _one(_run_records(night, "ENDED"))["totals"]
    expected = _sums(records)
    assert {key: totals[key] for key in expected} == expected
    assert totals["hook_blocks"] == 4 and totals["sessions"]["MATCHED"] == 1
    assert totals["wall_seconds"] == pytest.approx(night.now - begin)


def test_a_stopped_night_has_totals(tmp_path):
    """A STOPPED record carries totals too (a guardrail stop after one recorded attempt)."""
    sessions = [Sess(checks=(check_line(1, 20.0),)), Sess(write="tools/x.py")]
    night = Night(tmp_path, sessions=sessions)
    report = night.run()
    assert (report.event, report.reason) == ("STOPPED", "guardrail")
    stopped = _one(_run_records(night, "STOPPED"))
    driver.validate_record(stopped)
    assert stopped["totals"]["sessions"]["PARTIAL"] == 1
    assert stopped["totals"]["turns"] == _one(night.kinds("attempt"))["turns"]


def test_an_interrupted_night_has_totals(tmp_path):
    """The STOPPED `interrupted` record (written before the interrupt is re-raised) is v2."""
    night = Night(tmp_path, sessions=[Sess(raises=KeyboardInterrupt())])
    with pytest.raises(KeyboardInterrupt):
        night.run()
    stopped = _one(_run_records(night, "STOPPED"))
    driver.validate_record(stopped)
    assert (stopped["reason"], stopped["totals"]["sessions"]["GAVE_UP"]) == ("interrupted", 0)


def test_a_failed_match_commit_drops_its_matched_record_from_the_totals(tmp_path):
    """F19: an undone match commit truncates its MATCHED line from the log, so the totals count
    the GAVE_UP `tool` record that replaces it, never the dropped one."""
    from test_driver import REFUSE_FEAT_HOOK

    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    hook = night.repo / ".git" / "hooks" / "commit-msg"
    _write(hook, REFUSE_FEAT_HOOK)
    hook.chmod(0o755)
    report = night.run()
    assert report.event == "STOPPED", report.detail
    attempt_record = _one(night.kinds("attempt"))
    assert (attempt_record["outcome"], attempt_record["abort_reason"]) == ("GAVE_UP", "tool")
    totals = _one(_run_records(night, "STOPPED"))["totals"]
    assert (totals["sessions"]["MATCHED"], totals["sessions"]["GAVE_UP"]) == (0, 1)


def test_log_commit_after_drain(tmp_path):
    """The night's chore commit of the log runs after every worker has drained: no worker thread
    is alive at it, and the committed log holds every attempt record and the ENDED record."""
    import threading

    from test_driver import CHORE
    from test_driver_workers import WNight, _message_of, _unit, _wpick

    night = WNight(tmp_path, picks=(_wpick(0), _wpick(1), _wpick(2)),
                   sessions=[Sess(checks=(check_line(1, 30.0),))] * 3)  # fmt: skip
    alive: list[list[str]] = []

    def on_git(args):
        if "commit" in args and _message_of(args).startswith(CHORE):
            alive.append([t.name for t in threading.enumerate()
                          if t.name.startswith("drive-worker-") and t.is_alive()])  # fmt: skip

    night.on_git = on_git
    report = night.run(config={"workers": 3, "attempts_per_function": 1})
    assert report.event == "ENDED", report.detail
    assert alive == [[]]
    committed = [json.loads(line) for line in night.file_at(CHORE, LOG).splitlines()]
    assert committed == night.records()
    assert sorted(r["unit"] for r in committed if r["kind"] == "attempt") == [
        _unit(i) for i in range(3)]  # fmt: skip
    assert committed[-1]["event"] == "ENDED" and committed[-1]["totals"]["sessions"]["PARTIAL"] == 3

