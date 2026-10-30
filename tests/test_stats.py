"""`reverseapoc stats` (DEC-07, plan 07-37): the attempt log read through the driver's own
validator, every match classed from git trailers (unattended, human-hints, human-written; the
flag-approved subset of research R4 shown on its own), and the research metrics.

Every git test runs on a synthetic repository; only test_committed_history_classes reads the
real history (ruling F13)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

import reverseapoc
from reverseapoc import cli  # imports reverseapoc.stats with the verb
from reverseapoc.functions import FunctionRow, format_functions_csv
from reverseapoc.mechanics import MemberRow, write_members
from reverseapoc.status import StatusRow, format_status
from test_driver import _git, _git_env, _write

_SHA = "0" * 64  # a made-up source_sha256
_DRIVE = "Matched-By: reverseapoc drive"


# ---- synthetic repositories ----


def _repo(tmp_path: Path) -> tuple[Path, dict]:
    env = _git_env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, env, "init", "-q")
    return repo, env


def _status_text(rows: dict[int, str]) -> str:
    """A status.csv with one row per start: `matched` or `partial`."""
    return format_status(
        StatusRow(start, f"func_{start:08X}", "u_00010000", status,
                  100.0 if status == "matched" else 50.0, 1, _SHA, "2026-10-30")
        for start, status in rows.items())  # fmt: skip


def _commit(repo: Path, env: dict, exe: str, rows: dict[int, str], subject: str,
            *trailers: str) -> str:  # fmt: skip
    """Write config/<exe>/status.csv with `rows` and commit it; returns the commit's hash."""
    _write(repo / "config" / exe / "status.csv", _status_text(rows))
    _git(repo, env, "add", "--", f"config/{exe}/status.csv")
    message = subject + ("\n\nbody line\n\n" + "\n".join(trailers) if trailers else "")
    _git(repo, env, "commit", "-q", "-m", message)
    return _git(repo, env, "rev-parse", "HEAD").strip()


def _classed_repo(tmp_path: Path) -> Path:
    """Four commits, one match each: drive, drive with Match-Hints, drive with
    Flags-Approved-By, and a hand match with no trailer."""
    repo, env = _repo(tmp_path)
    rows = {0x10010: "matched"}
    _commit(repo, env, "ufo2p", rows, "feat(ufo2p): match one", _DRIVE)
    rows[0x10020] = "matched"
    _commit(repo, env, "ufo2p", rows, "feat(ufo2p): match two", _DRIVE, "Match-Hints: owner note")
    rows[0x10030] = "matched"
    _commit(repo, env, "ufo2p", rows, "feat(ufo2p): match three", _DRIVE,
            "Flags-Approved-By: NAME (F-0001, 2026-11-01)")  # fmt: skip
    _commit(repo, env, "tacp", {0x20010: "matched"}, "feat(tacp): a hand match")
    return repo


def _empty_log(tmp_path: Path) -> Path:
    log = tmp_path / "attempts.jsonl"
    log.write_bytes(b"")
    return log


def _run(repo: Path, log: Path, *extra: str, config: Path | None = None) -> int:
    argv = ["stats", "--repo", str(repo), "--log", str(log),
            "--config", str(config or repo / "config"), *extra]  # fmt: skip
    return cli.main(argv)


def _json(capsys, repo: Path, log: Path, *extra: str, config: Path | None = None) -> dict:
    assert _run(repo, log, "--json", *extra, config=config) == 0
    return json.loads(capsys.readouterr().out)


# ---- Task 1: classes from trailers, AGT-11, refusals, the empty report ----


def test_classes_from_trailers(tmp_path, capsys):
    repo = _classed_repo(tmp_path)
    report = _json(capsys, repo, _empty_log(tmp_path))
    assert report["classes"] == {"human-hints": 1, "human-written": 1, "unattended": 2}
    assert report["flags_approved"] == 1
    events = report["events"]
    assert [(e["exe"], e["start"], e["class"], e["flags_approved"]) for e in events] == [
        ("ufo2p", "0x00010010", "unattended", False),
        ("ufo2p", "0x00010020", "human-hints", False),
        ("ufo2p", "0x00010030", "unattended", True),
        ("tacp", "0x00020010", "human-written", False),
    ]


def test_match_history_events(tmp_path):
    repo = _classed_repo(tmp_path)
    events = reverseapoc.stats.match_history(repo)
    assert [e.cls for e in events] == ["unattended", "human-hints", "unattended", "human-written"]
    assert [e.flags_approved for e in events] == [False, False, True, False]
    assert all(len(e.commit) == 40 for e in events)


def test_partial_rows_are_no_match(tmp_path):
    repo, env = _repo(tmp_path)
    _commit(repo, env, "ufo2p", {0x10010: "partial"}, "chore(driver): attempt log", _DRIVE)
    assert reverseapoc.stats.match_history(repo) == []
    _commit(repo, env, "ufo2p", {0x10010: "matched"}, "feat(ufo2p): match", _DRIVE)
    assert [(e.start, e.cls) for e in reverseapoc.stats.match_history(repo)] == [
        (0x10010, "unattended")
    ]


def test_matched_by_must_name_the_driver(tmp_path):
    repo, env = _repo(tmp_path)
    _commit(repo, env, "ufo2p", {0x10010: "matched"}, "feat: x", "Matched-By: someone else")
    assert [e.cls for e in reverseapoc.stats.match_history(repo)] == ["human-written"]


def test_text_names_the_classes(tmp_path, capsys):
    repo = _classed_repo(tmp_path)
    assert _run(repo, _empty_log(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "unattended: 2 (flag-approved 1)" in out
    assert "human-hints: 1" in out
    assert "human-written: 1" in out


def test_min_unattended(tmp_path, capsys):
    repo = _classed_repo(tmp_path)
    log = _empty_log(tmp_path)
    assert _run(repo, log, "--min-unattended", "3") == 1
    assert "below --min-unattended 3" in capsys.readouterr().err
    assert _run(repo, log, "--min-unattended", "2") == 0


def test_min_unattended_with_json(tmp_path, capsys):
    repo = _classed_repo(tmp_path)
    assert _run(repo, _empty_log(tmp_path), "--json", "--min-unattended", "3") == 1
    assert json.loads(capsys.readouterr().out)["classes"]["unattended"] == 2


def _attempt_v1(**change) -> dict:
    record = {
        "kind": "attempt", "run": "night1", "exe": "ufo2p", "function": "func_00010010",
        "unit": "u_00010000", "start": "0x00010010", "attempt": 1, "outcome": "PARTIAL",
        "abort_reason": None, "turns": 3,
        "tokens": {"input": 10, "output": 20, "cache_read": 30, "cache_creation": 40},
        "cost_usd": 0.25, "seconds": 45.0, "model": "claude-opus-5-5", "cli_version": "2.1.240",
        "check": {"runs": 2, "best_percent": 73.5, "sweep_hit": None, "needs": None},
        "pack_bytes": 2048, "truncated": [], "date": "2026-10-25",
    }  # fmt: skip
    record.update(change)
    return record


def _attempt_v2(**change) -> dict:
    record = _attempt_v1()
    record.update({
        "schema": 2, "session": "matching", "pass": 1, "model_requested": "claude-opus-5-5",
        "budget_usd": 12.5, "worker": 0, "hook_blocks": 0,
        "gate": {"exit": 0, "claimed_ok": False, "regressions": 0, "problems": []},
        "sweep_source": None, "sweep_cells_100": [],
    })  # fmt: skip
    record.update(change)
    return record


def _log(tmp_path: Path, *records: dict, name: str = "attempts.jsonl") -> Path:
    log = tmp_path / name
    log.write_bytes(b"".join((json.dumps(r) + "\n").encode("ascii") for r in records))
    return log


@pytest.mark.parametrize(
    "bad",
    ["{not json", "[1, 2]", json.dumps(_attempt_v1(turns=-1))],
    ids=["not-json", "a-list", "fails-its-schema"],
)
def test_malformed_lines(tmp_path, capsys, bad):
    repo, _ = _repo(tmp_path)
    log = tmp_path / "attempts.jsonl"
    log.write_bytes((json.dumps(_attempt_v1()) + "\n" + bad + "\n").encode("ascii"))
    assert _run(repo, log) == 2
    assert "line 2" in capsys.readouterr().err


def test_read_attempts_names_the_line(tmp_path):
    log = tmp_path / "attempts.jsonl"
    log.write_bytes(b'{"kind": "attempt"}\n')
    with pytest.raises(reverseapoc.stats.StatsError, match="line 1"):
        reverseapoc.stats.read_attempts(log)


def test_a_missing_log_is_refused(tmp_path, capsys):
    repo, _ = _repo(tmp_path)
    assert _run(repo, tmp_path / "nowhere.jsonl") == 2
    assert "nowhere.jsonl" in capsys.readouterr().err


def test_v1_and_v2_lines_read_together(tmp_path):
    log = _log(tmp_path, _attempt_v1(), _attempt_v2())
    assert [("schema" in r) for r in reverseapoc.stats.read_attempts(log)] == [False, True]


def test_empty(tmp_path, capsys):
    repo, _ = _repo(tmp_path)
    report = _json(capsys, repo, _empty_log(tmp_path))
    assert report["classes"] == {"human-hints": 0, "human-written": 0, "unattended": 0}
    assert report["flags_approved"] == 0
    assert report["events"] == []
    assert report["attempts"]["records"] == 0
    assert report["totals"]["turns"] == 0
    assert report["totals"]["cost_usd"] == "0.00"


def test_help_lists_the_flags(capsys):
    with pytest.raises(SystemExit):
        cli.main(["stats", "--help"])
    out = capsys.readouterr().out
    for flag in ("--json", "--min-unattended", "--log", "--repo", "--config"):
        assert flag in out


# ---- Task 2: the metrics ----


def _functions(config: Path, exe: str, sizes: dict[int, int]) -> None:
    """config/<exe>/functions.csv with one game row of each size."""
    rows = [FunctionRow(start, start + size, f"func_{start:08X}", "game", "u_00010000", "call")
            for start, size in sorted(sizes.items())]  # fmt: skip
    _write(config / exe / "functions.csv", format_functions_csv(rows, f"{exe.upper()}.EXE"))


def _on(start: int, **change) -> dict:
    """A v1 attempt record of the ufo2p function at `start`."""
    return _attempt_v1(start=f"0x{start:08X}", function=f"func_{start:08X}", **change)


def _on_v2(start: int, **change) -> dict:
    return _attempt_v2(start=f"0x{start:08X}", function=f"func_{start:08X}", **change)


def _report(capsys, tmp_path: Path, *records: dict, config: Path | None = None) -> dict:
    repo, _ = _repo(tmp_path)
    return _json(capsys, repo, _log(tmp_path, *records), config=config or tmp_path / "config")


@pytest.mark.parametrize(
    ("size", "bucket"), [(0, 0), (63, 0), (64, 1), (255, 1), (256, 2), (1023, 2), (1024, 3)]
)
def test_size_bucket_edges(size, bucket):
    assert reverseapoc.stats.size_bucket(size) == bucket


def test_size_buckets(tmp_path, capsys):
    starts = {0x10000: 63, 0x10100: 64, 0x10200: 255, 0x10400: 256, 0x10800: 1024}
    _functions(tmp_path / "config", "ufo2p", starts)
    records = [_on(start) for start in starts]
    records += [_on(0x10100, outcome="MATCHED"), _on(0x10400, outcome="MATCHED")]
    by_size = _report(capsys, tmp_path, *records)["by_size"]
    assert [(b["bucket"], b["attempted"], b["matched"], b["rate_percent"]) for b in by_size] == [
        ("[0, 64)", 1, 0, "0.0"),
        ("[64, 256)", 2, 1, "50.0"),
        ("[256, 1024)", 1, 1, "100.0"),
        ("[1024, inf)", 1, 0, "0.0"),
    ]


def test_a_function_without_a_size_is_unknown(tmp_path, capsys):
    by_size = _report(capsys, tmp_path, _on(0x10000))["by_size"]
    assert by_size[-1] == {"bucket": "unknown", "attempted": 1, "matched": 0,
                           "rate_percent": "0.0"}  # fmt: skip


def test_per_match_figures(tmp_path, capsys):
    a, b = 0x10000, 0x10100
    records = [
        _on(a, turns=4, cost_usd=0.5, seconds=10.0),
        _on_v2(a, outcome="MATCHED", turns=6, cost_usd=1.25, seconds=20.5),
        _on(b, turns=10, cost_usd=2.0, seconds=30.0),
        _on_v2(b, attempt=2, turns=2, cost_usd=0.25, seconds=4.0),
    ]
    report = _report(capsys, tmp_path, *records)
    per = report["per_match"]
    assert per["matched_functions"] == 1
    assert per["attempts"] == "4.0"
    assert per["turns"] == "22.0"
    assert per["tokens"] == {"cache_creation": "160.0", "cache_read": "120.0",
                             "input": "40.0", "output": "80.0"}  # fmt: skip
    assert per["cost_usd"] == "4.00"
    assert per["seconds"] == "64.5"
    assert report["totals"]["cost_usd"] == "4.00"


def test_per_match_figures_without_a_match_are_none(tmp_path, capsys):
    per = _report(capsys, tmp_path, _on(0x10000))["per_match"]
    assert per["matched_functions"] == 0
    assert per["attempts"] is None and per["cost_usd"] is None


def test_a_git_match_counts_for_the_attempted_function(tmp_path, capsys):
    """A flag-approved match lands with no MATCHED record: the attempted function is still
    matched (its match comes from git)."""
    repo, env = _repo(tmp_path)
    _commit(repo, env, "ufo2p", {0x10000: "matched"}, "feat: approve", _DRIVE,
            "Flags-Approved-By: NAME (F-0001, 2026-11-01)")  # fmt: skip
    report = _json(capsys, repo, _log(tmp_path, _on(0x10000)), config=tmp_path / "config")
    assert report["per_match"]["matched_functions"] == 1


def test_v1_fields_na(tmp_path, capsys):
    repo, _ = _repo(tmp_path)
    log = _log(tmp_path, _on(0x10000), _on(0x10100))
    report = _json(capsys, repo, log, config=tmp_path / "config")
    assert report["hook_blocks"] == {"v1_records": 2, "value": None}
    assert report["regressions_stopped"] == {"v1_records": 2, "value": None}
    assert report["by_session"] == {"kinds": {}, "v1_records": 2}
    assert _run(repo, log, config=tmp_path / "config") == 0
    out = capsys.readouterr().out
    assert "hook blocks: n/a for v1" in out
    assert "regressions the gate stopped: n/a for v1" in out
    assert "per session kind: n/a for v1" in out
    assert "per model: n/a for v1" in out


def test_v2_fields_summed(tmp_path, capsys):
    gate = {"exit": 1, "claimed_ok": False, "regressions": 2, "problems": ["x"]}
    records = [_on(0x10000), _on_v2(0x10000, hook_blocks=3, gate=gate),
               _on_v2(0x10000, hook_blocks=1, gate=None)]  # fmt: skip
    report = _report(capsys, tmp_path, *records)
    assert report["hook_blocks"] == {"v1_records": 1, "value": 4}
    assert report["regressions_stopped"] == {"v1_records": 1, "value": 2}


def test_model_and_kind_splits(tmp_path, capsys):
    opus, fable = "claude-opus-5-5", "claude-fable-5-1"
    records = [
        _on_v2(0x10000, model_requested=opus, outcome="MATCHED", cost_usd=1.0),
        _on_v2(0x10100, model_requested=opus, cost_usd=0.5),
        _on_v2(0x10200, model_requested=fable, outcome="MATCHED", cost_usd=3.0),
        _on_v2(0x10300, model_requested=fable, session="readability", outcome="LANDED",
               cost_usd=0.25),
    ]  # fmt: skip
    report = _report(capsys, tmp_path, _on(0x10400), *records)
    assert report["by_model"] == {
        "models": {
            fable: {"cost_usd": "3.25", "matched": 1, "sessions": 2},
            opus: {"cost_usd": "1.50", "matched": 1, "sessions": 2},
        },
        "v1_records": 1,
    }
    assert report["by_session"] == {
        "kinds": {
            "matching": {"cost_usd": "4.50", "matched": 2, "sessions": 3},
            "readability": {"cost_usd": "0.25", "matched": 0, "sessions": 1},
        },
        "v1_records": 1,
    }


def test_readability_sessions_are_no_matching_attempts(tmp_path, capsys):
    records = [_on_v2(0x10000, outcome="MATCHED"),
               _on_v2(0x10000, session="readability", outcome="LANDED", turns=50)]  # fmt: skip
    per = _report(capsys, tmp_path, *records)["per_match"]
    assert per["attempts"] == "1.0"
    assert per["turns"] == "3.0"


def _members(config: Path, rows: list[tuple[int, tuple[int, ...]]]) -> None:
    write_members(config / "mechanics-members.csv", [
        MemberRow("ufo2p", address, ("263-1",), tiers, (), "direct", "closure")
        for address, tiers in rows])  # fmt: skip


def test_tier_split(tmp_path, capsys):
    repo, env = _repo(tmp_path)
    _commit(repo, env, "ufo2p", {0x10000: "matched", 0x10100: "matched", 0x10200: "matched"},
            "feat: three matches", _DRIVE)  # fmt: skip
    _members(repo / "config", [(0x10000, (2, 3)), (0x10100, (1,))])
    report = _json(capsys, repo, _empty_log(tmp_path))
    zero = dict.fromkeys(("human-hints", "human-written"), 0)
    assert report["by_tier"] == {
        "1": {**zero, "unattended": 1},
        "2": {**zero, "unattended": 1},
        "none": {**zero, "unattended": 1},
    }


def test_no_members_file_no_tier_split(tmp_path, capsys):
    assert _report(capsys, tmp_path)["by_tier"] is None


def test_precision(tmp_path, capsys):
    assert reverseapoc.stats.money(Decimal("0.125")) == "0.12"
    assert reverseapoc.stats.money(Decimal("0.135")) == "0.14"
    assert _report(capsys, tmp_path, _on(0x10000, cost_usd=0.125))["totals"]["cost_usd"] == "0.12"
    (tmp_path / "repo").rename(tmp_path / "old")
    assert _report(capsys, tmp_path, _on(0x10000, cost_usd=0.135))["totals"]["cost_usd"] == "0.14"


def test_precision_rate_and_text(tmp_path, capsys):
    _functions(tmp_path / "config", "ufo2p", {0x10000: 8, 0x10100: 8, 0x10200: 8})
    records = [_on(0x10000, outcome="MATCHED", cost_usd=0.125), _on(0x10100), _on(0x10200)]
    report = _report(capsys, tmp_path, *records)
    assert report["by_size"][0]["rate_percent"] == "33.3"
    assert _run(tmp_path / "repo", tmp_path / "attempts.jsonl", config=tmp_path / "config") == 0
    out = capsys.readouterr().out
    assert "33.3%" in out
    assert "$0.12" in out


def test_full_precision_sums(tmp_path, capsys):
    """Ten records of 0.1 add to exactly 1.00 (floats would give 0.9999999999999999)."""
    records = [_on(0x10000, cost_usd=0.1, attempt=n) for n in range(1, 11)]
    assert _report(capsys, tmp_path, *records)["totals"]["cost_usd"] == "1.00"


def test_rematch_counted_once(tmp_path, capsys):
    repo, env = _repo(tmp_path)
    _commit(repo, env, "ufo2p", {0x10000: "matched"}, "feat: match", _DRIVE)
    _commit(repo, env, "ufo2p", {}, "revert: the match")
    _commit(repo, env, "ufo2p", {0x10000: "matched"}, "feat: match again by hand")
    report = _json(capsys, repo, _empty_log(tmp_path))
    assert [e["class"] for e in report["events"]] == ["unattended", "human-written"]
    assert report["classes"] == {"human-hints": 0, "human-written": 1, "unattended": 0}
    assert report["re_matched"] == ["ufo2p 0x00010000"]
    assert report["reverted"] == []


def test_a_reverted_match_is_not_counted(tmp_path, capsys):
    repo, env = _repo(tmp_path)
    _commit(repo, env, "ufo2p", {0x10000: "matched"}, "feat: match", _DRIVE)
    _commit(repo, env, "ufo2p", {0x10000: "partial"}, "revert: back to partial")
    report = _json(capsys, repo, _empty_log(tmp_path))
    assert report["classes"]["unattended"] == 0
    assert report["reverted"] == ["ufo2p 0x00010000"]


def test_one_commit_matching_two_functions(tmp_path, capsys):
    repo, env = _repo(tmp_path)
    _commit(repo, env, "ufo2p", {0x10000: "matched", 0x10100: "matched"}, "feat: two", _DRIVE)
    report = _json(capsys, repo, _empty_log(tmp_path))
    assert [(e["start"], e["class"]) for e in report["events"]] == [
        ("0x00010000", "unattended"),
        ("0x00010100", "unattended"),
    ]
    assert report["classes"]["unattended"] == 2
