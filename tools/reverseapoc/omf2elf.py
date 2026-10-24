# Derived from Theme Hospital decomp tools/omf2elf.py (GPLv3), https://github.com/matteo-pacini/theme-hospital-decomp
"""Watcom OMF object -> ELF32 relocatable object, the base side of every objdiff pair (D-13).

Built on `omf.read_object`, which already parses the records (BAKPAT and NBKPAT applied, LIDATA
expanded, FIXUPP threads resolved, CEXTDEF names numbered with the other externs); nothing here
re-reads them. `convert(module)` maps:

- each SEGDEF to one section named like the SEGDEF (objdiff pairs on the section base name):
  a CODE class to PROGBITS ALLOC+EXECINSTR, a class ending in BSS to NOBITS ALLOC+WRITE with
  the segment length, any other class to PROGBITS ALLOC+WRITE; classes starting with DEB
  (DEBSYM, DEBTYP) are dropped with their fixups;
- each public to a GLOBAL symbol (LOCAL for LPUBDEF), STT_FUNC in code and STT_OBJECT
  elsewhere, sized to the next public of its segment or the segment end; in code, Watcom
  filler (nop, mov eax,eax in both encodings, lea eax,[eax+0]) after a terminal instruction
  is not counted, decoded with x86.py (a function may fall through, so no `ret` is required);
- each COMDAT (0xC2 or 0xC3) to its own section, named after its segment or, without one,
  after the COMDAT, with one symbol at offset 0: WEAK when the selection criterion allows
  duplicates (pick any, same size, exact match), GLOBAL for "no match"; a COMDAT without a
  segment is code when allocated as far code or code32;
- each extern to an undefined GLOBAL symbol named as in OMF (referenced or not);
- each offset32 fixup (location 9, and location 5 in an Easy OMF module, the TH rule) to one
  REL relocation by the Theme Hospital addend rule: a self-relative fixup becomes R_386_PC32
  with the field rewritten to stored + displacement - 4, a segment-relative one R_386_32 with
  stored + displacement. An extern target names its symbol, a segment target that section's
  STT_SECTION symbol.

Refused with Omf2ElfError, before any section is built, each message naming the record kind,
the segment or COMDAT and the offset: a fixup into iterated data (`unmaskable`), iterated
COMDAT data, a frame-number or group target, any fixup location but offset32 (pointer and
selector locations, 16-bit and byte offsets, location 5 outside Easy OMF), a 32-bit field
outside the data or an addend that does not fit in it, a fixup target in a dropped debug
segment, a BSS segment holding initialised bytes or a fixup, an absolute public, a public past
its segment's end or in a dropped debug segment. `convert_file(src, dst)` writes the ELF
atomically only after `convert` has returned. omf.py sizes an Easy OMF location-5 fixup at 4
bytes, so its mask and this conversion cover the same field.
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
    LOC_LOADER_OFFSET16,
    LOC_OFFSET32,
    LOC_POINTER48,
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
_FIELD_BITS = 8 * FIELD_SIZE
_FIELD_MIN = -(1 << (_FIELD_BITS - 1))
_FIELD_MAX = (1 << (_FIELD_BITS - 1)) - 1
PC32_BIAS = -FIELD_SIZE  # a PC32 addend counts from the field's end, the CPU from the next insn

# Fixup location types (TIS OMF 1.1) by name, for the refusal messages.
LOC_BASE = 2  # 16-bit base (selector)
LOC_POINTER32 = 3  # 16:16 far pointer
_LOCATION_NAMES = {
    0: "low byte",
    1: "16-bit offset",
    LOC_BASE: "16-bit base (selector)",
    LOC_POINTER32: "16:16 pointer",
    4: "high byte",
    LOC_LOADER_OFFSET16: "loader-resolved 16-bit offset",
    LOC_OFFSET32: "32-bit offset",
    LOC_POINTER48: "16:32 pointer",
    13: "loader-resolved 32-bit offset",
}
_SELECTOR_LOCATIONS = frozenset({LOC_BASE, LOC_POINTER32, LOC_POINTER48})
_CONVERTED_TARGETS = ("segment", "extern")


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
    """One ELF section to emit: an OMF segment or a COMDAT (`source`)."""

    name: str  # the section name
    where: str  # how errors name it: "segment _TEXT" or "COMDAT 'f_'"
    code: bool
    bss: bool
    source: Segment | Comdat

    @property
    def data(self) -> bytes:
        return self.source.data

    @property
    def length(self) -> int:
        return len(self.source.data)

    @property
    def fixups(self) -> tuple[OMFFixup, ...]:
        return self.source.fixups

    @property
    def segment_index(self) -> int:
        """1-based SEGDEF number of a segment part; 0 for a COMDAT."""
        return self.source.index if isinstance(self.source, Segment) else 0

    @property
    def comdat(self) -> Comdat | None:
        return self.source if isinstance(self.source, Comdat) else None


def _segment_part(seg: Segment) -> _Part:
    return _Part(seg.name, f"segment {seg.name}", seg.is_code, is_bss(seg), seg)


def _comdat_part(cd: Comdat, segments: dict[int, Segment]) -> _Part:
    """A COMDAT's section is named after its segment, or after the COMDAT when it has none."""
    seg = segments.get(cd.segment_index)
    code = seg.is_code if seg else cd.allocation in _CODE_ALLOCATIONS
    return _Part(seg.name if seg else cd.name, f"COMDAT {cd.name!r}", code, False, cd)


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


# ---- refusals: checked before any section is built ----


def _refuse_publics(module: Module) -> None:
    """Absolute publics, publics in a dropped debug segment, publics past their segment."""
    segments = {seg.index: seg for seg in module.segments}
    for pub in module.publics:
        kind = "LPUBDEF" if pub.local else "PUBDEF"
        if pub.segment_index == 0:
            raise Omf2ElfError(
                f"{kind} public {pub.name!r} is absolute (no segment), offset {pub.offset:#x}"
            )
        what = f"{kind} public {pub.name!r} offset {pub.offset:#x}"
        seg = segments[pub.segment_index]
        if is_debug(seg):
            raise Omf2ElfError(f"{what} is in debug segment {seg.name}, which is not emitted")
        if pub.offset > seg.length:
            raise Omf2ElfError(
                f"{what} is past the end of segment {seg.name} ({seg.length:#x} bytes)"
            )


def _refuse_unmaskable(parts: list[_Part]) -> None:
    """A FIXUPP after LIDATA addresses the iterated record, not the bytes it expands to."""
    for part in parts:
        if part.source.unmaskable:
            at = part.source.unmaskable_at or 0
            raise Omf2ElfError(f"{part.where} offset {at:#x}: FIXUPP addresses LIDATA (iterated "
                               "data), so the field it patches cannot be located")  # fmt: skip


def _refuse_iterated_comdats(parts: list[_Part]) -> None:
    for part in parts:
        cd = part.comdat
        if cd is not None and cd.iterated_at is not None:
            raise Omf2ElfError(f"{part.where} offset {cd.iterated_at:#x}: iterated COMDAT data "
                               "(LIDATA blocks) is not supported")  # fmt: skip


def _converts_as_offset32(location: int, easy_omf: bool) -> bool:
    return location == LOC_OFFSET32 or (easy_omf and location == LOC_LOADER_OFFSET16)


def _refuse_location(fx: OMFFixup, where: str, easy_omf: bool) -> None:
    if _converts_as_offset32(fx.location, easy_omf):
        return
    what = f"{where}: FIXUPP location {fx.location} ({_LOCATION_NAMES[fx.location]})"
    if fx.location in _SELECTOR_LOCATIONS:
        raise Omf2ElfError(f"{what} is not supported: selectors and far pointers have no ELF form")
    if fx.location == LOC_LOADER_OFFSET16:
        raise Omf2ElfError(f"{what} converts as a 32-bit offset only under Easy OMF")
    raise Omf2ElfError(f"{what} is not 9 (offset32)")


def _refuse_target(fx: OMFFixup, where: str, emitted: frozenset[int]) -> None:
    if fx.target_kind == "frame":
        raise Omf2ElfError(f"{where}: FIXUPP target is frame number {fx.target_index:#x}, "
                           "not a segment or an extern")  # fmt: skip
    if fx.target_kind not in _CONVERTED_TARGETS:
        raise Omf2ElfError(
            f"{where}: FIXUPP target {fx.target_kind} {fx.target_name!r} is not supported"
        )
    if fx.target_kind == "segment" and fx.target_index not in emitted:
        raise Omf2ElfError(f"{where}: FIXUPP target segment {fx.target_name!r} is not emitted "
                           "(a dropped debug segment)")  # fmt: skip


def _addend(fx: OMFFixup, data: bytes) -> int:
    """The REL addend of the field (TH rule): stored + displacement, - 4 when self-relative."""
    stored = _FIELD.unpack_from(data, fx.offset)[0]
    return stored + fx.displacement + (0 if fx.segment_relative else PC32_BIAS)


def _refuse_field(fx: OMFFixup, where: str, data: bytes) -> None:
    if fx.offset < 0 or fx.offset + FIELD_SIZE > len(data):
        raise Omf2ElfError(
            f"{where}: FIXUPP 32-bit field runs past the data ({len(data):#x} bytes)"
        )
    addend = _addend(fx, data)
    if not _FIELD_MIN <= addend <= _FIELD_MAX:
        raise Omf2ElfError(f"{where}: FIXUPP addend {addend:#x} does not fit in 32 signed bits")


def _refuse_bss(parts: list[_Part]) -> None:
    """A BSS segment becomes NOBITS: it can hold neither initialised bytes nor a fixup."""
    for part in parts:
        if not part.bss:
            continue
        for fx in part.fixups:
            raise Omf2ElfError(f"{part.where} offset {fx.offset:#x}: FIXUPP patches a BSS "
                               "segment, which holds no bytes")  # fmt: skip
        if any(part.data):
            raise Omf2ElfError(f"{part.where}: BSS segment holds initialised bytes")


def _refuse_fixups(parts: list[_Part], easy_omf: bool) -> None:
    emitted = frozenset(p.segment_index for p in parts if p.segment_index)
    for part in parts:
        for fx in part.fixups:
            where = f"{part.where} offset {fx.offset:#x}"
            _refuse_location(fx, where, easy_omf)
            _refuse_target(fx, where, emitted)
            _refuse_field(fx, where, part.data)


def _refuse(module: Module, parts: list[_Part]) -> None:
    """Every refusal, run before any section is built."""
    _refuse_publics(module)
    _refuse_unmaskable(parts)
    _refuse_iterated_comdats(parts)
    _refuse_bss(parts)
    _refuse_fixups(parts, module.easy_omf)


# ---- conversion (everything below runs only on a module `_refuse` accepted) ----


def _section(part: _Part, data: bytes) -> ElfSection:
    if part.code:
        return ElfSection(part.name, data, flags=SHF_ALLOC | SHF_EXECINSTR, align=CODE_ALIGN)
    if part.bss:
        return ElfSection(part.name, kind="nobits", flags=SHF_ALLOC | SHF_WRITE,
                          align=DATA_ALIGN, size=part.length)  # fmt: skip
    return ElfSection(part.name, data, flags=SHF_ALLOC | SHF_WRITE, align=DATA_ALIGN)


def _target(fx: OMFFixup, section_of: dict[int, int]) -> tuple[str, int | None]:
    """(symbol name, target section) of a fixup: an extern's name, or a segment's section."""
    if fx.target_kind == "extern":
        return fx.target_name, None
    return "", section_of[fx.target_index]


def _relocation(
    fx: OMFFixup, part: _Part, section: int, data: bytearray, section_of: dict[int, int]
) -> ElfReloc:
    """Rewrites the fixup's field to its REL addend and returns its relocation (the field and
    the addend were checked by `_refuse_field`)."""
    symbol, target_section = _target(fx, section_of)
    _FIELD.pack_into(data, fx.offset, _addend(fx, part.data))
    rtype = R_386_32 if fx.segment_relative else R_386_PC32
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


def _comdat_symbol(part: _Part, cd: Comdat, section: int) -> ElfSymbol:
    """The COMDAT's own symbol: WEAK when its selection criterion allows duplicates."""
    bind = STB_GLOBAL if cd.selection == COMDAT_SELECT_NO_MATCH else STB_WEAK
    kind = STT_FUNC if part.code else STT_OBJECT
    size = _code_end(part, 0, part.length) if part.code else part.length
    return ElfSymbol(cd.name, section, 0, size, bind=bind, type=kind)


def _symbols(module: Module, parts: list[_Part]) -> list[ElfSymbol]:
    """Publics and COMDATs, then every extern not defined here as an undefined GLOBAL."""
    symbols: list[ElfSymbol] = []
    for i, part in enumerate(parts):
        cd = part.comdat
        if cd is not None:
            symbols.append(_comdat_symbol(part, cd, i))
            continue
        symbols += _sized_publics(module, part, i)
    defined = {s.name for s in symbols}
    symbols += [ElfSymbol(name, None) for name in dict.fromkeys(module.externs)
                if name not in defined]  # fmt: skip
    return symbols


def convert(module: Module) -> ElfObject:
    """The ELF object of one Watcom OMF module."""
    parts = _parts(module)
    _refuse(module, parts)
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
