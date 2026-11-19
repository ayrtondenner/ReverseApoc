"""Todo long-tail-handoff-board, the threshold (owner ruling 2026-11-19): `reverseapoc handoff`
retires a function with at least 24 matching attempts whose best percent did not rise over its
last 9, and lists the board rows whose return rule is met (an owner hint, or tooling for its
failure class that landed after the row was retired). Every record and address is made up."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest

from reverseapoc import cli, handoff, picker
from reverseapoc.attempt import ATTEMPT_LOG, GIVEUP_CATEGORIES
from reverseapoc.functions import FunctionRow, format_functions_csv
from reverseapoc.status import StatusRow, format_status
from reverseapoc.targets import REPO_ROOT
from test_stats import _attempt_v3

TODAY = datetime.date(2026, 11, 19)
FA, FB, FC = 0x00010010, 0x00010040, 0x00020000
HEADER = ",".join(picker.HANDOFF_HEADER)


def _giveup(category: str) -> dict:
    return {"category": category, "tried": "two shapes", "still_differs": "the prologue",
            "suspected_cause": "the flags", "best_code": None}  # fmt: skip


def _attempts(start: int, percents: list[float | None], *, exe: str = "ufo2p",
              category: str = "register_allocation", run: str = "night1",
              **change) -> list[dict]:  # fmt: skip
    """One attempt record per percent, in order, each with a give-up of `category`."""
    fields = {"exe": exe, "function": f"func_{start:08X}", "start": f"0x{start:08X}",
              "run": run, "giveup": _giveup(category), **change}  # fmt: skip
    return [_attempt_v3(attempt=n, **fields,
                        check={"runs": 2, "best_percent": p, "sweep_hit": None, "needs": None})
            for n, p in enumerate(percents, start=1)]  # fmt: skip


# 15 earlier attempts peaking at 70, then 9 that stay at or under it: a long tail
FLAT = [50.0] * 9 + [70.0] + [50.0] * 5 + [60.0] * 9


def _world(tmp_path: Path, records: list[dict]) -> tuple[Path, Path]:
    """A config with both EXE directories and an attempt log holding `records`."""
    config = tmp_path / "config"
    for exe in picker.EXE_ORDER:
        (config / exe).mkdir(parents=True)
    log = tmp_path / ATTEMPT_LOG
    log.parent.mkdir(parents=True)
    log.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="ascii")
    return config, log


def _board(config: Path, rows: list[str]) -> Path:
    path = config / picker.HANDOFF_CSV
    path.write_text(HEADER + "\n" + "".join(f"{row}\n" for row in rows), encoding="utf-8")
    return path


def _keys(plan: handoff.Plan) -> list[tuple[str, int]]:
    return [(r.row.exe, r.row.address) for r in plan.retire]


def _hint(config: Path, exe: str, start: int) -> None:
    """A functions.csv holding `start` and an owner hint for it."""
    row = FunctionRow(start, start + 0x20, f"func_{start:08X}", "game", "u_00010000", "call")
    (config / exe / "functions.csv").write_text(format_functions_csv([row], f"{exe}.exe"),
                                                encoding="utf-8")  # fmt: skip
    (config / "hints").mkdir(exist_ok=True)
    (config / "hints" / f"{exe}.toml").write_text(f'0x{start:08X} = "a struct"\n',
                                                  encoding="utf-8")  # fmt: skip


def _tooling(config: Path, category: str, landed: str) -> None:
    (config / handoff.TOOLING_TOML).write_text(
        f'[[tooling]]\ncategory = "{category}"\nlanded = {landed}\ncommit = "abc1234"\n'
        'note = "a test"\n', encoding="utf-8")  # fmt: skip


# ---- retiring ----


def test_a_long_tail_function_is_retired(tmp_path):
    config, log = _world(tmp_path, _attempts(FA, FLAT))
    plan = handoff.plan(config, log, TODAY)
    assert [r.row for r in plan.retire] == [handoff.BoardRow(
        "ufo2p", FA, "long tail: 24 attempts, best 70.00%, mostly register_allocation",
        "2026-11-19", "hint or tooling:register_allocation")]  # fmt: skip
    assert plan.retire[0].name == f"func_{FA:08X}"
    assert plan.returns == ()


def test_23_attempts_are_not_enough(tmp_path):
    config, log = _world(tmp_path, _attempts(FA, FLAT[1:]))
    assert handoff.plan(config, log, TODAY).retire == ()


def test_a_rise_in_the_last_nine_keeps_it_queued(tmp_path):
    config, log = _world(tmp_path, _attempts(FA, FLAT[:-1] + [70.5]))
    assert handoff.plan(config, log, TODAY).retire == ()


def test_equalling_the_earlier_best_is_no_rise(tmp_path):
    config, log = _world(tmp_path, _attempts(FA, FLAT[:-1] + [70.0]))
    assert _keys(handoff.plan(config, log, TODAY)) == [("ufo2p", FA)]


def test_a_check_without_a_percent_counts_as_none(tmp_path):
    config, log = _world(tmp_path, _attempts(FA, FLAT[:-1] + [None]))
    assert _keys(handoff.plan(config, log, TODAY)) == [("ufo2p", FA)]


def test_only_matching_attempts_count_hold_runs_included(tmp_path):
    """23 matching attempts plus a readability session is not 24; a hold run's attempt is."""
    readability = _attempts(FA, [10.0], session="readability")
    config, log = _world(tmp_path, _attempts(FA, FLAT[1:]) + readability)
    assert handoff.plan(config, log, TODAY).retire == ()
    config, log = _world(tmp_path / "hold", _attempts(FA, FLAT[1:])
                         + _attempts(FA, [10.0], run="hold1", hold_run=True))  # fmt: skip
    assert _keys(handoff.plan(config, log, TODAY)) == [("ufo2p", FA)]


def test_errata_apply_before_the_rule(tmp_path):
    """The ledger lowers a mislogged 99 in the last nine to 60, so the best did not rise."""
    records = _attempts(FA, FLAT[:-1]) + _attempts(FA, [99.0], run="night2")
    config, log = _world(tmp_path, records)
    assert handoff.plan(config, log, TODAY).retire == ()
    (log.parent / "errata.toml").write_text(
        '[[correction]]\nrun = "night2"\nfield = "check.best_percent"\nold = 99.0\nnew = 60.0\n'
        'reason = "a test"\ndate = "2026-11-19"\n', encoding="utf-8")  # fmt: skip
    assert _keys(handoff.plan(config, log, TODAY)) == [("ufo2p", FA)]


def test_the_dominant_category_ties_go_to_the_category_order(tmp_path):
    records = (_attempts(FA, FLAT[:12], category="instruction_idiom")
               + _attempts(FA, FLAT[12:], category="flags"))  # fmt: skip
    config, log = _world(tmp_path, records)
    (row,) = [r.row for r in handoff.plan(config, log, TODAY).retire]
    assert GIVEUP_CATEGORIES.index("flags") < GIVEUP_CATEGORIES.index("instruction_idiom")
    assert row.reason.endswith("mostly flags") and row.return_rule == "hint or tooling:flags"


def test_no_give_up_record_counts_as_other(tmp_path):
    config, log = _world(tmp_path, _attempts(FA, FLAT, giveup=None))
    (row,) = [r.row for r in handoff.plan(config, log, TODAY).retire]
    assert row.reason.endswith("mostly other") and row.return_rule == "hint or tooling:other"


def test_a_matched_row_is_never_retired(tmp_path):
    config, log = _world(tmp_path, _attempts(FA, FLAT) + _attempts(FB, FLAT))
    matched = StatusRow(FA, f"func_{FA:08X}", "u_00010000", "matched", 100.0, 25, "0" * 64,
                        "2026-11-18")  # fmt: skip
    (config / "ufo2p" / "status.csv").write_text(format_status([matched]), encoding="utf-8")
    assert _keys(handoff.plan(config, log, TODAY)) == [("ufo2p", FB)]


def test_a_board_row_is_not_retired_again(tmp_path):
    config, log = _world(tmp_path, _attempts(FA, FLAT) + _attempts(FB, FLAT))
    _board(config, [f"ufo2p,0x{FA:08X},suspected bad split,2026-11-18,boundary fixed"])
    assert _keys(handoff.plan(config, log, TODAY)) == [("ufo2p", FB)]


def test_a_function_with_an_owner_hint_is_not_retired(tmp_path):
    """It would return on the next run: the owner's hint asks for agents on it."""
    config, log = _world(tmp_path, _attempts(FA, FLAT))
    _hint(config, "ufo2p", FA)
    assert handoff.plan(config, log, TODAY).retire == ()


def test_tooling_landed_after_its_last_attempt_keeps_it_queued(tmp_path):
    """It would return on the next run: the tooling has not been tried on it yet."""
    config, log = _world(tmp_path, _attempts(FA, FLAT))  # every record dated 2026-10-25
    _tooling(config, "register_allocation", "2026-10-26")
    assert handoff.plan(config, log, TODAY).retire == ()
    _tooling(config, "register_allocation", "2026-10-25")
    assert _keys(handoff.plan(config, log, TODAY)) == [("ufo2p", FA)]


def test_retirements_sort_by_exe_order_then_address(tmp_path):
    records = (_attempts(FC, FLAT, exe="tacp") + _attempts(FB, FLAT) + _attempts(FA, FLAT))
    config, log = _world(tmp_path, records)
    assert _keys(handoff.plan(config, log, TODAY)) == [("ufo2p", FA), ("ufo2p", FB),
                                                       ("tacp", FC)]  # fmt: skip


# ---- returns ----

LONG = '"long tail: 30 attempts, best 90.00%, mostly flags"'  # quoted: it holds commas


def test_a_hint_returns_a_long_tail_row(tmp_path):
    config, log = _world(tmp_path, [])
    _board(config, [f"ufo2p,0x{FA:08X},{LONG},2026-11-19,hint or tooling:flags"])
    _hint(config, "ufo2p", FA)
    plan = handoff.plan(config, log, TODAY)
    assert [(r.row.address, r.why) for r in plan.returns] == [
        (FA, "an owner hint in config/hints/ufo2p.toml")]  # fmt: skip


def test_tooling_for_its_category_landed_after_retirement_returns_it(tmp_path):
    config, log = _world(tmp_path, [])
    _board(config, [f"ufo2p,0x{FA:08X},{LONG},2026-11-19,hint or tooling:flags",
                    f"tacp,0x{FC:08X},{LONG},2026-11-20,hint or tooling:flags",
                    f"ufo2p,0x{FB:08X},{LONG},2026-11-01,hint or tooling:block_layout"])
    _tooling(config, "flags", "2026-11-20")
    plan = handoff.plan(config, log, TODAY)
    assert [(r.row.exe, r.row.address, r.why) for r in plan.returns] == [
        ("ufo2p", FA, "flags tooling landed 2026-11-20 (abc1234)")]  # fmt: skip


def test_rows_of_any_other_reason_are_never_returned(tmp_path):
    config, log = _world(tmp_path, [])
    _board(config, [f"ufo2p,0x{FA:08X},suspected bad split,2026-11-18,boundary fixed",
                    f"ufo2p,0x{FB:08X},owner keeps it,2026-11-18,hint or tooling:flags"])
    _hint(config, "ufo2p", FA)
    _tooling(config, "flags", "2026-11-30")
    assert handoff.plan(config, log, TODAY).returns == ()


# ---- the tooling ledger ----


def test_the_committed_tooling_ledger_has_a_header_and_no_entries():
    path = REPO_ROOT / "config" / handoff.TOOLING_TOML
    assert path.read_text(encoding="utf-8").startswith("#")
    assert handoff.read_tooling(path) == {}


def test_a_missing_ledger_lists_no_tooling(tmp_path):
    assert handoff.read_tooling(tmp_path / handoff.TOOLING_TOML) == {}


def test_the_latest_landing_per_category_counts(tmp_path):
    path = tmp_path / handoff.TOOLING_TOML
    entry = '[[tooling]]\ncategory = "flags"\nlanded = {}\ncommit = "{}"\nnote = "n"\n'
    path.write_text(entry.format("2026-11-21", "b") + entry.format("2026-11-20", "a"),
                    encoding="utf-8")  # fmt: skip
    assert handoff.read_tooling(path) == {"flags": (datetime.date(2026, 11, 21), "b")}


@pytest.mark.parametrize(("text", "words"), [
    ("[[tooling]]\ncategory = \"luck\"\nlanded = 2026-11-20\ncommit = \"a\"\nnote = \"n\"\n",
     "category"),
    ("[[tooling]]\ncategory = \"flags\"\nlanded = \"2026-11-20\"\ncommit = \"a\"\nnote = \"n\"\n",
     "landed"),
    ("[[tooling]]\ncategory = \"flags\"\nlanded = 2026-11-20\nnote = \"n\"\n", "keys"),
    ("[[tooling]]\ncategory = \"flags\"\nlanded = 2026-11-20\ncommit = \" \"\nnote = \"n\"\n",
     "commit"),
    ("other = 1\n", "only [[tooling]]"),
    ("[[tooling]\n", "TOML"),
], ids=["unknown-category", "string-date", "missing-commit", "blank-commit", "other-table",
        "not-toml"])  # fmt: skip
def test_a_bad_ledger_is_refused(tmp_path, text, words):
    path = tmp_path / handoff.TOOLING_TOML
    path.write_text(text, encoding="utf-8")
    with pytest.raises(handoff.HandoffError, match=words):
        handoff.read_tooling(path)


# ---- writing the board ----


def test_write_keeps_the_header_and_the_order(tmp_path):
    records = _attempts(FB, FLAT) + _attempts(FC, FLAT, exe="tacp")
    config, log = _world(tmp_path, records)
    kept = f"tacp,0x{FC + 0x10:08X},suspected bad split,2026-11-18,boundary fixed"
    back = f"ufo2p,0x{FA:08X},{LONG},2026-11-18,hint or tooling:flags"
    _board(config, [kept, back])
    _hint(config, "ufo2p", FA)
    plan = handoff.plan(config, log, TODAY)
    handoff.write(config, plan)
    lines = (config / picker.HANDOFF_CSV).read_text(encoding="utf-8").splitlines()
    assert lines == [
        HEADER,
        f"ufo2p,0x{FB:08X},"
        "\"long tail: 24 attempts, best 70.00%, mostly register_allocation\",2026-11-19,"
        "hint or tooling:register_allocation",
        f"tacp,0x{FC:08X},"
        "\"long tail: 24 attempts, best 70.00%, mostly register_allocation\",2026-11-19,"
        "hint or tooling:register_allocation",
        kept,
    ]
    assert picker.read_handoff(config / picker.HANDOFF_CSV) == {
        ("ufo2p", FB), ("tacp", FC), ("tacp", FC + 0x10)}  # fmt: skip


def test_write_without_a_board_starts_one(tmp_path):
    config, log = _world(tmp_path, _attempts(FA, FLAT))
    handoff.write(config, handoff.plan(config, log, TODAY))
    assert picker.read_handoff(config / picker.HANDOFF_CSV) == {("ufo2p", FA)}


# ---- the verb ----


def _cli_repo(tmp_path: Path, monkeypatch, records: list[dict]) -> Path:
    config, _log = _world(tmp_path, records)
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    return config


@pytest.mark.parametrize("argv", [[], ["--dry-run", "--write"]], ids=["neither", "both"])
def test_the_verb_takes_exactly_one_mode(argv, capsys):
    with pytest.raises(SystemExit) as caught:
        cli.build_parser().parse_args(["handoff", *argv])
    assert caught.value.code == 2


def test_dry_run_lists_and_writes_nothing(tmp_path, monkeypatch, capsys):
    config = _cli_repo(tmp_path, monkeypatch, _attempts(FA, FLAT))
    assert cli.main(["handoff", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "retire 1" in out and f"ufo2p 0x{FA:08X} func_{FA:08X}" in out
    assert "dry run: nothing written" in out
    assert not (config / picker.HANDOFF_CSV).exists()


def test_dry_run_json(tmp_path, monkeypatch, capsys):
    _cli_repo(tmp_path, monkeypatch, _attempts(FA, FLAT))
    assert cli.main(["handoff", "--dry-run", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["written"] is False and doc["returns"] == []
    assert doc["retire"] == [{
        "exe": "ufo2p", "address": f"0x{FA:08X}", "name": f"func_{FA:08X}",
        "reason": "long tail: 24 attempts, best 70.00%, mostly register_allocation",
        "retired_on": datetime.date.today().isoformat(),
        "return_rule": "hint or tooling:register_allocation"}]  # fmt: skip


def test_write_writes_the_board(tmp_path, monkeypatch, capsys):
    config = _cli_repo(tmp_path, monkeypatch, _attempts(FA, FLAT))
    assert cli.main(["handoff", "--write"]) == 0
    assert "wrote" in capsys.readouterr().out
    assert picker.read_handoff(config / picker.HANDOFF_CSV) == {("ufo2p", FA)}


def test_a_bad_ledger_exits_2(tmp_path, monkeypatch, capsys):
    config = _cli_repo(tmp_path, monkeypatch, [])
    (config / handoff.TOOLING_TOML).write_text("other = 1\n", encoding="utf-8")
    assert cli.main(["handoff", "--dry-run"]) == 2
    assert "reverseapoc handoff: error:" in capsys.readouterr().err
