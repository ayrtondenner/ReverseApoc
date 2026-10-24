"""The production pipeline on the spike 005 pair (plan 05-18): Watcom's own CMAIN386.C, read in
place from the owner's 10.6 tree and never copied, against the `__CMain` runtime row of each EXE.

check_source compiles it with `reverseapoc cc` (the `*` cflags rule), converts it with omf2elf, cuts
the target with target.py and scores it with objdiff-cli, the relocation check and the byte
compare; land() of that one function must give the manifest SHA-1. A planted wrong call target in
our object must fail the relocation check.

These tests skip unless CMAIN386.C, orig/<EXE>, a compiler runner and objdiff-cli all exist (the
main checkout's container). They write only under build/test-check/ (the compiler writes only
inside the repository) and assert on names, VAs, percentages, counts and SHA-1s, never on bytes.
"""

from __future__ import annotations

import dataclasses
import re
import shutil
from pathlib import Path

import pytest

from conftest import ORIG_DIR, REPO_ROOT, WATCOM_DIR, requires_objdiff, requires_runner
from reverseapoc import check
from reverseapoc.compiler import compile_source
from reverseapoc.land import LandedFunction, land
from reverseapoc.relocs import check_function
from reverseapoc.targets import load_manifest

CMAIN386 = WATCOM_DIR / "10.6" / "SRC" / "STARTUP" / "386" / "CMAIN386.C"
SYMBOL = "__CMain"  # the runtime row's name and its linker name
UNIT = "rt_cmain386"
MANIFEST = REPO_ROOT / "config" / "targets.toml"
CONFIG = REPO_ROOT / "config"
BUILD_ROOT = REPO_ROOT / "build" / "test-check"  # the compiler writes only inside the repository
CALLEE, PLANTED = "exit_", "main_"  # two externs CMAIN386.C calls; the plant swaps them


@pytest.fixture
def build_dir(request) -> Path:
    """A fresh build/test-check/<test name> directory for this test (removed and recreated)."""
    path = BUILD_ROOT / re.sub(r"[^A-Za-z0-9._-]", "_", request.node.name)
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


def _exe(name: str) -> check.ExeInputs:
    if not CMAIN386.is_file():
        pytest.skip(f"{CMAIN386} not found (the owner's Watcom 10.6 tree)")
    if not (ORIG_DIR / name).is_file():
        pytest.skip(f"orig/{name} not present (run uv run reverseapoc ingest)")
    requires_runner()
    requires_objdiff()
    target = check.select_exe(load_manifest(MANIFEST), name, MANIFEST)
    return check.load_exe(target, orig_dir=ORIG_DIR, manifest=MANIFEST, config_root=CONFIG)


def _row(exe: check.ExeInputs):
    (row,) = [row for row in exe.rows if row.name == SYMBOL]
    return row


def _compile(exe: check.ExeInputs, build_dir):
    """check_source on the pair, with the compiled object read back for the land step."""
    row = _row(exe)
    result = check.check_source(
        exe, UNIT, CMAIN386, [row], build_dir=build_dir, compile_fn=compile_source,
        objdiff_runner=check.default_objdiff_runner(f"{exe.stem}/{UNIT}"),
        options=check.CompileOptions(watcom_dir=WATCOM_DIR, log=build_dir / "cc.log"),
    )  # fmt: skip
    module = check.read_module(check.UnitPaths.of(build_dir, exe.stem, UNIT).obj)
    return row, result, module


@pytest.mark.parametrize("name", ["UFO2P.EXE", "TACP.EXE"])
def test_cmain386_pair_matches(name, build_dir):
    exe = _exe(name)
    row, result, module = _compile(exe, build_dir)
    assert result.compiler == "wcc386@10.6"
    assert result.problems == (), [p.format() for p in result.problems]
    assert result.target.raw_fields == () and result.target.undecoded == ()
    (fn,) = result.functions
    assert (fn.name, fn.va, fn.size) == (SYMBOL, row.start, row.end - row.start)
    assert fn.objdiff_percent == check.PERFECT
    assert fn.reloc.ok, fn.reloc.problems
    assert fn.bytes_ok and fn.differing == 0
    ((d, reloc),) = check.checked_functions(module, [row], exe)
    assert reloc.ok
    landed = land(exe.le, [LandedFunction(row, d.ours, reloc)], expected_sha1=exe.target.sha1,
                  flat=exe.flat)  # fmt: skip
    assert landed.landed == (row.start,)
    assert landed.ok, landed.format()


def test_cmain386_wrong_call_target_fails(build_dir):
    exe = _exe("UFO2P.EXE")
    row, _, module = _compile(exe, build_dir)
    assert {CALLEE, PLANTED} <= set(module.externs)
    (d,) = check.defined_functions(module, [row], exe.symbols)
    (fx,) = [fx for fx in d.segment.fixups
             if fx.target_kind == "extern" and fx.target_name == CALLEE]  # fmt: skip
    planted = dataclasses.replace(d.segment, fixups=tuple(
        dataclasses.replace(f, target_name=PLANTED) if f is fx else f for f in d.segment.fixups
    ))  # fmt: skip
    kwargs = {"off": d.off, "size": d.size, "row": row, "flat": exe.flat, "fixups": exe.fixups,
              "symbols": exe.symbols}  # fmt: skip
    assert check_function(d.segment, **kwargs).ok  # the control: the unplanted object passes
    result = check_function(planted, **kwargs)
    assert not result.ok
    field = f"0x{row.start + fx.offset - d.off:08X}"
    problems = result.problems
    assert any(p.startswith(f"{field}: ") and PLANTED in p for p in problems), problems
