# Derived from Theme Hospital decomp tools/omf2elf.py (GPLv3), https://github.com/matteo-pacini/theme-hospital-decomp
"""Watcom OMF object -> ELF32 relocatable object, the base side of every objdiff pair (D-13).

Built on `omf.read_object`, which already parses the records (BAKPAT applied, LIDATA expanded,
FIXUPP threads resolved); nothing here re-reads them. `convert(module)` maps:

- each SEGDEF to one section named like the SEGDEF (objdiff pairs on the section base name):
  a CODE class to PROGBITS ALLOC+EXECINSTR, a class ending in BSS to NOBITS ALLOC+WRITE with
  the segment length, any other class to PROGBITS ALLOC+WRITE; classes starting with DEB
  (DEBSYM, DEBTYP) are dropped with their fixups;
- each public to a GLOBAL symbol (LOCAL for LPUBDEF), STT_FUNC in code and STT_OBJECT
  elsewhere, sized to the next public of its segment or the segment end; in code, Watcom
  filler (nop, mov eax,eax in both encodings, lea eax,[eax+0]) after a terminal instruction
  is not counted, decoded with x86.py (a function may fall through, so no `ret` is required);
- each COMDAT (0xC2 or 0xC3, NBKPAT already applied) to its own section, named after its
  segment or, without one, after the COMDAT, with one symbol at offset 0: WEAK when the
  selection criterion allows duplicates (pick any, same size, exact match), GLOBAL for "no
  match"; a COMDAT without a segment is code when allocated as far code or code32;
- each extern to an undefined GLOBAL symbol named as in OMF (referenced or not);
- each location-9 (offset32) fixup to one REL relocation by the Theme Hospital addend rule: a
  self-relative fixup becomes R_386_PC32 with the field rewritten to stored + displacement - 4,
  a segment-relative one R_386_32 with stored + displacement. An extern target names its
  symbol, a segment target that section's STT_SECTION symbol.

Refused with Omf2ElfError: another fixup location, a group or frame-number target, a target in
a dropped segment, a fixup into iterated data (`Segment.unmaskable`), an absolute public and
initialised bytes in a BSS segment. `convert_file(src, dst)` reads an object, converts it and
writes the ELF atomically.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from .elf import (
    FIELD_SIZE,
    R_386_32,
    R_386_PC32,
    SHF_ALLOC,
    SHF_EXECINSTR,
    SHF_WRITE,
    STB_GLOBAL,
    STB_LOCAL,
    STB_WEAK,
    STT_FUNC,
    STT_OBJECT,
    ElfObject,
    ElfReloc,
    ElfSection,
    ElfSymbol,
    write_elf,
)
from .omf import (
    COMDAT_ALLOC_CODE32,
    COMDAT_ALLOC_FAR_CODE,
    COMDAT_SELECT_NO_MATCH,
    LOC_OFFSET32,
    REC_THEADR,
    Comdat,
    Module,
    OMFError,
    OMFFixup,
    Segment,
    read_object,
)
from .splice import _write_atomic
from .x86 import decode, is_filler

_CODE_ALLOCATIONS = (COMDAT_ALLOC_FAR_CODE, COMDAT_ALLOC_CODE32)  # COMDAT without a segment
CODE_ALIGN = 16
DATA_ALIGN = 4
DEBUG_CLASS_PREFIX = "DEB"  # DEBSYM, DEBTYP: Watcom debug information
BSS_CLASS_SUFFIX = "BSS"
_FIELD = struct.Struct("<i")  # a 32-bit relocated field, read and written signed
PC32_BIAS = -FIELD_SIZE  # a PC32 addend counts from the field's end, the CPU from the next insn


class Omf2ElfError(ValueError):
    """The object cannot be converted (or would convert to a wrong ELF)."""


@dataclass(frozen=True)
class ConvertResult:
    source: Path
    output: Path
    sections: int
    symbols: int
    relocations: int

    def format(self) -> str:
        return (
            f"OK {self.output} sections {self.sections} symbols {self.symbols} "
            f"relocations {self.relocations}"
        )

    def to_json(self) -> dict[str, object]:
        return {
            "source": str(self.source),
            "output": str(self.output),
            "sections": self.sections,
            "symbols": self.symbols,
            "relocations": self.relocations,
        }


def is_debug(seg: Segment) -> bool:
    return seg.class_name.upper().startswith(DEBUG_CLASS_PREFIX)


def is_bss(seg: Segment) -> bool:
    return seg.class_name.upper().endswith(BSS_CLASS_SUFFIX)


@dataclass(frozen=True)
class _Part:
    """One ELF section to emit: an OMF segment (`segment_index`) or a COMDAT (`comdat`)."""

    name: str  # the section name
    where: str  # how errors name it: "segment _TEXT" or "COMDAT 'f_'"
    code: bool
    bss: bool
    data: bytes
    length: int
    fixups: tuple[OMFFixup, ...]
    segment_index: int = 0  # 1-based SEGDEF number; 0 for a COMDAT
    comdat: Comdat | None = None


def _segment_part(seg: Segment) -> _Part:
    return _Part(seg.name, f"segment {seg.name}", seg.is_code, is_bss(seg), seg.data, seg.length,
                 seg.fixups, segment_index=seg.index)  # fmt: skip


def _comdat_part(cd: Comdat, segments: dict[int, Segment]) -> _Part:
    """A COMDAT's section is named after its segment, or after the COMDAT when it has none."""
    seg = segments.get(cd.segment_index)
    code = seg.is_code if seg else cd.allocation in _CODE_ALLOCATIONS
    name = seg.name if seg else cd.name
    return _Part(name, f"COMDAT {cd.name!r}", code, False, cd.data, len(cd.data), cd.fixups,
                 comdat=cd)  # fmt: skip


def _parts(module: Module) -> list[_Part]:
    """Every emitted segment in SEGDEF order, then every COMDAT; debug classes are dropped."""
    segments = {seg.index: seg for seg in module.segments}
    parts = [_segment_part(seg) for seg in module.segments if not is_debug(seg)]
    for cd in module.comdats:
        seg = segments.get(cd.segment_index)
        if seg is not None and is_debug(seg):
            continue
        parts.append(_comdat_part(cd, segments))
    return parts


def _section(part: _Part, data: bytes) -> ElfSection:
    if part.code:
        return ElfSection(part.name, data, flags=SHF_ALLOC | SHF_EXECINSTR, align=CODE_ALIGN)
    if part.bss:
        if any(data):
            raise Omf2ElfError(f"{part.where}: BSS segment holds initialised bytes")
        return ElfSection(part.name, kind="nobits", flags=SHF_ALLOC | SHF_WRITE,
                          align=DATA_ALIGN, size=part.length)  # fmt: skip
    return ElfSection(part.name, data, flags=SHF_ALLOC | SHF_WRITE, align=DATA_ALIGN)


def _code_end(part: _Part, start: int, end: int) -> int:
    """Where the code of [start, end) ends once trailing Watcom filler is trimmed (TH `sized`).

    The span is decoded with x86.decode, stopping at fixup sites (inline data). Only when it
    decodes to its last byte, ends in filler, and the last non-filler instruction is terminal
    is the filler cut off; otherwise (fall-through into the next function, inline data, bytes
    capstone cannot decode) the whole span is kept.
    """
    sites = frozenset(fx.offset for fx in part.fixups)
    insns = list(decode(part.data[start:end], start, data_sites=sites))
    if not insns or insns[-1].va + insns[-1].size != end:
        return end
    body = list(insns)
    while body and is_filler(body[-1]):
        body.pop()
    if len(body) == len(insns) or not body or not body[-1].is_terminal:
        return end
    return body[-1].va + body[-1].size


def _sized_publics(module: Module, part: _Part, section: int) -> list[ElfSymbol]:
    """A symbol per public in the segment of `part`, sized to the next public or the end;
    in code, trailing filler after a terminal instruction is not counted (`_code_end`)."""
    own = [p for p in module.publics if p.segment_index == part.segment_index]
    offsets = sorted({p.offset for p in own})
    ends = dict(zip(offsets, [*offsets[1:], part.length], strict=False))  # [length] if no public
    if part.code:
        ends = {start: _code_end(part, start, end) for start, end in ends.items()}
    kind = STT_FUNC if part.code else STT_OBJECT
    return [ElfSymbol(p.name, section, p.offset, ends[p.offset] - p.offset,
                      bind=STB_LOCAL if p.local else STB_GLOBAL, type=kind)
            for p in own]  # fmt: skip


def _comdat_symbol(part: _Part, section: int) -> ElfSymbol:
    """The COMDAT's own symbol: WEAK when its selection criterion allows duplicates."""
    assert part.comdat is not None
    bind = STB_GLOBAL if part.comdat.selection == COMDAT_SELECT_NO_MATCH else STB_WEAK
    kind = STT_FUNC if part.code else STT_OBJECT
    size = _code_end(part, 0, part.length) if part.code else part.length
    return ElfSymbol(part.comdat.name, section, 0, size, bind=bind, type=kind)


def _symbols(module: Module, parts: list[_Part]) -> list[ElfSymbol]:
    """Publics and COMDATs, then every extern not defined here as an undefined GLOBAL."""
    symbols: list[ElfSymbol] = []
    for i, part in enumerate(parts):
        if part.comdat is not None:
            symbols.append(_comdat_symbol(part, i))
            continue
        symbols += _sized_publics(module, part, i)
    defined = {s.name for s in symbols}
    symbols += [ElfSymbol(name, None) for name in dict.fromkeys(module.externs)
                if name not in defined]  # fmt: skip
    return symbols


def _target(fx: OMFFixup, where: str, section_of: dict[int, int]) -> tuple[str, int | None]:
    """(symbol name, target section) of a fixup: an extern's name, or a segment's section."""
    if fx.target_kind == "extern":
        return fx.target_name, None
    if fx.target_kind == "segment":
        if fx.target_index not in section_of:
            raise Omf2ElfError(f"{where}: target segment {fx.target_name!r} is not emitted")
        return "", section_of[fx.target_index]
    raise Omf2ElfError(
        f"{where}: fixup target {fx.target_kind} {fx.target_name!r} is not supported"
    )


def _relocation(
    fx: OMFFixup, part: _Part, section: int, data: bytearray, section_of: dict[int, int]
) -> ElfReloc:
    """Rewrites the fixup's field to its REL addend and returns its relocation."""
    where = f"{part.where} offset {fx.offset:#x}"
    if fx.location != LOC_OFFSET32:
        raise Omf2ElfError(f"{where}: fixup location {fx.location} is not 9 (offset32)")
    symbol, target_section = _target(fx, where, section_of)
    relative = not fx.segment_relative
    stored = _FIELD.unpack_from(data, fx.offset)[0]
    _FIELD.pack_into(data, fx.offset, stored + fx.displacement + (PC32_BIAS if relative else 0))
    rtype = R_386_PC32 if relative else R_386_32
    return ElfReloc(section, fx.offset, rtype, symbol, target_section)


def _relocations(
    part: _Part, section: int, section_of: dict[int, int]
) -> tuple[bytes, list[ElfReloc]]:
    """The part's bytes with every fixup field rewritten to its addend, and the relocations."""
    data = bytearray(part.data)
    relocs = [_relocation(fx, part, section, data, section_of) for fx in part.fixups]
    return bytes(data), relocs


def _sections(
    parts: list[_Part], section_of: dict[int, int]
) -> tuple[list[ElfSection], list[ElfReloc]]:
    sections: list[ElfSection] = []
    relocs: list[ElfReloc] = []
    for i, part in enumerate(parts):
        data, part_relocs = _relocations(part, i, section_of)
        sections.append(_section(part, data))
        relocs += part_relocs
    return sections, relocs


def _check_publics(module: Module) -> None:
    for pub in module.publics:
        if pub.segment_index == 0:
            raise Omf2ElfError(f"public {pub.name!r} is absolute (no segment)")


def _check_unmaskable(module: Module) -> None:
    for seg in module.segments:
        if seg.unmaskable and not is_debug(seg):
            raise Omf2ElfError(f"segment {seg.name}: a fixup addresses iterated data")


def convert(module: Module) -> ElfObject:
    """The ELF object of one Watcom OMF module."""
    _check_publics(module)
    _check_unmaskable(module)
    parts = _parts(module)
    section_of = {p.segment_index: i for i, p in enumerate(parts) if p.segment_index}
    sections, relocs = _sections(parts, section_of)
    symbols = _symbols(module, parts)
    return ElfObject(tuple(sections), tuple(symbols), tuple(relocs))


def convert_file(src: Path, dst: Path) -> ConvertResult:
    """Converts the OMF object at `src` and writes the ELF to `dst` atomically."""
    src, dst = Path(src), Path(dst)
    if dst.resolve() == src.resolve():
        raise Omf2ElfError(f"{dst}: refusing to write over the input object")
    data = src.read_bytes()
    if not data or data[0] != REC_THEADR:
        raise Omf2ElfError(f"{src}: not an OMF object (no THEADR record first)")
    try:
        module = read_object(data)
    except OMFError as exc:
        raise Omf2ElfError(f"{src}: {exc}") from exc
    try:
        obj = convert(module)
    except Omf2ElfError as exc:
        raise Omf2ElfError(f"{src}: {exc}") from exc
    dst.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(dst, write_elf(obj))
    return ConvertResult(src, dst, len(obj.sections), len(obj.symbols), len(obj.relocs))
