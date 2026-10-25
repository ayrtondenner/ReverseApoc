"""target.py: per-unit target ELF objects cut straight from a synthetic LE (SPL-08, D-13).

Every LE here is built by tests/conftest.py from made-up bytes; no game byte appears. The code
object is 0x10000..0x11800 (pages 1-2), the data object 0x20000..0x23000 (page 3)."""

from __future__ import annotations

import struct
from typing import NamedTuple

import pytest

from conftest import build_le_image, fixup_record
from elfread import read_elf
from relocpair import (
    CALLEES,
    CODE_BASE,
    Original,
    absolute,
    call,
    game_row,
    le_off32,
    original,
    our_segment,
)
from relocpair import table as reloc_table
from reverseapoc import relocs
from reverseapoc.elf import (
    R_386_32,
    R_386_PC32,
    STB_GLOBAL,
    STB_LOCAL,
    STT_FUNC,
    STT_NOTYPE,
    STT_OBJECT,
)
from reverseapoc.functions import FunctionRow, SymbolRow, data_name, game_name
from reverseapoc.land import LandedFunction, build_patch
from reverseapoc.le import LE, SRC_OFF32, SRC_PTR1632, SRC_REL32, SRC_SEL16
from reverseapoc.omf import Segment
from reverseapoc.relocs import RelocResult, check_function
from reverseapoc.symbols import SymbolTable
from reverseapoc.target import (
    RAW_BRANCH_NO_ROW,
    RAW_BRANCH_OUTSIDE,
    RAW_OFF32_NO_ROW,
    RawField,
    TargetError,
    TargetResult,
    build_target,
)

DATA_RANGES = [(0x20000, 0x23000)]  # the synthetic data object
NOP = b"\x90"


def _row(start: int, end: int, kind: str = "game", name: str | None = None) -> FunctionRow:
    if name is None:
        name = data_name(start) if kind == "data-in-code" else game_name(start)
    return FunctionRow(start, end, name, kind, "u_00010000", "call")


def _le(page1: bytes = b"", page2: bytes = b"", patches: dict[int, bytes] | None = None) -> LE:
    """A synthetic LE with these fixup records on the two code pages and these byte patches."""
    return LE(build_le_image(fixups=[page1, page2, b""], patches=patches).data)


def _table(rows: list[FunctionRow], symbols: list[SymbolRow] | None = None) -> SymbolTable:
    return SymbolTable.build(rows, symbols or [], data_ranges=DATA_RANGES)


def _section_of(view, name: str):
    """The `_TEXT` section holding the defined symbol `name` (read by section index, F10)."""
    return view.section(view.symbol(name).section_index)


def _relocs(view, name: str) -> list[tuple[int, int, str, int]]:
    """(offset, type, symbol, addend) of the section that defines `name`, by offset."""
    found = view.relocs(view.symbol(name).section_index)
    return sorted((r.offset, r.type, r.symbol, r.addend) for r in found)


def _unrelocated_bytes_match(section, start: int, flat: bytes, fields: list[int]) -> bool:
    """Every byte of `section` outside the 4-byte fields at `fields` (section offsets) equals
    load_flat(relocate=False) at the same address."""
    masked = {offset + k for offset in fields for k in range(4)}
    return all(byte == flat[start + i] for i, byte in enumerate(section.data) if i not in masked)


# A at 0x10000: mov eax,[abs32]; call rel32 B; ret; then nops up to 0x10010. B at 0x10010: ret.
# The mov's field holds the raw target_off 0x100, as wlink leaves it (Pitfall 1).
CALL_REL = 0x10010 - 0x1000A  # call at 0x10005, 5 bytes, to B
A_BYTES = (
    b"\xa1" + struct.pack("<I", 0x100) + b"\xe8" + struct.pack("<i", CALL_REL) + b"\xc3" + NOP * 5
)
TRACER_PATCHES = {0x10000: A_BYTES, 0x10010: b"\xc3"}
TRACER_FIXUPS = fixup_record(SRC_OFF32, 0x001, 2, 0x100)  # A+1 -> data 0x20100
A = _row(0x10000, 0x10010)
B = _row(0x10010, 0x10011)


def test_function_with_data_fixup_and_call():
    le = _le(TRACER_FIXUPS, patches=TRACER_PATCHES)
    result = build_target(le, [A, B], _table([A, B]))
    view = read_elf(result.data)

    assert [s.name for s in view.sections if s.name == "_TEXT"] == ["_TEXT", "_TEXT"]
    a, b = view.symbol("func_00010000_"), view.symbol("func_00010010_")
    assert (a.bind, a.type, a.size, a.value) == (STB_GLOBAL, STT_FUNC, 0x10, 0)
    assert (b.bind, b.type, b.size) == (STB_GLOBAL, STT_FUNC, 1)
    assert a.section_index != b.section_index
    assert _relocs(view, "func_00010000_") == [
        (1, R_386_32, "_D_00020100", 0),
        (6, R_386_PC32, "func_00010010_", -4),
    ]
    assert _relocs(view, "func_00010010_") == []
    flat = bytes(le.load_flat(relocate=False))
    assert _unrelocated_bytes_match(_section_of(view, "func_00010000_"), 0x10000, flat, [1, 6])
    assert _section_of(view, "func_00010010_").data == flat[0x10010:0x10011]
    assert result.raw_fields == ()


# ---- every target rule ------------------------------------------------------------------------

RET_PAD = b"\xc3" + NOP * 15  # ret, then nops: a 16-byte function body


def _cut(rows, *, unit=None, page1=b"", page2=b"", patches=None, symbols=None):
    """(le, result, view) for the unit `unit` (default: every row) of a synthetic LE."""
    le = _le(page1, page2, patches)
    result = build_target(le, unit if unit is not None else rows, _table(rows, symbols))
    return le, result, read_elf(result.data)


def _rel(dest: int, field: int) -> bytes:
    """The rel32 a branch whose field is at `field` stores to reach `dest`."""
    return struct.pack("<i", dest - (field + 4))


def test_target_inside_a_function():
    # B: mov eax, offset A+4 (off32 into A's body); call A+4 (rel32 into A's body); ret
    a, b = _row(0x10000, 0x10010), _row(0x10010, 0x10020)
    body = b"\xb8" + struct.pack("<I", 4) + b"\xe8" + _rel(0x10004, 0x10016) + RET_PAD[:6]
    _, _, view = _cut([a, b], page1=fixup_record(SRC_OFF32, 0x011, 1, 0x4),
                      patches={0x10000: RET_PAD, 0x10010: body})  # fmt: skip
    assert _relocs(view, "func_00010010_") == [
        (1, R_386_32, "func_00010000_", 4),
        (6, R_386_PC32, "func_00010000_", 0),  # -4 plus 4 bytes into A
    ]


def test_obj1_target_at_a_start():
    # A: mov eax, offset B (a function pointer to B's start); ret
    a, b = _row(0x10000, 0x10010), _row(0x10010, 0x10020)
    body = b"\xb8" + struct.pack("<I", 0x10) + RET_PAD[:11]
    _, _, view = _cut([a, b], page1=fixup_record(SRC_OFF32, 0x001, 1, 0x10),
                      patches={0x10000: body, 0x10010: RET_PAD})  # fmt: skip
    assert _relocs(view, "func_00010000_") == [(1, R_386_32, "func_00010010_", 0)]


def test_symbols_csv_name():
    # A: mov eax,[_errno]; call main_; ret. Both names come from symbols.csv (D-19)
    a, b = _row(0x10000, 0x10010), _row(0x10010, 0x10020)
    names = [SymbolRow(0x10010, "main_", "func"), SymbolRow(0x20200, "_errno", "data")]
    body = b"\xa1" + struct.pack("<I", 0x200) + b"\xe8" + _rel(0x10010, 0x10006) + RET_PAD[:6]
    _, _, view = _cut([a, b], page1=fixup_record(SRC_OFF32, 0x001, 2, 0x200),
                      patches={0x10000: body, 0x10010: RET_PAD}, symbols=names)  # fmt: skip
    assert _relocs(view, "func_00010000_") == [
        (1, R_386_32, "_errno", 0),
        (6, R_386_PC32, "main_", -4),
    ]
    main = view.symbol("main_")
    assert (main.bind, main.type, main.size) == (STB_GLOBAL, STT_FUNC, 0x10)
    assert view.symbol("_errno").section is None  # an extern of this unit


def test_runtime_target():
    # A calls the runtime row exit_, which is in no unit: an undefined GLOBAL NOTYPE extern
    a = _row(0x10000, 0x10010)
    exit_row = _row(0x10020, 0x10030, "runtime", "exit_")
    body = b"\xe8" + _rel(0x10020, 0x10001) + RET_PAD[:11]
    _, _, view = _cut([a, exit_row], unit=[a], patches={0x10000: body, 0x10020: RET_PAD})
    assert _relocs(view, "func_00010000_") == [(1, R_386_PC32, "exit_", -4)]
    ext = view.symbol("exit_")
    assert (ext.bind, ext.type, ext.section) == (STB_GLOBAL, STT_NOTYPE, None)


def test_jumps():
    # A: jz rel32 inside A; jmp rel8 out of A; nops; jmp rel32 to B; ret; nops
    a, b = _row(0x10000, 0x10020), _row(0x10020, 0x10030)
    body = (
        b"\x0f\x84" + _rel(0x1000C, 0x10002)  # jz 0x1000C: stays in A, no relocation
        + b"\xeb" + bytes([0x10022 - 0x10008])  # jmp rel8 into B: no field to relocate
        + NOP * 4
        + b"\xe9" + _rel(0x10020, 0x1000D)  # jmp rel32 to B: leaves A
        + RET_PAD[:15]
    )  # fmt: skip
    _, _, view = _cut([a, b], patches={0x10000: body, 0x10020: RET_PAD})
    assert _relocs(view, "func_00010000_") == [(0xD, R_386_PC32, "func_00010020_", -4)]


def test_straddler():
    # C spans the page boundary at 0x11000. Its mov eax,[abs32] field 0x10FFE..0x11002 is
    # listed on both pages in the file and once by le.fixups() (P3)
    c = _row(0x10FF0, 0x11010)
    page1 = fixup_record(SRC_OFF32, 0xFFE, 2, 0x40)
    page2 = fixup_record(SRC_OFF32, -2, 2, 0x40)
    patches = {0x10FF0: NOP * 13 + b"\xa1\x40\x00", 0x11000: b"\x00\x00" + RET_PAD[:14]}
    le, _, view = _cut([c], page1=page1, page2=page2, patches=patches)
    assert _relocs(view, "func_00010FF0_") == [(0xE, R_386_32, "_D_00020040", 0)]
    section = _section_of(view, "func_00010FF0_")
    assert section.data[0xE:0x12] == bytes(4)  # rewritten on both sides of the boundary
    flat = bytes(le.load_flat(relocate=False))
    assert flat[0x10FFE:0x11002] != bytes(4)  # the file's field held target_off
    assert _unrelocated_bytes_match(section, 0x10FF0, flat, [0xE])


def test_inline_data():
    # A: jmp [table + eax*4]; nop; a one-entry table at A+8 whose bytes would decode as a call
    # to nowhere; then a real call to B after the table
    a, b = _row(0x10000, 0x10020), _row(0x10020, 0x10030)
    body = (
        b"\xff\x24\x85" + struct.pack("<I", 0x8) + NOP  # jmp [0x10008 + eax*4]
        + b"\xe8\x00\x00\x00"  # the table entry -> A (its raw bytes look like a call opcode)
        + b"\xe8" + _rel(0x10020, 0x1000D)  # call B, decoded after the table
        + RET_PAD[:15]
    )  # fmt: skip
    page1 = fixup_record(SRC_OFF32, 0x003, 1, 0x8) + fixup_record(SRC_OFF32, 0x008, 1, 0x0)
    _, _, view = _cut([a, b], page1=page1, patches={0x10000: body, 0x10020: RET_PAD})
    assert _relocs(view, "func_00010000_") == [
        (3, R_386_32, "func_00010000_", 8),
        (8, R_386_32, "func_00010000_", 0),
        (0xD, R_386_PC32, "func_00010020_", -4),
    ]


def test_data_in_code_row():
    # A: jmp [D + eax*4] with two case labels in A; D: the jump table, its own data-in-code row
    a, table = _row(0x10000, 0x10010), _row(0x10010, 0x10018, "data-in-code")
    body = b"\xff\x24\x85" + struct.pack("<I", 0x10) + b"\xc3" + NOP * 2 + b"\xc3" + NOP * 5
    entries = b"\xe8\x07\x00\x00" + struct.pack("<I", 0xA)  # would decode as a call if scanned
    page1 = (
        fixup_record(SRC_OFF32, 0x003, 1, 0x10)
        + fixup_record(SRC_OFF32, 0x010, 1, 0x7)
        + fixup_record(SRC_OFF32, 0x014, 1, 0xA)
    )
    _, _, view = _cut([a, table], page1=page1, patches={0x10000: body, 0x10010: entries})
    sym = view.symbol("_D_00010010")
    assert (sym.bind, sym.type, sym.size, sym.value) == (STB_LOCAL, STT_OBJECT, 8, 0)
    assert view.section(sym.section_index).name == "_TEXT"
    assert sym.section_index != view.symbol("func_00010000_").section_index
    assert _relocs(view, "func_00010000_") == [(3, R_386_32, "_D_00010010", 0)]
    assert _relocs(view, "_D_00010010") == [
        (0, R_386_32, "func_00010000_", 7),
        (4, R_386_32, "func_00010000_", 0xA),
    ]


@pytest.mark.parametrize(
    ("kind", "size", "opcode", "name"),
    [
        (SRC_SEL16, 2, b"\x66\xb8", "sel16"),  # mov ax, seg X
        (SRC_PTR1632, 6, b"\xea", "ptr16:32"),  # jmp far ptr16:32
    ],
    ids=["sel16", "ptr16:32"],
)
def test_non_off32_field_stays_raw(kind, size, opcode, name):
    # Orchestrator ruling F11: no refusal and no relocation; the result names the site
    a = _row(0x10000, 0x10010)
    body = opcode + bytes(range(1, size + 1)) + RET_PAD[: 16 - len(opcode) - size]
    off = None if kind == SRC_SEL16 else 0x0
    record = fixup_record(kind, len(opcode), 2, off, off32=kind != SRC_SEL16)
    le, result, view = _cut([a], page1=record, patches={0x10000: body})
    flat = bytes(le.load_flat(relocate=False))
    assert _section_of(view, "func_00010000_").data == flat[0x10000:0x10010]
    assert _relocs(view, "func_00010000_") == []
    assert result.raw_fields == (RawField(0x10000 + len(opcode), name),)


def test_rel32_field_with_an_le_fixup_gets_no_pc32():
    # the call's field is an LE rel32 fixup site: the fixup owns it, so it stays raw (F11)
    a, b = _row(0x10000, 0x10010), _row(0x10010, 0x10020)
    body = b"\xe8" + _rel(0x10010, 0x10001) + RET_PAD[:11]
    record = fixup_record(SRC_REL32, 0x001, 1, 0x10)
    _, result, view = _cut([a, b], page1=record, patches={0x10000: body, 0x10010: RET_PAD})
    assert _relocs(view, "func_00010000_") == []
    assert result.raw_fields == (RawField(0x10001, "rel32"),)


def test_branch_synthesis_stops_at_an_undecodable_byte():
    # Review fix round 1 (orchestrator ruling): 0f 04 at A+1 does not decode. Decoding a
    # resynchronised guess past it could read an e8 as a call, so no PC32 is synthesized after
    # it. The bytes stay as the file has them, the off32 fixup after it still relocates (it
    # comes from the fixup table), and the VA is reported.
    a, b = _row(0x10000, 0x10020), _row(0x10020, 0x10030)
    body = (
        NOP + b"\x0f\x04" + NOP  # nop; undecodable at 0x10001; nop
        + b"\xe8" + _rel(0x10020, 0x10005)  # looks like a call to B
        + b"\xa1" + struct.pack("<I", 0x100)  # mov eax,[abs32], field 0x1000A -> data
        + RET_PAD + NOP * 2
    )  # fmt: skip
    page1 = fixup_record(SRC_OFF32, 0x00A, 2, 0x100)
    le, result, view = _cut([a, b], page1=page1, patches={0x10000: body, 0x10020: RET_PAD})
    assert _relocs(view, "func_00010000_") == [(0xA, R_386_32, "_D_00020100", 0)]
    flat = bytes(le.load_flat(relocate=False))
    assert _unrelocated_bytes_match(_section_of(view, "func_00010000_"), 0x10000, flat, [0xA])
    assert result.undecoded == (0x10001,)
    assert result.raw_fields == ()


def test_a_fully_decoded_unit_reports_nothing_undecoded():
    le = _le(TRACER_FIXUPS, patches=TRACER_PATCHES)
    assert build_target(le, [A, B], _table([A, B])).undecoded == ()


# Plan 05-18 (Rule 3, the F11 principle): the real graph has branches and off32 fixups into code
# no functions.csv row covers (split gaps D-11 leaves for later) and decoded "branches" out of
# the code object (data read as code in a runtime row). Refusing them left 18 real units
# uncuttable and `ninja` failing before any C existed. Such a field keeps its raw bytes and gets
# no relocation, and the result names it, so the unit stays cuttable (D-13) and a function
# holding one is no first-match candidate. What the relocation check does with it depends on the
# kind; the end-to-end cases at the end of this file (06-08) pin each, including the two that pass
# with bytes identical to the original.


def _assert_raw_field(body: bytes, kind: str, page1: bytes = b"") -> None:
    a = _row(0x10000, 0x10010)
    le, result, view = _cut([a], page1=page1, patches={0x10000: body})
    flat = bytes(le.load_flat(relocate=False))
    assert _section_of(view, "func_00010000_").data == flat[0x10000:0x10010]
    assert _relocs(view, "func_00010000_") == []
    assert result.raw_fields == (RawField(0x10001, kind),)


def test_a_branch_out_of_the_code_object_stays_raw():
    # a call rel32 whose destination lies in the data object is no function reference
    body = b"\xe8" + _rel(0x20100, 0x10001) + RET_PAD[:11]
    _assert_raw_field(body, "branch outside the code object")


def test_a_call_to_no_row_stays_raw():
    body = b"\xe8" + _rel(0x10400, 0x10001) + RET_PAD[:11]
    _assert_raw_field(body, "branch to no row")


def test_refuses_a_row_outside_the_code_object():
    a, data_row = _row(0x10000, 0x10010), _row(0x20000, 0x20010)
    with pytest.raises(TargetError, match="0x00020000"):
        _cut([a, data_row], patches={0x10000: RET_PAD})


def test_an_off32_target_in_no_row_stays_raw():
    # the target is in the code object, but in a gap between rows
    body = b"\xb8" + struct.pack("<I", 0x400) + RET_PAD[:11]
    _assert_raw_field(body, "off32 to no row", fixup_record(SRC_OFF32, 0x001, 1, 0x400))


@pytest.mark.parametrize("unit", ["a", "b"])
def test_refuses_a_field_split_by_a_row_boundary(unit):
    # an off32 field 0x1000E..0x10012 starts in A and ends in B: either unit would split it
    a, b = _row(0x10000, 0x10010), _row(0x10010, 0x10020)
    page1 = fixup_record(SRC_OFF32, 0x00E, 2, 0x100)
    with pytest.raises(TargetError, match="0x0001000e"):
        _cut([a, b], unit=[a] if unit == "a" else [b], page1=page1,
             patches={0x10000: RET_PAD, 0x10010: RET_PAD})  # fmt: skip


# ---- end to end: what the relocation check does with a raw field (05-REVIEW rows 18a, 18c) -----
# A target cut leaves a field raw when it names no row. What holds, per raw kind (target.py):
# - `off32 to no row`: rule 4 refuses any fixup of ours there (no name reaches a gap), and rule 5
#   refuses an object with no fixup there (the LE has one). Every object fails.
# - `branch to no row`: rule 4 refuses any fixup of ours there. A rel32 is no LE fixup, so rule 5
#   has nothing to check, and an unrelocated displacement byte-identical to the original passes.
#   wcc386 emits a fixup for every call, even to a static, so compiled C never gives that case.
# - `branch outside the code object`: a data-object destination is nameable (`_D_<va>`), so a
#   fixup of ours to it passes rule 4.
# The two passing cases are pinned below. Neither is a byte-level false pass: the landed bytes
# equal the original's, and the whole-EXE SHA-1 gate still holds. The cases cut a unit, compile
# nothing, and run check_function on objects built by tests/relocpair.py.

GAP = 0x10400  # code in no functions.csv row: a split gap (D-11)
NAMED = CALLEES[0].start  # relocpair's row func_00010010, a nameable start
FIELD_VA = CODE_BASE + 1  # the field after the one-byte opcode
EXTERN_GAP = f"{game_name(GAP)}_"
EXTERN_NAMED = f"{game_name(NAMED)}_"
NO_ROW_AT_GAP = f"{EXTERN_GAP}: no game or thunk row starts at 0x{GAP:08X}"  # SymbolError
_PLACEHOLDER_CALL = b"\xe8" + bytes(4) + b"\xc3"  # call rel32 0; ret
_PLACEHOLDER_LOAD = b"\xb8" + bytes(4) + b"\xc3"  # mov eax, 0; ret


def _call_to(dest: int) -> bytes:
    """call rel32 dest; ret, at CODE_BASE."""
    return b"\xe8" + _rel(dest, FIELD_VA) + b"\xc3"


def _load_of(dest: int) -> tuple[bytes, bytes]:
    """mov eax, offset dest; ret, at CODE_BASE, and its off32 LE fixup record."""
    body = b"\xb8" + struct.pack("<I", dest - CODE_BASE) + b"\xc3"
    return body, le_off32(FIELD_VA, dest - CODE_BASE, obj=1)


class _EndToEnd(NamedTuple):
    row: FunctionRow
    orig: Original
    cut: TargetResult
    verdict: RelocResult


def _end_to_end(original_body: bytes, page1: bytes, ours: Segment, size: int) -> _EndToEnd:
    """The target cut of the one-row unit at CODE_BASE, and check_function of `ours` against
    that row."""
    row = game_row(CODE_BASE, CODE_BASE + len(original_body))
    orig = original({CODE_BASE: original_body}, page1=page1)
    symbols = reloc_table(row)
    cut = build_target(orig.le, [row], symbols, flat=orig.flat, fixups=orig.fixups)
    verdict = check_function(ours, off=0, size=size, row=row, flat=orig.flat,
                             fixups=orig.fixups, symbols=symbols)  # fmt: skip
    return _EndToEnd(row, orig, cut, verdict)


def _landed_bytes(e2e: _EndToEnd, ours: bytes) -> bytes:
    """What land would write for the row: build_patch of our bytes under the verdict."""
    return build_patch(LandedFunction(e2e.row, ours, e2e.verdict), e2e.orig.flat)


_RAW_CASES = {
    # rule 4: the extern names no row start, so it has no address (SymbolError)
    "branch, extern at the gap": (
        _call_to(GAP), b"", _PLACEHOLDER_CALL, [call(1, 1)], [EXTERN_GAP], RAW_BRANCH_NO_ROW,
        NO_ROW_AT_GAP,
    ),
    # rule 4: a nameable start, but not the original target
    "branch, nameable start": (
        _call_to(GAP), b"", _PLACEHOLDER_CALL, [call(1, 1)], [EXTERN_NAMED], RAW_BRANCH_NO_ROW,
        f"{EXTERN_NAMED} resolves to 0x{NAMED:08X}, the original lands on 0x{GAP:08X}",
    ),
    "off32, extern at the gap": (
        *_load_of(GAP), _PLACEHOLDER_LOAD, [absolute(1, 1)], [EXTERN_GAP], RAW_OFF32_NO_ROW,
        NO_ROW_AT_GAP,
    ),
    "off32, nameable start": (
        *_load_of(GAP), _PLACEHOLDER_LOAD, [absolute(1, 1)], [EXTERN_NAMED], RAW_OFF32_NO_ROW,
        f"{EXTERN_NAMED} resolves to 0x{NAMED:08X}, the original targets 0x{GAP:08X}",
    ),
    # rule 5: our constant equals the raw field, so only reverse coverage tells them apart
    "off32, our constant": (
        *_load_of(GAP), _load_of(GAP)[0], [], [], RAW_OFF32_NO_ROW,
        "the original has an off32 LE fixup here and ours has none (a constant where the "
        "original has an address)",
    ),
}


def _run_case(case) -> tuple[_EndToEnd, str, str]:
    original_body, page1, ours, fixups, externs, kind, problem = case
    e2e = _end_to_end(original_body, page1, our_segment(ours, fixups, externs), len(ours))
    return e2e, kind, problem


@pytest.mark.parametrize("case", _RAW_CASES.values(), ids=_RAW_CASES.keys())
def test_raw_field_reference_fails_check_function(case):
    """Rule 4 refuses every fixup of ours at a `branch to no row` or `off32 to no row` field, and
    rule 5 an object with none at an `off32 to no row` field, naming the field VA."""
    e2e, kind, problem = _run_case(case)
    assert e2e.cut.raw_fields == (RawField(FIELD_VA, kind),)
    assert not e2e.verdict.ok
    assert e2e.verdict.problems == (f"0x{FIELD_VA:08X}: {problem}",)


@pytest.mark.parametrize("case", _RAW_CASES.values(), ids=_RAW_CASES.keys())
def test_raw_field_failures_come_from_rules_4_and_5(case, monkeypatch):
    """The negative case: with rule 4 (each of our fixups) and rule 5 (reverse coverage) turned
    off, every case above passes, so its failure is those rules' verdict and nothing else."""
    monkeypatch.setattr(relocs, "_fixup", lambda pair, fx: iter(()))
    monkeypatch.setattr(relocs, "_reverse_coverage", lambda pair, ours: iter(()))
    e2e, _, _ = _run_case(case)
    assert e2e.verdict.ok, e2e.verdict.problems


@pytest.mark.parametrize("kind", ["branch", "off32"])
def test_the_same_reference_to_a_named_row_passes(kind):
    """The control: the same shapes with the target at a row start cut with no raw field and
    pass, so the failures above come from the raw target, not from the fixture."""
    if kind == "branch":
        original_body, page1, ours, fixup = _call_to(NAMED), b"", _PLACEHOLDER_CALL, call(1, 1)
    else:
        (original_body, page1), ours, fixup = _load_of(NAMED), _PLACEHOLDER_LOAD, absolute(1, 1)
    e2e = _end_to_end(original_body, page1, our_segment(ours, [fixup], [EXTERN_NAMED]), len(ours))
    assert e2e.cut.raw_fields == ()
    assert e2e.verdict.ok, e2e.verdict.problems


DATA_DEST = DATA_RANGES[0][0] + 0x10  # a destination inside the data object


def test_an_unrelocated_branch_to_no_row_passes_the_relocation_check():
    """The limit of `branch to no row`: our displacement byte-identical to the original's, with
    no fixup, passes rule 3, and rules 4 and 5 have nothing to judge. Acceptable: the landed
    bytes equal the original's and the SHA-1 gate holds; wcc386 emits a fixup for every call, so
    compiled C does not give this object."""
    body = _call_to(GAP)
    e2e = _end_to_end(body, b"", our_segment(body), len(body))
    assert e2e.cut.raw_fields == (RawField(FIELD_VA, RAW_BRANCH_NO_ROW),)
    assert e2e.verdict.ok, e2e.verdict.problems
    assert _landed_bytes(e2e, body) == body


def test_a_branch_outside_the_code_object_to_a_data_name_passes_the_relocation_check():
    """The limit of `branch outside the code object`: the data destination is nameable as
    `_D_<va>`, so our fixup to it lands on the original target and passes rule 4. Acceptable:
    the landed bytes equal the original's and the SHA-1 gate holds."""
    body = _call_to(DATA_DEST)
    data_name_ = f"_{data_name(DATA_DEST)}"
    e2e = _end_to_end(body, b"", our_segment(_PLACEHOLDER_CALL, [call(1, 1)], [data_name_]),
                      len(_PLACEHOLDER_CALL))  # fmt: skip
    assert e2e.cut.raw_fields == (RawField(FIELD_VA, RAW_BRANCH_OUTSIDE),)
    assert e2e.verdict.ok, e2e.verdict.problems
    assert _landed_bytes(e2e, _PLACEHOLDER_CALL) == body
