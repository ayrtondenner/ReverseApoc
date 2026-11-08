"""The lifter's C forms against the real wcc386 10.6: probe/cg_lift.c round trips.

These tests skip without capstone, a compiler runner or an installed Watcom 10.6 the gate accepts.
They write only under build/test-lift-probe/ (the compiler refuses objects outside the repository,
so pytest's tmp_path cannot be used). probe/cg_lift.c compiles once per cell; each probe
function's bytes are lifted from a stub row, and the draft compiles under the same cell back to
the same bytes. The C is our own clean-room probe: no game byte is read here.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

import pytest

from conftest import REPO_ROOT, WATCOM_DIR, requires_capstone, requires_runner, requires_version
from reverseapoc import batch, lift, omf, x86
from reverseapoc.cflags import Rule
from reverseapoc.compiler import CompilerError, check_gate
from reverseapoc.probe import PROBE_DIR
from test_lift import VA, clear_caches, stub_exe
from test_slots_real import _function

BUILD_ROOT = REPO_ROOT / "build" / "test-lift-probe"
VERSION = "10.6"
CELLS = {"plain": ("-4r", "-s", "-fpi"), "oneatx": ("-4r", "-oneatx", "-s", "-fpi")}
BOTH = tuple(CELLS)
# Each probe function and the cells it round-trips under.
CASES = {
    "pr_lift_copy_3": BOTH,
    "pr_lift_copy_5": BOTH,
    "pr_lift_copy_6": BOTH,
    "pr_lift_copy_7": BOTH,
    "pr_lift_copy_8": BOTH,
    "pr_lift_copy_9": BOTH,
    "pr_lift_copy_10": BOTH,
    "pr_lift_copy_11": BOTH,
    "pr_lift_copy_12": BOTH,
    "pr_lift_copy_16": BOTH,
    "pr_lift_copy_17": BOTH,
    "pr_lift_copy_18": BOTH,
    "pr_lift_copy_19": BOTH,
    "pr_lift_copy_20": BOTH,
    "pr_lift_copy_21": BOTH,
    "pr_lift_copy_24": BOTH,
    "pr_lift_copy_46": BOTH,
}
PAIRS = [(cell, name) for name, cells in CASES.items() for cell in cells]


@dataclass(frozen=True)
class Trip:
    code: bytes  # the probe function, its trailing filler cut off
    text: str = ""  # the draft
    error: str = ""  # why there is no draft
    compiled: batch.Compiled | None = None


def _rule(cell: str) -> Rule:
    return Rule("*", "wcc386", VERSION, CELLS[cell], 0)


def _trimmed(code: bytes) -> bytes:
    """`code` up to its trailing alignment filler."""
    insns = list(x86.decode(code, 0))
    while insns and x86.is_alignment_filler(insns[-1]):
        insns.pop()
    return code[: insns[-1].va + insns[-1].size] if insns else b""


def _leaves(code: bytes) -> bool:
    """A jump of `code` lands outside it: a folded body or a tail merged into another function."""
    return any(i.branch_target is not None and not 0 <= i.branch_target < len(code)
               for i in x86.decode(code, 0))  # fmt: skip


@pytest.fixture(scope="module")
def modules() -> dict[str, omf.Module]:
    """probe/cg_lift.c compiled once per cell, by cell name."""
    requires_capstone()
    requires_runner()
    requires_version(VERSION)
    try:
        check_gate("wcc386", VERSION, watcom_dir=WATCOM_DIR)
    except CompilerError as exc:
        pytest.skip(f"Watcom {VERSION}: gate refused ({exc})")
    shutil.rmtree(BUILD_ROOT, ignore_errors=True)
    jobs = [batch.Job(PROBE_DIR / "cg_lift.c", BUILD_ROOT / "probe" / cell / "cg_lift.obj",
                      _rule(cell))
            for cell in CELLS]  # fmt: skip
    compiled = batch.compile_batch(jobs, len(jobs), watcom_dir=WATCOM_DIR).compiled
    for one in compiled:
        assert one.ok, one.output
    return {cell: omf.read_object(one.job.obj.read_bytes())
            for cell, one in zip(CELLS, compiled, strict=True)}  # fmt: skip


def _lift(code: bytes, case_dir) -> Trip:
    """The strict draft of `code` from a stub row, with the lifter's cache under `case_dir`."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(lift, "CACHE_DIR", case_dir / "lift")
        clear_caches()
        exe = stub_exe(code.hex())
        try:
            return Trip(code, text=lift.Lifter(exe, exe.rows[0]).lift())
        except lift.Unliftable as exc:
            return Trip(code, error=f"unliftable: {exc}")
        finally:
            clear_caches()


@pytest.fixture(scope="module")
def trips(modules) -> dict[tuple[str, str], Trip]:
    """Every case lifted, and every draft compiled in one batch, by (cell, name)."""
    lifted: dict[tuple[str, str], Trip] = {}
    jobs: dict[tuple[str, str], batch.Job] = {}
    for cell, name in PAIRS:
        code = _trimmed(_function(modules[cell], name))
        if not code or _leaves(code):
            lifted[cell, name] = Trip(code)
            continue
        case_dir = BUILD_ROOT / cell / name
        lifted[cell, name] = trip = _lift(code, case_dir)
        if not trip.error:
            (jobs[cell, name],) = batch.write_cell_jobs(case_dir, trip.text, code, VA,
                                                        [(cell, _rule(cell))])  # fmt: skip
    workers = min(len(jobs), os.cpu_count() or 1) or 1
    compiled = batch.compile_batch(list(jobs.values()), workers, watcom_dir=WATCOM_DIR).compiled
    for key, one in zip(jobs, compiled, strict=True):
        lifted[key] = Trip(lifted[key].code, lifted[key].text, compiled=one)
    return lifted


@pytest.mark.parametrize(("cell", "name"), PAIRS, ids=[f"{c}-{n}" for c, n in PAIRS])
def test_a_probe_draft_compiles_to_the_probe_bytes(trips, cell, name):
    trip = trips[cell, name]
    assert trip.code, f"{name}: no code"
    assert not _leaves(trip.code), f"{name}: a jump leaves the function, so give it its own tail"
    assert not trip.error, f"{name}: {trip.error}"
    assert trip.compiled.ok, trip.compiled.output
    ours = _function(omf.read_object(trip.compiled.job.obj.read_bytes()), f"func_{VA:08x}")
    assert _trimmed(ours) == trip.code, f"{name}:\n{trip.text}"
