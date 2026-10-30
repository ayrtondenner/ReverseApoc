"""The attempt wrapper (tools/reverseapoc/attempt.py, `reverseapoc attempt`, D-44, D-07, F10, F27,
F33). The container is never run: every check goes through a fake runner, every root is a tmp
directory, and every LE byte, listing and check result below is made up."""

from __future__ import annotations

import dataclasses
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import REPO_ROOT, build_le_image, fixup_record, write_manifest
from reverseapoc import attempt, check, hooks
from reverseapoc.cli import build_parser, main
from reverseapoc.functions import (
    FunctionRow,
    SymbolRow,
    UnitRow,
    write_functions_csv,
    write_symbols_csv,
    write_units_csv,
)
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


_NAME = re.compile(r"reverseapoc-attempt-([0-9a-f]{8})-([0-9]{4})")


def test_attempt_check_builds_the_container_argv(repo: Path, monkeypatch):
    """M7: the container is named reverseapoc-attempt-<8 hex of the attempt dir>-<NNNN>, so a
    run the wrapper stopped can be removed by name."""
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 0
    (first,) = runner.calls
    assert first[:6] == ("docker", "compose", "run", "--rm", "-T", "--name")
    name = _NAME.fullmatch(first[6])
    assert name is not None and name.group(2) == "0001"
    assert first[7:] == ("build", "uv", "run", "--frozen", "reverseapoc", "check", CLAIM, "--json")
    runner.answer = attempt.Ran(0, json.dumps(_sweep_doc()), "")
    assert _run(["attempt", "check", "--sweep"]) == 0
    second = runner.calls[1]
    assert second[6] == f"reverseapoc-attempt-{name.group(1)}-0002"  # same attempt, next slot
    assert second[7:] == (*first[7:], "--sweep", FUNC)


def test_container_names_differ_per_attempt_dir(repo: Path, monkeypatch):
    """M7: two attempt directories never share a container name."""
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 0
    other = repo.parent / "attempt-2"
    other.mkdir()
    monkeypatch.setenv(attempt.DIR_ENV, str(other))
    monkeypatch.setenv(hooks.NOTES_ENV, str(other / "notes.md"))
    assert _run(["attempt", "check"]) == 0
    one, two = (_NAME.fullmatch(call[6]) for call in runner.calls)
    assert one.group(1) != two.group(1)
    assert one.group(2) == two.group(2) == "0001"


class TimeoutRunner:
    """The check run times out (the default runner's TimeoutExpired); `docker rm -f` then
    answers with `rm_code`, or raises with `rm_raises`. Records each call's keyword arguments
    and, at the removal, whether the run's evidence was already on disk (fix round 2 N2).
    Duck-typed answers: only the fields the wrapper reads."""

    def __init__(self, rm_code: int = 0, *, attempt_dir: Path | None = None,
                 rm_raises: bool = False) -> None:  # fmt: skip
        self.calls: list[tuple[str, ...]] = []
        self.kwargs: list[dict] = []
        self.rm_code = rm_code
        self.attempt_dir = attempt_dir
        self.rm_raises = rm_raises
        self.evidence_at_removal: tuple[bool, bool] | None = None

    def __call__(self, argv, **kwargs):
        self.calls.append(tuple(argv))
        self.kwargs.append(kwargs)
        if argv[:2] == ("docker", "rm"):
            if self.attempt_dir is not None:
                saved = self.attempt_dir / "checks" / "0001.json"
                log = self.attempt_dir / "checks.jsonl"
                self.evidence_at_removal = (saved.is_file(), log.is_file())
            if self.rm_raises:
                raise subprocess.TimeoutExpired(argv, 15)
            return SimpleNamespace(returncode=self.rm_code, stdout="", stderr="made-up rm",
                                   timed_out=False)  # fmt: skip
        return SimpleNamespace(returncode=2, stdout="", stderr="made-up timeout", timed_out=True)


def test_a_timed_out_run_removes_its_container(repo: Path, monkeypatch):
    """M7: on the runner's timeout the wrapper runs `docker rm -f <name>` through the same
    runner before it releases the lock; the run is logged as exit 2."""
    runner = TimeoutRunner(rm_code=0)
    monkeypatch.setattr(attempt, "RUNNER", runner)
    assert _run(["attempt", "check"]) == 2
    check, remove = runner.calls
    assert remove == ("docker", "rm", "-f", check[6])
    assert not (repo / "check.lock").exists()
    assert _lines(repo)[-1]["exit"] == 2


def test_a_container_that_cannot_be_removed_keeps_the_lock(repo: Path, monkeypatch, capsys):
    """M7: if `docker rm -f` fails, the lock stays: this attempt's checks are over (fail
    closed), because the orphan container may still write build/."""
    runner = TimeoutRunner(rm_code=1)
    monkeypatch.setattr(attempt, "RUNNER", runner)
    assert _run(["attempt", "check"]) == 2
    assert len(runner.calls) == 2
    assert (repo / "check.lock").is_file()
    assert "could not be removed" in capsys.readouterr().out
    assert _run(["attempt", "check"]) == 2
    assert len(runner.calls) == 2  # refused: the lock is held


def test_the_evidence_is_written_before_the_removal(repo: Path, monkeypatch):
    """Fix round 2 N2: the run's JSON and its checks.jsonl line (exit 2) are on disk before
    `docker rm -f` starts, so a slow or failing removal cannot lose them; a removal that
    raises keeps the lock (fail closed)."""
    runner = TimeoutRunner(attempt_dir=repo, rm_raises=True)
    monkeypatch.setattr(attempt, "RUNNER", runner)
    assert _run(["attempt", "check"]) == 2
    assert runner.evidence_at_removal == (True, True)
    assert (repo / "check.lock").is_file()
    assert _lines(repo)[-1]["exit"] == 2
    saved = json.loads((repo / "checks" / "0001.json").read_text(encoding="utf-8"))
    assert "made-up timeout" in saved["stderr"]


def _failing_write(monkeypatch, which: str) -> None:
    def broken(*args, **kwargs):
        raise OSError(f"made-up {which} failure")

    monkeypatch.setattr(attempt, which, broken)


@pytest.mark.parametrize("which", ["write_atomic", "_append"])
@pytest.mark.parametrize(("rm_code", "lock_kept"), [(0, False), (1, True)])
def test_a_failed_evidence_write_still_removes_the_container(
    repo: Path, monkeypatch, capsys, which, rm_code, lock_kept
):
    """Fix round 2 N7 (security finding, fail-open): after a timeout the lock is marked kept
    before any evidence write, the removal runs in a `finally`, and only a removal that
    succeeded releases the lock. The write error surfaces as exit 2."""
    runner = TimeoutRunner(rm_code=rm_code)
    monkeypatch.setattr(attempt, "RUNNER", runner)
    _failing_write(monkeypatch, which)
    assert _run(["attempt", "check"]) == 2
    assert [call[:2] for call in runner.calls] == [("docker", "compose"), ("docker", "rm")]
    assert (repo / "check.lock").is_file() is lock_kept
    assert f"made-up {which} failure" in capsys.readouterr().err


@pytest.mark.parametrize("which", ["write_atomic", "_append"])
def test_a_failed_evidence_write_and_a_raising_removal_keep_the_lock(repo: Path, monkeypatch,
                                                                     which):  # fmt: skip
    """N7: a removal that raises after a failed evidence write still fails closed."""
    runner = TimeoutRunner(rm_raises=True)
    monkeypatch.setattr(attempt, "RUNNER", runner)
    _failing_write(monkeypatch, which)
    assert _run(["attempt", "check"]) == 2
    assert len(runner.calls) == 2
    assert (repo / "check.lock").is_file()


def test_the_removal_has_its_own_short_timeout(repo: Path, monkeypatch):
    """Fix round 2 N2: `docker rm -f` gets RM_TIMEOUT (15 s), so 580 + 15 stays under the
    Bash tool's 600 s; the check run keeps the runner's own timeout."""
    assert getattr(attempt, "RM_TIMEOUT", None) == 15
    assert attempt.CHECK_TIMEOUT + attempt.RM_TIMEOUT < 600
    runner = TimeoutRunner()
    monkeypatch.setattr(attempt, "RUNNER", runner)
    assert _run(["attempt", "check"]) == 2
    assert runner.kwargs == [{}, {"timeout": attempt.RM_TIMEOUT}]
    assert not (repo / "check.lock").exists()


def test_the_default_runner_takes_a_timeout(monkeypatch):
    """Fix round 2 N2: default_runner passes a given timeout to subprocess.run."""
    seen = {}

    def run(argv, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(attempt.subprocess, "run", run)
    try:
        attempt.default_runner(("docker", "rm", "-f", "x"), timeout=15)
    except TypeError:
        pytest.fail("default_runner takes no timeout")
    assert seen["timeout"] == 15
    attempt.default_runner(("docker", "compose", "run"))
    assert seen["timeout"] == attempt.CHECK_TIMEOUT


def test_container_prefix_is_the_names_single_source(repo: Path, monkeypatch):
    """Fix round 2 N3: attempt.container_prefix(attempt dir) is the one name builder the
    06-23 driver reuses; it resolves the directory, so any spelling of it gives the prefix of
    the name the wrapper passed to docker."""
    prefix = getattr(attempt, "container_prefix", None)
    assert prefix is not None, "attempt.container_prefix is the driver's name helper"
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 0
    name = runner.calls[0][6]
    assert name == prefix(repo) + "0001"
    assert prefix(repo / "sub" / "..") == prefix(repo)
    assert prefix(repo).startswith(attempt.CONTAINER_PREFIX) and prefix(repo).endswith("-")


def test_the_default_runner_reports_a_timeout(monkeypatch):
    """M7: the default runner turns TimeoutExpired into a timed-out exit-2 run."""

    def slow(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, attempt.CHECK_TIMEOUT)

    monkeypatch.setattr(attempt.subprocess, "run", slow)
    ran = attempt.default_runner(("docker", "compose", "run"))
    assert ran.returncode == 2
    assert getattr(ran, "timed_out", False) is True


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


def test_attempt_sweep_with_no_measured_cell_logs_no_percent(repo: Path, monkeypatch, capsys):
    """Review IN-01: a sweep that measured no cell carries no measurement, like a plain check
    that compiled nothing: best_percent, reloc_ok and bytes_ok are all null, and the driver's
    reader still takes the line."""
    from reverseapoc import driver

    failed = dict(_cell(1, "10.6", ["-4r", "-s", "-fpi"], 0.0), status="failed")
    _use(monkeypatch, FakeRunner(json.dumps(_sweep_doc(failed))))
    assert _run(["attempt", "check", "--sweep"]) == 0
    (line,) = _lines(repo)
    assert (line["best_percent"], line["reloc_ok"], line["bytes_ok"]) == (None, None, None)
    summary = driver.read_checks(repo)
    assert (summary.runs, summary.best_percent) == (1, None)


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


@pytest.mark.parametrize("error", [RuntimeError, OSError])  # outside and inside cli._ERRORS
def test_a_multi_line_error_is_printed_as_one_line(repo: Path, monkeypatch, capsys, error):
    """Fix round 2 N1: a tool error is exactly one stderr line, CR/LF in its text replaced."""

    def broken(argv):
        raise error("line one\nline two\r\nline three")

    monkeypatch.setattr(attempt, "RUNNER", broken)
    assert _run(["attempt", "check"]) == 2
    err = capsys.readouterr().err
    assert err.count("\n") == 1 and "\r" not in err
    assert "line one line two line three" in err


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
    write_units_csv(config / "ufo2p" / "units.csv", [UnitRow(UNIT_AB, FUNC_A, FUNC_C, "first"),
                    UnitRow(UNIT_C, FUNC_C, END, "first")], "UFO2P.EXE")  # fmt: skip
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


def test_context_verb_keeps_long_notes_whole_when_the_pack_fits(tree: attempt.Roots, capsys):
    """M11: no fixed notes cap; a 10 KB notes.md stays whole when the pack fits, and the
    notes.md texts come before the attempts.jsonl records."""
    long = "FIRST" + "n" * 10_000 + "LAST\n"
    _write(tree.repo / "build" / "driver" / "run0" / "ufo2p" / "func_00010010" / "attempt-1"
           / "notes.md", long)  # fmt: skip
    assert _run(_context_argv(tree, "--json")) == 0, capsys.readouterr().err
    doc = json.loads(capsys.readouterr().out)
    assert doc["truncated"] == []
    text = Path(doc["path"]).read_text(encoding="utf-8")
    assert long.rstrip("\n") in text
    assert text.index("note two") < text.index("progress/attempts.jsonl")


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


def test_attempt_reads_the_exe_with_checks_loader(tree: attempt.Roots, monkeypatch):
    """M12: attempt asm/context and the context verb load the EXE through check.load_exe (one
    loader: the same CSVs, symbols.csv default and data ranges as check), not a third copy."""
    assert not hasattr(attempt, "load_exe") and not hasattr(attempt, "ExeData")
    calls = []
    real = check.load_exe
    monkeypatch.setattr(check, "load_exe", lambda *a, **k: calls.append(1) or real(*a, **k))
    _claim_b(tree, monkeypatch)
    assert _run(["attempt", "asm"]) == 0
    assert _run(_context_argv(tree)) == 0
    assert len(calls) == 2


def test_context_verb_reads_config_like_check(capsys):
    """M12: the context verb takes check's config root (--config) for every CSV, so it has no
    --functions or --symbols of its own."""
    assert _run(["context", "--help"]) == 0
    out = capsys.readouterr().out
    assert "--config" in out
    assert "--functions" not in out and "--symbols" not in out


def test_context_and_attempt_help_exit_0(capsys):
    assert _run(["context", "--help"]) == 0
    assert _run(["attempt", "--help"]) == 0


# ---- 07-11 (D-24 P7): checks rooted in the session's private view ----

VIEW_TEXT = UNIT_TEXT + b"/* the view unit, private to this session */\n"
VIEW_CFLAGS = "* wcc386@10.6 -4r -s -fpi\nsrc/ufo2p/u_000a34f0.c wcc386@10.6 -4r -ot -s -fpi\n"
PHASE6_FORMS = (("check",), ("check", "--sweep"), ("asm",), ("asm", hooks.ATTEMPT_NAME_SLOT),
                ("context",))  # fmt: skip


@pytest.fixture
def view(repo: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`repo` plus the driver's D-24 view of HEAD under <attempt dir>/view (src/, include/,
    config/ with cflags.txt and the CSVs) and the view env set: the view unit differs from
    src/'s, so a test can tell which one was read."""
    top = repo / "view"
    unit = top / "src" / "ufo2p" / "u_000a34f0.c"
    unit.parent.mkdir(parents=True)
    unit.write_bytes(VIEW_TEXT)
    (top / "include").mkdir()
    write_functions_csv(top / "config" / "ufo2p" / "functions.csv", CHECK_ROWS, "UFO2P.EXE")
    (top / "config" / "cflags.txt").write_text(VIEW_CFLAGS, encoding="utf-8")
    monkeypatch.setenv(hooks.UNIT_FILE_ENV, str(unit))
    monkeypatch.setenv(hooks.PROPOSALS_ENV, str(repo / "proposals.jsonl"))
    return top


def _rel(path: Path) -> str:
    return path.relative_to(attempt.ROOTS.repo.resolve()).as_posix()


def test_view_mode_argv(view: Path, monkeypatch):
    """D-24 P7: with REVERSEAPOC_UNIT_FILE set, the container check is rooted in the view: the
    five root flags, each a repo-relative POSIX path under <attempt dir>/view/, then --json;
    a sweep still appends --sweep <function>."""
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 0
    roots = ("--src", _rel(view / "src"), "--config", _rel(view / "config"),
             "--cflags", _rel(view / "config" / "cflags.txt"), "--build", _rel(view / "build"),
             "--log", _rel(view / "build" / "logs" / "cc.log"))  # fmt: skip
    check_argv = ("build", "uv", "run", "--frozen", "reverseapoc", "check", CLAIM)
    assert runner.calls[0][7:] == (*check_argv, *roots, "--json")
    assert all(not Path(p).is_absolute() and "\\" not in p for p in roots[1::2])
    assert all(p.startswith(_rel(view) + "/") for p in roots[1::2])
    runner.answer = attempt.Ran(0, json.dumps(_sweep_doc()), "")
    assert _run(["attempt", "check", "--sweep"]) == 0
    assert runner.calls[1][7:] == (*check_argv, *roots, "--json", "--sweep", FUNC)


def test_view_mode_snapshot_reads_the_view_unit(view: Path, monkeypatch):
    """The check's snapshot checks/0001.c is the view unit's bytes, not src/'s."""
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 0
    snapshot = view.parent / "checks" / "0001.c"
    assert snapshot.read_bytes() == VIEW_TEXT != UNIT_TEXT
    assert _lines(view.parent)[0]["source"] == "checks/0001.c"


def test_view_mode_claim_row_comes_from_the_view_config(view: Path, monkeypatch, capsys):
    """The claim's functions.csv row is read from the view's config/, the tree the container
    check reads (--config <view>/config), not the shared one."""
    other = [dataclasses.replace(row, unit="u_000a4000") if row.name == FUNC else row
             for row in CHECK_ROWS]  # fmt: skip
    write_functions_csv(view / "config" / "ufo2p" / "functions.csv", other, "UFO2P.EXE")
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 2
    assert "u_000a4000" in capsys.readouterr().err
    assert runner.calls == []


def test_legacy_mode_argv_unchanged(repo: Path, monkeypatch):
    """Without REVERSEAPOC_UNIT_FILE the argv is exactly Phase 6's, and the snapshot is src/'s
    unit."""
    monkeypatch.delenv(hooks.UNIT_FILE_ENV, raising=False)
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 0
    assert runner.calls[0][7:] == ("build", "uv", "run", "--frozen", "reverseapoc", "check",
                                   CLAIM, "--json")  # fmt: skip
    assert (repo / "checks" / "0001.c").read_bytes() == UNIT_TEXT


def _view_unit(view: Path) -> Path:
    return view / "src" / "ufo2p" / "u_000a34f0.c"


def _env() -> dict[str, str]:
    return dict(attempt.os.environ)


def _refused(monkeypatch, capsys, *words: str) -> None:
    """`attempt check` and `attempt check --sweep` exit 2 before any run, naming `words`."""
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    for argv in (["attempt", "check"], ["attempt", "check", "--sweep"]):
        assert _run(argv) == 2
        err = capsys.readouterr().err
        assert all(word in err for word in words), (words, err)
    assert runner.calls == []


def _place(path: Path, text: bytes = VIEW_TEXT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text)
    return path


def _given_unit_file(view: Path, where: str) -> Path:
    """A REVERSEAPOC_UNIT_FILE value that is not the claim's view unit."""
    expected = _view_unit(view)
    if where == "other-attempt":
        return _place(view.parent.parent / "attempt-2" / "view" / "src" / "ufo2p"
                      / "u_000a34f0.c")  # fmt: skip
    if where == "missing":
        expected.unlink()
        return expected
    return {
        "other-unit": lambda: _place(view / "src" / "ufo2p" / "u_000a4000.c"),
        "other-exe": lambda: _place(view / "src" / "tacp" / "u_000a34f0.c"),
        "other-case-dir": lambda: view / "SRC" / "ufo2p" / "u_000a34f0.c",
        "other-case-file": lambda: view / "src" / "ufo2p" / "U_000A34F0.c",
        "shared-src": lambda: attempt.ROOTS.src / "ufo2p" / "u_000a34f0.c",
        "view-itself": lambda: view,
    }[where]()


@pytest.mark.parametrize(
    "where",
    ["other-attempt", "other-unit", "other-exe", "other-case-dir", "other-case-file", "missing",
     "shared-src", "view-itself"],
)  # fmt: skip
def test_unit_file_must_be_the_view_unit(view: Path, monkeypatch, capsys, where):
    """T-07-31: REVERSEAPOC_UNIT_FILE must be exactly <attempt dir>/view/src/<exe>/<unit>.c of
    the claim (resolved, part by part, exact case) and exist; anything else is exit 2 naming
    the env and the expected path."""
    monkeypatch.setenv(hooks.UNIT_FILE_ENV, str(_given_unit_file(view, where)))
    with pytest.raises(attempt.AttemptError, match=hooks.UNIT_FILE_ENV):
        attempt.Claim.from_env(_env(), roots=attempt.ROOTS)
    _refused(monkeypatch, capsys, hooks.UNIT_FILE_ENV, str(_view_unit(view)))
    assert not (view.parent / "checks").exists()


def test_unit_file_relative_to_the_repository_is_accepted(view: Path, monkeypatch):
    """The driver may give the path repo-relative (as the hooks read it) or absolute."""
    monkeypatch.setenv(hooks.UNIT_FILE_ENV, _rel(_view_unit(view)))
    claim = attempt.Claim.from_env(_env(), roots=attempt.ROOTS)
    assert claim.unit_file == _view_unit(view)
    assert claim.view_root == view


@pytest.mark.parametrize("value", ["other.jsonl", "../proposals.jsonl", "notes.md",
                                   "PROPOSALS.JSONL", "view/proposals.jsonl", None])  # fmt: skip
def test_proposals_must_be_in_the_attempt_dir(view: Path, monkeypatch, capsys, value):
    """T-07-31: REVERSEAPOC_PROPOSALS must be <attempt dir>/proposals.jsonl (it need not exist
    yet); in view mode it must be set. Anything else is exit 2."""
    if value is None:
        monkeypatch.delenv(hooks.PROPOSALS_ENV)
    else:
        monkeypatch.setenv(hooks.PROPOSALS_ENV, str(view.parent / value))
    _refused(monkeypatch, capsys, hooks.PROPOSALS_ENV, str(view.parent / "proposals.jsonl"))


def test_proposals_are_checked_in_legacy_mode_too(repo: Path, monkeypatch, capsys):
    """A legacy session (no unit file) may leave REVERSEAPOC_PROPOSALS unset; set, it must be
    the attempt dir's proposals.jsonl."""
    monkeypatch.setenv(hooks.PROPOSALS_ENV, str(repo / "elsewhere.jsonl"))
    _refused(monkeypatch, capsys, hooks.PROPOSALS_ENV)
    monkeypatch.setenv(hooks.PROPOSALS_ENV, str(repo / "proposals.jsonl"))
    claim = attempt.Claim.from_env(_env(), roots=attempt.ROOTS)
    assert claim.proposals == repo / "proposals.jsonl"
    assert claim.unit_file is None


@pytest.mark.parametrize("kind", ["other", "Readability", "readability ", "", "MATCHING"])
def test_session_kind_values(view: Path, monkeypatch, capsys, kind):
    """REVERSEAPOC_SESSION_KIND: absent means matching, readability is accepted, any other
    value (empty, other case, trailing space) is exit 2 listing hooks.SESSION_KINDS, as the
    hook denies it every write."""
    env = _env()
    assert attempt.Claim.from_env(env, roots=attempt.ROOTS).kind == "matching"
    env[hooks.SESSION_KIND_ENV] = "readability"
    assert attempt.Claim.from_env(env, roots=attempt.ROOTS).kind == "readability"
    monkeypatch.setenv(hooks.SESSION_KIND_ENV, kind)
    _refused(monkeypatch, capsys, hooks.SESSION_KIND_ENV, *hooks.SESSION_KINDS)


def test_a_readability_session_needs_a_view(repo: Path, monkeypatch, capsys):
    """A readability session checks only its view (the hook denies it every write without one),
    so without REVERSEAPOC_UNIT_FILE the wrapper refuses it."""
    monkeypatch.setenv(hooks.SESSION_KIND_ENV, "readability")
    _refused(monkeypatch, capsys, hooks.UNIT_FILE_ENV, "readability")


def test_sweep_default_rule_from_view_cflags(view: Path, monkeypatch):
    """In view mode the sweep's default rule (a cell under it is no hit) is the view's
    config/cflags.txt rule for the unit, not the shared file's."""
    view_default = _cell(1, "10.6", ["-4r", "-ot", "-s", "-fpi"], 100.0)
    runner = _use(monkeypatch, FakeRunner(json.dumps(_sweep_doc(view_default))))
    assert _run(["attempt", "check", "--sweep"]) == 0
    assert _lines(view.parent)[0]["sweep_hit"] is None
    shared_default = _cell(2, "10.6", ["-4r", "-s", "-fpi"], 100.0)
    runner.answer = attempt.Ran(0, json.dumps(_sweep_doc(shared_default)), "")
    assert _run(["attempt", "check", "--sweep"]) == 0
    assert _lines(view.parent)[1]["sweep_hit"] == "wcc386@10.6 -4r -s -fpi"


def test_forms_unchanged():
    """D-15, T-07-32: views add no agent form; the roots come only from the driver's env."""
    assert hooks.ATTEMPT_FORMS == PHASE6_FORMS
    for flag in ("--src", "--config", "--cflags", "--build", "--log"):
        assert not attempt.form_allowed(["check", flag, "x"])


VIEW_MARK = "/* made-up view text of unit {unit} */\n"


def test_view_mode_context_reads_the_view_units(tree: attempt.Roots, monkeypatch, capsys):
    """In view mode `attempt context` packs the view's unit texts (this session's unit and
    HEAD's others), not the shared src/'s."""
    attempt_dir = _claim_b(tree, monkeypatch)
    src = attempt_dir / "view" / "src" / "ufo2p"
    for unit, text in ((UNIT_AB, UNIT_AB_TEXT), (UNIT_C, UNIT_C_TEXT)):
        _write(src / f"{unit}.c", text + VIEW_MARK.format(unit=unit))
    (attempt_dir / "view" / "include").mkdir()
    monkeypatch.setenv(hooks.UNIT_FILE_ENV, str(src / f"{UNIT_AB}.c"))
    monkeypatch.setenv(hooks.PROPOSALS_ENV, str(attempt_dir / "proposals.jsonl"))
    roots_read = []
    real = attempt._unit_texts
    monkeypatch.setattr(attempt, "_unit_texts",
                        lambda src, *a: roots_read.append(Path(src)) or real(src, *a))  # fmt: skip
    assert _run(["attempt", "context"]) == 0, capsys.readouterr().err
    assert VIEW_MARK.format(unit=UNIT_AB) in capsys.readouterr().out  # the claimed unit's text
    assert roots_read == [attempt_dir / "view" / "src"]  # every unit text: the view's tree


# ---- 07-14: a stage-2 hit is reported through the same sweep line ----------------------------


def test_wrapper_reports_stage2_hit(repo: Path, monkeypatch, capsys):
    """D-15: when no stage-1 cell is a hit, a perfect stage-2 cell under non-default flags is
    the sweep line's sweep_hit, still from `attempt check --sweep`."""
    near = _cell(1, "10.6", ["-4r", "-s", "-fpi"], 92.0)
    stage2_hit = _cell(31, "10.6", ["-4r", "-of+", "-s", "-fpi"], 100.0)
    stage2_miss = _cell(32, "10.6", ["-4r", "-od", "-s", "-fpi"], 80.0)
    doc = {**_sweep_doc(near), "stage2": {"from": 1, "cells": [stage2_miss, stage2_hit],
                                          "best": [31]}}  # fmt: skip
    runner = _use(monkeypatch, FakeRunner(json.dumps(doc)))
    assert _run(["attempt", "check", "--sweep"]) == 0
    (line,) = _lines(repo)
    assert line["sweep"] is True
    assert line["sweep_hit"] == "wcc386@10.6 -4r -of+ -s -fpi"
    assert "needs flags wcc386@10.6 -4r -of+ -s -fpi" in capsys.readouterr().out

    stage1_hit = _cell(7, "10.5", ["-4r", "-ox", "-s", "-fpi"], 100.0)
    runner.answer = attempt.Ran(0, json.dumps({**doc, "cells": [near, stage1_hit]}), "")
    assert _run(["attempt", "check", "--sweep"]) == 0
    assert _lines(repo)[1]["sweep_hit"] == "wcc386@10.5 -4r -ox -s -fpi"  # stage 1 first

    runner.answer = attempt.Ran(0, json.dumps({**doc, "stage2": None}), "")
    assert _run(["attempt", "check", "--sweep"]) == 0
    assert _lines(repo)[2]["sweep_hit"] is None


# ---- 07-31 (D-17, D-18, D-20): a readability session's check adds readlint on its view unit ----

NAMED = "tick_count"
READ_HEADER = """/*
 * {name}: returns the current tick count.
 * Address: UFO2P.EXE 0x000A3980
 * Evidence: call: read by the timer loop
 */
"""
DEFINITION_LINE = 10  # the line of `int <name>(void)` in _readable_text


def _readable_text(name: str) -> str:
    """A made-up view unit: OTHER still a stub, the claimed function defined under `name` with a
    D-21 header comment."""
    return ('#include "common.h"\n\nINCLUDE_ASM(func_000A34F0);\n\n' + READ_HEADER.format(name=name)
            + f"int {name}(void)\n{{\n    return 0;\n}}\n")  # fmt: skip


@pytest.fixture
def readable(view: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`view` as a readability session: REVERSEAPOC_SESSION_KIND=readability and the claimed
    function matched in the view's status.csv (readlint lints matched units only)."""
    monkeypatch.setenv(hooks.SESSION_KIND_ENV, "readability")
    row = StatusRow(0x000A3980, FUNC, "u_000a34f0", "matched", 100.0, 1, "ab" * 32, "2026-10-30")
    write_status(status_path(view / "config", "ufo2p"), [row])
    return view


def _readable_unit(view: Path, name: str, *, renamed: bool) -> None:
    """Write the view unit with the claimed function named `name`; `renamed` also gives it that
    name in the view's symbols.csv (the naming state readlint reads)."""
    _view_unit(view).write_bytes(_readable_text(name).encode("utf-8"))
    if renamed:
        write_symbols_csv(view / "config" / "ufo2p" / "symbols.csv",
                          [SymbolRow(0x000A3980, f"{name}_", "func")], "UFO2P.EXE")  # fmt: skip


def test_readability_check_runs_readlint(readable: Path, monkeypatch, capsys):
    """D-17, D-20: the container check passes, the view unit keeps one RL01 placeholder: the
    summary shows the check OK, `readlint: 1 violation` with rule, line and message, and the
    verdict line is not OK (exit 1)."""
    _readable_unit(readable, FUNC, renamed=False)
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 1
    out = capsys.readouterr().out
    head = out.splitlines()[0]
    assert "exit 1 FAILED" in head and "OK" not in head
    assert "  check: OK" in out
    assert "  readlint: 1 violation," in out
    assert (f"src/ufo2p/u_000a34f0.c:{DEFINITION_LINE}: RL01 {FUNC} is a placeholder name"
            in out)  # fmt: skip


def test_readability_clean(readable: Path, monkeypatch, capsys):
    """DEC-04 empty: a view unit with no violation prints `readlint: clean`; with the check OK
    the verdict is OK (exit 0)."""
    _readable_unit(readable, NAMED, renamed=True)
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 0
    out = capsys.readouterr().out
    assert "exit 0 OK" in out.splitlines()[0]
    assert "  readlint: clean" in out


def test_readability_check_failure_wins_over_a_clean_lint(readable: Path, monkeypatch, capsys):
    """Both must pass: a clean unit whose container check fails is exit 1, and readlint is still
    reported so the agent sees both halves."""
    _readable_unit(readable, NAMED, renamed=True)
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=False, percent=87.5)), returncode=1))
    assert _run(["attempt", "check"]) == 1
    out = capsys.readouterr().out
    assert "exit 1 FAILED" in out.splitlines()[0]
    assert "  check: FAILED" in out and "  readlint: clean" in out


def test_readability_check_needs_every_function(readable: Path, monkeypatch, capsys):
    """D-17: a readability edit must leave every defined function at objdiff 100%, not just the
    claimed one: another function of the unit below 100% fails the check half."""
    _readable_unit(readable, NAMED, renamed=True)
    doc = _check_doc(ok=True)
    other = {**doc["functions"][0], "name": OTHER, "va": "0x000A34F0", "objdiff_percent": 90.0}
    doc["functions"].append(other)
    _use(monkeypatch, FakeRunner(json.dumps(doc)))
    assert _run(["attempt", "check"]) == 1
    assert "  check: FAILED" in capsys.readouterr().out


def test_matching_check_unchanged(view: Path, monkeypatch, capsys):
    """A matching session's check prints exactly the Phase 6 summary: no readlint run, no
    readlint line, the Phase 6 verdict, even over a unit readlint would fail."""
    _readable_unit(view, FUNC, renamed=False)

    def boom(*_args, **_kwargs):
        raise AssertionError("readlint ran in a matching session")

    monkeypatch.setattr(attempt, "run_readlint", boom, raising=False)
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 0
    out = capsys.readouterr().out
    assert "readlint" not in out
    assert out.splitlines()[0].endswith(
        "exit 0 OK: the claimed function matches and its unit passes check")
    assert "  check:" not in out


def test_checks_line_has_readlint_counts(readable: Path, monkeypatch):
    """The checks.jsonl line of a readability check carries readlint's violation and waiver
    counts next to the check fields; a matching line and a sweep line carry null."""
    _readable_unit(readable, FUNC, renamed=False)
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 1
    first = _lines(readable.parent)[0]
    assert (first["readlint_violations"], first["readlint_waivers"]) == (1, 0)
    assert (first["exit"], first["best_percent"], first["splice_ok"]) == (1, 100.0, True)
    runner.answer = attempt.Ran(0, json.dumps(_sweep_doc()), "")
    assert _run(["attempt", "check", "--sweep"]) == 0
    sweep = _lines(readable.parent)[1]
    assert (sweep["readlint_violations"], sweep["readlint_waivers"]) == (None, None)
    monkeypatch.delenv(hooks.SESSION_KIND_ENV)
    runner.answer = attempt.Ran(0, json.dumps(_check_doc(ok=True)), "")
    assert _run(["attempt", "check"]) == 0
    matching = _lines(readable.parent)[2]
    assert (matching["readlint_violations"], matching["readlint_waivers"]) == (None, None)


def test_checks_line_counts_waivers(readable: Path, monkeypatch):
    """A tagged `/* lit: */` waiver readlint accepted is counted on the line."""
    text = _readable_text(NAMED).replace("return 0;", "return 36; /* lit: made-up tick rate */")
    _view_unit(readable).write_bytes(text.encode("utf-8"))
    write_symbols_csv(readable / "config" / "ufo2p" / "symbols.csv",
                      [SymbolRow(0x000A3980, f"{NAMED}_", "func")], "UFO2P.EXE")  # fmt: skip
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 0
    line = _lines(readable.parent)[0]
    assert (line["readlint_violations"], line["readlint_waivers"]) == (0, 1)


def test_readlint_tool_error(readable: Path, monkeypatch, capsys):
    """A view unit with `#ifdef` makes readlint a tool error (its exit 2): the line is a tool line
    (exit 2, readlint counts null), the summary names the error, and the check budget advances
    once (one reserved snapshot per run)."""
    text = _readable_text(NAMED) + "#ifdef MADE_UP\nint x;\n#endif\n"
    _view_unit(readable).write_bytes(text.encode("utf-8"))
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 2
    out = capsys.readouterr().out
    head = out.splitlines()[0]
    assert "attempt check 1/25" in head and "(24 left)" in head and "exit 2 TOOL ERROR" in head
    assert "  readlint: TOOL ERROR:" in out and "#ifdef" in out
    (line,) = _lines(readable.parent)
    assert (line["n"], line["exit"]) == (1, 2)
    assert (line["readlint_violations"], line["readlint_waivers"]) == (None, None)
    assert sorted(p.name for p in (readable.parent / "checks").iterdir()) == ["0001.c", "0001.json"]
    assert _run(["attempt", "check"]) == 2
    assert _lines(readable.parent)[1]["n"] == 2


def test_readlint_unchecked_unit_is_a_tool_error(readable: Path, monkeypatch, capsys):
    """Fail closed: a unit readlint skips (not matched in the view's status.csv) never passes
    unlinted; it is a tool line naming why."""
    _readable_unit(readable, NAMED, renamed=True)
    write_status(status_path(readable / "config", "ufo2p"), [])
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 2
    assert "readlint checked no file" in capsys.readouterr().out


def test_readability_forms_unchanged(readable: Path, monkeypatch, capsys):
    """T-07-92: a readability session gets no new command: ATTEMPT_FORMS is still the five
    Phase 6 forms and a readlint argument is refused before any run."""
    assert hooks.ATTEMPT_FORMS == PHASE6_FORMS
    runner = _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    for extra in (["--readlint"], ["readlint"], ["check", "--units", CLAIM]):
        assert _run(["attempt", *extra]) == 2
    assert runner.calls == []


def test_check_log_line_positional_construction():
    """Ruling F11: the two readlint fields come after `source` with default None, so a
    nine-argument positional CheckLogLine (tests/test_skill.py) still builds."""
    line = attempt.CheckLogLine(1, 0, False, 100.0, True, True, True, None, "checks/0001.c")
    assert (line.readlint_violations, line.readlint_waivers) == (None, None)
    names = [f.name for f in dataclasses.fields(attempt.CheckLogLine)]
    assert names[-3:] == ["source", "readlint_violations", "readlint_waivers"]


# ---- ruling F18: an RL01 hit that the session's own valid rename proposal covers ----


def _propose(view: Path, *lines: dict) -> None:
    text = "".join(json.dumps(line) + "\n" for line in lines)
    (view.parent / "proposals.jsonl").write_text(text, encoding="utf-8")


def _rename(name: str, *, kind: str = "func", address: str = "0x000A3980") -> dict:
    return {"op": "rename", "exe": "ufo2p", "kind": kind, "address": address, "name": name,
            "evidence": "call: made-up evidence for the test"}  # fmt: skip


def test_pending_rename_does_not_fail_the_verdict(readable: Path, monkeypatch, capsys):
    """F18: names change only through proposals the driver applies after the session, so an
    RL01 hit on a placeholder the session's own valid rename proposal covers is reported as a
    pending rename and does not fail the verdict (the driver lints again at landing)."""
    _readable_unit(readable, FUNC, renamed=False)
    _propose(readable, _rename(NAMED))
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 0
    out = capsys.readouterr().out
    assert "exit 0 OK" in out.splitlines()[0]
    assert "1 pending rename" in out
    assert f"pending rename: src/ufo2p/u_000a34f0.c:{DEFINITION_LINE}: {FUNC} -> {NAMED}" in out
    line = _lines(readable.parent)[0]
    assert (line["exit"], line["readlint_violations"]) == (0, 0)


@pytest.mark.parametrize(("proposal", "refused"), [
    (_rename("int"), "keyword"),  # not a name the driver may give
    (_rename("func_000A34F0"), "placeholder-shaped"),
    (_rename(NAMED, address="0x000A34F0"), None),  # another row: not this hit's
    (_rename(NAMED, kind="data"), None),  # a data rename: not this func hit's
])  # fmt: skip
def test_invalid_rename_keeps_the_violation(readable: Path, monkeypatch, capsys, proposal,
                                            refused):  # fmt: skip
    """F18: only a valid proposal for that very row covers an RL01 hit; an invalid one for it is
    named as refused, and the hit still fails the verdict."""
    _readable_unit(readable, FUNC, renamed=False)
    _propose(readable, proposal)
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 1
    out = capsys.readouterr().out
    assert "pending rename:" not in out
    if refused is None:
        assert "rename proposal refused" not in out
    else:
        assert "rename proposal refused:" in out and refused in out
    assert _lines(readable.parent)[0]["readlint_violations"] == 1


def test_a_data_placeholder_rename_is_pending(readable: Path, monkeypatch, capsys):
    """F18 for data: an RL01 hit on a D_ placeholder that a valid data rename covers is pending
    (the host does not read the EXE's data objects; the driver checks them at landing)."""
    text = _readable_text(NAMED).replace("return 0;", "return D_00200010;")
    _view_unit(readable).write_bytes(("extern int D_00200010;\n" + text).encode("utf-8"))
    write_symbols_csv(readable / "config" / "ufo2p" / "symbols.csv",
                      [SymbolRow(0x000A3980, f"{NAMED}_", "func")], "UFO2P.EXE")  # fmt: skip
    _propose(readable, _rename("g_ticks", kind="data", address="0x00200010"))
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 0
    out = capsys.readouterr().out
    assert "2 pending renames" in out and "D_00200010 -> g_ticks" in out


def test_unreadable_proposals_count_no_pending_rename(readable: Path, monkeypatch, capsys):
    """F18, fail closed: a proposals.jsonl that does not parse covers nothing; the summary says
    so and the hit fails the verdict."""
    _readable_unit(readable, FUNC, renamed=False)
    (readable.parent / "proposals.jsonl").write_text("not json\n", encoding="utf-8")
    _use(monkeypatch, FakeRunner(json.dumps(_check_doc(ok=True))))
    assert _run(["attempt", "check"]) == 1
    assert "proposals.jsonl" in capsys.readouterr().out
