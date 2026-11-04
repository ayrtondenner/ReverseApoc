"""lift.py against the real EXEs and the real Watcom 10.6, end to end through the judge.

The pin: for every row of 07.1-SAMPLE.csv plus the two rows that crashed the spike's lifter, the
moved lifter and the spike's give the same text, or the same exception type and message. Text is
compared in memory, and only addresses reach an assertion.

These tests skip as tests/test_batch_real.py does (orig/, capstone, a compiler runner, every Watcom
version config/cflags.txt names). They write only under build/test-lift/ (the compiler refuses
objects outside the repository, so pytest's tmp_path cannot be used) and assert on addresses,
counts and booleans. No C and no game byte is in this file.
"""

from __future__ import annotations

import csv
import importlib
import importlib.util
import shutil
import sys
from pathlib import Path

from conftest import REPO_ROOT, WATCOM_DIR
from reverseapoc import batch
from reverseapoc.check import ExeInputs
from test_batch_real import _require

BUILD_ROOT = REPO_ROOT / "build" / "test-lift"
SPIKE = REPO_ROOT / ".planning" / "spikes" / "010-deterministic-matching"
SAMPLE = REPO_ROOT / ".planning" / "phases" / "07.1-matching-tooling" / "07.1-SAMPLE.csv"
CRASH_ROWS = (("ufo2p", 0x00010940), ("tacp", 0x00010EE0))
JUDGED = ("ufo2p", 0x00048860)  # matched, and judge-exact from the lifter at point 0


def _lifter():
    return importlib.import_module("reverseapoc.lift")


def _fresh(*parts: str) -> Path:
    path = BUILD_ROOT.joinpath(*parts)
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


def _spike_lifter(monkeypatch):
    """The spike's own file under its own name; it reads `common` from its directory."""
    monkeypatch.syspath_prepend(str(SPIKE))
    spec = importlib.util.spec_from_file_location("spike_lift", SPIKE / "lift.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "spike_lift", module)
    spec.loader.exec_module(module)
    return module


def _pinned_rows() -> list[tuple[str, int]]:
    with SAMPLE.open(newline="", encoding="ascii") as fh:
        rows = [(row["exe"], int(row["address"], 16)) for row in csv.DictReader(fh)]
    return rows + list(CRASH_ROWS)


def _outcome(module, exe: ExeInputs, start: int, sigs: dict) -> tuple[str, str]:
    """(exception type name, message), or ("", text) for a row that lifted."""
    try:
        return "", module.lift_row(exe, start, sigs)
    except Exception as exc:  # a crash is half of what the pin compares
        return type(exc).__name__, str(exc)


def test_moved_lifter_equals_the_spike(monkeypatch):
    _require()
    moved = _lifter()
    spike = _spike_lifter(monkeypatch)
    exes = {stem: batch.load_exe_inputs(stem) for stem in ("ufo2p", "tacp")}
    for stem in exes:  # both sides read one census
        name = f"result-used-{stem}.json"
        assert (moved.CACHE_DIR / name).read_bytes() == (
            REPO_ROOT / "build" / "spike-010" / name
        ).read_bytes()
    moved_sigs = {stem: {} for stem in exes}
    spike_sigs = {stem: {} for stem in exes}
    rows = _pinned_rows()
    differing = [
        f"{stem} 0x{start:08X}"
        for stem, start in rows
        if _outcome(moved, exes[stem], start, moved_sigs[stem])
        != _outcome(spike, exes[stem], start, spike_sigs[stem])
    ]
    assert len(rows) == 122
    assert differing == []


def test_the_lifter_reaches_the_judge():
    rules = _require()
    stem, start = JUDGED
    exe = batch.load_exe_inputs(stem)
    row = batch.row_at(exe, start)
    text = _lifter().lift_row(exe, start)
    cells = [(batch.COMMITTED_CELL, batch.committed_rule(rules, stem, row.unit))]
    jobs = batch.write_cell_jobs(_fresh("judge"), text, exe.flat[row.start : row.end], start, cells)
    (compiled,) = batch.compile_batch(jobs, 1, watcom_dir=WATCOM_DIR).compiled
    assert compiled.ok
    assert batch.judge(exe, compiled.job.obj, start).exact
