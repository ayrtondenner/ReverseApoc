"""The attempt wrapper (tools/reverseapoc/attempt.py, `reverseapoc attempt`, D-44, D-07, F10, F27,
F33). The container is never run: every check goes through a fake runner, every root is a tmp
directory, and every LE byte, listing and check result below is made up."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from reverseapoc import attempt, hooks
from reverseapoc.cli import build_parser, main

CLAIM = "ufo2p/u_000a34f0"
FUNC = "func_000A3980"
UNIT_TEXT = b'#include "common.h"\n\nINCLUDE_ASM(func_000A3980);\n'


class FakeRunner:
    """Records each argv and answers with one canned (returncode, stdout, stderr)."""

    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = "") -> None:
        self.calls: list[tuple[str, ...]] = []
        self.answer = attempt.Ran(returncode, stdout, stderr)

    def __call__(self, argv):
        self.calls.append(tuple(argv))
        return self.answer


def _check_doc(*, ok: bool, percent: float = 100.0) -> dict:
    return {
        "exe": "ufo2p",
        "unit": "u_000a34f0",
        "compiler": "wcc386@10.6",
        "flags": ["-4r", "-s", "-fpi"],
        "functions": [{
            "name": FUNC, "va": "0x000A3980", "size": 16, "objdiff_percent": percent,
            "reloc": {"ok": ok, "problems": [] if ok else ["made-up relocation problem"]},
            "bytes": {"ok": ok, "differing": 0 if ok else 3, "first_va": None},
            "raw_fields": [],
        }],
        "problems": [],
        "stubs": [],
        "splice": [{"exe": "UFO2P.EXE", "ok": ok}],
        "target": {"raw_fields": [], "undecoded": []},
        "ok": ok,
    }  # fmt: skip


def _cell(number: int, version: str, flags: list[str], percent: float, *, reloc_ok: bool = True,
          differing: int = 0) -> dict:  # fmt: skip
    return {"cell": number, "compiler": f"wcc386@{version}", "flags": flags,
            "status": "measured", "objdiff_percent": percent, "reloc_ok": reloc_ok,
            "differing": differing}  # fmt: skip


def _sweep_doc(*cells: dict) -> dict:
    return {"exe": "ufo2p", "unit": "u_000a34f0", "function": FUNC, "chk": False,
            "cells": list(cells), "best": [cells[0]["cell"]] if cells else [],
            "log": "/repo/build/logs/sweep.log"}  # fmt: skip


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tmp repository root holding the claimed unit file and the attempt directory, with the
    driver's environment set and attempt.ROOTS pointed at it."""
    root = tmp_path / "repo"
    unit = root / "src" / "ufo2p" / "u_000a34f0.c"
    unit.parent.mkdir(parents=True)
    unit.write_bytes(UNIT_TEXT)
    attempt_dir = root / "build" / "driver" / "run1" / "ufo2p" / FUNC / "attempt-1"
    attempt_dir.mkdir(parents=True)
    roots = dataclasses.replace(attempt.ROOTS, repo=root, src=root / "src")
    monkeypatch.setattr(attempt, "ROOTS", roots)
    monkeypatch.setenv(attempt.CLAIM_ENV, CLAIM)
    monkeypatch.setenv(attempt.FUNC_ENV, FUNC)
    monkeypatch.setenv(attempt.DIR_ENV, str(attempt_dir))
    return attempt_dir


def _use(monkeypatch: pytest.MonkeyPatch, runner: FakeRunner) -> FakeRunner:
    monkeypatch.setattr(attempt, "RUNNER", runner)
    return runner


def _run(argv: list[str]) -> int:
    """main's exit code, with argparse's SystemExit turned into its code."""
    try:
        return main(argv)
    except SystemExit as exc:
        return int(exc.code)


def _lines(attempt_dir: Path) -> list[dict]:
    path = attempt_dir / "checks.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# ---- Task 1: attempt check ----


def test_attempt_check_builds_the_container_argv(repo: Path, monkeypatch):
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 0
    assert runner.calls == [(
        "docker", "compose", "run", "--rm", "-T", "build",
        "uv", "run", "--frozen", "reverseapoc", "check", CLAIM, "--json",
    )]  # fmt: skip
    runner.answer = attempt.Ran(0, json.dumps(_sweep_doc()), "")
    assert _run(["attempt", "check", "--sweep"]) == 0
    assert runner.calls[1] == (*runner.calls[0], "--sweep", FUNC)


def test_attempt_check_passes_exit_codes_and_logs(repo: Path, monkeypatch, capsys):
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 0
    saved = repo / "checks" / "0001.json"
    assert json.loads(saved.read_text(encoding="utf-8"))["ok"] is True
    (line,) = _lines(repo)
    assert line["n"] == 1
    assert line["exit"] == 0
    assert line["best_percent"] == 100.0
    assert (line["reloc_ok"], line["bytes_ok"], line["splice_ok"]) == (True, True, True)
    assert line["sweep_hit"] is None
    out = capsys.readouterr().out
    assert "1/25" in out and "checks/0001.json" in out

    runner.answer = attempt.Ran(1, json.dumps(_check_doc(ok=False, percent=87.5)), "")
    assert _run(["attempt", "check"]) == 1
    second = _lines(repo)[1]
    assert (second["n"], second["exit"], second["best_percent"]) == (2, 1, 87.5)
    assert (second["reloc_ok"], second["bytes_ok"], second["splice_ok"]) == (False, False, False)
    assert "made-up relocation problem" in capsys.readouterr().out

    runner.answer = attempt.Ran(2, "not json", "reverseapoc check: error: made-up tool error")
    assert _run(["attempt", "check"]) == 2
    third = _lines(repo)[2]
    assert (third["n"], third["exit"], third["best_percent"]) == (3, 2, None)
    assert "made-up tool error" in capsys.readouterr().out

    runner.answer = attempt.Ran(0, "not json either", "")
    assert _run(["attempt", "check"]) == 2  # exit 0 with no JSON is never a pass


def test_attempt_check_snapshots_the_source(repo: Path, monkeypatch):
    """F10: each check keeps the C it checked next to its JSON, and the log line names it."""
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=False, percent=50.0)), returncode=1))
    unit = attempt.ROOTS.src / "ufo2p" / "u_000a34f0.c"
    assert _run(["attempt", "check"]) == 1
    unit.write_bytes(UNIT_TEXT + b"/* second shape */\n")
    assert _run(["attempt", "check"]) == 1
    first, second = _lines(repo)
    assert first["source"] == "checks/0001.c"
    assert second["source"] == "checks/0002.c"
    assert (repo / "checks" / "0001.c").read_bytes() == UNIT_TEXT
    assert (repo / "checks" / "0002.c").read_bytes().endswith(b"/* second shape */\n")


def test_attempt_check_sweep_logs_a_hit(repo: Path, monkeypatch, capsys):
    """F33: a 100.0 cell under flags other than the unit's cflags rule is a sweep hit."""
    default = _cell(1, "10.6", ["-4r", "-s", "-fpi"], 62.5)
    hit = _cell(7, "10.5", ["-4r", "-ox", "-s", "-fpi"], 100.0)
    runner = _use(monkeypatch, FakeRunner(json.dumps(_sweep_doc(hit, default))))
    assert _run(["attempt", "check", "--sweep"]) == 0
    (line,) = _lines(repo)
    assert line["sweep"] is True
    assert line["sweep_hit"] == "wcc386@10.5 -4r -ox -s -fpi"
    assert line["best_percent"] == 100.0
    assert "needs flags wcc386@10.5 -4r -ox -s -fpi" in capsys.readouterr().out

    near = _cell(3, "11.0", ["-5r", "-s", "-fpi"], 100.0, reloc_ok=False)
    same = _cell(1, "10.6", ["-4r", "-s", "-fpi"], 100.0)  # the default rule: no hit
    runner.answer = attempt.Ran(0, json.dumps(_sweep_doc(same, near)), "")
    assert _run(["attempt", "check", "--sweep"]) == 0
    assert _lines(repo)[1]["sweep_hit"] is None


@pytest.mark.parametrize(
    "extra",
    [
        ["ufo2p/u_other"],
        ["--cflags", "x"],
        ["--watcom-dir", "x"],
        ["--src", "x"],
        ["--json"],
        ["--swe"],
        ["--sweep", "func_000A3990"],
        ["check"],
    ],
)
def test_attempt_refuses_agent_arguments(repo: Path, monkeypatch, extra):
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check", *extra]) == 2
    assert runner.calls == []
    assert not (repo / "checks.jsonl").exists()


def test_attempt_refuses_an_unknown_subcommand(repo: Path, monkeypatch):
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    for argv in (["attempt"], ["attempt", "sweep"], ["attempt", "land"], ["attempt", "CHECK"]):
        assert _run(argv) == 2, argv
    assert runner.calls == []


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("claim", None),
        ("claim", "../x"),
        ("claim", "ufo2p/../../x"),
        ("claim", "doom/u_000a34f0"),
        ("claim", "ufo2p/U_000A34F0"),
        ("func", None),
        ("func", "func_000a3980"),
        ("func", "func_000A398"),
        ("func", "main_"),
        ("dir", None),
        ("dir", "outside"),
        ("dir", "build"),
        ("dir", "build/driver"),
        ("dir", "Build/driver/run1/ufo2p/func_000A3980/attempt-1"),
        ("dir", "build/driver/../../x"),
    ],
)
def test_attempt_refuses_a_bad_environment(repo: Path, monkeypatch, name, value):
    env = {"claim": attempt.CLAIM_ENV, "func": attempt.FUNC_ENV, "dir": attempt.DIR_ENV}[name]
    if value is None:
        monkeypatch.delenv(env)
    elif name == "dir":
        target = attempt.ROOTS.repo / value
        target.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(env, str(target))
    else:
        monkeypatch.setenv(env, value)
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 2
    assert runner.calls == []


def test_attempt_check_budget(repo: Path, monkeypatch, capsys):
    """D-07: at most 25 check runs per attempt; the 26th is refused before anything runs."""
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=False, percent=10.0)), 1))
    (repo / "checks.jsonl").write_text(
        "".join(json.dumps({"n": n}) + "\n" for n in range(1, attempt.CHECK_BUDGET)),
        encoding="utf-8",
    )
    assert attempt.CHECK_BUDGET == 25
    assert _run(["attempt", "check"]) == 1  # the 25th still runs
    assert _lines(repo)[-1]["n"] == 25
    capsys.readouterr()
    assert _run(["attempt", "check", "--sweep"]) == 2  # a sweep is a check run too
    assert len(runner.calls) == 1
    assert "check budget" in capsys.readouterr().err
    assert len(_lines(repo)) == 25


def test_attempt_forms_match_the_hook(repo: Path, monkeypatch):
    """F27: the wrapper accepts exactly hooks.ATTEMPT_FORMS (after ATTEMPT_PREFIX)."""
    assert hooks.ATTEMPT_PREFIX[-1] == "attempt"
    parser = build_parser()
    for form in hooks.ATTEMPT_FORMS:
        argv = [FUNC if token == hooks.ATTEMPT_NAME_SLOT else token for token in form]
        assert hooks.attempt_form_matches(argv)
        assert attempt.form_allowed(argv)
        parser.parse_args(["attempt", *argv])  # no SystemExit
    for bad in (["check", "--sweep", "--sweep"], ["asm", "9x"], ["asm", "--", FUNC],
                ["asm", FUNC, FUNC], ["context", FUNC], ["context", "--json"], []):  # fmt: skip
        assert not attempt.form_allowed(bad), bad
        runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
        assert _run(["attempt", *bad]) == 2, bad
        assert runner.calls == []


def test_attempt_help_exits_0(capsys):
    assert _run(["attempt", "--help"]) == 0
    assert "check" in capsys.readouterr().out


def test_default_roots_are_the_repository():
    assert attempt.ROOTS.repo == REPO_ROOT
    assert attempt.ROOTS.src == REPO_ROOT / "src"
