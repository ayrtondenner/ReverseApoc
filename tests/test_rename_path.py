"""The linker-name path of a rename (D-19, D-29), pinned on synthetic inputs: symbols.csv renames
func_00010010 to `Foo_`, and the target cut, check's pairing and relocation check, and
objdiff.json all follow it (gate's status row under the new name: tests/test_gate.py).

objdiff pairs a target symbol with a base symbol by name. The target ELF names a row by
SymbolTable.linker_name and our object exports the public the C defines (`Foo` -> `Foo_`), so
both sides carry `Foo_` and objdiff.json itself holds no symbol name. Every byte, name and
address here is made up (tests/relocpair.py)."""

from __future__ import annotations

import dataclasses
import json
from types import SimpleNamespace

import configure
from elfread import read_elf
from relocpair import (
    CALL_FIELD,
    CALLEES,
    CODE_BASE,
    DATA_RANGES,
    GOOD_ORIGINAL,
    GOOD_OURS,
    GOOD_ROW,
    LOAD_FIELD,
    absolute,
    call,
    le_off32,
    original,
    our_module,
    our_segment,
)
from reverseapoc import check
from reverseapoc.elf import R_386_PC32, STB_GLOBAL, STT_FUNC
from reverseapoc.functions import SymbolRow, game_name, write_symbols_csv
from reverseapoc.omf2elf import convert
from reverseapoc.relocs import check_function
from reverseapoc.symbols import SymbolTable
from reverseapoc.target import build_target
from test_configure import FOO_DEFINITION, UNIT_SOURCE, _split_tree

RENAMED = 0x10010  # func_00010010, renamed by symbols.csv
NEW = "Foo_"  # its linker name after the rename; the C defines Foo
OLD = game_name(RENAMED) + "_"  # func_00010010_, its placeholder linker name before
# xor eax,eax; inc eax (x5); ret: no trailing filler, so omf2elf sizes the public 8 bytes.
CALLEE_BYTES = bytes.fromhex("31c0" "4040404040" "c3")  # fmt: skip
CALLEE = dataclasses.replace(CALLEES[0], end=RENAMED + len(CALLEE_BYTES), unit="u_00010010")
ROWS = [GOOD_ROW, CALLEE, CALLEES[1]]  # GOOD_ROW (another unit) calls the renamed row
FOO_SOURCE = "int Foo(void)\n{\n    return 5;\n}\n"


def renamed_table() -> SymbolTable:
    return SymbolTable.build(ROWS, [SymbolRow(RENAMED, NEW, "func")], data_ranges=DATA_RANGES)


def renamed_original():
    """The LE: GOOD_ORIGINAL at 0x10000 (calls 0x10010, loads 0x20004), CALLEE_BYTES at
    0x10010."""
    return original({CODE_BASE: GOOD_ORIGINAL, RENAMED: CALLEE_BYTES},
                    page1=le_off32(LOAD_FIELD, 0x4))  # fmt: skip


def function_names(symbols) -> set[str]:
    """The defined STT_FUNC symbols of an ELF view or an omf2elf ElfObject."""
    return {s.name for s in symbols
            if s.type == STT_FUNC and getattr(s, "section", None) is not None}  # fmt: skip


# ---- symbols.csv -> the target cut ---------------------------------------------------------


def test_target_cut_uses_new_name():
    """The target ELF of the renamed row's unit defines it as `Foo_`; a caller's cut relocates
    its call against `Foo_`; the old placeholder appears nowhere."""
    orig = renamed_original()
    own = read_elf(build_target(orig.le, [CALLEE], renamed_table()).data)
    foo = own.symbol(NEW)
    assert (foo.bind, foo.type, foo.size) == (STB_GLOBAL, STT_FUNC, len(CALLEE_BYTES))
    caller = read_elf(build_target(orig.le, [GOOD_ROW], renamed_table()).data)
    relocs = caller.relocs(caller.symbol(game_name(CODE_BASE) + "_").section_index)
    assert [(r.offset, r.type, r.symbol) for r in relocs if r.type == R_386_PC32] == [
        (CALL_FIELD - CODE_BASE, R_386_PC32, NEW)
    ]
    assert caller.symbol(NEW).section is None  # an extern of the caller's unit
    for view in (own, caller):
        assert OLD not in {s.name for s in view.symbols}


def test_target_and_base_name_the_renamed_function_alike():
    """objdiff pairs by name: the target cut and our converted object (the base) both define
    `Foo_` and nothing else."""
    orig = renamed_original()
    target = read_elf(build_target(orig.le, [CALLEE], renamed_table()).data)
    base = convert(our_module(CALLEE_BYTES, publics=((NEW, 0),)))
    assert function_names(target.symbols) == function_names(base.symbols) == {NEW}


# ---- check's pairing ----------------------------------------------------------------------


def exe_inputs(orig) -> SimpleNamespace:
    """The part of check.ExeInputs checked_functions reads."""
    return SimpleNamespace(flat=orig.flat, fixups=tuple(orig.fixups), symbols=renamed_table())


def test_check_pairs_renamed_public():
    """Our object exporting `Foo_` pairs with the renamed row and passes its relocation check
    and the unit's account; one still exporting `func_00010010_` pairs with nothing, and the
    account names both the unexported row and the stray public."""
    orig = renamed_original()
    exe = exe_inputs(orig)
    good = our_module(CALLEE_BYTES, publics=((NEW, 0),))
    ((defined, reloc),) = check.checked_functions(good, [CALLEE], exe)
    assert (defined.row, defined.symbol) == (CALLEE, NEW)
    assert reloc.ok, reloc.problems
    account = check.account_unit(good, [CALLEE], exe.symbols, FOO_SOURCE)
    assert account.problems == () and [d.row for d in account.defined] == [CALLEE]

    stale = our_module(CALLEE_BYTES, publics=((OLD, 0),))
    assert check.checked_functions(stale, [CALLEE], exe) == []
    account = check.account_unit(stale, [CALLEE], exe.symbols, FOO_SOURCE)
    assert account.defined == ()
    reasons = {(p.name, p.va): p.reason for p in account.problems}
    assert NEW in reasons[(CALLEE.name, RENAMED)]
    assert OLD in reasons[(OLD, None)]


# ---- the relocation check of a caller ------------------------------------------------------


def caller_check(callee: str):
    orig = renamed_original()
    segment = our_segment(GOOD_OURS, [call(1, 1), absolute(6, 2)], [callee, "_D_00020004"])
    return check_function(segment, off=0, size=len(GOOD_OURS), row=GOOD_ROW, flat=orig.flat,
                          fixups=orig.fixups, symbols=renamed_table(), own_publics=())  # fmt: skip


def test_stale_caller_fails_relocation():
    """D-29 point 4: a caller in another unit still calling `func_00010010_` fails its
    relocation check after the rename, naming the field and the new name; rewritten to call
    `Foo_`, it passes."""
    stale = caller_check(OLD)
    assert not stale.ok
    (problem,) = stale.problems
    assert problem.startswith(f"0x{CALL_FIELD:08X}: ")
    assert OLD in problem and NEW in problem
    rewritten = caller_check(NEW)
    assert rewritten.ok, rewritten.problems


# ---- objdiff.json --------------------------------------------------------------------------


def objdiff_text(root, source: str, *, rename: bool) -> str:
    root.mkdir()
    argv = _split_tree(root, source=source)
    if rename:
        write_symbols_csv(root / "config" / "ufo2p" / "symbols.csv",
                          [SymbolRow(RENAMED, NEW, "func")], "UFO2P.EXE")  # fmt: skip
    assert configure.main(argv) == 0
    return (root / "objdiff.json").read_text(encoding="utf-8")


def test_objdiff_json_has_no_symbol_names(tmp_path):
    """configure writes units and paths only: objdiff.json is the same before and after the
    rename, and names no function, so objdiff's pairing follows the two ELF objects alone."""
    before = objdiff_text(tmp_path / "before", UNIT_SOURCE, rename=False)
    renamed_source = "INCLUDE_ASM(func_00010000);\n" + FOO_DEFINITION
    after = objdiff_text(tmp_path / "after", renamed_source, rename=True)
    assert after == before
    for name in ("Foo", "func_"):
        assert name not in after
    for unit in json.loads(after)["units"]:
        assert set(unit) <= {"name", "target_path", "base_path", "metadata"}
        assert set(unit["metadata"]) <= {"source_path", "progress_categories"}
