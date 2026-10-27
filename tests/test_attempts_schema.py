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
            "checks_failed": [], "uncommitted": [], "date": "2026-10-25"}  # fmt: skip


def test_committed_log_follows_the_schema():
    assert LOG.is_file(), "progress/attempts.jsonl is committed (empty until the pilot)"
    data = LOG.read_bytes()
    assert b"\r" not in data
    for line in data.decode("utf-8").splitlines():
        validate_record(json.loads(line))


@pytest.mark.parametrize("record", [_attempt(), _abort(), _run(), _run("STARTED", "start"),
                                    _run("ENDED", "nothing to do")])  # fmt: skip
def test_schema_accepts_good_records(record):
    assert _problem(record) is None


def _problem(record) -> str | None:
    try:
        validate_record(record)
    except RecordError as exc:
        return str(exc)
    return None


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
    "run without checks_failed": _mutated(_run, lambda r: r.pop("checks_failed")),  # L1
    "checks_failed not a list": _mutated(_run, lambda r: r.update(checks_failed="ninja")),
    "run without uncommitted": _mutated(_run, lambda r: r.pop("uncommitted")),  # L2
    "uncommitted not strings": _mutated(_run, lambda r: r.update(uncommitted=[1])),
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


def test_schema_accepts_an_ended_record_with_failed_checks():
    record = _run("ENDED", "queue exhausted")
    record["checks_failed"] = ["ninja verify exit 1", "gate --all exit 1"]
    assert _problem(record) is None


# ---- schema 2 (Phase 7, DEC-06/DEC-07): v1 lines stay valid, v2 lines carry "schema": 2 ----


def _attempt_v2() -> dict:
    record = _attempt()
    record.update({
        "schema": 2, "session": "matching", "pass": 3, "model_requested": "claude-fable-5-1",
        "budget_usd": 12.5, "worker": 2, "hook_blocks": 1,
        "gate": {"exit": 0, "claimed_ok": True, "regressions": 0, "problems": []},
        "sweep_source": "checks/0007.c", "sweep_cells_100": ["wcc386@10.6 -4r -oneatx -s -fpi"],
    })  # fmt: skip
    return record


def test_v2_attempt_accepted():
    assert _problem(_attempt_v2()) is None


@pytest.mark.parametrize("change", [
    lambda r: r.update(gate=None, sweep_source=None, sweep_cells_100=[]),
    lambda r: r["gate"].update(exit=None, claimed_ok=False, regressions=2, problems=["splice"]),
])  # fmt: skip
def test_v2_attempt_optional_parts(change):
    assert _problem(_mutated(_attempt_v2, change)) is None


@pytest.mark.parametrize(("session", "outcome", "ok"), [
    ("readability", "LANDED", True), ("readability", "REFUSED", True),
    ("readability", "PARTIAL", True), ("readability", "GAVE_UP", True),
    ("readability", "MATCHED", False), ("matching", "LANDED", False),
    ("matching", "REFUSED", False), ("matching", "MATCHED", True),
])  # fmt: skip
def test_v2_readability_outcomes(session, outcome, ok):
    record = _mutated(_attempt_v2, lambda r: r.update(session=session, outcome=outcome))
    assert (_problem(record) is None) is ok


@pytest.mark.parametrize("schema", [1, 3, 2.0, "2", True, None])
def test_v1_record_with_schema_key_refused(schema):
    with pytest.raises(RecordError):
        validate_record(_mutated(_attempt, lambda r: r.update(schema=schema)))


def test_v2_record_with_another_schema_refused():
    with pytest.raises(RecordError):
        validate_record(_mutated(_attempt_v2, lambda r: r.update(schema=3)))


def test_mixed_log_validates(tmp_path):
    log = tmp_path / "attempts.jsonl"
    for record in (_run("STARTED", "start"), _attempt(), _attempt_v2(), _attempt()):
        append_record(log, record)
    lines = log.read_text(encoding="ascii").splitlines()
    assert len(lines) == 4
    for line in lines:
        validate_record(json.loads(line))
    assert ["schema" in json.loads(line) for line in lines] == [False, False, True, False]


def test_v2_function_accepts_a_renamed_name():
    assert _problem(_mutated(_attempt_v2, lambda r: r.update(function="GetSoundVolume"))) is None
    with pytest.raises(RecordError):
        validate_record(_mutated(_attempt, lambda r: r.update(function="GetSoundVolume")))


BAD_V2 = {
    "v1 record lacks v2 keys": _mutated(_attempt, lambda r: r.update(schema=2)),
    "unknown session": _mutated(_attempt_v2, lambda r: r.update(session="naming")),
    "pass 0": _mutated(_attempt_v2, lambda r: r.update(**{"pass": 0})),
    "budget 0": _mutated(_attempt_v2, lambda r: r.update(budget_usd=0)),
    "negative worker": _mutated(_attempt_v2, lambda r: r.update(worker=-1)),
    "hook_blocks text": _mutated(_attempt_v2, lambda r: r.update(hook_blocks="1")),
    "model_requested null": _mutated(_attempt_v2, lambda r: r.update(model_requested=None)),
    "gate missing key": _mutated(_attempt_v2, lambda r: r["gate"].pop("problems")),
    "gate claimed_ok int": _mutated(_attempt_v2, lambda r: r["gate"].update(claimed_ok=1)),
    "sweep_source path": _mutated(_attempt_v2, lambda r: r.update(sweep_source="src/x.c")),
    "sweep_cells_100 text": _mutated(_attempt_v2, lambda r: r.update(sweep_cells_100="-4r")),
    "function not a C name": _mutated(_attempt_v2, lambda r: r.update(function="1st")),
    "start not the key": _mutated(_attempt_v2, lambda r: r.update(start="GetSoundVolume")),
}


@pytest.mark.parametrize("name", sorted(BAD_V2))
def test_schema_refuses_bad_v2_records(name):
    with pytest.raises(RecordError):
        validate_record(BAD_V2[name])
