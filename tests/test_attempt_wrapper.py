"""The attempt wrapper (tools/reverseapoc/attempt.py, `reverseapoc attempt`, D-44, D-07, F10, F27,
F33). The container is never run: every check goes through a fake runner, every root is a tmp
directory, and every LE byte, listing and check result below is made up."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from conftest import REPO_ROOT, build_le_image, fixup_record, write_manifest
from reverseapoc import attempt, hooks
from reverseapoc.cli import build_parser, main
from reverseapoc.functions import FunctionRow, write_functions_csv
from reverseapoc.status import StatusRow, lf_sha256, status_path, write_status
from test_contextpack import (
    A_BYTES,
    B_BYTES,
    C_BYTES,
    END,
    FUNC_A,
    FUNC_B,
    FUNC_C,
    UNIT_AB,
    UNIT_AB_TEXT,
    UNIT_C,
)

CLAIM = "ufo2p/u_000a34f0"
FUNC = "func_000A3980"
UNIT_TEXT = b'#include "common.h"\n\nINCLUDE_ASM(func_000A3980);\n'
OTHER = "func_000A34F0"  # a second game row of the claimed unit
CHECK_ROWS = [  # made-up functions.csv rows for the check tests (I1: the claim must be one)
    FunctionRow(0x000A34F0, 0x000A3980, OTHER, "game", "u_000a34f0", "call"),
    FunctionRow(0x000A3980, 0x000A3990, FUNC, "game", "u_000a34f0", "call"),
    FunctionRow(0x000A3990, 0x000A39A0, "func_000A3990", "runtime", "u_000a34f0", "runtime"),
    FunctionRow(0x000A4000, 0x000A4010, "func_000A4000", "game", "u_000a4000", "call"),
]


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
    write_functions_csv(root / "config" / "ufo2p" / "functions.csv", CHECK_ROWS, "UFO2P.EXE")
    roots = dataclasses.replace(attempt.ROOTS, repo=root, src=root / "src", config=root / "config")
    monkeypatch.setattr(attempt, "ROOTS", roots)
    monkeypatch.setenv(attempt.CLAIM_ENV, CLAIM)
    monkeypatch.setenv(attempt.FUNC_ENV, FUNC)
    monkeypatch.setenv(attempt.DIR_ENV, str(attempt_dir))
    monkeypatch.setenv(hooks.NOTES_ENV, str(attempt_dir / "notes.md"))
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


def test_attempt_check_names_the_attempt_dir(repo: Path, monkeypatch, capsys):
    """The goal prompt does not give the attempt directory; the summary does, so the agent can
    Read checks/NNNN.json and write notes.md there."""
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 0
    out = capsys.readouterr().out
    assert (repo / "checks" / "0001.json").as_posix() in out
    assert (repo / "notes.md").as_posix() in out


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


def _stub_doc() -> dict:
    """check's JSON for a unit whose other function matched while the claimed one is still
    INCLUDE_ASM: check's unit-wide ok is true and the claimed function is only a stub."""
    doc = _check_doc(ok=True)
    doc["functions"][0].update(name=OTHER, va="0x000A34F0")
    doc["stubs"] = [{"name": FUNC, "va": "0x000A3980", "status": "stub, not checked"}]
    return doc


def test_attempt_check_a_stub_claim_is_not_a_match(repo: Path, monkeypatch, capsys):
    """I1(b): exit 0 only for the claimed function itself. check exits 0 for this unit, but the
    claimed function was never compiled, so the wrapper says 1 and why."""
    _use(monkeypatch, FakeRunner(json.dumps(_stub_doc())))
    assert _run(["attempt", "check"]) == 1
    assert f"{FUNC} was not compiled (still INCLUDE_ASM?)" in capsys.readouterr().out
    (line,) = _lines(repo)
    assert line["exit"] == 1
    assert (line["best_percent"], line["reloc_ok"], line["bytes_ok"]) == (None, None, None)


def test_attempt_check_a_claim_missing_from_the_json_is_not_a_match(repo: Path, monkeypatch,
                                                                    capsys):  # fmt: skip
    doc = _stub_doc()
    doc["stubs"] = []
    _use(monkeypatch, FakeRunner(json.dumps(doc)))
    assert _run(["attempt", "check"]) == 1
    assert f"{FUNC} was not compiled (still INCLUDE_ASM?)" in capsys.readouterr().out


def test_attempt_check_the_claimed_function_must_pass_and_check_exit_0(repo: Path, monkeypatch):
    """I1(b): the claimed function at 100 with reloc and bytes ok is not enough when check
    exits 1 for its unit; check's own exit 2 passes through."""
    doc = _check_doc(ok=False)
    doc["functions"][0].update(objdiff_percent=100.0, reloc={"ok": True, "problems": []},
                               bytes={"ok": True, "differing": 0, "first_va": None})  # fmt: skip
    runner = _use(monkeypatch, FakeRunner(json.dumps(doc), returncode=1))
    assert _run(["attempt", "check"]) == 1
    runner.answer = attempt.Ran(2, "", "reverseapoc check: error: made-up")
    assert _run(["attempt", "check"]) == 2


@pytest.mark.parametrize(
    "func",
    ["func_000A4000",  # a game row of another unit
     "func_000A3990",  # a runtime row of the claimed unit
     "func_00099990"],  # no row at all
)  # fmt: skip
def test_attempt_refuses_a_func_that_is_no_game_row_of_the_claimed_unit(repo: Path, monkeypatch,
                                                                        capsys, func):  # fmt: skip
    """I1(a): the environment check refuses, with exit 2 and before any slot is reserved, a
    FUNC that is not a game or thunk row of the claimed unit (functions.csv, as check reads)."""
    monkeypatch.setenv(attempt.FUNC_ENV, func)
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    for argv in (["attempt", "check"], ["attempt", "check", "--sweep"]):
        assert _run(argv) == 2
        assert func in capsys.readouterr().err
    assert runner.calls == []
    assert not (repo / "checks").exists()


def test_attempt_sweep_exit_is_never_a_match(repo: Path, monkeypatch, capsys):
    """I1(c): a sweep exits 0 when it ran, whatever its cells say, and 2 when it did not; it
    never exits 1 and its 0 never reads as a match."""
    low = _cell(1, "10.6", ["-4r", "-s", "-fpi"], 10.0, reloc_ok=False, differing=9)
    runner = _use(monkeypatch, FakeRunner(json.dumps(_sweep_doc(low))))
    assert _run(["attempt", "check", "--sweep"]) == 0
    out = capsys.readouterr().out
    assert "never a match" in out
    assert " OK" not in out
    runner.answer = attempt.Ran(1, json.dumps(_sweep_doc(low)), "")
    assert _run(["attempt", "check", "--sweep"]) == 2
    runner.answer = attempt.Ran(2, "", "reverseapoc check: error: made-up")
    assert _run(["attempt", "check", "--sweep"]) == 2
    assert [line["exit"] for line in _lines(repo)] == [0, 2, 2]
    assert all(line["sweep"] is True for line in _lines(repo))  # M6: sweep lines say so


def test_attempt_help_states_the_claimed_function_rule(capsys):
    """I1(d): exit 0 is the claimed function's match, not a unit-wide 'matched'."""
    assert _run(["attempt", "--help"]) == 0
    out = " ".join(capsys.readouterr().out.split())
    assert "Exit 0 matched," not in out
    assert "claimed function" in out and "--sweep" in out


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


def test_attempt_dir_is_compared_with_exact_case():
    """The container's file system does not fold case, and .gitignore's build/ does not cover
    Build/ (contextpack's rule); a pure-path check, so it holds on every host."""
    anchor = Path("/repo/build/driver")
    assert attempt._inside(Path("/repo/build/driver/run1/ufo2p"), anchor)
    assert not attempt._inside(Path("/repo/Build/driver/run1/ufo2p"), anchor)
    assert not attempt._inside(anchor, anchor)


def test_attempt_check_budget(repo: Path, monkeypatch, capsys):
    """D-07: at most 25 check runs per attempt; the 26th is refused before anything runs."""
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=False, percent=10.0)), 1))
    _reserve(repo, attempt.CHECK_BUDGET - 1, log=True)
    assert attempt.CHECK_BUDGET == 25
    assert _run(["attempt", "check"]) == 1  # the 25th still runs
    assert _lines(repo)[-1]["n"] == 25
    capsys.readouterr()
    assert _run(["attempt", "check", "--sweep"]) == 2  # a sweep is a check run too
    assert len(runner.calls) == 1
    assert "check budget" in capsys.readouterr().err
    assert len(_lines(repo)) == 25
    assert not (repo / "checks" / "0026.c").exists()


def _reserve(attempt_dir: Path, count: int, *, log: bool) -> None:
    """`count` earlier runs: their snapshots (the reserved slots) and, with `log`, their lines."""
    checks = attempt_dir / "checks"
    checks.mkdir(exist_ok=True)
    for n in range(1, count + 1):
        (checks / f"{n:04d}.c").write_bytes(UNIT_TEXT)
    if log:
        lines = "".join(json.dumps({"n": n}) + "\n" for n in range(1, count + 1))
        (attempt_dir / "checks.jsonl").write_text(lines, encoding="utf-8")


def test_a_reserved_slot_counts_even_when_its_run_failed(repo: Path, monkeypatch, capsys):
    """Security finding 1: the budget counts reserved slots (checks/NNNN.c), so a run that was
    killed or crashed before it logged a line still counts."""
    runner = _use(monkeypatch, FakeRunner("not json", returncode=2))
    _reserve(repo, attempt.CHECK_BUDGET - 1, log=False)
    assert _run(["attempt", "check"]) == 2  # an exit-2 run is a run
    assert _lines(repo)[-1]["n"] == attempt.CHECK_BUDGET
    capsys.readouterr()
    assert _run(["attempt", "check"]) == 2
    assert "check budget" in capsys.readouterr().err
    assert len(runner.calls) == 1


def test_attempt_check_refuses_a_concurrent_run(repo: Path, monkeypatch, capsys):
    """Security finding 1: a second check while one runs (Bash run_in_background) is refused
    at once, and the count stays right."""
    import threading

    entered, release = threading.Event(), threading.Event()
    calls = []

    def blocking(argv):
        calls.append(tuple(argv))
        entered.set()
        assert release.wait(10)
        return attempt.Ran(0, json.dumps(_check_doc(ok=True)), "")

    monkeypatch.setattr(attempt, "RUNNER", blocking)
    first: list[int] = []
    thread = threading.Thread(target=lambda: first.append(_run(["attempt", "check"])))
    thread.start()
    try:
        assert entered.wait(10)
        assert _run(["attempt", "check"]) == 2
        assert _run(["attempt", "check", "--sweep"]) == 2
    finally:
        release.set()
        thread.join(10)
    assert first == [0]
    assert len(calls) == 1
    assert "another check is running in this attempt" in capsys.readouterr().err
    assert [line["n"] for line in _lines(repo)] == [1]
    assert sorted(p.name for p in (repo / "checks").iterdir()) == ["0001.c", "0001.json"]
    assert not (repo / "check.lock").exists()
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 0
    assert [line["n"] for line in _lines(repo)] == [1, 2]


def test_attempt_check_releases_the_lock_after_a_runner_exception(repo: Path, monkeypatch):
    def broken(argv):
        raise RuntimeError("made-up runner failure")

    monkeypatch.setattr(attempt, "RUNNER", broken)
    assert _run(["attempt", "check"]) == 2  # M9: never 1, which means "mismatch"
    assert not (repo / "check.lock").exists()
    assert (repo / "checks" / "0001.c").is_file()  # the slot stays reserved
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 0
    assert _lines(repo)[-1]["n"] == 2


def test_an_unexpected_exception_is_a_tool_error(repo: Path, monkeypatch, capsys):
    """M9: an exception outside cli._ERRORS exits 2 (a tool error), never 1, with one line on
    stderr and no traceback on stdout."""

    def broken(argv):
        raise RuntimeError("made-up runner failure")

    monkeypatch.setattr(attempt, "RUNNER", broken)
    assert _run(["attempt", "check"]) == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out
    (line,) = captured.err.strip().splitlines()
    assert "RuntimeError" in line and "made-up runner failure" in line


def test_attempt_check_prints_elapsed_seconds_and_checks_left(repo: Path, monkeypatch, capsys):
    """M2: the summary line gives the run's elapsed seconds and the checks left, so the agent
    budgets by measured time against the 30-minute clock."""
    _reserve(repo, 6, log=False)
    ticks = iter([100.0, 141.2])
    monkeypatch.setattr(attempt, "CLOCK", lambda: next(ticks), raising=False)
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=False, percent=50.0)), returncode=1))
    assert _run(["attempt", "check"]) == 1
    head = capsys.readouterr().out.splitlines()[0]
    assert "check 7/25, 41 s" in head
    assert "18 left" in head


@pytest.mark.parametrize("notes", [None, "other.md", "../notes.md"])
def test_attempt_refuses_a_notes_path_that_is_not_the_attempt_dirs(repo: Path, monkeypatch,
                                                                   notes):  # fmt: skip
    """M8: REVERSEAPOC_ATTEMPT_NOTES (the one path the hook lets the agent write) must be
    <attempt dir>/notes.md; anything else is refused with exit 2 before a run."""
    if notes is None:
        monkeypatch.delenv(hooks.NOTES_ENV)
    else:
        monkeypatch.setenv(hooks.NOTES_ENV, str(repo / notes))
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 2
    assert runner.calls == []


def test_attempt_check_prints_the_notes_env_path(repo: Path, monkeypatch, capsys):
    """M8: the printed notes path is REVERSEAPOC_ATTEMPT_NOTES as the driver set it."""
    given = repo / "sub" / ".." / "notes.md"
    monkeypatch.setenv(hooks.NOTES_ENV, str(given))
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 0
    assert f"notes: {given.as_posix()}" in capsys.readouterr().out


def test_a_stale_lock_is_never_cleared(repo: Path, monkeypatch, capsys):
    """A lock left by a killed run ends this attempt's checks (fail closed): the driver gives
    every session a fresh attempt directory."""
    (repo / "check.lock").write_text("12345\n", encoding="utf-8")
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 2
    assert runner.calls == []
    assert (repo / "check.lock").is_file()
    assert "another check is running in this attempt" in capsys.readouterr().err


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


# ---- Task 2: the context verb, attempt asm and attempt context ----

LISTING_B = "# func_00010010  made-up listing of B\n  0x00010010  ret\n"
LISTING_A = "# func_00010000  made-up listing of A\n  0x00010000  ret\n"
UNIT_C_TEXT = '#include "common.h"\n\nINCLUDE_ASM(func_00010020);\n'


def _image() -> bytes:
    records = (
        fixup_record(7, 0x06, 1, 0x20)
        + fixup_record(7, 0x11, 2, 0x200)
        + fixup_record(7, 0x16, 2, 0x100)
    )
    return build_le_image(
        fixups=[records, b"", b""], patches={FUNC_A: A_BYTES, FUNC_B: B_BYTES, FUNC_C: C_BYTES}
    ).data


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> attempt.Roots:
    """A tmp repository with a synthetic UFO2P.EXE, its CSVs, two unit files, listings, a
    draft, earlier notes in the driver's layout (ruling F9) and an attempt log."""
    repo = tmp_path / "repo"
    data = _image()
    orig = repo / "orig"
    orig.mkdir(parents=True)
    (orig / "UFO2P.EXE").write_bytes(data)
    manifest = write_manifest(repo / "targets.toml", {"UFO2P.EXE": data})
    config = repo / "config"
    rows = [
        FunctionRow(FUNC_A, FUNC_B, "func_00010000", "game", UNIT_AB, "call"),
        FunctionRow(FUNC_B, FUNC_C, "func_00010010", "game", UNIT_AB, "call"),
        FunctionRow(FUNC_C, END, "func_00010020", "game", UNIT_C, "call"),
    ]
    (config / "ufo2p").mkdir(parents=True)
    write_functions_csv(config / "ufo2p" / "functions.csv", rows, "UFO2P.EXE")
    write_status(status_path(config, "ufo2p"), [StatusRow(
        FUNC_A, "func_00010000", UNIT_AB, "matched", 100.0, 0, lf_sha256(UNIT_AB_TEXT),
        "2026-10-25")])  # fmt: skip
    src = repo / "src"
    _write(src / "ufo2p" / f"{UNIT_AB}.c", UNIT_AB_TEXT)
    _write(src / "ufo2p" / f"{UNIT_C}.c", UNIT_C_TEXT)
    asm_root = repo / "asm"
    _write(asm_root / "ufo2p" / "func_00010010.s", LISTING_B)
    _write(asm_root / "ufo2p" / "func_00010000.s", LISTING_A)
    _write(asm_root / "ufo2p" / "ghidra" / "func_00010010.c", "int func_00010010(void) {}\n")
    driver = repo / "build" / "driver"
    _write(driver / "run0" / "ufo2p" / "func_00010010" / "attempt-2" / "notes.md", "note two\n")
    _write(driver / "run0" / "ufo2p" / "func_00010010" / "attempt-1" / "notes.md", "note one\n")
    _write(driver / "manual" / "ufo2p" / "func_00010010" / "notes.md", "manual note\n")
    _write(driver / "run0" / "ufo2p" / "func_00010020" / "attempt-1" / "notes.md", "OTHER\n")
    _write(driver / "run0" / "tacp" / "func_00010010" / "attempt-1" / "notes.md", "TACP\n")
    _write(repo / "progress" / "attempts.jsonl", "\n".join([
        json.dumps({"kind": "attempt", "exe": "ufo2p", "function": "func_00010010",
                    "outcome": "PARTIAL", "run": "run0", "attempt": 1}),
        json.dumps({"kind": "attempt", "exe": "ufo2p", "function": "func_00010020",
                    "outcome": "GAVE_UP", "run": "run0", "attempt": 1}),
        "not json",
    ]) + "\n")  # fmt: skip
    roots = dataclasses.replace(attempt.ROOTS, repo=repo, orig=orig, manifest=manifest,
                                config=config, src=src, asm=asm_root)  # fmt: skip
    monkeypatch.setattr(attempt, "ROOTS", roots)
    return roots


def _context_argv(roots: attempt.Roots, *extra: str) -> list[str]:
    return ["context", "ufo2p", "func_00010010", "--orig", str(roots.orig),
            "--manifest", str(roots.manifest), "--config", str(roots.config),
            "--src", str(roots.src), "--asm", str(roots.asm), *extra]  # fmt: skip


def _claim_b(roots: attempt.Roots, monkeypatch: pytest.MonkeyPatch) -> Path:
    attempt_dir = roots.repo / "build" / "driver" / "run1" / "ufo2p" / "func_00010010" / "attempt-1"
    attempt_dir.mkdir(parents=True)
    monkeypatch.setenv(attempt.CLAIM_ENV, f"ufo2p/{UNIT_AB}")
    monkeypatch.setenv(attempt.FUNC_ENV, "func_00010010")
    monkeypatch.setenv(attempt.DIR_ENV, str(attempt_dir))
    monkeypatch.setenv(hooks.NOTES_ENV, str(attempt_dir / "notes.md"))
    return attempt_dir


def test_context_verb_writes_the_pack(tree: attempt.Roots, capsys):
    out = tree.repo / "build" / "driver" / "r" / "ufo2p" / "func_00010010"
    assert _run(_context_argv(tree, "--out", str(out))) == 0, capsys.readouterr().err
    text = (out / "context.md").read_text(encoding="utf-8")
    assert text.startswith("# Context pack: func_00010010")
    for title in ("Target listing", "Unit file", "Callers", "Callees", "D_ externs",
                  "include/common.h", "Ghidra draft", "Matching idioms", "Earlier notes",
                  "Look-alikes"):  # fmt: skip
        assert f"\n## {title}\n" in text
    assert "made-up listing of B" in text
    assert "func_00010000 (game, matched): int func_00010000(void);" in text  # status.csv
    assert "func_00010020 (game, unmatched)" in text
    assert "int func_00010010(void) {}" in text  # the draft
    assert "Known idioms" in text and "Relocation rules" in text  # matching.md, by heading
    assert "#define INCLUDE_ASM" in text  # include/common.h


def test_context_verb_collects_earlier_notes(tree: attempt.Roots, capsys):
    """F9: the driver's attempt-*/notes.md and manual notes.md of this EXE and function, sorted
    by path, and this function's attempts.jsonl records."""
    assert _run(_context_argv(tree)) == 0, capsys.readouterr().err
    out = tree.repo / "build" / "driver" / "manual" / "ufo2p" / "func_00010010"
    text = (out / "context.md").read_text(encoding="utf-8")
    manual, one, two = text.index("manual note"), text.index("note one"), text.index("note two")
    assert manual < one < two
    assert "run0/ufo2p/func_00010010/attempt-1/notes.md" in text
    assert "OTHER" not in text and "TACP" not in text
    assert '"outcome": "PARTIAL"' in text and "GAVE_UP" not in text


def test_context_verb_json_reports_size_and_cuts(tree: attempt.Roots, capsys):
    assert _run(_context_argv(tree, "--json")) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["pack_bytes"] > 0
    assert doc["truncated"] == []
    assert doc["path"].endswith("context.md")


def test_context_verb_refuses_an_out_outside_build_driver(tree: attempt.Roots, capsys):
    out = tree.repo / "elsewhere"
    assert _run(_context_argv(tree, "--out", str(out))) != 0
    assert not out.exists()
    assert "build" in capsys.readouterr().err


def test_attempt_asm_prints_the_claimed_listing(tree: attempt.Roots, monkeypatch, capsys):
    _claim_b(tree, monkeypatch)
    assert _run(["attempt", "asm"]) == 0
    assert capsys.readouterr().out == LISTING_B
    assert _run(["attempt", "asm", "func_00010000"]) == 0  # another row of the same EXE
    assert capsys.readouterr().out == LISTING_A
    assert _run(["attempt", "asm", "func_00099999"]) == 2  # no such row
    assert "func_00099999" in capsys.readouterr().err
    assert _run(["attempt", "asm", "func_00010020"]) == 2  # a row with no listing yet
    assert "reverseapoc asm" in capsys.readouterr().err


def test_attempt_asm_an_undecodable_listing_is_a_tool_error(tree: attempt.Roots, monkeypatch,
                                                            capsys):  # fmt: skip
    """M9: a UnicodeDecodeError (outside cli._ERRORS) is exit 2, one line, no traceback."""
    _claim_b(tree, monkeypatch)
    (tree.asm / "ufo2p" / "func_00010010.s").write_bytes(b"\xff\xfe made-up\n")
    assert _run(["attempt", "asm"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "UnicodeDecodeError" in captured.err


def test_attempt_context_rebuilds_into_the_attempt_dir(tree: attempt.Roots, monkeypatch, capsys):
    attempt_dir = _claim_b(tree, monkeypatch)
    assert _run(["attempt", "context"]) == 0
    captured = capsys.readouterr()
    printed = captured.out
    saved = (attempt_dir / "context.md").read_text(encoding="utf-8")
    assert printed == saved
    assert saved.startswith("# Context pack: func_00010010")
    assert "made-up listing of B" in saved
    assert (attempt_dir / "notes.md").as_posix() in captured.err


def test_context_and_attempt_help_exit_0(capsys):
    assert _run(["context", "--help"]) == 0
    assert _run(["attempt", "--help"]) == 0
