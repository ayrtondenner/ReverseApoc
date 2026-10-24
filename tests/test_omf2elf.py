"""OMF -> ELF32 conversion, checked on synthetic Watcom-shaped modules from tests/omfimage.py and
read back with tests/elfread.py. Every byte and name here is made up."""

from __future__ import annotations

import pytest

from elfread import read_elf
from omfimage import (
    comdat16,
    extdef,
    fixup,
    fixupp32,
    grpdef,
    ledata32,
    lidata32,
    lnames,
    module,
    nbkpat,
    pubdef32,
    segdef32,
    thread,
)
from reverseapoc.cli import main as cli_main
from reverseapoc.elf import write_elf
from reverseapoc.omf import read_object
from reverseapoc.omf2elf import Omf2ElfError, convert, convert_file

# Made-up ELF values from the gABI/psABI, written out here rather than imported from elf.py.
STB_GLOBAL = 1
STT_NOTYPE = 0
STT_FUNC = 2
R_386_PC32 = 2

CALL_CODE = bytes.fromhex("e800000000c3")  # call rel32 (field 0); ret


def call_module() -> bytes:
    """_TEXT/CODE holding one function that calls an extern through a self-relative fixup."""
    return module(
        "callmod",
        lnames("", "_TEXT", "CODE"),
        segdef32(2, 3, len(CALL_CODE)),
        pubdef32(1, [("func_00010000_", 0)]),
        extdef("func_00012345_"),
        ledata32(1, 0, CALL_CODE),
        fixupp32(fixup(1, segment_relative=False, target=(2, 1))),
    )


def test_cli_converts_a_synthetic_module(tmp_path, capsys):
    obj, out = tmp_path / "callmod.obj", tmp_path / "callmod.o"
    obj.write_bytes(call_module())
    assert cli_main(["omf2elf", str(obj), "-o", str(out)]) == 0
    assert capsys.readouterr().out.startswith("OK ")

    elf = read_elf(out.read_bytes())
    text = elf.section("_TEXT")
    assert text.data[:1] + text.data[5:] == CALL_CODE[:1] + CALL_CODE[5:]
    func = elf.symbol("func_00010000_")
    expected = (STB_GLOBAL, STT_FUNC, "_TEXT", 0, 6)
    assert (func.bind, func.type, func.section, func.value, func.size) == expected
    callee = elf.symbol("func_00012345_")
    assert (callee.bind, callee.section) == (STB_GLOBAL, None)
    relocs = elf.relocs("_TEXT")
    assert [(r.offset, r.type, r.symbol, r.addend) for r in relocs] == [
        (1, R_386_PC32, "func_00012345_", -4)
    ]


def test_cli_refuses_a_non_omf_input(tmp_path, capsys):
    obj = tmp_path / "junk.obj"
    obj.write_bytes(b"this is not an OMF object at all")
    assert cli_main(["omf2elf", str(obj), "-o", str(tmp_path / "junk.o")]) == 1
    assert "reverseapoc omf2elf: error:" in capsys.readouterr().err
    assert not (tmp_path / "junk.o").exists()


# ---- core conversion rules (Task 2) ----

SHF_WRITE = 1
SHF_ALLOC = 2
SHF_EXECINSTR = 4
SHT_PROGBITS = 1
SHT_NOBITS = 8
STT_OBJECT = 1
STT_SECTION = 3
R_386_32 = 1

# LNAMES of the Watcom segment layout, plus one debug segment.
WATCOM_LNAMES = ("", "_TEXT", "CODE", "CONST", "DATA", "CONST2", "_DATA", "_BSS", "BSS",
                 "$$SYMBOLS", "DEBSYM")  # fmt: skip
TEXT_LN, CODE_LN, CONST_LN, DATA_LN, CONST2_LN, UDATA_LN, BSS_LN, BSSCLS_LN = range(2, 10)
SYMS_LN, DEBSYM_LN = 10, 11


def convert_bytes(data: bytes):
    """read_elf of the conversion of an OMF object."""
    return read_elf(write_elf(convert(read_object(data))))


def watcom_module(*records: bytes, text: bytes = b"\x90" * 4) -> bytes:
    """_TEXT CODE, CONST/CONST2/_DATA DATA (4 bytes each), _BSS BSS (8), $$SYMBOLS DEBSYM (4)."""
    return module(
        "watcom",
        lnames(*WATCOM_LNAMES),
        segdef32(TEXT_LN, CODE_LN, len(text)),  # 1
        segdef32(CONST_LN, DATA_LN, 4),  # 2
        segdef32(CONST2_LN, DATA_LN, 4),  # 3
        segdef32(UDATA_LN, DATA_LN, 4),  # 4
        segdef32(BSS_LN, BSSCLS_LN, 8),  # 5
        segdef32(SYMS_LN, DEBSYM_LN, 4),  # 6
        ledata32(1, 0, text),
        *records,
    )


def test_segment_classes_become_progbits_and_bss_becomes_nobits():
    elf = convert_bytes(watcom_module(ledata32(4, 0, b"\x01\x02\x03\x04")))
    names = [s.name for s in elf.sections if not s.name.startswith(".")]
    assert names == ["_TEXT", "CONST", "CONST2", "_DATA", "_BSS"]
    text = elf.section("_TEXT")
    assert (text.type, text.flags) == (SHT_PROGBITS, SHF_ALLOC | SHF_EXECINSTR)
    for name in ("CONST", "CONST2", "_DATA"):
        sec = elf.section(name)
        assert (sec.type, sec.flags, len(sec.data)) == (SHT_PROGBITS, SHF_ALLOC | SHF_WRITE, 4)
    assert elf.section("_DATA").data == b"\x01\x02\x03\x04"
    bss = elf.section("_BSS")
    assert (bss.type, bss.flags, bss.size) == (SHT_NOBITS, SHF_ALLOC | SHF_WRITE, 8)


def test_debug_class_segment_and_its_fixups_are_dropped():
    elf = convert_bytes(watcom_module(
        extdef("dbg_"),
        ledata32(6, 0, bytes(4)),
        fixupp32(fixup(0, target=(2, 1))),
    ))  # fmt: skip
    assert "$$SYMBOLS" not in [s.name for s in elf.sections]
    assert not [s for s in elf.sections if s.name.startswith(".rel")]


def test_public_in_data_is_an_object_and_in_bss_too():
    elf = convert_bytes(watcom_module(pubdef32(4, [("D_00020000", 0)]),
                                      pubdef32(5, [("D_00030000", 0)])))  # fmt: skip
    data, bss = elf.symbol("D_00020000"), elf.symbol("D_00030000")
    assert (data.type, data.section, data.size) == (STT_OBJECT, "_DATA", 4)
    assert (bss.type, bss.section, bss.size) == (STT_OBJECT, "_BSS", 8)


def test_publics_are_sized_to_the_next_public_and_the_segment_end():
    elf = convert_bytes(watcom_module(pubdef32(1, [("g_", 6), ("f_", 0)]), text=b"\x90" * 10))
    assert (elf.symbol("f_").value, elf.symbol("f_").size) == (0, 6)
    assert (elf.symbol("g_").value, elf.symbol("g_").size) == (6, 4)


def test_switch_table_fixup_addend_is_the_stored_offset():
    # jmp [table + eax*4] with the table at _TEXT+8, then a made-up table entry.
    text = bytes.fromhex("ff248508000000c3") + bytes(4)
    elf = convert_bytes(watcom_module(fixupp32(fixup(3, target=(0, 1))), text=text))
    sec = elf.section("_TEXT")
    (rel,) = elf.relocs("_TEXT")
    assert (rel.offset, rel.type, rel.symbol_type) == (3, R_386_32, STT_SECTION)
    assert (rel.symbol_section_index, rel.addend) == (sec.index, 8)


def test_extern_data_fixup_keeps_stored_addend_8():
    text = bytes.fromhex("a108000000c3")  # mov eax,[D_000D2000 + 8]; ret
    elf = convert_bytes(watcom_module(
        extdef("_D_000D2000"), fixupp32(fixup(1, target=(2, 1))), text=text
    ))  # fmt: skip
    rels = [(r.offset, r.type, r.symbol, r.addend) for r in elf.relocs("_TEXT")]
    assert rels == [(1, R_386_32, "_D_000D2000", 8)]
    assert elf.symbol("_D_000D2000").section is None


def test_fixup_through_thread_subrecords_converts_like_an_explicit_one():
    explicit = watcom_module(
        extdef("callee_"),
        fixupp32(fixup(1, segment_relative=False, frame=(5, None), target=(2, 1))),
        text=CALL_CODE,
    )
    threaded = watcom_module(
        extdef("callee_"),
        fixupp32(thread("frame", 1, 5), thread("target", 2, 2, 1),
                 fixup(1, segment_relative=False, frame=("thread", 1), target=("thread", 2))),
        text=CALL_CODE,
    )  # fmt: skip
    a, b = convert_bytes(explicit), convert_bytes(threaded)
    assert a.relocs("_TEXT") == b.relocs("_TEXT") != []
    assert a.section("_TEXT").data == b.section("_TEXT").data


def test_location_other_than_9_is_refused_naming_segment_and_offset():
    data = watcom_module(extdef("x_"), fixupp32(fixup(2, location=1, target=(2, 1))))
    with pytest.raises(Omf2ElfError, match=r"_TEXT offset 0x2.*location 1"):
        convert(read_object(data))


def test_fixup_into_iterated_data_is_refused():
    data = watcom_module(
        extdef("x_"), lidata32(4, 0, [(1, b"\x00" * 4)]), fixupp32(fixup(0, target=(2, 1)))
    )
    with pytest.raises(Omf2ElfError, match=r"_DATA.*iterated data"):
        convert(read_object(data))


def test_fixup_to_a_group_target_is_refused():
    data = watcom_module(grpdef(TEXT_LN, 1), fixupp32(fixup(0, target=(1, 1))))
    with pytest.raises(Omf2ElfError, match="group"):
        convert(read_object(data))


def test_convert_file_refuses_to_overwrite_its_input(tmp_path):
    obj = tmp_path / "m.obj"
    obj.write_bytes(call_module())
    with pytest.raises(Omf2ElfError, match="over the input"):
        convert_file(obj, tmp_path / "." / "m.obj")
    assert obj.read_bytes() == call_module()


def test_convert_file_reports_counts(tmp_path):
    obj, out = tmp_path / "m.obj", tmp_path / "sub" / "m.o"
    obj.write_bytes(call_module())
    result = convert_file(obj, out)
    assert (result.sections, result.symbols, result.relocations) == (1, 2, 1)
    assert result.to_json()["relocations"] == 1
    assert result.format() == f"OK {out} sections 1 symbols 2 relocations 1"


def test_initialised_bytes_in_bss_are_refused():
    data = watcom_module(ledata32(5, 0, b"\x01"))
    with pytest.raises(Omf2ElfError, match="_BSS.*initialised"):
        convert(read_object(data))


def test_absolute_public_is_refused():
    data = watcom_module(pubdef32(0, [("abs_", 0x10)]))
    with pytest.raises(Omf2ElfError, match="'abs_' is absolute"):
        convert(read_object(data))


def test_fixup_to_a_dropped_debug_segment_is_refused():
    data = watcom_module(fixupp32(fixup(0, target=(0, 6))))
    with pytest.raises(Omf2ElfError, match=r"\$\$SYMBOLS.*not emitted"):
        convert(read_object(data))


# ---- 05-06: COMDATs, NBKPAT, LPUBDEF, LIDATA, BAKPAT, CEXTDEF, filler, refusals ----

STB_LOCAL = 0
STB_WEAK = 2


def test_comdat16_converts_to_a_weak_section():
    # "pick any" (selection 1) explicitly allocated in _TEXT, patched by NBKPAT; "no match"
    # (selection 0) with code32 allocation (3), so no segment and no public base.
    data = module(
        "cd",
        lnames("", "_TEXT", "CODE", "f_", "g_"),
        segdef32(2, 3, 0),
        comdat16(4, bytes.fromhex("b801000000c3"), attributes=0x10, seg=1),  # mov eax,1; ret
        nbkpat(4, 1, [(1, 0x0102)]),
        comdat16(5, b"\xc3", attributes=0x03),
    )
    elf = convert_bytes(data)
    f, g = elf.symbol("f_"), elf.symbol("g_")
    assert (f.bind, f.type, f.value, f.size) == (STB_WEAK, STT_FUNC, 0, 6)
    f_sec = elf.section(f.section_index)
    assert (f_sec.name, f_sec.data) == ("_TEXT", bytes.fromhex("b80301" "0000c3"))
    assert f_sec.flags == SHF_ALLOC | SHF_EXECINSTR
    assert (g.bind, g.type, g.size) == (STB_GLOBAL, STT_FUNC, 1)
    g_sec = elf.section(g.section_index)
    assert (g_sec.name, g_sec.data, g_sec.flags) == ("g_", b"\xc3", SHF_ALLOC | SHF_EXECINSTR)
