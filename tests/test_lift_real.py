"""lift.py against the real EXEs and the real Watcom 10.6, end to end through the judge.

These tests skip as tests/test_batch_real.py does (orig/, capstone, a compiler runner, every Watcom
version config/cflags.txt names). They write only under build/test-lift/ (the compiler refuses
objects outside the repository, so pytest's tmp_path cannot be used) and assert on addresses,
counts and booleans. No C and no game byte is in this file.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from conftest import REPO_ROOT, WATCOM_DIR
from reverseapoc import batch, lift
from reverseapoc.cli import main
from test_batch_real import _require

BUILD_ROOT = REPO_ROOT / "build" / "test-lift"
JUDGED = ("ufo2p", 0x00048860)  # matched, and judge-exact from the lifter at point 0
PRINTED = 0x000108E0  # a ufo2p row the lifter takes
REFUSED = 0x00075630  # a ufo2p row with a real ebp frame
HOLED = ("ufo2p", 0x00050EA0)  # refused at point 0, on a call target that is no row start


def _fresh(*parts: str) -> Path:
    path = BUILD_ROOT.joinpath(*parts)
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


def test_the_lifter_reaches_the_judge():
    rules = _require()
    stem, start = JUDGED
    exe = batch.load_exe_inputs(stem)
    row = batch.row_at(exe, start)
    text = lift.lift_row(exe, start)
    cells = [(batch.COMMITTED_CELL, batch.committed_rule(rules, stem, row.unit))]
    jobs = batch.write_cell_jobs(_fresh("judge"), text, exe.flat[row.start : row.end], start, cells)
    (compiled,) = batch.compile_batch(jobs, 1, watcom_dir=WATCOM_DIR).compiled
    assert compiled.ok
    assert batch.judge(exe, compiled.job.obj, start).exact


def test_a_hole_draft_compiles():
    rules = _require()
    stem, start = HOLED
    exe = batch.load_exe_inputs(stem)
    row = batch.row_at(exe, start)
    with pytest.raises(lift.Unliftable):
        lift.lift_row(exe, start)
    text = lift.Lifter(exe, row, holes=True).lift()
    holed = lift.HOLE_MARK in text  # a bool: no C reaches a pytest report
    assert holed
    cells = [(batch.COMMITTED_CELL, batch.committed_rule(rules, stem, row.unit))]
    jobs = batch.write_cell_jobs(_fresh("hole"), text, exe.flat[row.start : row.end], start, cells)
    (compiled,) = batch.compile_batch(jobs, 1, watcom_dir=WATCOM_DIR).compiled
    assert compiled.ok
    assert not batch.judge(exe, compiled.job.obj, start).exact


def test_lift_verb_prints_c(capsys):
    _require()
    assert main(["lift", "ufo2p", f"0x{PRINTED:08X}"]) == 0
    text = capsys.readouterr().out
    printed = "\n{\n" in text and text.endswith("}\n")  # a bool: no C reaches a pytest report
    assert printed
    assert main(["lift", "ufo2p", f"0x{REFUSED:08X}"]) == 1
    assert "frame: ebp frame" in capsys.readouterr().err
    assert main(["lift", "ufo2p", "0x00000001"]) == 2
    assert "no functions.csv row" in capsys.readouterr().err
