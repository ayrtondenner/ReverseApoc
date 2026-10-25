"""Real-compiler probes of DI-02 and DI-03 (05-REVIEW IN-02 and IN-01, D-39): C sources compiled
by the real wcc386 10.6 under the `*` cflags rule, laid into a synthetic LE built from that object.

The test writes the C source (it is in this file), compiles it under build/test-check-tables/ (the
compiler writes only inside the repository), and builds the "original" from our own object: rows
at made-up VAs, the object's bytes patched into the tests/conftest.py LE image, and one LE fixup
per fixup of ours, synthesised from the object. No game byte is read or embedded. Then
check.check_source runs omf2elf, target.py, the unit account, the relocation check and the byte
compare on it, and a planted wrong target in the LE must fail.

The relocation and byte tests skip without a compiler runner or the 10.6 tree
(REVERSEAPOC_WATCOM_DIR points a git worktree at the main checkout's tree). The objdiff layer of
each probe is its own test (orchestrator ruling F25) and also needs objdiff-cli: it runs in the
container (plan 06-16).
"""

from __future__ import annotations

import json
import re
import shutil
import struct
from pathlib import Path

import pytest

from conftest import REPO_ROOT, WATCOM_DIR, requires_objdiff, requires_runner, requires_version
from relocpair import CODE_BASE, DATA_RANGES, le_off32, original
from reverseapoc import check
from reverseapoc.compiler import compile_source
from reverseapoc.functions import FunctionRow, game_name
from reverseapoc.omf import Module, Segment
from reverseapoc.symbols import SymbolTable

BUILD_ROOT = REPO_ROOT / "build" / "test-check-tables"  # the compiler writes only in the repo
STEM = "syn"
UNIT = "u_00010100"
FIELD = struct.Struct("<i")
REL32_END = 4  # a rel32 counts from the end of its 4-byte field
TABLE_ENTRY = 4  # one jump-table entry: an off32 to a case label

# ---- DI-02: the IN-02 6-case switch -------------------------------------------------------------

SWITCH_VA = CODE_BASE + 0x140  # the function's row; its table row sits right before it
SWITCH_NAME = game_name(SWITCH_VA)
SWITCH_CASES = 6
SWITCH_SOURCE = f"""\
/* 05-REVIEW IN-02: a 6-case switch, so wcc386 emits a jump table. */
int {SWITCH_NAME}(int x)
{{
    switch (x) {{
    case 0: return 10;
    case 1: return 21;
    case 2: return 32;
    case 3: return 43;
    case 4: return 54;
    case 5: return 65;
    }}
    return 0;
}}
"""


@pytest.fixture
def build_dir(request) -> Path:
    """A fresh build/test-check-tables/<test name> directory (removed and recreated)."""
    path = BUILD_ROOT / re.sub(r"[^A-Za-z0-9._-]", "_", request.node.name)
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


def _compile(source: str, build_dir: Path) -> tuple[Path, Module]:
    """`source` compiled by the real 10.6 with the `*` rule, and its OMF module."""
    requires_runner()
    requires_version("10.6")
    src = build_dir / "probe.c"
    src.write_text(source, encoding="utf-8")
    obj = build_dir / "probe.obj"
    result = compile_source(src, obj, watcom_dir=WATCOM_DIR, log=build_dir / "cc.log",
                            stamps=build_dir / "stamps")  # fmt: skip
    assert result.ok, result.output
    return src, check.read_module(obj)


def _text(module: Module) -> Segment:
    (text,) = [seg for seg in module.segments if seg.is_code]
    return text


def _public(module: Module, name: str) -> int:
    (offset,) = [p.offset for p in module.publics if p.name == name]
    return offset


def _row(start: int, end: int, name: str, kind: str = "game") -> FunctionRow:
    return FunctionRow(start, end, name, kind, UNIT, "fixup" if kind != "game" else "call")


def _exe(rows, flat_original) -> check.ExeInputs:
    """ExeInputs over a synthetic original (relocpair.Original); only check_source's fields."""
    symbols = SymbolTable.build(rows, data_ranges=DATA_RANGES)
    return check.ExeInputs(None, STEM, flat_original.le, flat_original.flat,
                           tuple(flat_original.fixups), tuple(rows), (), symbols,
                           Path("units.csv"))  # fmt: skip


def _check(exe: check.ExeInputs, src: Path, build_dir: Path, runner) -> check.SourceCheck:
    """check_source on the probe: it compiles `src` again (the same object), then converts, cuts
    the target, accounts the unit and checks every function."""
    options = check.CompileOptions(watcom_dir=WATCOM_DIR, log=build_dir / "check.log")
    return check.check_source(exe, UNIT, src, list(exe.rows), build_dir=build_dir / "check",
                              compile_fn=compile_source, objdiff_runner=runner,
                              options=options)  # fmt: skip


def _perfect(argv) -> str:
    """Stands in for objdiff-cli on the host tests: the relocation and byte checks are the gate
    here; the real objdiff layer is test_real_*_objdiff."""
    return json.dumps({"left": {"symbols": [{"name": argv[-1], "match_percent": 100.0}]}})


def _switch(build_dir: Path):
    """The compiled switch, its rows and the LE fixup records of an original built from it."""
    src, module = _compile(SWITCH_SOURCE, build_dir)
    text = _text(module)
    head = _public(module, f"{SWITCH_NAME}_")
    entries = [fx for fx in text.fixups if fx.offset < head]
    # 05-REVIEW IN-02, observed again here: the table leads _TEXT, the public follows it.
    assert [fx.offset for fx in entries] == [TABLE_ENTRY * i for i in range(SWITCH_CASES)]
    assert head == SWITCH_CASES * TABLE_ENTRY, f"observed table size {head:#x}"
    table_va = SWITCH_VA - head
    rows = [_row(table_va, table_va + head, f"D_{table_va:08X}", "data-in-code"),
            _row(SWITCH_VA, SWITCH_VA + len(text.data) - head, SWITCH_NAME)]  # fmt: skip
    return src, module, rows, table_va


def _switch_original(module: Module, table_va: int, *, plant: int | None = None):
    """The original: our _TEXT bytes at `table_va`, and an off32 LE fixup per own-segment fixup
    of ours (the table entries and the jmp's table address). `plant` moves the target of that
    table entry to the next entry's case label."""
    text = _text(module)
    records = []
    targets = {fx.offset: FIELD.unpack_from(text.data, fx.offset)[0] for fx in text.fixups}
    for offset, target in targets.items():
        if offset == plant:
            target = targets[offset + TABLE_ENTRY]
        records.append(le_off32(table_va + offset, table_va - CODE_BASE + target, obj=1))
    return original({table_va: bytes(text.data)}, page1=b"".join(records))


def test_real_switch_probe_passes(build_dir):
    """[10.6] The IN-02 switch passes the relocation and byte checks; a planted wrong case target
    in the original's table fails, naming that entry's VA."""
    src, module, rows, table_va = _switch(build_dir)
    exe = _exe(rows, _switch_original(module, table_va))
    result = _check(exe, src, build_dir, _perfect)
    assert result.problems == (), [p.format() for p in result.problems]
    (fn,) = result.functions
    assert (fn.name, fn.va) == (SWITCH_NAME, SWITCH_VA)
    assert fn.reloc.ok, fn.reloc.problems
    assert fn.bytes_ok and fn.differing == 0

    planted = TABLE_ENTRY * 2
    exe = _exe(rows, _switch_original(module, table_va, plant=planted))
    (fn,) = _check(exe, src, build_dir, _perfect).functions
    assert not fn.reloc.ok
    field = f"0x{table_va + planted:08X}: "
    assert any(p.startswith(field) for p in fn.reloc.problems), fn.reloc.problems


def test_real_switch_probe_objdiff(build_dir):
    """[10.6] objdiff-cli scores the switch 100.0 against its target (container, plan 06-16)."""
    src, module, rows, table_va = _switch(build_dir)
    requires_objdiff()
    exe = _exe(rows, _switch_original(module, table_va))
    runner = check.default_objdiff_runner(f"{STEM}/{UNIT}")
    (fn,) = _check(exe, src, build_dir, runner).functions
    assert fn.objdiff_percent == check.PERFECT
