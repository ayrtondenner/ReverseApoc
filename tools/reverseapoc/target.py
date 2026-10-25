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
- decoding of a row stops for good at a byte capstone cannot decode that is no LE fixup site:
  guessing where the next instruction starts could read an e8/e9/0f 8x inside an immediate as a
  branch. No PC32 is synthesized past it, the remaining bytes stay as the file has them (LE
  off32 fixups there still relocate: they come from the fixup table), and the result lists the
  VA in `undecoded`, so the unit stays cuttable (D-13);
- a non-off32 LE fixup (sel16, ptr16:32, ...) keeps its raw bytes and gets no relocation; the
  result lists its VA and kind (orchestrator ruling F11), so every unit stays cuttable;
- so do an off32 fixup or rel32 branch whose target lies in the code object but in no
  functions.csv row (a split gap D-11 leaves for later), and a decoded rel32 branch whose
  destination is outside the code object (data read as code): kinds `off32 to no row`,
  `branch to no row` and `branch outside the code object` (plan 05-18, the F11 principle).
  A function holding one is no first-match candidate. What the relocation check guarantees
  depends on the kind (rule 4: each of our fixups lands on the original target through a
  nameable start; rule 5: every LE fixup field in the row is one of ours):
  - `off32 to no row`: every object fails. Rule 4 refuses a fixup of ours there, since no name
    reaches a gap (placeholders and symbols.csv functions need a row start, data names a data
    range), and rule 5 refuses an object with none, since the LE has a fixup there.
  - `branch to no row`: rule 4 refuses every fixup of ours there. A rel32 is no LE fixup, so
    rule 5 checks nothing, and our displacement left unrelocated and byte-identical to the
    original passes rule 3. That this does not happen also rests on wcc386 emitting a fixup for
    every call, even to a static.
  - `branch outside the code object`: a destination in a data object is nameable as `_D_<va>`,
    so a fixup of ours to it passes rule 4.
  In the two passing cases the residual risk is bounded by byte identity: rule 3 compares every
  byte outside the fields and build_patch keeps the original bytes under every field, so the
  landed bytes equal the original's and the whole-EXE SHA-1 gate still holds.
  tests/test_target.py pins all three kinds end to end
  (`test_raw_field_reference_fails_check_function` and the two passing cases).

Referenced names the unit does not define become undefined GLOBAL STT_NOTYPE symbols.
`build_target` refuses, with a TargetError naming the VA, a row outside the code object and an
LE fixup field split by a row boundary.

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
RAW_OFF32_NO_ROW = "off32 to no row"  # RawField kinds of references the cut cannot name
RAW_BRANCH_NO_ROW = "branch to no row"
RAW_BRANCH_OUTSIDE = "branch outside the code object"
_FIELD = struct.Struct("<i")  # a 32-bit relocated field holds its REL addend


class TargetError(ValueError):
    """The unit cannot be cut as a target object; the message names the VA."""


@dataclass(frozen=True)
class RawField:
    """An LE fixup field left as raw bytes with no relocation (orchestrator ruling F11)."""

    va: int
    kind: str  # le.Fixup.kind_name, or one of the RAW_* kinds of an unnamed reference


@dataclass(frozen=True)
class TargetResult:
    data: bytes  # the ELF object
    raw_fields: tuple[RawField, ...] = ()  # fields written without relocation (F11, RAW_*)
    undecoded: tuple[int, ...] = ()  # per row, the VA past which no PC32 was synthesized


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


def _target_symbol(img: _Image, va: int) -> tuple[str, int] | None:
    """(symbol, offset of `va` past it) for a reference to `va`; None for a code address in
    no functions.csv row, which has no name to relocate against."""
    if not img.code.contains(va):
        return img.symbols.linker_name(va, data=True), 0
    row = img.symbols.containing(va)
    if row is None:
        return None
    return img.symbols.linker_name(row.start), va - row.start


def _fixup_relocs(
    img: _Image, row: FunctionRow, covered: Sequence[Fixup]
) -> tuple[list[_Field], list[RawField]]:
    """R_386_32 fields for the off32 fixups in `row`, and the fields left raw: other kinds (F11)
    and off32 fixups into no row."""
    fields, raw = [], []
    for fx in covered:
        if fx.src_va + fx.size > row.end:
            raise _split(fx, row.end)
        if fx.kind != SRC_OFF32:
            raw.append(RawField(fx.src_va, fx.kind_name))
            continue
        named = _target_symbol(img, fx.target_va)
        if named is None:
            raw.append(RawField(fx.src_va, RAW_OFF32_NO_ROW))
            continue
        fields.append(_Field(fx.src_va - row.start, R_386_32, *named))
    return fields, raw


@dataclass(frozen=True)
class _Decoded:
    insns: list[Insn]  # in order
    undecoded: int | None  # VA of the byte decoding stopped at, short of the row end


def _decode_row(row: FunctionRow, flat: bytes, sites: Mapping[int, int]) -> _Decoded:
    """The instructions of `row` in order. An LE fixup site at an instruction start is inline
    data (a jump table entry): it is skipped whole and decoding resumes after it (P8). Any other
    byte capstone cannot decode ends decoding of the row: past it, instruction starts are
    unknown, and a guess could read an immediate's e8/e9/0f 8x byte as a branch."""
    insns: list[Insn] = []
    va = row.start
    while va < row.end:
        if va in sites:
            va += sites[va]
            continue
        before = len(insns)
        insns += decode(bytes(flat[va : row.end]), va, data_sites=sites)
        end = insns[-1].va + insns[-1].size if len(insns) > before else va
        if end < row.end and end not in sites:
            return _Decoded(insns, end)
        va = end
    return _Decoded(insns, None)


def _branches(
    row: FunctionRow, insns: Sequence[Insn], sites: Mapping[int, int]
) -> Iterator[tuple[int, int]]:
    """(field, destination) of the rel32 calls and of the rel32 jumps leaving `row`."""
    for insn in insns:
        field, dest = insn.rel32_field, insn.branch_target
        if field is None or dest is None or field in sites:
            continue
        if not insn.is_call and row.start <= dest < row.end:
            continue  # an intra-function jump
        yield field, dest


def branch_fields(
    row: FunctionRow, flat: bytes, fixup_sites: Mapping[int, int]
) -> list[tuple[int, int]]:
    """(field VA, destination VA) of every rel32 call in `row` and of every rel32 jump whose
    destination lies outside it, up to the first undecodable byte. `fixup_sites` maps each LE
    fixup field VA to its size; a rel32 field that is itself an LE fixup site belongs to that
    fixup and is not listed."""
    return list(_branches(row, _decode_row(row, flat, fixup_sites).insns, fixup_sites))


@dataclass(frozen=True)
class _Branches:
    fields: list[_Field]  # the PC32 relocations
    raw: list[RawField]  # branches with no name to relocate against
    undecoded: int | None  # the VA where decoding stopped short, None if it did not


def _branch_relocs(img: _Image, row: FunctionRow) -> _Branches:
    """PC32 fields of `row`, the branches left raw, and where decoding stopped short."""
    decoded = _decode_row(row, img.flat, img.sites)
    out, raw = [], []
    for field, dest in _branches(row, decoded.insns, img.sites):
        if not img.code.contains(dest):
            raw.append(RawField(field, RAW_BRANCH_OUTSIDE))
            continue
        named = _target_symbol(img, dest)
        if named is None:
            raw.append(RawField(field, RAW_BRANCH_NO_ROW))
            continue
        name, offset = named
        out.append(_Field(field - row.start, R_386_PC32, name, PC32_ADDEND + offset))
    return _Branches(out, raw, decoded.undecoded)


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


@dataclass(frozen=True)
class _Cut:
    section: ElfSection
    fields: list[_Field]
    raw: list[RawField]
    undecoded: int | None


def _cut_row(img: _Image, row: FunctionRow) -> _Cut:
    _check_row(row, img.code)
    fields, raw = _fixup_relocs(img, row, _covered(img, row))
    undecoded = None
    if row.kind != KIND_DATA_IN_CODE:
        branches = _branch_relocs(img, row)
        fields += branches.fields
        raw += branches.raw
        undecoded = branches.undecoded
    data = _rewrite(bytearray(img.flat[row.start : row.end]), fields)
    section = ElfSection(SECTION_NAME, data, flags=SHF_ALLOC | SHF_EXECINSTR, align=CODE_ALIGN)
    return _Cut(section, fields, raw, undecoded)


def build_target(
    le: LE,
    rows: Sequence[FunctionRow],
    symbols: SymbolTable,
    *,
    flat: bytes | None = None,
    fixups: Sequence[Fixup] | None = None,
) -> TargetResult:
    """The target ELF object of the unit made of `rows`, with the non-off32 fixup sites it left
    raw and the VAs where decoding stopped short. `flat` and `fixups` default to
    `le.load_flat(relocate=False)` and `le.fixups()`; a caller cutting many units passes them
    once."""
    flat = bytes(le.load_flat(relocate=False)) if flat is None else flat
    fixups = le.fixups() if fixups is None else fixups
    img = _Image(flat, fixups, [fx.src_va for fx in fixups],
                 {fx.src_va: fx.size for fx in fixups}, symbols, _code_object(le))  # fmt: skip
    sections, syms, relocs, all_fields, raw, undecoded = [], [], [], [], [], []
    for index, row in enumerate(sorted(rows, key=lambda r: r.start)):
        cut = _cut_row(img, row)
        sections.append(cut.section)
        syms.append(_row_symbol(img, row, index))
        relocs += [ElfReloc(index, f.offset, f.type, f.symbol) for f in cut.fields]
        all_fields += cut.fields
        raw += cut.raw
        if cut.undecoded is not None:
            undecoded.append(cut.undecoded)
    syms += _undefined({s.name for s in syms}, all_fields)
    obj = ElfObject(tuple(sections), tuple(syms), tuple(relocs))
    return TargetResult(write_elf(obj), tuple(sorted(raw, key=lambda f: f.va)), tuple(undecoded))
