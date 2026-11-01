"""The owner's opt-in Fable trial night (quick 261101-b5f; amends D-09 as an owner opt-in).

`reverseapoc drive --fable-trial` runs every matching session on Fable 5.1 with the Fable
budget, whatever the function's pass, and queues only functions Opus already left partial in
status.csv, so the owner can compare Fable's cost per match with Opus's. A night without the
flag is unchanged.

Owner rule (D-11, D-25): no test runs the real `claude`, a real `drive` or the canary. Every
session is tests/fakeclaude.py through the existing harnesses (test_driver's Night, the
test_escalation Argv, test_drive's Rig, test_driver_pick's tier fixtures). Every name and
address is made up. Every new API is reached through its module inside the test body, so a
missing name fails its own tests, never the file's collection.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from reverseapoc import cli, driver, picker, status
from reverseapoc.session import FABLE_MODEL, OPUS_MODEL
from test_drive import BASE, EXES, Rig, _fixed_now, _git
from test_drive import _world as _pools_world
from test_driver import EXE, RUN, START, UNIT, Night, Sess, _one
from test_driver_pick import (
    TA,
    TB,
    TC,
    TD,
    UFO2P,
    _member,
    _rig_world,
    _seams,
    _signed_files,
    _signed_rig,
    _tq,
)
from test_driver_pick import _world as _tier_world
from test_driver_records import _commit
from test_escalation import (
    FABLE_COAUTHOR,
    Argv,
    _capped_passes,
    _exit_code,
    _night,
    _no_drive,
    _value,
)

FABLE_BUDGET = 12.5  # D-25 default, the trial's per-session budget
OPUS_BUDGET = 5  # D-07 default
TRIAL_DAY = "2026-11-01"  # "today" for the tier slice


def _status_files(partial: dict[int, str], matched=()) -> dict[str, str]:
    """Both EXEs' status.csv texts: UFO2P's `partial` starts (start -> date) partial and its
    `matched` starts matched; TACP's table empty."""
    rows = [status.StatusRow(s, f"func_{s:08X}", f"u_{s:08x}", status.MATCHED, 100.0, 1,
                             "0" * 64, "2026-10-01") for s in matched]  # fmt: skip
    rows += [status.StatusRow(s, f"func_{s:08X}", f"u_{s:08x}", status.PARTIAL, 40.0, 3,
                              "0" * 64, day) for s, day in partial.items()]  # fmt: skip
    return {"config/ufo2p/status.csv": status.format_status(rows),
            "config/tacp/status.csv": status.format_status([])}  # fmt: skip


# ---- Task 1: the tracer, the flag end to end on the tier path ----


def test_fable_trial_flag_reaches_the_options(capsys, monkeypatch):
    """OD-1: off by default; on with or without --dry-run."""
    seen = _no_drive(monkeypatch)
    assert cli.build_parser().parse_args(["drive"]).fable_trial is False
    assert cli.main(["drive", "--fable-trial", "--run", "t1"]) == 0
    options = _one(seen)
    assert (options.fable_trial, options.canary) == (True, False)
    seen.clear()
    assert cli.main(["drive", "--fable-trial", "--dry-run", "--run", "t2"]) == 0
    options = _one(seen)
    assert (options.fable_trial, options.dry_run) == (True, True)
    capsys.readouterr()
    assert _exit_code(["drive", "--help"]) == 0
    assert "--fable-trial" in capsys.readouterr().out


@pytest.mark.parametrize("extra, conflict", [
    (["--canary"], "--canary"),
    (["--session", "readability"], "--session readability"),
    (["--session", "readability", "--dry-run"], "--session readability"),
])  # fmt: skip
def test_fable_trial_is_refused_with_canary_or_readability(capsys, monkeypatch, extra, conflict):
    """OD-1: a trial is a matching night; the refusal comes before any preflight."""
    seen = _no_drive(monkeypatch)
    assert cli.main(["drive", "--fable-trial", *extra]) == 2
    err = capsys.readouterr().err
    assert "--fable-trial" in err and conflict in err
    assert seen == []


@pytest.mark.parametrize("log, pass_n", [([], 1), (_capped_passes(1), 2)])
def test_fable_trial_runs_every_pass_on_fable(tmp_path, log, pass_n):
    """OD-2, OD-4: passes 1 and 2 ask for Fable with the Fable budget; the record keeps the
    function's pass and the validator accepts it."""
    night, argv = _night(tmp_path, log)
    report = night.run(config={"attempts_per_function": 1, "fable_trial": True}, argv=argv)
    assert report.event == "ENDED", report.detail
    assert argv.asked == [(FABLE_MODEL, FABLE_BUDGET, 40)]
    real = _one(argv.real)
    assert (_value(real, "--model"), _value(real, "--max-budget-usd")) == (FABLE_MODEL, "12.5")
    record = _one([r for r in night.kinds("attempt") if r["run"] == RUN])
    assert (record["pass"], record["model_requested"], record["budget_usd"]) == (
        pass_n, FABLE_MODEL, FABLE_BUDGET)  # fmt: skip
    driver.validate_record(record)


def test_fable_trial_off_pass_2_stays_on_opus(tmp_path):
    """Pin (D-09): without the flag pass 2 still asks for Opus with the Opus budget."""
    night, argv = _night(tmp_path, _capped_passes(1))
    report = night.run(config={"attempts_per_function": 1}, argv=argv)
    assert report.event == "ENDED", report.detail
    assert argv.asked == [(OPUS_MODEL, OPUS_BUDGET, 40)]


def test_fable_trial_match_commit_and_claim_name_fable(tmp_path):
    """OD-2: the unit's claim file and the match commit's co-author name Fable."""
    night, argv = _night(tmp_path, [], gate_exits=[0])
    claims: list[dict] = []

    def spy(argv_, **kw):
        unit = kw["env"]["REVERSEAPOC_CLAIM"].split("/")[1]
        claim = night.repo / "build" / "driver" / "claims" / f"{EXE}__{unit}.json"
        claims.append(json.loads(claim.read_text(encoding="utf-8")))
        return night._session(argv_, **kw)

    report = night.run(config={"attempts_per_function": 1, "fable_trial": True}, argv=argv,
                       session=spy)  # fmt: skip
    assert report.event == "ENDED", report.detail
    assert [(c["pass"], c["model"]) for c in claims] == [(1, FABLE_MODEL)]
    body = night.message("feat(")
    assert body.rstrip("\n").splitlines()[-2:] == [FABLE_COAUTHOR, driver.MATCHED_BY]
    assert f"model {FABLE_MODEL}" in body


def _fake_drive(monkeypatch) -> list:
    """run_drive's night is a recorder: it keeps the DriveConfig and ends with nothing to do."""
    seen: list = []

    def fake_drive(config, deps, *, lock=None):
        seen.append(config)
        return driver.DriveReport(driver.ENDED, driver.NOTHING_TO_DO, 0, 0)

    monkeypatch.setattr(driver, "drive", fake_drive)
    return seen


def test_fable_trial_run_drive_hands_the_flag_to_the_night(tmp_path, capsys, monkeypatch):
    seen = _fake_drive(monkeypatch)
    code, _, _ = Rig(tmp_path / "on").drive(capsys, json=True, fable_trial=True)
    assert code == 0
    code, _, _ = Rig(tmp_path / "off").drive(capsys, json=True)
    assert code == 0
    assert [config.fable_trial for config in seen] == [True, False]


def _starts(items) -> list[int]:
    return [item.pick.start for item in items]


def test_fable_trial_only_keeps_the_queue_order_and_drops_outside_waits():
    """OD-3: the trial queue is the full queue's own items in the trial set, in the same
    order; an item never waits on a callee the trial does not offer."""
    full = _tq([_member(a) for a in (TA, TB, TC, TD)], [(TA, TD), (TB, TC)], matched=(TC,))
    full_order = _starts(full.preview(10))
    assert full_order == [TD, TA, TB]
    keys = {(UFO2P, TA), (UFO2P, TB), (UFO2P, TC)}
    trial = full.only(keys)
    assert isinstance(trial, picker.TierQueue)
    assert trial.next_item().pick.start == TA  # its wait on TD is dropped
    order = _starts(trial.preview(10))
    assert order == [TA, TB]
    assert order == [s for s in full_order if (UFO2P, s) in keys]
    held = _tq([_member(TA), _member(TB)], held=[(UFO2P, TB)]).only({(UFO2P, TA), (UFO2P, TB)})
    assert _starts(held.preview(10)) == [TA]
    assert held.held == ((UFO2P, TB),)


@pytest.mark.parametrize("case", ["trial", "off"])
def test_fable_trial_tier_night_launches_a_partial_row_on_fable(tmp_path, case):
    """The end-to-end slice: with a signed tier, the trial night's first session is a partial
    row (today's included, its wait on a never-attempted leaf dropped) on Fable; without the
    flag the night starts at the leaf on Opus."""
    leaf, mid, top = START, START + 0x10, START + 0x20
    rows = [_member(a) for a in (leaf, mid, top)]
    night = Night(tmp_path / case, sessions=[Sess()], gate_exits=[1])
    _commit(night, {**_signed_files(rows, tmp_path),
                    **_status_files({mid: TRIAL_DAY, top: "2026-10-30"})})  # fmt: skip
    worlds = _tier_world((leaf, mid, top), [(top, mid), (mid, leaf)], unit=UNIT)
    trial = {"fable_trial": True} if case == "trial" else {}
    options = driver.DriveOptions(repo=night.repo, run_id=RUN, **trial)
    deps = driver.real_deps(options, _seams(night, worlds), worlds, today=TRIAL_DAY)
    argv = Argv(night)
    night.run(config={"max_sessions": 1, **trial}, queue=deps.queue, requeue=deps.requeue,
              argv=argv)  # fmt: skip
    first, model = (mid, FABLE_MODEL) if case == "trial" else (leaf, OPUS_MODEL)
    assert [p.start for p, _, _ in night.packed][:1] == [first]
    assert argv.asked[0][0] == model
    record = _one([r for r in night.kinds("attempt") if r["run"] == RUN])
    assert record["pass"] == 1


# ---- Task 2: the pools fallback, the requeue guard, the dry run, the drafts, the console ----

F0, F1, F2, F3 = (BASE["ufo2p"] + i * 0x10000 for i in range(4))  # test_drive's ufo2p_f0..f3
POOLS_DAY = "2026-10-25"
TRIAL_DRY_RUN = ("fable trial: 2 picks, every session would run on claude-fable-5-1 at USD 12.5 "
                 "per session; queued from partial status.csv rows only")  # fmt: skip
TRIAL_NIGHT = ("[21:04:05] drive: fable trial: every session runs on claude-fable-5-1 at USD "
               "12.5 per session; queued from partial status.csv rows only")  # fmt: skip


def _commit_rig(rig: Rig, files: dict[str, str]) -> None:
    """Commit `files` in the rig's checkout (the preflight wants a clean tree)."""
    for rel, text in files.items():
        (rig.repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (rig.repo / rel).write_text(text, encoding="utf-8", newline="\n")
    _git(rig.repo, rig.env, "add", "--", *files)
    _git(rig.repo, rig.env, "commit", "-q", "-m", "status (made up)")


def _pools_rig(path: Path) -> Rig:
    """A rig without a signed tier: ufo2p_f0 matched, f1 partial today, f2 partial earlier."""
    rig = Rig(path)
    _commit_rig(rig, _status_files({F1: POOLS_DAY, F2: "2026-10-24"}, matched=(F0,)))
    return rig


def _tier_rig(path: Path) -> tuple[Rig, dict]:
    """A rig with tier 1 signed over TA..TD (TA calls TD, TB calls TC): TA partial on an earlier
    day, TB partial today, TC matched, TD never attempted."""
    rig = _signed_rig(path, [_member(a) for a in (TA, TB, TC, TD)])
    _commit_rig(rig, _status_files({TA: "2026-10-30", TB: driver._today()}, matched=(TC,)))
    return rig, _rig_world(rig.packs, (TA, TB, TC, TD), [(TA, TD), (TB, TC)])


def test_fable_trial_pools_queue_offers_only_partial_rows(tmp_path):
    """OD-3: without a signed tier the trial queue is the pools' partial rows, today's
    included; the matched and the never-attempted rows are out."""
    rig = _pools_rig(tmp_path)
    deps = driver.real_deps(rig.options(fable_trial=True), rig.seams(), _pools_world(rig.packs),
                            today=POOLS_DAY)  # fmt: skip
    picks = list(deps.queue(frozenset()))
    assert [p.start for p in picks if p.exe == "ufo2p"] == [F1, F2]
    assert not [p for p in picks if p.exe == "tacp"]


def test_fable_trial_pools_requeue_keeps_other_difficult_rows(tmp_path):
    """T-b5f-04: once both partial rows are difficult the trial pool is empty, so requeue gives
    them back, never the non-trial row (the night start saves what requeue returns)."""
    rig = _pools_rig(tmp_path)
    deps = driver.real_deps(rig.options(fable_trial=True), rig.seams(), _pools_world(rig.packs),
                            today=POOLS_DAY)  # fmt: skip
    difficult = {(UFO2P, F1): (), (UFO2P, F2): (), (UFO2P, F3): ()}
    assert tuple(deps.requeue(difficult)) == ((UFO2P, F1), (UFO2P, F2))


def test_fable_trial_dry_run_lists_the_trial_picks(tmp_path, capsys):
    """OD-5: the dry run lists the trial picks and says every session would run on Fable."""
    rig, worlds = _tier_rig(tmp_path / "json")
    code, out, _ = rig.drive(capsys, dry_run=True, json=True, fable_trial=True,
                             seams={"world": lambda: worlds})  # fmt: skip
    assert code == 0, out
    assert out.count("\n") == 1
    doc = json.loads(out)
    assert [(int(p["start"], 16), p["tier"], p["level"], p["pass"]) for p in doc["picks"]] == [
        (TA, 1, 1, 1), (TB, 1, 1, 1)]  # fmt: skip
    assert doc["fable_trial"] == {"model": FABLE_MODEL, "budget_usd": FABLE_BUDGET}
    assert [start for _, start, _ in rig.packs.built] == [TA, TB]
    assert not [c for c in rig.runner.calls if c[:1] == ["claude"]]
    assert not rig.commands("gate")
    rig, worlds = _tier_rig(tmp_path / "text")
    code, out, _ = rig.drive(capsys, dry_run=True, fable_trial=True,
                             seams={"world": lambda: worlds})  # fmt: skip
    assert code == 0, out
    lines = out.splitlines()
    assert lines[0] == TRIAL_DRY_RUN
    assert lines[1].startswith(f"ufo2p 0x{TA:08X}") and lines[2].startswith(f"ufo2p 0x{TB:08X}")


def test_fable_trial_dry_run_without_a_tier_uses_the_pools(tmp_path, capsys):
    """Discretion (b): the trial dry run lists up to --max-sessions trial picks, never the
    pilot's 5 + 5 (which a short partial set could not fill)."""
    rig = _pools_rig(tmp_path)
    code, out, _ = rig.drive(capsys, dry_run=True, json=True, fable_trial=True)
    assert code == 0, out
    doc = json.loads(out)
    assert [(p["exe"], p["start"]) for p in doc["picks"]] == [
        ("ufo2p", f"0x{F1:08X}"), ("ufo2p", f"0x{F2:08X}")]  # fmt: skip
    assert "fable_trial" in doc


def test_fable_trial_night_drafts_the_trial_picks(tmp_path):
    rig, worlds = _tier_rig(tmp_path)
    picks = driver.night_top_picks(rig.options(fable_trial=True), worlds, today=driver._today())
    assert [p.start for p in picks] == [TA, TB]
    assert all(isinstance(p, picker.Pick) for p in picks)


def test_fable_trial_night_names_the_trial_on_the_console(tmp_path, capsys, monkeypatch):
    """Discretion (c): a text-mode trial night prints one stamped line naming the trial before
    the night starts; --json keeps stderr empty; a night without the flag prints none."""
    seen = _fake_drive(monkeypatch)
    code, _, err = Rig(tmp_path / "text").drive(capsys, fable_trial=True,
                                                seams={"now": _fixed_now})  # fmt: skip
    assert code == 0, err
    assert TRIAL_NIGHT in err.splitlines()
    code, _, err = Rig(tmp_path / "json").drive(capsys, json=True, fable_trial=True,
                                                seams={"now": _fixed_now})  # fmt: skip
    assert (code, err) == (0, "")
    code, _, err = Rig(tmp_path / "off").drive(capsys, seams={"now": _fixed_now})
    assert code == 0, err
    assert not [line for line in err.splitlines() if "fable trial" in line]
    assert len(seen) == 3


def test_fable_trial_off_changes_nothing(tmp_path, capsys):
    """Pin (OD-1): the flag is off by default and a dry run without it is exactly as before."""
    assert driver.DriveOptions(repo=Path("."), run_id="r").fable_trial is False
    defaults = {f.name: f.default for f in dataclasses.fields(driver.DriveConfig)}
    assert defaults["fable_trial"] is False
    rig = Rig(tmp_path / "json")
    code, out, _ = rig.drive(capsys, dry_run=True, json=True)
    assert code == 0, out
    doc = json.loads(out)
    assert set(doc) == {"picks", "held", "held_starts"}
    expected = [(exe, BASE[exe] + i * 0x10000) for i in range(5) for exe in EXES]
    assert [(p["exe"], int(p["start"], 16)) for p in doc["picks"]] == expected
    code, out, _ = Rig(tmp_path / "text").drive(capsys, dry_run=True)
    assert code == 0, out
    assert not [line for line in out.splitlines() if line.startswith("fable trial")]
