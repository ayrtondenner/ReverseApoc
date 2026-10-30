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

from reverseapoc import attempt, driver
from reverseapoc.picker import Pick
from reverseapoc.session import MAX_BUDGET_USD, MODEL
from test_driver import (
    EXE,
    FUNC,
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


def test_every_record_of_a_night_is_v2(tmp_path):
    """From this plan on the driver writes only v2 records: the run records too."""
    night = Night(tmp_path, sessions=[Sess()], gate_exits=[0])
    night.run()
    for record in night.records():
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

