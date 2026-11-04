"""`reverseapoc search` against the real EXE and the real Watcom 10.6: a shuffled match comes back.

TARGET's declaration order decides its bytes (RESEARCH: 16 of 22 orders stay exact). The test
reads the committed unit from src/ at run time, shuffles the declarations of TARGET with a fixed
seed until batch.judge says not exact, and asserts that search.run_search finds an exact variant.
The control proves the committed text is exact on this path, so it is the shuffle that broke it.

D-26's acceptance rule is proven by the stubbed test_statement_variant tests in test_search.py: a
restored declaration order need not touch the statement axis.

These tests skip as tests/test_batch_real.py does (orig/, capstone, a compiler runner, every Watcom
version config/cflags.txt names). They write only under build/test-search/ (the compiler refuses
objects outside the repository, so pytest's tmp_path cannot be used) and assert on addresses,
counts and booleans. No C and no game byte is in this file.
"""

from __future__ import annotations

import random
import shutil
from pathlib import Path

import pytest

from conftest import ORIG_DIR, REPO_ROOT, WATCOM_DIR
from reverseapoc import batch, search
from reverseapoc.cflags import Rule
from reverseapoc.check import ExeInputs
from reverseapoc.functions import FunctionRow
from test_batch_real import _require

TARGET = ("UFO2P.EXE", 0x0005FBD0, "u_0005f750")
SHUFFLE_SEED = 20261103
SHUFFLES = 64
BUILD_ROOT = REPO_ROOT / "build" / "test-search"


def _judged(exe: ExeInputs, row: FunctionRow, text: str, rule: Rule, out: Path) -> batch.Verdict:
    """batch.judge of `text` under `rule`, on the path search itself takes."""
    cells = [(batch.COMMITTED_CELL, rule)]
    jobs = batch.write_cell_jobs(out, text, exe.flat[row.start : row.end], row.start, cells)
    (compiled,) = batch.compile_batch(jobs, 1, watcom_dir=WATCOM_DIR).compiled
    assert compiled.ok, compiled.output
    return batch.judge(exe, compiled.job.obj, row.start)


def _shuffled(text: str, name: str, rng: random.Random) -> str:
    """`text` with the declarations of `name` in a random order."""
    lines = text.split("\n")
    at = search.declarations(text, search.function_span(text, name))
    assert len(at) >= 2
    for n, line in zip(at, rng.sample([lines[n] for n in at], len(at)), strict=True):
        lines[n] = line
    return "\n".join(lines)


def _broken(exe: ExeInputs, row: FunctionRow, text: str, rule: Rule) -> str:
    """The first seeded shuffle of `text` that batch.judge says is not exact."""
    rng = random.Random(SHUFFLE_SEED)
    name = exe.symbols.c_name(row.start)
    for n in range(SHUFFLES):
        shuffled = _shuffled(text, name, rng)
        if not _judged(exe, row, shuffled, rule, BUILD_ROOT / "shuffled" / f"{n:02d}").exact:
            return shuffled
    pytest.fail(f"{SHUFFLES} shuffles of {name} all stayed exact")


def test_search_restores_a_shuffled_match(monkeypatch):
    rules = _require()
    name, start, unit = TARGET
    exe = batch.load_exe_inputs(name, orig_dir=ORIG_DIR)
    row = batch.row_at(exe, start)
    assert row.unit == unit
    rule = batch.committed_rule(rules, exe.stem, unit)
    shutil.rmtree(BUILD_ROOT, ignore_errors=True)
    text = batch.read_ascii(REPO_ROOT / "src" / exe.stem / f"{unit}.c")
    assert _judged(exe, row, text, rule, BUILD_ROOT / "control").exact is True

    shuffled = _broken(exe, row, text, rule)
    monkeypatch.setattr(search, "OUT", BUILD_ROOT / "search")
    result = search.run_search(exe, row, shuffled, rules, watcom_dir=WATCOM_DIR)

    assert result.exact is True
    assert "declaration" in result.axes
    assert result.compiles <= search.BUDGET
    assert result.best.is_relative_to(BUILD_ROOT)
    assert result.slots.frame_ours == result.slots.frame_theirs
    assert result.slots.bijection is True
