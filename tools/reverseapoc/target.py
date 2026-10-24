# Derived from Theme Hospital decomp tools/split.py (GPLv3), https://github.com/matteo-pacini/theme-hospital-decomp
"""Target side of every objdiff pair: one ELF32 object per unit, cut straight from the LE (D-13).

There is no assembler step. `build_target` writes, for each functions.csv row of a unit, one
`_TEXT` section holding `load_flat(relocate=False)[start:end]` and one GLOBAL STT_FUNC sized
end - start, named by `SymbolTable.linker_name` (the one naming function, P8). The section name
`_TEXT` is the one omf2elf gives Watcom's code segments, so objdiff pairs the two sides.

Relocations are REL, so every relocated field is rewritten to its addend:

- every LE off32 fixup whose field starts in the function becomes one R_386_32: against the
  function starting at the target (addend 0), or the data symbol `_D_<target>` / a symbols.csv
  name (addend 0). `le.fixups()` lists a page-straddling field once, so it is one relocation
  (P3);
- every decoded `call rel32` becomes one R_386_PC32 against the destination's symbol, field -4.

Target bytes come only from `load_flat(relocate=False)` (P4): never from Ghidra and never from a
relocated image, whose fields would hold load addresses instead of the file's bytes.
"""

from __future__ import annotations

import struct
from bisect import bisect_left
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from .elf import (
    R_386_32,
    R_386_PC32,
    SHF_ALLOC,
    SHF_EXECINSTR,
    STB_GLOBAL,
    STT_FUNC,
    STT_NOTYPE,
    ElfObject,
    ElfReloc,
    ElfSection,
    ElfSymbol,
    write_elf,
)
from .functions import FunctionRow
from .le import LE, SRC_OFF32, Fixup, LEObject
from .symbols import SymbolTable
from .x86 import decode

SECTION_NAME = "_TEXT"  # Watcom's code segment, as omf2elf names it (spike 005)
CODE_ALIGN = 16  # the alignment omf2elf gives code sections
OBJ_EXECUTABLE = 0x0004  # LE object flag: executable
PC32_ADDEND = -4  # a rel32 field is relative to the end of its 4-byte field
_FIELD = struct.Struct("<i")  # a 32-bit relocated field holds its REL addend


class TargetError(ValueError):
    """The unit cannot be cut as a target object; the message names the VA."""


@dataclass(frozen=True)
class RawField:
    """An LE fixup field left as raw bytes with no relocation (orchestrator ruling F11)."""

    va: int
    kind: str  # le.Fixup.kind_name


@dataclass(frozen=True)
class TargetResult:
    data: bytes  # the ELF object
    raw_fields: tuple[RawField, ...] = ()  # non-off32 fixup sites written without relocation


@dataclass(frozen=True)
class _Field:
    """One relocated field of a section: its offset, type, symbol name and REL addend."""

    offset: int
    type: int
    symbol: str
    addend: int


def _hex(va: int) -> str:
    return f"{va:#010x}"


def _code_object(le: LE) -> LEObject:
    obj = next((o for o in le.objects if o.flags & OBJ_EXECUTABLE), None)
    if obj is None:
        raise TargetError("the LE has no executable object")
    return obj


def _covered(fixups: Sequence[Fixup], srcs: Sequence[int], row: FunctionRow) -> list[Fixup]:
    """The fixups whose field starts in [row.start, row.end) (`srcs` their sorted addresses)."""
    return list(fixups[bisect_left(srcs, row.start) : bisect_left(srcs, row.end)])


def _target_symbol(va: int, symbols: SymbolTable, code: LEObject) -> tuple[str, int]:
    """(symbol, addend) for an absolute reference to `va`."""
    if not code.contains(va):
        return symbols.linker_name(va, data=True), 0
    if symbols.function_at(va) is None:
        raise TargetError(f"reference to {_hex(va)}: no functions.csv row starts there")
    return symbols.linker_name(va), 0


def _fixup_relocs(row: FunctionRow, covered: Sequence[Fixup], symbols: SymbolTable,
                  code: LEObject) -> list[_Field]:  # fmt: skip
    out = []
    for fx in covered:
        if fx.kind != SRC_OFF32:
            raise TargetError(f"LE fixup at {_hex(fx.src_va)}: kind {fx.kind_name} not handled")
        name, addend = _target_symbol(fx.target_va, symbols, code)
        out.append(_Field(fx.src_va - row.start, R_386_32, name, addend))
    return out


def branch_fields(
    row: FunctionRow, flat: bytes, fixup_sites: Mapping[int, int]
) -> list[tuple[int, int]]:
    """(field VA, destination VA) of every rel32 call in `row`."""
    code = bytes(flat[row.start : row.end])
    return [
        (insn.rel32_field, insn.branch_target)
        for insn in decode(code, row.start, data_sites=fixup_sites)
        if insn.is_call and insn.rel32_field is not None and insn.branch_target is not None
    ]


def _branch_relocs(row: FunctionRow, flat: bytes, sites: Mapping[int, int],
                   symbols: SymbolTable, code: LEObject) -> list[_Field]:  # fmt: skip
    out = []
    for field, dest in branch_fields(row, flat, sites):
        name, addend = _target_symbol(dest, symbols, code)
        out.append(_Field(field - row.start, R_386_PC32, name, addend + PC32_ADDEND))
    return out


def _rewrite(data: bytearray, fields: Sequence[_Field]) -> bytes:
    for f in fields:
        _FIELD.pack_into(data, f.offset, f.addend)
    return bytes(data)


def _undefined(defined: set[str], fields: Sequence[_Field]) -> Iterator[ElfSymbol]:
    """One undefined GLOBAL STT_NOTYPE per referenced name the unit does not define."""
    for name in sorted({f.symbol for f in fields} - defined):
        yield ElfSymbol(name, None, bind=STB_GLOBAL, type=STT_NOTYPE)


def build_target(
    le: LE,
    rows: Sequence[FunctionRow],
    symbols: SymbolTable,
    *,
    flat: bytes | None = None,
    fixups: Sequence[Fixup] | None = None,
) -> TargetResult:
    """The target ELF object of the unit made of `rows`. `flat` and `fixups` default to
    `le.load_flat(relocate=False)` and `le.fixups()`; a caller cutting many units passes them
    once."""
    flat = bytes(le.load_flat(relocate=False)) if flat is None else flat
    fixups = le.fixups() if fixups is None else fixups
    srcs = [fx.src_va for fx in fixups]
    sites = {fx.src_va: fx.size for fx in fixups}
    code = _code_object(le)
    sections, syms, relocs, all_fields = [], [], [], []
    for index, row in enumerate(sorted(rows, key=lambda r: r.start)):
        fields = _fixup_relocs(row, _covered(fixups, srcs, row), symbols, code)
        fields += _branch_relocs(row, flat, sites, symbols, code)
        data = _rewrite(bytearray(flat[row.start : row.end]), fields)
        sections.append(ElfSection(SECTION_NAME, data, flags=SHF_ALLOC | SHF_EXECINSTR,
                                   align=CODE_ALIGN))  # fmt: skip
        syms.append(ElfSymbol(symbols.linker_name(row.start), index, 0, row.end - row.start,
                              STB_GLOBAL, STT_FUNC))  # fmt: skip
        relocs += [ElfReloc(index, f.offset, f.type, f.symbol) for f in fields]
        all_fields += fields
    syms += _undefined({s.name for s in syms}, all_fields)
    obj = ElfObject(tuple(sections), tuple(syms), tuple(relocs))
    return TargetResult(write_elf(obj))
