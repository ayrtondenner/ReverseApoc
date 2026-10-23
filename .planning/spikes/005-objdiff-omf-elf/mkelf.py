"""Spike 005: a minimal ELF32 writer, a Watcom OMF -> ELF converter and an LE target cut.

Spike-local (see .planning/spikes/CONVENTIONS.md). The production modules come in plans 05-02
(omf2elf), 05-06 and 05-08 (target writer). The addend rule follows Theme Hospital's
tools/omf2elf.py convert() (GPLv3): a self-relative field becomes R_386_PC32 with the field
rewritten to stored + displacement - 4, a segment-relative one R_386_32 with stored +
displacement. Relocations are REL, so the addend lives in the field bytes.

Target bytes come from le.LE.load_flat(relocate=False) and relocations from le.LE.fixups() only
(P4: never Ghidra, never relocate=True).
"""

from __future__ import annotations

import struct
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from reverseapoc.le import LE, SRC_OFF32
from reverseapoc.omf import Module, OMFFixup, Segment

# ---- ELF32 constants (System V gABI, i386 psABI) ----

ELFMAG = b"\x7fELF"
ELFCLASS32 = 1
ELFDATA2LSB = 1
EV_CURRENT = 1
ELFOSABI_NONE = 0
ET_REL = 1
EM_386 = 3

SHN_UNDEF = 0
SHT_NULL = 0
SHT_PROGBITS = 1
SHT_SYMTAB = 2
SHT_STRTAB = 3
SHT_REL = 9
SHF_ALLOC = 2
SHF_EXECINSTR = 4

STB_LOCAL = 0
STB_GLOBAL = 1
STT_NOTYPE = 0
STT_FUNC = 2
STT_SECTION = 3
STV_DEFAULT = 0

R_386_32 = 1
R_386_PC32 = 2

# e_ident: magic, class, data, version, OS ABI, then zero padding up to EI_NIDENT bytes.
EI_NIDENT = 16
_IDENT = struct.Struct("<4sBBBB")
# Elf32_Ehdr after e_ident: e_type, e_machine, e_version, e_entry, e_phoff, e_shoff, e_flags,
# e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx.
_EHDR = struct.Struct(f"<{EI_NIDENT}sHHIIIIIHHHHHH")
# Elf32_Shdr: sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size, sh_link, sh_info,
# sh_addralign, sh_entsize.
_SHDR = struct.Struct("<IIIIIIIIII")
# Elf32_Sym: st_name, st_value, st_size, st_info, st_other, st_shndx.
_SYM = struct.Struct("<IIIBBH")
# Elf32_Rel: r_offset, r_info.
_REL = struct.Struct("<II")
EHDR_SIZE = _EHDR.size
SHDR_SIZE = _SHDR.size
SYM_SIZE = _SYM.size
REL_SIZE = _REL.size
R_SYM_SHIFT = 8  # ELF32_R_INFO(sym, type) = (sym << 8) | type
ST_BIND_SHIFT = 4  # ELF32_ST_INFO(bind, type) = (bind << 4) | type

CODE_ALIGN = 16
TABLE_ALIGN = 4
FIELD = struct.Struct("<i")  # a 32-bit relocated field
FIELD_SIZE = FIELD.size
PC32_ADDEND = -FIELD_SIZE  # REL addend of a call rel32 aimed at the symbol itself
REL_PREFIX = ".rel"


@dataclass(frozen=True)
class Symbol:
    name: str  # "" for a section symbol
    section: int | None  # index into the section list, None when undefined
    value: int = 0
    size: int = 0
    bind: int = STB_GLOBAL
    kind: int = STT_NOTYPE


@dataclass(frozen=True)
class Reloc:
    section: int  # index into the section list
    offset: int
    rtype: int
    symbol: int  # index into the symbol list


@dataclass
class ElfParts:
    """What write_elf takes, kept mutable so a plant can rename a symbol or edit a field."""

    sections: list[tuple[str, bytearray]]
    symbols: list[Symbol]
    relocs: list[Reloc] = field(default_factory=list)

    def symbol_index(self, name: str) -> int:
        """The index of the named symbol, adding an undefined GLOBAL STT_NOTYPE one if new."""
        for i, sym in enumerate(self.symbols):
            if sym.name == name and sym.kind != STT_SECTION:
                return i
        self.symbols.append(Symbol(name, None))
        return len(self.symbols) - 1

    def to_bytes(self) -> bytes:
        return write_elf(self.sections, self.symbols, self.relocs)


def function_parts(
    section_name: str, data: bytearray, name: str, value: int, size: int
) -> ElfParts:
    """One code section holding one GLOBAL STT_FUNC, plus the section's own symbol."""
    section = Symbol("", 0, bind=STB_LOCAL, kind=STT_SECTION)
    return ElfParts([(section_name, data)], [section, Symbol(name, 0, value, size, kind=STT_FUNC)])


class _Strtab:
    def __init__(self) -> None:
        self.data = bytearray(b"\0")
        self.index: dict[str, int] = {"": 0}

    def add(self, name: str) -> int:
        if name not in self.index:
            self.index[name] = len(self.data)
            self.data += name.encode("ascii") + b"\0"
        return self.index[name]


def _align(buf: bytearray, alignment: int) -> None:
    buf += b"\0" * (-len(buf) % alignment)


def write_elf(
    sections: list[tuple[str, bytes | bytearray]],
    symbols: list[Symbol],
    relocs: Iterable[Reloc],
) -> bytes:
    """An ELF32 LSB ET_REL EM_386 object: null, each code section, each `.rel<name>`, .symtab,
    .strtab, .shstrtab. Locals come first in the symtab; its sh_info is the first global."""
    relocs = list(relocs)
    order = sorted(range(len(symbols)), key=lambda i: symbols[i].bind != STB_LOCAL)
    sym_pos = {old: new + 1 for new, old in enumerate(order)}  # +1: the null symbol
    first_global = 1 + sum(1 for s in symbols if s.bind == STB_LOCAL)

    with_rels = [i for i in range(len(sections)) if any(r.section == i for r in relocs)]
    code_index = {i: 1 + i for i in range(len(sections))}
    symtab_index = 1 + len(sections) + len(with_rels)
    strtab_index, shstrtab_index = symtab_index + 1, symtab_index + 2

    strtab, shstrtab = _Strtab(), _Strtab()
    symtab = bytearray(SYM_SIZE)  # the null symbol
    for old in order:
        s = symbols[old]
        shndx = SHN_UNDEF if s.section is None else code_index[s.section]
        info = (s.bind << ST_BIND_SHIFT) | s.kind
        symtab += _SYM.pack(strtab.add(s.name), s.value, s.size, info, STV_DEFAULT, shndx)

    out = bytearray(EHDR_SIZE)
    headers = [bytes(SHDR_SIZE)]

    def emit(name, stype, flags, data, link=0, info=0, align=1, entsize=0):
        _align(out, max(align, 1))
        offset = len(out)
        out.extend(data)
        headers.append(_SHDR.pack(shstrtab.add(name), stype, flags, 0, offset, len(data), link,
                                  info, align, entsize))  # fmt: skip

    for name, data in sections:
        emit(name, SHT_PROGBITS, SHF_ALLOC | SHF_EXECINSTR, data, align=CODE_ALIGN)
    for i in with_rels:
        body = b"".join(
            _REL.pack(r.offset, (sym_pos[r.symbol] << R_SYM_SHIFT) | r.rtype)
            for r in sorted(relocs, key=lambda r: r.offset)
            if r.section == i
        )
        emit(REL_PREFIX + sections[i][0], SHT_REL, 0, body, link=symtab_index,
             info=code_index[i], align=TABLE_ALIGN, entsize=REL_SIZE)  # fmt: skip
    emit(".symtab", SHT_SYMTAB, 0, symtab, link=strtab_index, info=first_global,
         align=TABLE_ALIGN, entsize=SYM_SIZE)  # fmt: skip
    emit(".strtab", SHT_STRTAB, 0, strtab.data)
    shstrtab.add(".shstrtab")
    emit(".shstrtab", SHT_STRTAB, 0, shstrtab.data)
    assert len(headers) == shstrtab_index + 1

    _align(out, TABLE_ALIGN)
    shoff = len(out)
    for h in headers:
        out += h
    ident = _IDENT.pack(ELFMAG, ELFCLASS32, ELFDATA2LSB, EV_CURRENT, ELFOSABI_NONE)
    out[:EHDR_SIZE] = _EHDR.pack(ident, ET_REL, EM_386, EV_CURRENT, 0, 0, shoff, 0, EHDR_SIZE,
                                 0, 0, SHDR_SIZE, len(headers), shstrtab_index)  # fmt: skip
    return bytes(out)


# ---- OMF -> ELF (spike-local omf2elf) ----


def find_public(module: Module, name: str) -> tuple[Segment, int]:
    """The segment holding public `name` and the public's offset in it."""
    for pub in module.publics:
        if pub.name == name:
            for seg in module.segments:
                if seg.index == pub.segment_index:
                    return seg, pub.offset
    raise ValueError(f"public {name} not found in module {module.name}")


def relocation_of(fx: OMFFixup) -> tuple[int, int]:
    """(ELF type, REL addend minus the stored field) for an OMF offset32 fixup (TH rule)."""
    if fx.size != FIELD_SIZE:
        raise ValueError(f"fixup at {fx.offset:#x}: {fx.size}-byte field, spike handles 4 only")
    if fx.segment_relative:
        return R_386_32, fx.displacement
    return R_386_PC32, fx.displacement + PC32_ADDEND


def from_omf(module: Module, public_name: str) -> ElfParts:
    """The code segment holding `public_name` as one section named like the segment, the public
    as a GLOBAL STT_FUNC sized to the segment, every fixup as REL with the TH addend rule."""
    seg, pub_offset = find_public(module, public_name)
    data = bytearray(seg.data)
    parts = function_parts(seg.name, data, public_name, pub_offset, seg.length - pub_offset)
    for fx in seg.fixups:
        rtype, extra = relocation_of(fx)
        stored = FIELD.unpack_from(data, fx.offset)[0]
        FIELD.pack_into(data, fx.offset, stored + extra)
        parts.relocs.append(Reloc(0, fx.offset, rtype, _omf_target(parts, seg, fx)))
    return parts


def _omf_target(parts: ElfParts, seg: Segment, fx: OMFFixup) -> int:
    if fx.target_kind == "extern":
        return parts.symbol_index(fx.target_name)
    if fx.target_kind == "segment" and fx.target_index == seg.index:
        return 0  # the section symbol of the one emitted section
    raise ValueError(
        f"fixup at {fx.offset:#x}: target {fx.target_kind} {fx.target_name} is not emitted "
        "by the spike converter"
    )


# ---- LE -> target ELF (spike-local target cut) ----


def _name_at(names_by_address: Mapping[int, str], address: int, field_va: int) -> str:
    try:
        return names_by_address[address]
    except KeyError:
        raise ValueError(f"field {field_va:#010x}: no name for address {address:#010x}") from None


def cut_target(
    le: LE,
    start: int,
    end: int,
    name: str,
    names_by_address: Mapping[int, str],
    call_fields: Iterable[int],
    *,
    section_name: str = "_TEXT",
) -> ElfParts:
    """[start, end) of the LE as one section with one GLOBAL STT_FUNC `name`. Every LE off32
    fixup in range becomes R_386_32 against the name of its target (field rewritten to 0, the
    raw field holds target_off). Every VA in `call_fields` becomes R_386_PC32 against the name
    of the call's destination (field rewritten to -4)."""
    flat = le.load_flat(relocate=False)
    data = bytearray(flat[start:end])
    parts = function_parts(section_name, data, name, 0, end - start)
    for fx in le.fixups():
        if not start <= fx.src_va < end:
            continue
        if fx.kind != SRC_OFF32:
            raise ValueError(f"LE fixup at {fx.src_va:#010x}: kind {fx.kind_name} not handled")
        sym = parts.symbol_index(_name_at(names_by_address, fx.target_va, fx.src_va))
        FIELD.pack_into(data, fx.src_va - start, 0)
        parts.relocs.append(Reloc(0, fx.src_va - start, R_386_32, sym))
    for va in call_fields:
        rel = FIELD.unpack_from(flat, va)[0]
        dest = va + FIELD_SIZE + rel
        sym = parts.symbol_index(_name_at(names_by_address, dest, va))
        FIELD.pack_into(data, va - start, PC32_ADDEND)
        parts.relocs.append(Reloc(0, va - start, R_386_PC32, sym))
    return parts
