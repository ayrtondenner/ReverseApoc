# Derived from Theme Hospital decomp tools/split.py (GPLv3), https://github.com/matteo-pacini/theme-hospital-decomp
"""Target side of every objdiff pair: one ELF32 object per unit, cut straight from the LE (D-13).

There is no assembler step. `build_target` writes, for each functions.csv row of a unit, one
`_TEXT` section holding `load_flat(relocate=False)[start:end]` and one symbol named by
`SymbolTable.linker_name`, the one naming function (P8). A function gets a GLOBAL STT_FUNC sized
end - start; a data-in-code row (a jump table) gets a LOCAL STT_OBJECT so the relocations into it
resolve. `_TEXT` is the name omf2elf gives Watcom's code segments, so objdiff pairs both sides.

Relocations are REL, so every relocated field is rewritten to its addend (the file holds the
target's object offset there, Pitfall 1):

- every LE off32 fixup whose field starts in the row becomes one R_386_32: against the row
  starting at the target (addend 0), the row containing the target (addend = the offset into
  it), or, for a target outside the code object, the data symbol `_D_<target>` or its
  symbols.csv name (addend 0). `le.fixups()` lists a page-straddling field once, so it is one
  relocation, rewritten across the page boundary (P3);
- every decoded `call rel32`, and every `jmp`/`jcc rel32` whose destination leaves the
  function, becomes one R_386_PC32 against the destination's symbol, field -4 plus the offset
  into the destination row. Intra-function jumps and rel8 branches get none. Decoding treats an
  LE fixup site at an instruction start as inline data and resumes after the field (P8), and
  data-in-code rows are not decoded at all;
- a non-off32 LE fixup (sel16, ptr16:32, ...) keeps its raw bytes and gets no relocation; the
  result lists its VA and kind (orchestrator ruling F11), so every unit stays cuttable.

Referenced names the unit does not define become undefined GLOBAL STT_NOTYPE symbols.
`build_target` refuses, with a TargetError naming the VA, a row outside the code object, a
reference into the code object that lies in no functions.csv row, and an LE fixup field split
by a row boundary.

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
    STB_LOCAL,
    STT_FUNC,
    STT_NOTYPE,
    STT_OBJECT,
    ElfObject,
    ElfReloc,
    ElfSection,
    ElfSymbol,
    write_elf,
)
from .functions import KIND_DATA_IN_CODE, FunctionRow
from .le import LE, SRC_OFF32, SRC_SIZE, Fixup, LEObject
from .symbols import SymbolTable
from .x86 import Insn, decode

SECTION_NAME = "_TEXT"  # Watcom's code segment, as omf2elf names it (spike 005)
CODE_ALIGN = 16  # the alignment omf2elf gives code sections
OBJ_EXECUTABLE = 0x0004  # LE object flag: executable
PC32_ADDEND = -4  # a rel32 field is relative to the end of its 4-byte field
MAX_FIELD = max(SRC_SIZE.values())  # the longest LE fixup field (ptr16:32)
_UNDECODABLE_SKIP = 1  # resume one byte past a byte capstone cannot decode
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


@dataclass(frozen=True)
class _Image:
    """What every row of a unit is cut from."""

    flat: bytes
    fixups: Sequence[Fixup]
    srcs: list[int]  # fixups' src_va, sorted
    sites: Mapping[int, int]  # LE fixup field VA -> field size
    symbols: SymbolTable
    code: LEObject


def _hex(va: int) -> str:
    return f"{va:#010x}"


def _code_object(le: LE) -> LEObject:
    obj = next((o for o in le.objects if o.flags & OBJ_EXECUTABLE), None)
    if obj is None:
        raise TargetError("the LE has no executable object")
    return obj


def _check_row(row: FunctionRow, code: LEObject) -> None:
    if not (code.base <= row.start and row.end <= code.end):
        raise TargetError(
            f"row {row.name} at {_hex(row.start)}: not inside the code object "
            f"{_hex(code.base)}..{_hex(code.end)}"
        )


def _split(fx: Fixup, boundary: int) -> TargetError:
    return TargetError(
        f"LE fixup field at {_hex(fx.src_va)} ({fx.kind_name}, {fx.size} bytes) is split by "
        f"the row boundary at {_hex(boundary)}"
    )


def _covered(img: _Image, row: FunctionRow) -> list[Fixup]:
    """The fixups whose field starts in [row.start, row.end). A field that starts before the
    row and runs into it is refused: no section can hold it whole."""
    first = bisect_left(img.srcs, row.start)
    for fx in img.fixups[bisect_left(img.srcs, row.start - MAX_FIELD + 1) : first]:
        if fx.src_va + fx.size > row.start:
            raise _split(fx, row.start)
    return list(img.fixups[first : bisect_left(img.srcs, row.end)])


def _target_symbol(img: _Image, va: int, where: str) -> tuple[str, int]:
    """(symbol, offset of `va` past it) for a reference to `va`."""
    if not img.code.contains(va):
        return img.symbols.linker_name(va, data=True), 0
    row = img.symbols.containing(va)
    if row is None:
        raise TargetError(f"{where} to {_hex(va)}: in no functions.csv row")
    return img.symbols.linker_name(row.start), va - row.start


def _fixup_relocs(
    img: _Image, row: FunctionRow, covered: Sequence[Fixup]
) -> tuple[list[_Field], list[RawField]]:
    """R_386_32 fields for the off32 fixups in `row`, and the other kinds left raw (F11)."""
    fields, raw = [], []
    for fx in covered:
        if fx.src_va + fx.size > row.end:
            raise _split(fx, row.end)
        if fx.kind != SRC_OFF32:
            raw.append(RawField(fx.src_va, fx.kind_name))
            continue
        name, addend = _target_symbol(img, fx.target_va, f"LE fixup at {_hex(fx.src_va)}")
        fields.append(_Field(fx.src_va - row.start, R_386_32, name, addend))
    return fields, raw


def _instructions(row: FunctionRow, flat: bytes, sites: Mapping[int, int]) -> Iterator[Insn]:
    """The instructions of `row` in order. An LE fixup site at an instruction start is inline
    data (a jump table entry): it is skipped whole and decoding resumes after it (P8)."""
    va = row.start
    while va < row.end:
        if va in sites:
            va += sites[va]
            continue
        last = None
        for last in decode(bytes(flat[va : row.end]), va, data_sites=sites):
            yield last
        va = _UNDECODABLE_SKIP + va if last is None else last.va + last.size


def branch_fields(
    row: FunctionRow, flat: bytes, fixup_sites: Mapping[int, int]
) -> list[tuple[int, int]]:
    """(field VA, destination VA) of every rel32 call in `row` and of every rel32 jump whose
    destination lies outside it. `fixup_sites` maps each LE fixup field VA to its size; a rel32
    field that is itself an LE fixup site belongs to that fixup and is not listed."""
    out = []
    for insn in _instructions(row, flat, fixup_sites):
        field, dest = insn.rel32_field, insn.branch_target
        if field is None or dest is None or field in fixup_sites:
            continue
        if not insn.is_call and row.start <= dest < row.end:
            continue  # an intra-function jump
        out.append((field, dest))
    return out


def _branch_relocs(img: _Image, row: FunctionRow) -> list[_Field]:
    out = []
    for field, dest in branch_fields(row, img.flat, img.sites):
        name, offset = _target_symbol(img, dest, f"branch at {_hex(field)}")
        out.append(_Field(field - row.start, R_386_PC32, name, PC32_ADDEND + offset))
    return out


def _rewrite(data: bytearray, fields: Sequence[_Field]) -> bytes:
    """`data` with each relocated field holding its REL addend."""
    for f in fields:
        _FIELD.pack_into(data, f.offset, f.addend)
    return bytes(data)


def _undefined(defined: set[str], fields: Sequence[_Field]) -> Iterator[ElfSymbol]:
    """One undefined GLOBAL STT_NOTYPE per referenced name the unit does not define."""
    for name in sorted({f.symbol for f in fields} - defined):
        yield ElfSymbol(name, None, bind=STB_GLOBAL, type=STT_NOTYPE)


def _row_symbol(img: _Image, row: FunctionRow, section: int) -> ElfSymbol:
    name, size = img.symbols.linker_name(row.start), row.end - row.start
    if row.kind == KIND_DATA_IN_CODE:
        return ElfSymbol(name, section, 0, size, STB_LOCAL, STT_OBJECT)
    return ElfSymbol(name, section, 0, size, STB_GLOBAL, STT_FUNC)


def _cut_row(img: _Image, row: FunctionRow) -> tuple[ElfSection, list[_Field], list[RawField]]:
    _check_row(row, img.code)
    fields, raw = _fixup_relocs(img, row, _covered(img, row))
    if row.kind != KIND_DATA_IN_CODE:
        fields += _branch_relocs(img, row)
    data = _rewrite(bytearray(img.flat[row.start : row.end]), fields)
    section = ElfSection(SECTION_NAME, data, flags=SHF_ALLOC | SHF_EXECINSTR, align=CODE_ALIGN)
    return section, fields, raw


def build_target(
    le: LE,
    rows: Sequence[FunctionRow],
    symbols: SymbolTable,
    *,
    flat: bytes | None = None,
    fixups: Sequence[Fixup] | None = None,
) -> TargetResult:
    """The target ELF object of the unit made of `rows`, with the non-off32 fixup sites it left
    raw. `flat` and `fixups` default to `le.load_flat(relocate=False)` and `le.fixups()`; a
    caller cutting many units passes them once."""
    flat = bytes(le.load_flat(relocate=False)) if flat is None else flat
    fixups = le.fixups() if fixups is None else fixups
    img = _Image(flat, fixups, [fx.src_va for fx in fixups],
                 {fx.src_va: fx.size for fx in fixups}, symbols, _code_object(le))  # fmt: skip
    sections, syms, relocs, all_fields, raw = [], [], [], [], []
    for index, row in enumerate(sorted(rows, key=lambda r: r.start)):
        section, fields, row_raw = _cut_row(img, row)
        sections.append(section)
        syms.append(_row_symbol(img, row, index))
        relocs += [ElfReloc(index, f.offset, f.type, f.symbol) for f in fields]
        all_fields += fields
        raw += row_raw
    syms += _undefined({s.name for s in syms}, all_fields)
    obj = ElfObject(tuple(sections), tuple(syms), tuple(relocs))
    return TargetResult(write_elf(obj), tuple(raw))
