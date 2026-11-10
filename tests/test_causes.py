"""`reverseapoc causes` (999.8, plan 07.2-04): failed builds and mismatches counted by cause
over drive run directories, from saved evidence only.

Every test builds a synthetic build/driver/<run>/<exe>/<function>/attempt-N under tmp_path:
checks.jsonl lines and checks/NNNN.json documents written here, no game bytes, never the real
runs."""

from __future__ import annotations

import json
from pathlib import Path

from reverseapoc import causes, cli

_FUNCTION = "func_00012340"


# ---- synthetic run directories ----


def _attempt(repo: Path, run: str, function: str = _FUNCTION, exe: str = "ufo2p",
             n: int = 1) -> Path:  # fmt: skip
    attempt_dir = repo / "build" / "driver" / run / exe / function / f"attempt-{n}"
    attempt_dir.mkdir(parents=True)
    return attempt_dir


def _line(n: int, exit_code: int, *, sweep: bool = False, **extra) -> dict:
    """A checks.jsonl line with the plain-check keys of RESEARCH Q5."""
    return {"best_percent": 100.0 if exit_code == 0 else 50.0, "bytes_ok": exit_code == 0,
            "exit": exit_code, "n": n, "readlint_violations": 0, "readlint_waivers": 0,
            "reloc_ok": exit_code != 2, "source": f"checks/{n:04d}.c", "splice_ok": True,
            "sweep": sweep, "sweep_hit": False, **extra}  # fmt: skip


def _log(attempt_dir: Path, lines: list) -> None:
    text = "".join((ln if isinstance(ln, str) else json.dumps(ln)) + "\n" for ln in lines)
    (attempt_dir / "checks.jsonl").write_text(text, encoding="utf-8")


def _five(attempt_dir: Path) -> None:
    """3 plain exit 1, 1 plain exit 0, 1 plain exit 2 and 2 sweeps."""
    plain = [_line(n, e) for n, e in enumerate((1, 1, 1, 0, 2), start=1)]
    _log(attempt_dir, [*plain, _line(6, 1, sweep=True), _line(7, 0, sweep=True)])


def _json(capsys, *argv: str) -> dict:
    assert cli.main(["causes", "--json", *argv]) == 0
    return json.loads(capsys.readouterr().out)


# ---- per-try rates (Task 1) ----


def test_rates(tmp_path):
    _five(_attempt(tmp_path, "run-a"))
    (row,) = causes.collect(tmp_path, ["run-a"]).to_json()["runs"]
    assert row["run"] == "run-a" and row["checks"] == 5
    assert (row["build_failure"], row["build_failure_percent"]) == (1, "20.0")
    assert (row["mismatch"], row["mismatch_percent"]) == (3, "60.0")
    assert (row["match"], row["match_percent"]) == (1, "20.0")
    assert row["sweeps"] == 2


def test_two_runs_and_total(tmp_path):
    _five(_attempt(tmp_path, "run-a"))
    _five(_attempt(tmp_path, "run-b", function="func_00012350"))
    _log(_attempt(tmp_path, "run-b", n=2), [_line(1, 0)])
    report = causes.collect(tmp_path, ["run-a", "run-b"])
    doc = report.to_json()
    assert [r["run"] for r in doc["runs"]] == ["run-a", "run-b"]
    assert [r["checks"] for r in doc["runs"]] == [5, 6]
    total = doc["rates"]
    assert (total["checks"], total["match"], total["mismatch"], total["build_failure"]) == (11, 3, 6, 2)
    assert total["match_percent"] == "27.3" and doc["sweeps"] == 4
    text = report.format()
    assert "run-a" in text and "run-b" in text and "total" in text and "27.3%" in text


def test_unknown_run_is_exit_2(tmp_path, capsys):
    _five(_attempt(tmp_path, "run-a"))
    assert cli.main(["causes", "nosuch", "--repo", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert captured.err.startswith("reverseapoc causes: error:") and "nosuch" in captured.err
    assert "Traceback" not in captured.err


def test_no_run_named_reads_every_run(tmp_path, capsys):
    _five(_attempt(tmp_path, "run-a"))
    _five(_attempt(tmp_path, "run-b"))
    doc = _json(capsys, "--repo", str(tmp_path))
    assert [r["run"] for r in doc["runs"]] == ["run-a", "run-b"]
    assert doc["rates"]["checks"] == 10


def test_ignores_extra_keys(tmp_path):
    attempt_dir = _attempt(tmp_path, "run-a")
    noted = _line(2, 0, note="checks/0002.note.json")  # 07.2-03's key
    _log(attempt_dir, [_line(1, 1), noted, "{not json", "[1, 2]", _line(3, 7)])
    doc = causes.collect(tmp_path, []).to_json()
    assert (doc["rates"]["checks"], doc["rates"]["match"], doc["rates"]["mismatch"]) == (2, 1, 1)
    assert doc["malformed"] == 3 and doc["runs"][0]["malformed"] == 3


def test_an_empty_checkout_prints_a_zero_total(tmp_path, capsys):
    assert cli.main(["causes", "--repo", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "total" in out and "0 checks" in out


def test_help_names_run_and_says_it_never_compiles(capsys):
    try:
        cli.main(["causes", "--help"])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out
    assert "RUN" in out and "--json" in out and "--repo" in out and "never compiles" in out
