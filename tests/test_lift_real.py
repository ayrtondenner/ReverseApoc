"""lift.py against the real EXEs and the real Watcom 10.6, end to end through the judge.

These tests skip as tests/test_batch_real.py does (orig/, capstone, a compiler runner, every Watcom
version config/cflags.txt names). They write only under build/test-lift/ (the compiler refuses
objects outside the repository, so pytest's tmp_path cannot be used) and assert on addresses,
counts and booleans. No C and no game byte is in this file.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from conftest import REPO_ROOT, WATCOM_DIR
from reverseapoc import batch, lift
from test_batch_real import _require

BUILD_ROOT = REPO_ROOT / "build" / "test-lift"
JUDGED = ("ufo2p", 0x00048860)  # matched, and judge-exact from the lifter at point 0


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
