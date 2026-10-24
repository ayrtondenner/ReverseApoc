"""OMF -> ELF32 conversion, checked on synthetic Watcom-shaped modules from tests/omfimage.py and
read back with tests/elfread.py. Every byte and name here is made up."""

from __future__ import annotations

from elfread import read_elf
from omfimage import extdef, fixup, fixupp32, ledata32, lnames, module, pubdef32, segdef32
from reverseapoc.cli import main as cli_main

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
