"""Model escalation in the driver (plan 07-30; AGT-11, DEC-02, DEC-06; D-07, D-09, D-25).

Passes 1 and 2 of a function run on Opus 5.5 with the Opus budget, pass 3 and every later pass
on Fable 5.1 with the Fable budget; the pass comes from the committed log (07-23), the model from
session.model_for_pass and the argv from session.build_argv (07-42). The init check expects the
requested model, and each match commit names the model that wrote it.

Owner rule (D-11, D-25): no test runs the real `claude`. Every session is tests/fakeclaude.py
through the Night harness of test_driver.py; `--model` makes the stand-in echo the requested
model into its init event, `--init-model` forces another one. Every name and address is made up.
"""

from __future__ import annotations

import json

import pytest

from reverseapoc import driver, session, streamjson
from reverseapoc.session import FABLE_MODEL, OPUS_MODEL, build_argv
from test_drive import CANARY_DIR, _canary, _canary_rig
from test_driver import EXE, LOG, Night, Sess, _one
from test_driver_records import _commit, _lines, _v1, _v2

OPUS_BUDGET, FABLE_BUDGET = 5, 12.5  # D-07 (Opus) and D-25 (Fable) defaults


class Argv:
    """Deps.argv for the escalation tests: records what the driver asked for and the real argv
    session.build_argv gives for it, and returns the harness's stand-in argv with `--model`
    (the stand-in echoes it into its init event) and, if set, `--init-model`."""

    def __init__(self, night: Night, *, init_model: str | None = None) -> None:
        self.night, self.init_model = night, init_model
        self.asked: list[tuple[str, float, int]] = []
        self.real: list[list[str]] = []

    def __call__(self, prompt: str, *, model: str, max_budget_usd: float,
                 max_turns: int) -> list[str]:  # fmt: skip
        self.asked.append((model, max_budget_usd, max_turns))
        self.real.append(build_argv(prompt, claude="claude", model=model,
                                    max_budget_usd=max_budget_usd, max_turns=max_turns))
        fake = self.night._argv(prompt, model=model, max_budget_usd=max_budget_usd,
                                max_turns=max_turns)  # fmt: skip
        forced = ["--init-model", self.init_model] if self.init_model else []
        return [*fake, "--model", model, *forced]


def _value(argv: list[str], flag: str) -> str:
    return argv[argv.index(flag) + 1]


def _capped_passes(passes: int) -> list[dict]:
    """`passes` capped v2 passes of START on Opus, three PARTIAL attempts each (D-07)."""
    records = []
    for pass_n in range(1, passes + 1):
        for n in (1, 2, 3):
            record = _v2(f"night0-{pass_n}", pass_n, n)
            record.update(model_requested=OPUS_MODEL, budget_usd=OPUS_BUDGET, model=OPUS_MODEL)
            records.append(record)
    return records


def _night(tmp_path, log: list[dict], *, gate_exits=(1,), **argv) -> tuple[Night, Argv]:
    night = Night(tmp_path, sessions=[Sess()], gate_exits=list(gate_exits))
    if log:  # the harness's base commit holds an empty log
        _commit(night, {LOG: _lines(log)})
    return night, Argv(night, **argv)


# ---- Task 1: the tracer ----


def test_escalation_from_log(tmp_path):
    """D-09: two capped Opus passes in the committed log, so the next launch is pass 3 on Fable
    with the Fable budget (D-25), the record names the requested model and budget next to the
    init's model, and the stand-in's Fable init passes the driver's init check."""
    night, argv = _night(tmp_path, _capped_passes(2))
    report = night.run(config={"attempts_per_function": 1}, argv=argv)
    assert (report.event, report.reason) == ("ENDED", "queue exhausted"), report.detail
    assert argv.asked == [(FABLE_MODEL, FABLE_BUDGET, 40)]
    real = _one(argv.real)
    assert (_value(real, "--model"), _value(real, "--max-budget-usd")) == (FABLE_MODEL, "12.5")
    assert _value(real, "--max-turns") == "40"
    record = _one([r for r in night.kinds("attempt") if r["run"] == "night1"])
    assert (record["pass"], record["model_requested"], record["budget_usd"]) == (
        3, FABLE_MODEL, FABLE_BUDGET)  # fmt: skip
    assert record["model"] == FABLE_MODEL  # the init event's, as the stand-in echoed it
    driver.validate_record(record)


def test_pilot_function_next_pass_is_opus(tmp_path):
    """07-23: one v1 capped pass (the Phase 6 pilot) makes the next pass 2, still Opus with the
    Opus budget."""
    night, argv = _night(tmp_path, [_v1("20261026-005209", n) for n in (1, 2, 3)])
    report = night.run(config={"attempts_per_function": 1}, argv=argv)
    assert report.event == "ENDED", report.detail
    assert argv.asked == [(OPUS_MODEL, OPUS_BUDGET, 40)]
    assert _value(_one(argv.real), "--model") == OPUS_MODEL
    assert _value(_one(argv.real), "--max-budget-usd") == "5"
    record = _one([r for r in night.kinds("attempt") if r["run"] == "night1"])
    assert (record["pass"], record["model_requested"], record["budget_usd"]) == (
        2, OPUS_MODEL, OPUS_BUDGET)  # fmt: skip


def test_a_function_with_no_pass_runs_pass_1_on_opus(tmp_path):
    night, argv = _night(tmp_path, [])
    night.run(config={"attempts_per_function": 1}, argv=argv)
    assert argv.asked == [(OPUS_MODEL, OPUS_BUDGET, 40)]


def test_driver_passes_requested_model(tmp_path):
    """T-07-88: a Fable request answered by an Opus init stops the night (STOPPED init), and
    the STOPPED record names both models; nothing is counted or committed."""
    night, argv = _night(tmp_path, _capped_passes(2), init_model=OPUS_MODEL)
    report = night.run(config={"attempts_per_function": 1}, argv=argv)
    assert (report.event, report.reason) == ("STOPPED", "init")
    assert OPUS_MODEL in report.detail and FABLE_MODEL in report.detail
    stopped = _one([r for r in night.kinds("run") if r["event"] == "STOPPED"])
    assert OPUS_MODEL in stopped["detail"] and FABLE_MODEL in stopped["detail"]
    assert not [s for s in night.commits() if s.startswith("feat(")]
    assert not [r for r in night.kinds("attempt") if r["run"] == "night1"]


def test_an_opus_request_answered_by_fable_stops_the_night(tmp_path):
    """The check is the requested model's, both ways: an Opus pass answered by Fable stops."""
    night, argv = _night(tmp_path, [], init_model=FABLE_MODEL)
    report = night.run(config={"attempts_per_function": 1}, argv=argv)
    assert (report.event, report.reason) == ("STOPPED", "init")
    assert OPUS_MODEL in report.detail and FABLE_MODEL in report.detail


def test_budgets_and_turns_come_from_the_config(tmp_path):
    """D-07/D-25: the night's per-model budgets and max turns are config values (the drive
    flags), not constants."""
    night, argv = _night(tmp_path, _capped_passes(2))
    night.run(config={"attempts_per_function": 1, "fable_budget_usd": 20.0,
                      "max_budget_usd": 3.0, "max_turns": 12}, argv=argv)  # fmt: skip
    assert argv.asked == [(FABLE_MODEL, 20.0, 12)]
    record = _one([r for r in night.kinds("attempt") if r["run"] == "night1"])
    assert record["budget_usd"] == 20.0


def test_the_claim_names_the_requested_model(tmp_path):
    """The unit's claim file (D-06) carries the pass's requested model."""
    night, argv = _night(tmp_path, _capped_passes(2))
    claims: list[dict] = []

    def spy(argv_, **kw):
        unit = kw["env"]["REVERSEAPOC_CLAIM"].split("/")[1]
        claim = night.repo / "build" / "driver" / "claims" / f"{EXE}__{unit}.json"
        claims.append(json.loads(claim.read_text(encoding="utf-8")))
        return night._session(argv_, **kw)

    night.run(config={"attempts_per_function": 1}, argv=argv, session=spy)
    assert [(c["pass"], c["model"]) for c in claims] == [(3, FABLE_MODEL)]


# ---- Task 2: the canary checks its requested model; commits name the model that wrote them ----

FABLE_COAUTHOR = "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
OPUS_COAUTHOR = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"


def _expected_models(monkeypatch) -> list:
    """Every expected_model streamjson.check_init is called with (None: not passed)."""
    seen: list = []
    real = streamjson.check_init

    def check_init(init, **kw):
        seen.append(kw.get("expected_model"))
        return real(init, **kw)

    monkeypatch.setattr(streamjson, "check_init", check_init)
    return seen


def test_canary_passes_requested_model(tmp_path, capsys, monkeypatch):
    """T-07-88: the canary passes the model it asked for to check_init (Phase 6 passed none)."""
    seen = _expected_models(monkeypatch)
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md")
    code, doc = _canary(rig, capsys)
    assert (code, doc["canary"]) == (0, "PASS")
    assert seen == [OPUS_MODEL]
    assert rig.asked[0] == OPUS_MODEL


def test_canary_fails_when_its_init_names_another_model(tmp_path, capsys):
    rig = _canary_rig(tmp_path, "canary_pass", write=f"{CANARY_DIR}/context.md")
    plain = rig.argv

    def argv(prompt, **values):
        return [*plain(prompt, **values), "--init-model", FABLE_MODEL]

    rig.argv = argv
    code, doc = _canary(rig, capsys)
    assert (code, doc["canary"]) == (1, "FAIL")
    failed = [c["check"] for c in doc["checks"] if not c["ok"]]
    assert any(FABLE_MODEL in text and OPUS_MODEL in text for text in failed), failed


def test_coauthor_by_model():
    """07-42's MODEL_NAMES names each model; COAUTHOR stays the Opus line; an unknown model is
    refused rather than mislabelled (T-07-89)."""
    assert driver.coauthor(FABLE_MODEL) == FABLE_COAUTHOR
    assert driver.coauthor(OPUS_MODEL) == driver.COAUTHOR == OPUS_COAUTHOR
    with pytest.raises(driver.DriverError, match="claude-made-up-1"):
        driver.coauthor("claude-made-up-1")


def test_commit_message_uses_the_requested_models_coauthor():
    fields = dict(exe=EXE, function="func_00010010", unit="u_00010000", attempt_n=1,
                  attempts=3, model=FABLE_MODEL, usage=streamjson.usage({}), seconds=1.0,
                  sha1s=())  # fmt: skip
    message = driver.commit_message(**fields, requested_model=FABLE_MODEL)
    assert message.rstrip("\n").splitlines()[-2:] == [FABLE_COAUTHOR, driver.MATCHED_BY]
    with pytest.raises(driver.DriverError):
        driver.commit_message(**fields, requested_model="claude-made-up-1")


def test_a_fable_match_commit_names_fable(tmp_path):
    night, argv = _night(tmp_path, _capped_passes(2), gate_exits=[0])
    report = night.run(config={"attempts_per_function": 1}, argv=argv)
    assert report.event == "ENDED", report.detail
    body = night.message("feat(")
    assert body.rstrip("\n").splitlines()[-2:] == [FABLE_COAUTHOR, driver.MATCHED_BY]
    assert f"model {FABLE_MODEL}" in body


def test_an_opus_match_commit_keeps_the_opus_line(tmp_path):
    night, argv = _night(tmp_path, [], gate_exits=[0])
    night.run(config={"attempts_per_function": 1}, argv=argv)
    body = night.message("feat(")
    assert body.rstrip("\n").splitlines()[-2:] == [OPUS_COAUTHOR, driver.MATCHED_BY]


def test_an_unknown_model_is_never_committed(tmp_path, monkeypatch):
    """T-07-89: a model the co-author table does not name raises DriverError before the match
    commit; the night stops and the match is undone (no commit, no MATCHED record)."""
    monkeypatch.delitem(session.MODEL_NAMES, OPUS_MODEL)
    night, argv = _night(tmp_path, [], gate_exits=[0])
    report = night.run(config={"attempts_per_function": 1}, argv=argv)
    assert report.event == "STOPPED"
    assert "DriverError" in report.detail and OPUS_MODEL in report.detail
    assert not [s for s in night.commits() if s.startswith("feat(")]
    assert '"outcome":"MATCHED"' not in (night.repo / LOG).read_text(encoding="utf-8")
