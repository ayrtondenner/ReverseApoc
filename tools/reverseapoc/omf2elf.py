# Derived from Theme Hospital decomp tools/omf2elf.py (GPLv3), https://github.com/matteo-pacini/theme-hospital-decomp
"""Watcom OMF object -> ELF32 relocatable object, the base side of every objdiff pair (D-13).

Built on `omf.read_object`, which already parses the records; nothing here re-reads them.
`convert(module)` maps the module's code segments to ELF sections named like their SEGDEF, its
publics to GLOBAL STT_FUNC symbols sized to the next public or the segment end, its externs to
undefined GLOBAL symbols, and each location-9 (offset32) fixup to one REL relocation by the
Theme Hospital addend rule: a self-relative fixup becomes R_386_PC32 with the field rewritten to
stored + displacement - 4, a segment-relative one R_386_32 with stored + displacement.

`convert_file(src, dst)` reads an object, converts it and writes the ELF atomically.
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
    STT_FUNC,
    ElfObject,
    ElfReloc,
    ElfSection,
    ElfSymbol,
    write_elf,
)
from .omf import LOC_OFFSET32, REC_THEADR, Module, OMFError, OMFFixup, Segment, read_object
from .splice import _write_atomic

CODE_ALIGN = 16
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


def _sizes(module: Module, seg: Segment) -> list[tuple[str, int, int]]:
    """(name, offset, size) of each public in `seg`, sized to the next public or the end."""
    offsets = sorted({p.offset for p in module.publics if p.segment_index == seg.index})
    ends = dict(zip(offsets, [*offsets[1:], seg.length], strict=True))
    return [(p.name, p.offset, ends[p.offset] - p.offset)
            for p in module.publics if p.segment_index == seg.index]  # fmt: skip


def _relocation(fx: OMFFixup, seg: Segment, data: bytearray, section: int) -> ElfReloc:
    """Rewrites the fixup's field to its REL addend and returns its relocation."""
    if fx.location != LOC_OFFSET32:
        raise Omf2ElfError(
            f"segment {seg.name} offset {fx.offset:#x}: fixup location {fx.location} is not 9 "
            "(offset32)"
        )
    if fx.target_kind != "extern":
        raise Omf2ElfError(
            f"segment {seg.name} offset {fx.offset:#x}: fixup target {fx.target_kind} "
            f"{fx.target_name!r} is not supported"
        )
    relative = not fx.segment_relative
    stored = _FIELD.unpack_from(data, fx.offset)[0]
    _FIELD.pack_into(data, fx.offset, stored + fx.displacement + (PC32_BIAS if relative else 0))
    rtype = R_386_PC32 if relative else R_386_32
    return ElfReloc(section, fx.offset, rtype, symbol=fx.target_name)


def convert(module: Module) -> ElfObject:
    """The ELF object of one Watcom OMF module."""
    sections: list[ElfSection] = []
    symbols: list[ElfSymbol] = []
    relocs: list[ElfReloc] = []
    for seg in module.segments:
        if not seg.is_code:
            continue
        index = len(sections)
        data = bytearray(seg.data)
        relocs += [_relocation(fx, seg, data, index) for fx in seg.fixups]
        sections.append(ElfSection(seg.name, bytes(data), flags=SHF_ALLOC | SHF_EXECINSTR,
                                   align=CODE_ALIGN))  # fmt: skip
        symbols += [ElfSymbol(name, index, offset, size, type=STT_FUNC)
                    for name, offset, size in _sizes(module, seg)]  # fmt: skip
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
