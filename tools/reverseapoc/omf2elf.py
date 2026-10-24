# Derived from Theme Hospital decomp tools/omf2elf.py (GPLv3), https://github.com/matteo-pacini/theme-hospital-decomp
"""Watcom OMF object -> ELF32 relocatable object, the base side of every objdiff pair (D-13).

Built on `omf.read_object`, which already parses the records (BAKPAT applied, LIDATA expanded,
FIXUPP threads resolved); nothing here re-reads them. `convert(module)` maps:

- each SEGDEF to one section named like the SEGDEF (objdiff pairs on the section base name):
  a CODE class to PROGBITS ALLOC+EXECINSTR, a class ending in BSS to NOBITS ALLOC+WRITE with
  the segment length, any other class to PROGBITS ALLOC+WRITE; classes starting with DEB
  (DEBSYM, DEBTYP) are dropped with their fixups;
- each public to a GLOBAL symbol, STT_FUNC in code and STT_OBJECT elsewhere, sized to the next
  public of its segment or the segment end;
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
    STT_FUNC,
    STT_OBJECT,
    ElfObject,
    ElfReloc,
    ElfSection,
    ElfSymbol,
    write_elf,
)
from .omf import LOC_OFFSET32, REC_THEADR, Module, OMFError, OMFFixup, Segment, read_object
from .splice import _write_atomic

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


def _section(seg: Segment, data: bytes) -> ElfSection:
    if seg.is_code:
        return ElfSection(seg.name, data, flags=SHF_ALLOC | SHF_EXECINSTR, align=CODE_ALIGN)
    if is_bss(seg):
        if any(data):
            raise Omf2ElfError(f"segment {seg.name}: BSS segment holds initialised bytes")
        return ElfSection(seg.name, kind="nobits", flags=SHF_ALLOC | SHF_WRITE,
                          align=DATA_ALIGN, size=seg.length)  # fmt: skip
    return ElfSection(seg.name, data, flags=SHF_ALLOC | SHF_WRITE, align=DATA_ALIGN)


def _publics(module: Module, seg: Segment, section: int) -> list[ElfSymbol]:
    """A symbol per public in `seg`, sized to the next public or the segment end."""
    own = [p for p in module.publics if p.segment_index == seg.index]
    offsets = sorted({p.offset for p in own})
    ends = dict(zip(offsets, [*offsets[1:], seg.length], strict=False))  # [length] if no public
    kind = STT_FUNC if seg.is_code else STT_OBJECT
    return [ElfSymbol(p.name, section, p.offset, ends[p.offset] - p.offset, type=kind)
            for p in own]  # fmt: skip


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
    fx: OMFFixup, seg: Segment, data: bytearray, section_of: dict[int, int]
) -> ElfReloc:
    """Rewrites the fixup's field to its REL addend and returns its relocation."""
    where = f"segment {seg.name} offset {fx.offset:#x}"
    if fx.location != LOC_OFFSET32:
        raise Omf2ElfError(f"{where}: fixup location {fx.location} is not 9 (offset32)")
    symbol, target_section = _target(fx, where, section_of)
    relative = not fx.segment_relative
    stored = _FIELD.unpack_from(data, fx.offset)[0]
    _FIELD.pack_into(data, fx.offset, stored + fx.displacement + (PC32_BIAS if relative else 0))
    rtype = R_386_PC32 if relative else R_386_32
    return ElfReloc(section_of[seg.index], fx.offset, rtype, symbol, target_section)


def _check_publics(module: Module) -> None:
    for pub in module.publics:
        if pub.segment_index == 0:
            raise Omf2ElfError(f"public {pub.name!r} is absolute (no segment)")


def convert(module: Module) -> ElfObject:
    """The ELF object of one Watcom OMF module."""
    _check_publics(module)
    emitted = [seg for seg in module.segments if not is_debug(seg)]
    section_of = {seg.index: i for i, seg in enumerate(emitted)}
    sections: list[ElfSection] = []
    symbols: list[ElfSymbol] = []
    relocs: list[ElfReloc] = []
    for seg in emitted:
        if seg.unmaskable:
            raise Omf2ElfError(f"segment {seg.name}: a fixup addresses iterated data")
        data = bytearray(seg.data)
        relocs += [_relocation(fx, seg, data, section_of) for fx in seg.fixups]
        sections.append(_section(seg, bytes(data)))
        symbols += _publics(module, seg, section_of[seg.index])
    defined = {s.name for s in symbols}
    symbols += [ElfSymbol(name, None) for name in dict.fromkeys(module.externs)
                if name not in defined]  # fmt: skip
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
