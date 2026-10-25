"""objdiff's blind spot through the production writers (roadmap criterion 4, SPL-13 negative).

Spike 005 plant P3, repeated with omf2elf, target.py and objdiff-cli instead of the spike's own
writers: in `mov dword [abs32], imm32` objdiff compares only the first relocation of the
instruction, so a wrong symbol on the second (the imm32) still scores 100.0. relocs.check_function
must fail it. Every byte, name and address is made up (tests/relocpair.py); the test needs
objdiff-cli on PATH (the container).
"""

from __future__ import annotations

from conftest import requires_objdiff
from omfimage import extdef, fixupp32, grpdef, ledata32, lnames, module, pubdef32, segdef32
from relocpair import CODE_BASE, FLAT_LNAME, absolute, game_row, le_off32, original, table
from reverseapoc import check
from reverseapoc.elf import write_elf
from reverseapoc.omf import read_object
from reverseapoc.omf2elf import convert
from reverseapoc.relocs import check_function
from reverseapoc.target import build_target

# mov dword [0x20004], offset 0x20010; ret. Both 4-byte fields are relocated, back to back.
ORIGINAL = bytes.fromhex("c705" "04000000" "10000000" "c3")  # raw fields = the target offsets
OURS = bytes.fromhex("c705" "00000000" "00000000" "c3")
ROW = game_row(CODE_BASE, CODE_BASE + len(ORIGINAL))
FIRST_FIELD, SECOND_FIELD = CODE_BASE + 2, CODE_BASE + 6
SYMBOL = "func_00010000_"
FIRST, SECOND, WRONG = "_D_00020004", "_D_00020010", "_D_00020020"


def our_module(first: str, second: str):
    return read_object(module(
        "u_00010000",
        lnames("", "_TEXT", "CODE", FLAT_LNAME),
        segdef32(2, 3, len(OURS)),
        grpdef(4),  # FLAT, the frame of the relocpair fixups
        pubdef32(1, [(SYMBOL, 0)]),
        extdef(first, second),
        ledata32(1, 0, OURS),
        fixupp32(absolute(2, 1), absolute(6, 2)),
    ))  # fmt: skip


def score(tmp_path, first: str, second: str) -> tuple[float, bool, tuple[str, ...]]:
    """objdiff's match_percent and the relocation check's verdict for our object."""
    orig = original({CODE_BASE: ORIGINAL},
                    page1=le_off32(FIRST_FIELD, 0x4) + le_off32(SECOND_FIELD, 0x10))  # fmt: skip
    symbols = table(ROW)
    target = build_target(orig.le, [ROW], symbols, flat=orig.flat, fixups=orig.fixups)
    assert target.raw_fields == () and target.undecoded == ()
    mod = our_module(first, second)
    base_o, target_o = tmp_path / f"{second}-base.o", tmp_path / f"{second}-target.o"
    base_o.write_bytes(write_elf(convert(mod)))
    target_o.write_bytes(target.data)
    percent = check.objdiff_percent(target_o, base_o, SYMBOL,
                                    runner=check.default_objdiff_runner())  # fmt: skip
    segment = next(seg for seg in mod.segments if seg.name == "_TEXT")
    result = check_function(segment, off=0, size=len(OURS), row=ROW, flat=orig.flat,
                            fixups=orig.fixups, symbols=symbols)  # fmt: skip
    return percent, result.ok, result.problems


def test_second_relocation_blind_spot(tmp_path):
    requires_objdiff()
    assert score(tmp_path, FIRST, SECOND) == (check.PERFECT, True, ())  # the good pair
    first_wrong = score(tmp_path, WRONG, SECOND)  # control: objdiff sees the 1st relocation
    assert first_wrong[0] < check.PERFECT and not first_wrong[1]
    percent, ok, problems = score(tmp_path, FIRST, WRONG)
    assert percent == check.PERFECT  # objdiff misses the 2nd relocation of one instruction
    assert not ok
    (problem,) = problems
    assert problem.startswith(f"0x{SECOND_FIELD:08X}: ") and WRONG in problem
