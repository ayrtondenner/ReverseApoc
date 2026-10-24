"""target.py: per-unit target ELF objects cut straight from a synthetic LE (SPL-08, D-13).

Every LE here is built by tests/conftest.py from made-up bytes; no game byte appears. The code
object is 0x10000..0x11800 (pages 1-2), the data object 0x20000..0x23000 (page 3)."""

from __future__ import annotations

import struct

from conftest import build_le_image, fixup_record
from elfread import read_elf
from reverseapoc.elf import R_386_32, R_386_PC32, STB_GLOBAL, STT_FUNC
from reverseapoc.functions import FunctionRow, SymbolRow, data_name, game_name
from reverseapoc.le import LE, SRC_OFF32
from reverseapoc.symbols import SymbolTable
from reverseapoc.target import build_target

DATA_RANGES = [(0x20000, 0x23000)]  # the synthetic data object
FIELD = struct.Struct("<i")
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
    return all(
        byte == flat[start + i] for i, byte in enumerate(section.data) if i not in masked
    )


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
