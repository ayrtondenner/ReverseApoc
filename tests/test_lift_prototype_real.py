"""One argument count per callee against the real wcc386 10.6: no draft trips E1151.

E1151 ("Parameter count does not agree with previous definition") is a call whose argument count
differs from the declaration in scope. Each stub row of test_lift.ONE_COUNT_ROWS calls one callee
from sites whose own evidence disagrees; its draft must compile under the `*` rule of
config/cflags.txt with no E1151. These tests skip without capstone, a compiler runner or an
installed Watcom 10.6 the gate accepts. They write only under build/test-lift-prototype/ (the
compiler refuses objects outside the repository, so pytest's tmp_path cannot be used). The rows
are hand-encoded: no game byte and no orig/ file is read here.
"""

from __future__ import annotations

import shutil

import pytest

from conftest import REPO_ROOT, WATCOM_DIR, requires_capstone, requires_runner, requires_version
from reverseapoc import batch, cflags, lift
from reverseapoc.compiler import CompilerError, check_gate
from test_lift import ONE_COUNT_ROWS, VA, clear_caches, one_count_exe

BUILD_ROOT = REPO_ROOT / "build" / "test-lift-prototype"


@pytest.fixture(scope="module")
def rule() -> cflags.Rule:
    """The `*` rule of config/cflags.txt, the first rule, as batch.check_cells reads it."""
    rule = cflags.load_cflags()[0]
    requires_capstone()
    requires_runner()
    requires_version(rule.version)
    try:
        check_gate(rule.compiler, rule.version, watcom_dir=WATCOM_DIR)
    except CompilerError as exc:
        pytest.skip(f"Watcom {rule.version}: gate refused ({exc})")
    return rule


@pytest.fixture(autouse=True)
def fresh_lifter(monkeypatch, tmp_path):
    """A stub row must never read stale rows or write the real census under build/lift."""
    monkeypatch.setattr(lift, "CACHE_DIR", tmp_path)
    clear_caches()
    yield
    clear_caches()


@pytest.mark.parametrize("name", ["later_site"])
def test_one_count_draft_compiles(rule, name):
    assert name in ONE_COUNT_ROWS
    exe = one_count_exe(name)
    text = lift.lift_row(exe, VA)
    row = exe.rows[0]
    out = BUILD_ROOT / name
    shutil.rmtree(out, ignore_errors=True)
    cells = [(batch.COMMITTED_CELL, rule)]
    jobs = batch.write_cell_jobs(out, text, exe.flat[row.start : row.end], VA, cells)
    (compiled,) = batch.compile_batch(jobs, 1, watcom_dir=WATCOM_DIR).compiled
    assert compiled.ok, compiled.output
    assert "E1151" not in compiled.output, compiled.output
