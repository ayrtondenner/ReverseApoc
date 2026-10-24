"""ELF32 LSB relocatable object writer for i386 (System V gABI, i386 psABI).

`write_elf(ElfObject)` lays a file out as objdiff 3.8.2 accepted it in spike 005: the ELF header,
then the sections `null, <data sections in order>, .rel<name> for each relocated section,
.symtab, .strtab, .shstrtab`, then the section header table. Each `.rel<name>` links to the
symtab and names the section it relocates in sh_info; the symtab's sh_info is its first
non-local symbol.

The symtab holds the null symbol, one LOCAL STT_SECTION symbol per data section (in section
order), the caller's LOCAL symbols, then its GLOBAL and WEAK ones. Relocations are REL: the
addend is the field's own content, so callers write it into the section bytes first.

A relocation names its symbol (`ElfReloc.symbol`) or a section whose STT_SECTION symbol it uses
(`ElfReloc.target_section`). Two GLOBAL symbols of one name, a relocation naming an unknown or
ambiguous symbol, a relocated field outside its section and a relocation on a NOBITS section
raise ElfError. Several sections may share a name (one `_TEXT` per function).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Literal

# e_ident: magic, then one byte per field, zero padded to EI_NIDENT bytes.
ELFMAG = b"\x7fELF"
EI_CLASS = 4
EI_DATA = 5
EI_VERSION = 6
EI_OSABI = 7
EI_NIDENT = 16
ELFCLASS32 = 1
ELFDATA2LSB = 1
EV_CURRENT = 1
ELFOSABI_NONE = 0

ET_REL = 1
EM_386 = 3

# Section header types and flags.
SHN_UNDEF = 0
SHT_NULL = 0
SHT_PROGBITS = 1
SHT_SYMTAB = 2
SHT_STRTAB = 3
SHT_NOBITS = 8
SHT_REL = 9
SHF_WRITE = 1
SHF_ALLOC = 2
SHF_EXECINSTR = 4

# Symbol binding and type: st_info = bind << ST_BIND_SHIFT | type.
STB_LOCAL = 0
STB_GLOBAL = 1
STB_WEAK = 2
STT_NOTYPE = 0
STT_OBJECT = 1
STT_FUNC = 2
STT_SECTION = 3
STV_DEFAULT = 0
ST_BIND_SHIFT = 4

# i386 relocation types: r_info = symbol index << R_SYM_SHIFT | type.
R_386_32 = 1
R_386_PC32 = 2
R_SYM_SHIFT = 8

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
FIELD_SIZE = 4  # both R_386_32 and R_386_PC32 patch a 32-bit field

NULL_ENTRIES = 1  # section header 0 and symbol 0 are the reserved null entries
TABLE_ALIGN = 4  # .rel and .symtab entries are 32-bit words
REL_PREFIX = ".rel"
SYMTAB_NAME = ".symtab"
STRTAB_NAME = ".strtab"
SHSTRTAB_NAME = ".shstrtab"


class ElfError(ValueError):
    """The object cannot be written as a well-formed ELF relocatable."""


@dataclass(frozen=True)
class ElfSection:
    name: str
    data: bytes = b""  # empty for NOBITS
    kind: Literal["progbits", "nobits"] = "progbits"
    flags: int = SHF_ALLOC
    align: int = 1
    size: int = 0  # NOBITS only: the length the section reserves

    @property
    def byte_size(self) -> int:
        return self.size if self.kind == "nobits" else len(self.data)


@dataclass(frozen=True)
class ElfSymbol:
    name: str
    section: int | None  # index into ElfObject.sections, None when undefined
    value: int = 0
    size: int = 0
    bind: int = STB_GLOBAL
    type: int = STT_NOTYPE


@dataclass(frozen=True)
class ElfReloc:
    section: int  # index into ElfObject.sections: the section the field is in
    offset: int  # field offset in that section
    type: int  # R_386_32 or R_386_PC32
    symbol: str = ""  # a symbol of ElfObject.symbols, by name ...
    target_section: int | None = None  # ... or the STT_SECTION symbol of this section


@dataclass(frozen=True)
class ElfObject:
    sections: tuple[ElfSection, ...]
    symbols: tuple[ElfSymbol, ...] = ()
    relocs: tuple[ElfReloc, ...] = ()


class _Strtab:
    def __init__(self) -> None:
        self.data = bytearray(b"\0")
        self.offsets: dict[str, int] = {"": 0}

    def add(self, name: str) -> int:
        if name not in self.offsets:
            self.offsets[name] = len(self.data)
            self.data += name.encode("latin-1") + b"\0"
        return self.offsets[name]


def _check_symbols(obj: ElfObject) -> None:
    seen: set[str] = set()
    for sym in obj.symbols:
        if sym.section is not None and not 0 <= sym.section < len(obj.sections):
            raise ElfError(f"symbol {sym.name!r}: section index {sym.section} out of range")
        if sym.bind == STB_LOCAL:
            continue
        if sym.name in seen:
            raise ElfError(f"duplicate global symbol {sym.name!r}")
        seen.add(sym.name)


def _check_reloc(obj: ElfObject, rel: ElfReloc) -> None:
    if not 0 <= rel.section < len(obj.sections):
        raise ElfError(f"relocation at {rel.offset:#x}: section index {rel.section} out of range")
    sec = obj.sections[rel.section]
    where = f"relocation at {sec.name}+{rel.offset:#x}"
    if sec.kind == "nobits":
        raise ElfError(f"{where}: {sec.name} is NOBITS and has no field to relocate")
    if rel.offset < 0 or rel.offset + FIELD_SIZE > len(sec.data):
        raise ElfError(f"{where}: field runs outside the section ({len(sec.data):#x} bytes)")
    if rel.target_section is not None and not 0 <= rel.target_section < len(obj.sections):
        raise ElfError(f"{where}: target section index {rel.target_section} out of range")


@dataclass
class _Layout:
    """Section header numbers and symtab positions, computed before anything is written."""

    obj: ElfObject
    rel_sections: list[int] = field(default_factory=list)  # data sections that have relocations
    symbol_order: list[int] = field(default_factory=list)  # obj.symbols indexes, locals first
    names: dict[str, list[int]] = field(default_factory=dict)  # name -> symtab positions

    def __post_init__(self) -> None:
        relocated = {r.section for r in self.obj.relocs}
        self.rel_sections = [i for i in range(len(self.obj.sections)) if i in relocated]
        syms = self.obj.symbols
        self.symbol_order = sorted(range(len(syms)), key=lambda i: syms[i].bind != STB_LOCAL)
        for pos, old in enumerate(self.symbol_order):
            self.names.setdefault(syms[old].name, []).append(self.first_symbol + pos)

    def shndx(self, section: int) -> int:
        return NULL_ENTRIES + section  # after the null section

    @property
    def symtab_index(self) -> int:
        return NULL_ENTRIES + len(self.obj.sections) + len(self.rel_sections)

    @property
    def first_symbol(self) -> int:
        return NULL_ENTRIES + len(self.obj.sections)  # after the null and the section symbols

    @property
    def first_global(self) -> int:
        locals_ = sum(1 for s in self.obj.symbols if s.bind == STB_LOCAL)
        return self.first_symbol + locals_

    def symbol_index(self, rel: ElfReloc) -> int:
        if rel.target_section is not None:
            return NULL_ENTRIES + rel.target_section  # section symbols follow the null one
        found = self.names.get(rel.symbol, [])
        if len(found) != 1:
            what = "unknown" if not found else "ambiguous"
            raise ElfError(f"relocation at {rel.offset:#x}: {what} symbol {rel.symbol!r}")
        return found[0]


def _symtab(layout: _Layout, strtab: _Strtab) -> bytes:
    out = bytearray(SYM_SIZE)  # the null symbol
    for i in range(len(layout.obj.sections)):
        info = STB_LOCAL << ST_BIND_SHIFT | STT_SECTION
        out += _SYM.pack(0, 0, 0, info, STV_DEFAULT, layout.shndx(i))
    for old in layout.symbol_order:
        sym = layout.obj.symbols[old]
        shndx = SHN_UNDEF if sym.section is None else layout.shndx(sym.section)
        info = sym.bind << ST_BIND_SHIFT | sym.type
        out += _SYM.pack(strtab.add(sym.name), sym.value, sym.size, info, STV_DEFAULT, shndx)
    return bytes(out)


def _rel_body(layout: _Layout, section: int) -> bytes:
    rels = sorted((r for r in layout.obj.relocs if r.section == section), key=lambda r: r.offset)
    return b"".join(
        _REL.pack(r.offset, layout.symbol_index(r) << R_SYM_SHIFT | r.type) for r in rels
    )


class _Writer:
    def __init__(self) -> None:
        self.out = bytearray(EHDR_SIZE)
        self.headers = [bytes(SHDR_SIZE)]  # the null section
        self.shstrtab = _Strtab()

    def emit(self, name: str, stype: int, data: bytes, *, flags: int = 0, size: int | None = None,
             link: int = 0, info: int = 0, align: int = 1, entsize: int = 0) -> None:  # fmt: skip
        align = max(align, 1)
        self.out += bytes(-len(self.out) % align)
        offset = len(self.out)
        self.out += data
        length = len(data) if size is None else size
        self.headers.append(_SHDR.pack(self.shstrtab.add(name), stype, flags, 0, offset, length,
                                       link, info, align, entsize))  # fmt: skip


def write_elf(obj: ElfObject) -> bytes:
    """The ELF32 LSB ET_REL EM_386 bytes of `obj`."""
    _check_symbols(obj)
    for rel in obj.relocs:
        _check_reloc(obj, rel)
    layout = _Layout(obj)
    strtab = _Strtab()
    symtab = _symtab(layout, strtab)
    w = _Writer()
    for sec in obj.sections:
        if sec.kind == "nobits":
            w.emit(sec.name, SHT_NOBITS, b"", flags=sec.flags, size=sec.size, align=sec.align)
        else:
            w.emit(sec.name, SHT_PROGBITS, sec.data, flags=sec.flags, align=sec.align)
    for i in layout.rel_sections:
        w.emit(REL_PREFIX + obj.sections[i].name, SHT_REL, _rel_body(layout, i),
               link=layout.symtab_index, info=layout.shndx(i), align=TABLE_ALIGN,
               entsize=REL_SIZE)  # fmt: skip
    strtab_index = layout.symtab_index + 1  # .strtab follows .symtab, .shstrtab follows it
    w.emit(SYMTAB_NAME, SHT_SYMTAB, symtab, link=strtab_index, info=layout.first_global,
           align=TABLE_ALIGN, entsize=SYM_SIZE)  # fmt: skip
    w.emit(STRTAB_NAME, SHT_STRTAB, bytes(strtab.data))
    shstrtab_index = strtab_index + 1
    w.shstrtab.add(SHSTRTAB_NAME)
    w.emit(SHSTRTAB_NAME, SHT_STRTAB, bytes(w.shstrtab.data))

    w.out += bytes(-len(w.out) % TABLE_ALIGN)
    shoff = len(w.out)
    for header in w.headers:
        w.out += header
    ident = bytearray(EI_NIDENT)
    ident[: len(ELFMAG)] = ELFMAG
    ident[EI_CLASS] = ELFCLASS32
    ident[EI_DATA] = ELFDATA2LSB
    ident[EI_VERSION] = EV_CURRENT
    ident[EI_OSABI] = ELFOSABI_NONE
    w.out[:EHDR_SIZE] = _EHDR.pack(bytes(ident), ET_REL, EM_386, EV_CURRENT, 0, 0, shoff, 0,
                                   EHDR_SIZE, 0, 0, SHDR_SIZE, len(w.headers),
                                   shstrtab_index)  # fmt: skip
    return bytes(w.out)
