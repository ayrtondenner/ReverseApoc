"""`reverseapoc stats` (DEC-07, plan 07-37): the attempt log read through the driver's own
validator, every match classed from git trailers (unattended, human-hints, human-written; the
flag-approved subset of research R4 shown on its own), and the research metrics.

Every git test runs on a synthetic repository; only test_committed_history_classes reads the
real history (ruling F13)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import reverseapoc
from reverseapoc import cli  # imports reverseapoc.stats with the verb
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
