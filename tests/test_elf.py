"""ELF32 relocatable writer, read back with tests/elfread.py. Section contents, names and values
are made up; the expected header values are written out from the gABI/psABI here."""

from __future__ import annotations

import pytest

from elfread import read_elf
from reverseapoc.elf import (
    R_386_32,
    R_386_PC32,
    SHF_ALLOC,
    SHF_EXECINSTR,
    STB_LOCAL,
    STT_FUNC,
    ElfError,
    ElfObject,
    ElfReloc,
    ElfSection,
    ElfSymbol,
    write_elf,
)

CODE = bytes.fromhex("a100000000e800000000c3")  # mov eax,[abs32]; call rel32; ret
TEXT = ElfSection("_TEXT", CODE, flags=SHF_ALLOC | SHF_EXECINSTR, align=16)
DATA = ElfSection("_DATA", bytes(8))


def sample() -> ElfObject:
    return ElfObject(
        (TEXT, DATA),
        (
            ElfSymbol("f_", 0, 0, len(CODE), type=STT_FUNC),
            ElfSymbol("static_", 1, 4, 4, bind=STB_LOCAL),
            ElfSymbol("ext_", None),
        ),
        (
            ElfReloc(0, 6, R_386_PC32, symbol="ext_"),
            ElfReloc(0, 1, R_386_32, target_section=1),
        ),
    )


def test_header_names_an_elf32_lsb_i386_relocatable():
    elf = read_elf(write_elf(sample()))
    h = elf.header
    assert (h.ei_class, h.ei_data, h.e_type, h.e_machine) == (1, 1, 1, 3)  # 32, LSB, REL, 386
    assert elf.section(h.e_shstrndx).name == ".shstrtab"
    assert h.e_shnum == len(elf.sections) + 1  # plus the null section


def test_section_order_and_links():
    elf = read_elf(write_elf(sample()))
    names = [s.name for s in elf.sections]
    assert names == ["_TEXT", "_DATA", ".rel_TEXT", ".symtab", ".strtab", ".shstrtab"]
    rel, symtab = elf.section(".rel_TEXT"), elf.section(".symtab")
    assert (rel.link, rel.info) == (symtab.index, elf.section("_TEXT").index)
    assert elf.section(symtab.link).name == ".strtab"


def test_locals_precede_globals_and_symtab_info_is_the_first_global():
    elf = read_elf(write_elf(sample()))
    first_global = elf.symtab_info - 1  # ElfView.symbols leaves out the null symbol
    assert all(s.bind == STB_LOCAL for s in elf.symbols[:first_global])
    assert all(s.bind != STB_LOCAL for s in elf.symbols[first_global:])
    assert [s.name for s in elf.symbols[:2]] == ["_TEXT", "_DATA"]  # section symbols first
    assert elf.symbol("static_").section == "_DATA"


def test_relocations_read_back_with_their_targets():
    obj = sample()
    elf = read_elf(write_elf(obj))
    got = [(r.offset, r.type, r.symbol, r.symbol_section_index) for r in elf.relocs("_TEXT")]
    data_index = elf.section("_DATA").index
    assert got == [(1, R_386_32, "_DATA", data_index), (6, R_386_PC32, "ext_", None)]


def test_two_sections_with_one_name_stay_two_sections():
    second = ElfSection("_TEXT", bytes.fromhex("e800000000"), flags=SHF_ALLOC | SHF_EXECINSTR)
    obj = ElfObject(
        (TEXT, second),
        (ElfSymbol("f_", 0, 0, len(CODE), type=STT_FUNC), ElfSymbol("g_", 1, 0, 5, type=STT_FUNC),
         ElfSymbol("ext_", None)),
        (ElfReloc(1, 1, R_386_PC32, symbol="ext_"),),
    )  # fmt: skip
    elf = read_elf(write_elf(obj))
    texts = [s for s in elf.sections if s.name == "_TEXT"]
    assert len(texts) == 2
    assert elf.symbol("g_").section_index == texts[1].index
    assert [(r.offset, r.symbol) for r in elf.relocs(texts[1].index)] == [(1, "ext_")]
    assert elf.relocs(texts[0].index) == []
    with pytest.raises(KeyError, match="2 sections named"):
        elf.relocs("_TEXT")


def test_duplicate_global_name_is_refused():
    obj = ElfObject((TEXT,), (ElfSymbol("f_", 0), ElfSymbol("f_", None)))
    with pytest.raises(ElfError, match="duplicate global symbol 'f_'"):
        write_elf(obj)


def test_relocation_outside_its_section_is_refused():
    obj = ElfObject((TEXT,), (ElfSymbol("ext_", None),),
                    (ElfReloc(0, len(CODE) - 2, R_386_32, symbol="ext_"),))  # fmt: skip
    with pytest.raises(ElfError, match="outside the section"):
        write_elf(obj)


def test_relocation_on_nobits_is_refused():
    bss = ElfSection("_BSS", kind="nobits", size=8)
    obj = ElfObject((bss,), (ElfSymbol("ext_", None),), (ElfReloc(0, 0, R_386_32, symbol="ext_"),))
    with pytest.raises(ElfError, match="NOBITS"):
        write_elf(obj)


def test_relocation_naming_an_unknown_symbol_is_refused():
    obj = ElfObject((TEXT,), (), (ElfReloc(0, 1, R_386_32, symbol="nowhere_"),))
    with pytest.raises(ElfError, match="unknown symbol 'nowhere_'"):
        write_elf(obj)


def test_reader_refuses_a_relocation_against_symbol_0():
    # tests/elfread.py: symbol 0 is the null symbol; reading it must not wrap to the last one.
    data = bytearray(write_elf(sample()))
    rel = read_elf(bytes(data)).section(".rel_TEXT")
    start = data.find(rel.data)
    data[start + 4 : start + 8] = (R_386_32).to_bytes(4, "little")  # r_info: symbol 0
    with pytest.raises(ValueError, match="symbol index 0"):
        read_elf(bytes(data)).relocs("_TEXT")
