"""The schema of progress/attempts.jsonl (D-23, AGT-03): pinned key sets per kind, enums, types,
and no hex string longer than 64 characters (no game bytes, T-06-55). The committed log must
follow it, and so must every record the driver writes. Every value below is made up."""

from __future__ import annotations

import copy
import json

import pytest

from conftest import REPO_ROOT
from reverseapoc.driver import RecordError, append_record, validate_record
from test_driver import Night, Sess, check_line

LOG = REPO_ROOT / "progress" / "attempts.jsonl"


def _attempt() -> dict:
    return {
        "kind": "attempt", "run": "night1", "exe": "ufo2p", "function": "func_00010010",
        "unit": "u_00010000", "start": "0x00010010", "attempt": 1, "outcome": "PARTIAL",
        "abort_reason": None, "turns": 3,
        "tokens": {"input": 1200, "output": 300, "cache_read": 5000, "cache_creation": 800},
        "cost_usd": 0.25, "seconds": 45.0, "model": "claude-opus-5-5", "cli_version": "2.1.240",
        "check": {"runs": 2, "best_percent": 73.5, "sweep_hit": None, "needs": None},
        "pack_bytes": 2048, "truncated": ["look-alikes"], "date": "2026-10-25",
    }  # fmt: skip


def _abort() -> dict:
    return {"kind": "abort", "run": "night1", "exe": "tacp", "function": "func_00010010",
            "unit": "u_00010000", "start": "0x00010010", "attempt": 2,
            "abort_reason": "transient", "retries": 3, "date": "2026-10-25"}  # fmt: skip


def _run(event: str = "STOPPED", reason: str = "guardrail") -> dict:
    return {"kind": "run", "run": "night1", "event": event, "reason": reason,
            "detail": "stray paths: tools/x.py", "sessions": 2, "matched": 1,
            "date": "2026-10-25"}  # fmt: skip


def test_committed_log_follows_the_schema():
    assert LOG.is_file(), "progress/attempts.jsonl is committed (empty until the pilot)"
    data = LOG.read_bytes()
    assert b"\r" not in data
    for line in data.decode("utf-8").splitlines():
        validate_record(json.loads(line))


@pytest.mark.parametrize("record", [_attempt(), _abort(), _run(), _run("STARTED", "start"),
                                    _run("ENDED", "nothing to do")])  # fmt: skip
def test_schema_accepts_good_records(record):
    validate_record(record)


def _mutated(make, change):
    record = copy.deepcopy(make())
    change(record)
    return record


BAD = {
    "missing key": _mutated(_attempt, lambda r: r.pop("turns")),
    "extra key": _mutated(_attempt, lambda r: r.update(transcript="...")),
    "extra nested key": _mutated(_attempt, lambda r: r["tokens"].update(other=1)),
    "missing nested key": _mutated(_attempt, lambda r: r["check"].pop("needs")),
    "wrong type": _mutated(_attempt, lambda r: r.update(turns="3")),
    "bool for int": _mutated(_attempt, lambda r: r.update(attempt=True)),
    "wrong nested type": _mutated(_attempt, lambda r: r["check"].update(runs=None)),
    "unknown outcome": _mutated(_attempt, lambda r: r.update(outcome="MAYBE")),
    "unknown kind": _mutated(_attempt, lambda r: r.update(kind="session")),
    "unknown abort reason": _mutated(_abort, lambda r: r.update(abort_reason="tired")),
    "unknown event": _mutated(_run, lambda r: r.update(event="PAUSED")),
    "reason of another event": _mutated(_run, lambda r: r.update(reason="nothing to do")),
    "stopped without reason": _mutated(_run, lambda r: r.pop("reason")),  # F30
    "bad start": _mutated(_attempt, lambda r: r.update(start="65552")),
    "bad function": _mutated(_attempt, lambda r: r.update(function="FUN_10010")),
    "unknown exe": _mutated(_attempt, lambda r: r.update(exe="ufo2")),
    "bad date": _mutated(_attempt, lambda r: r.update(date="yesterday")),
    "65 hex characters": _mutated(_attempt, lambda r: r.update(model="a" * 65)),
    "65 hex characters nested": _mutated(
        _attempt, lambda r: r["check"].update(sweep_hit="needs " + "0123456789abcdef" * 4 + "f")
    ),  # fmt: skip
    "65 hex characters in a list": _mutated(_attempt, lambda r: r.update(truncated=["F" * 65])),
    "not an object": ["kind", "attempt"],
}


@pytest.mark.parametrize("name", sorted(BAD))
def test_schema_refuses_bad_records(name):
    with pytest.raises(RecordError):
        validate_record(BAD[name])


def test_a_64_character_hex_string_is_allowed():
    validate_record(_mutated(_attempt, lambda r: r.update(model="a" * 64)))


def test_append_record_refuses_a_bad_record_and_writes_nothing(tmp_path):
    log = tmp_path / "attempts.jsonl"
    with pytest.raises(RecordError):
        append_record(log, BAD["extra key"])
    assert not log.exists() or log.read_bytes() == b""


def _scenarios(tmp_path):
    """Nights covering every record shape the driver writes."""
    yield Night(tmp_path / "match", sessions=[Sess()], gate_exits=[0]), {}
    checks = (check_line(1, 50.0, sweep_hit="wcc386@10.5 -4r"),)
    yield Night(tmp_path / "partial", sessions=[Sess(checks=checks)]), {"attempts_per_function": 1}
    yield Night(tmp_path / "gave_up", sessions=[Sess()] * 3), {}
    yield Night(tmp_path / "lint", sessions=[Sess()], lint_exits=[1]), {"attempts_per_function": 1}
    yield Night(tmp_path / "timeout", sessions=[Sess("no_result", write=None, timeout=True)]), {
        "attempts_per_function": 1}  # fmt: skip
    yield Night(tmp_path / "abort", sessions=[Sess("overloaded", write=None)] * 4), {}
    yield Night(tmp_path / "stray", sessions=[Sess(write="tools/x.py")]), {}
    yield Night(tmp_path / "stop", sessions=[Sess("auth")]), {}
    yield Night(tmp_path / "init", sessions=[Sess("bad_init_model")]), {}
    yield Night(tmp_path / "tool", sessions=[Sess()], gate_exits=[2]), {}
    yield Night(tmp_path / "empty", picks=()), {}


def test_schema_accepts_driver_records(tmp_path):
    kinds = set()
    for night, config in _scenarios(tmp_path):
        night.run(config=config)
        for record in night.records():
            validate_record(record)
            kinds.add((record["kind"], record.get("outcome") or record.get("event")))
    assert {("attempt", "MATCHED"), ("attempt", "PARTIAL"), ("attempt", "GAVE_UP"),
            ("abort", None), ("run", "STARTED"), ("run", "STOPPED"),
            ("run", "ENDED")} <= kinds  # fmt: skip
