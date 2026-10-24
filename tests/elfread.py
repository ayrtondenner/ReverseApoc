"""Test-only ELF32 LSB reader: sections, symbols and REL relocations with their implicit addends.

Independent of tools/reverseapoc/elf.py: every field position below is written out here from the
System V gABI and the i386 psABI, so the writer is checked against the format, not against its
own constants.

Sections are addressed by index (the section header number) as well as by name: a writer may
emit several sections with one name (one `_TEXT` per function), and the name form refuses such an
ambiguous name instead of picking one.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

# e_ident
ELF_MAGIC = b"\x7fELF"
EI_CLASS = 4
EI_DATA = 5
EI_NIDENT = 16
ELFCLASS32 = 1
ELFDATA2LSB = 1

# Elf32_Ehdr after e_ident: type, machine, version, entry, phoff, shoff, flags, ehsize,
# phentsize, phnum, shentsize, shnum, shstrndx.
_EHDR = struct.Struct(f"<{EI_NIDENT}sHHIIIIIHHHHHH")
# Elf32_Shdr: name, type, flags, addr, offset, size, link, info, addralign, entsize.
_SHDR = struct.Struct("<IIIIIIIIII")
# Elf32_Sym: name, value, size, info, other, shndx.
_SYM = struct.Struct("<IIIBBH")
# Elf32_Rel: offset, info.
_REL = struct.Struct("<II")
_FIELD = struct.Struct("<i")  # a 32-bit relocated field holds the implicit addend

SHT_SYMTAB = 2
SHT_NOBITS = 8
SHT_REL = 9
SHN_UNDEF = 0
STT_SECTION = 3


@dataclass(frozen=True)
class ElfHeader:
    ei_class: int
    ei_data: int
    e_type: int
    e_machine: int
    e_shentsize: int
    e_shnum: int
    e_shstrndx: int


@dataclass(frozen=True)
class SectionView:
    index: int  # section header number
    name: str
    type: int
    flags: int
    data: bytes  # empty for NOBITS
    size: int  # sh_size (the NOBITS length too)
    link: int
    info: int
    align: int
    entsize: int


@dataclass(frozen=True)
class SymbolView:
    name: str  # a section symbol reports its section's name
    bind: int
    type: int
    section: str | None  # section name, None when undefined
    section_index: int | None  # section header number, None when undefined
    value: int
    size: int


@dataclass(frozen=True)
class RelocView:
    offset: int
    type: int
    symbol: str  # a section symbol reports its section's name
    symbol_type: int
    symbol_section_index: int | None
    addend: int  # read as int32 from the relocated field


@dataclass(frozen=True)
class ElfView:
    header: ElfHeader
    sections: tuple[SectionView, ...]  # every section after the null one, in header order
    symbols: tuple[SymbolView, ...]  # every symbol after the null one, in symtab order
    symtab_info: int  # sh_info of .symtab: index of the first non-local symbol

    def section(self, key: int | str) -> SectionView:
        """The section with this header index, or the only section with this name."""
        if isinstance(key, int):
            for sec in self.sections:
                if sec.index == key:
                    return sec
            raise KeyError(f"no section with index {key}")
        found = [sec for sec in self.sections if sec.name == key]
        if len(found) != 1:
            raise KeyError(f"{len(found)} sections named {key!r}; address it by index")
        return found[0]

    def symbol(self, name: str) -> SymbolView:
        found = [s for s in self.symbols if s.name == name and s.type != STT_SECTION]
        if len(found) != 1:
            raise KeyError(f"{len(found)} symbols named {name!r}")
        return found[0]

    def relocs(self, key: int | str) -> list[RelocView]:
        """Relocations applying to the section with this index (or this unique name)."""
        target = self.section(key)
        rel = [s for s in self.sections if s.type == SHT_REL and s.info == target.index]
        return [r for sec in rel for r in self._entries(sec, target)]

    def _entries(self, rel: SectionView, target: SectionView) -> list[RelocView]:
        out = []
        for pos in range(0, len(rel.data), _REL.size):
            offset, info = _REL.unpack_from(rel.data, pos)
            index = info >> 8
            if not 0 < index <= len(self.symbols):  # 0 is the null symbol, not in self.symbols
                raise ValueError(f"{rel.name} entry at {pos:#x}: symbol index {index} is invalid")
            sym = self.symbols[index - 1]
            addend = _FIELD.unpack_from(target.data, offset)[0]
            out.append(RelocView(offset, info & 0xFF, sym.name, sym.type,
                                 sym.section_index, addend))  # fmt: skip
        return out


def _cstr(table: bytes, pos: int) -> str:
    return table[pos : table.index(b"\0", pos)].decode("ascii")


def read_elf(data: bytes) -> ElfView:
    if data[: len(ELF_MAGIC)] != ELF_MAGIC:
        raise ValueError("not an ELF file")
    ident, e_type, e_machine, _, _, _, shoff, _, _, _, _, shentsize, shnum, shstrndx = (
        _EHDR.unpack_from(data, 0)
    )
    header = ElfHeader(ident[EI_CLASS], ident[EI_DATA], e_type, e_machine, shentsize, shnum,
                       shstrndx)  # fmt: skip
    raw = [_SHDR.unpack_from(data, shoff + i * shentsize) for i in range(shnum)]
    names = data[raw[shstrndx][4] : raw[shstrndx][4] + raw[shstrndx][5]]
    sections = []
    for i, (name, stype, flags, _, offset, size, link, info, align, entsize) in enumerate(raw):
        if i == 0:
            continue
        body = b"" if stype == SHT_NOBITS else bytes(data[offset : offset + size])
        sections.append(SectionView(i, _cstr(names, name), stype, flags, body, size, link, info,
                                    align, entsize))  # fmt: skip
    by_index = {s.index: s for s in sections}
    symtab = next(s for s in sections if s.type == SHT_SYMTAB)
    strtab = by_index[symtab.link].data
    symbols = []
    for pos in range(_SYM.size, len(symtab.data), _SYM.size):  # skip the null symbol
        name, value, size, info, _, shndx = _SYM.unpack_from(symtab.data, pos)
        sec = None if shndx == SHN_UNDEF else by_index[shndx]
        stype = info & 0x0F
        text = sec.name if stype == STT_SECTION and sec is not None else _cstr(strtab, name)
        symbols.append(SymbolView(text, info >> 4, stype, None if sec is None else sec.name,
                                  None if sec is None else sec.index, value, size))  # fmt: skip
    return ElfView(header, tuple(sections), tuple(symbols), symtab.info)
