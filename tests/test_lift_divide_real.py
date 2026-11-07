"""Signed divide by a power of two against the real wcc386 10.6: probe/cg_divide.c round trips.

These tests skip without capstone, a compiler runner or an installed Watcom 10.6 the gate accepts.
They write only under build/test-lift-divide/ (the compiler refuses objects outside the repository,
so pytest's tmp_path cannot be used). Each probe function's bytes are lifted from a stub row, and
the draft compiles under the same rule to the same bytes. The C is our own clean-room probe: no
game byte is read here.
"""

from __future__ import annotations

import shutil

import pytest

from conftest import REPO_ROOT, WATCOM_DIR, requires_capstone, requires_runner, requires_version
from reverseapoc import batch, cflags, lift, omf
from reverseapoc.compiler import CompilerError, check_gate
from reverseapoc.probe import PROBE_DIR
from test_lift import VA, clear_caches, stub_exe
from test_slots_real import _function

BUILD_ROOT = REPO_ROOT / "build" / "test-lift-divide"
# Each probe function, by name, and the quotient its draft must hold.
QUOTIENTS = {
    "pr_div2": " / 2",
    "pr_div4": " / 4",
    "pr_div16": " / 16",
    "pr_div8_load": " / 8",
    "pr_div2_second": " / 2",
}


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


@pytest.fixture(scope="module")
def module(rule) -> omf.Module:
    """probe/cg_divide.c compiled once under the `*` rule."""
    out = BUILD_ROOT / "probe"
    shutil.rmtree(out, ignore_errors=True)
    job = batch.Job(PROBE_DIR / "cg_divide.c", out / "cg_divide.obj", rule)
    (compiled,) = batch.compile_batch([job], 1, watcom_dir=WATCOM_DIR).compiled
    assert compiled.ok, compiled.output
    return omf.read_object(job.obj.read_bytes())


@pytest.fixture(autouse=True)
def fresh_lifter(monkeypatch, tmp_path):
    """A stub row must never read stale rows or write the real census under build/lift."""
    monkeypatch.setattr(lift, "CACHE_DIR", tmp_path)
    clear_caches()
    yield
    clear_caches()


@pytest.mark.parametrize(("name", "quotient"), QUOTIENTS.items(), ids=QUOTIENTS)
def test_a_power_of_two_draft_compiles_to_the_probe_bytes(module, rule, name, quotient):
    code = _function(module, name)
    text = lift.lift_row(stub_exe(code.hex()), VA)
    assert quotient in text
    assert lift.HOLE_MARK not in text
    out = BUILD_ROOT / name
    shutil.rmtree(out, ignore_errors=True)
    jobs = batch.write_cell_jobs(out, text, code, VA, [(batch.COMMITTED_CELL, rule)])
    (compiled,) = batch.compile_batch(jobs, 1, watcom_dir=WATCOM_DIR).compiled
    assert compiled.ok, compiled.output
    assert _function(omf.read_object(compiled.job.obj.read_bytes()), f"func_{VA:08x}") == code
