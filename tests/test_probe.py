"""Idiom counters and calibration bookkeeping of tools/reverseapoc/probe.py (CID-03, D-10).

Every input here is a short x86 encoding written as a literal in this file and annotated with its
mnemonics, or a synthetic OMF object built by tests/omfimage.py, never bytes taken from a compiler
object or the game.
"""

from __future__ import annotations

import json

import pytest

import omfimage
from reverseapoc import omf
from reverseapoc.compiler import CompilerError
from reverseapoc.probe import (
    FLAG_SETS,
    IDIOMS,
    PROBE_DIR,
    PROBE_SOURCES,
    Calibration,
    Cell,
    calibrate,
    chk_sites,
    count_idioms,
)
from watcomtree import TREE_FILES, FakeCompiler, make_tree, write_watcom_manifest

# cmp al,5; sete al; and eax,0FFh; ret
SETCC_AND = b"\x3c\x05\x0f\x94\xc0\x25\xff\x00\x00\x00\xc3"
SETCC_AND_START = 2  # offset of the 0F of sete inside SETCC_AND
SETCC_AND_END = 10  # one past the last 00 of the and immediate
# setne al; movzx eax,al
SETCC_MOVZX = b"\x0f\x95\xc0\x0f\xb6\xc0"


def test_idioms_order():
    assert IDIOMS == (
        "setcc_and",
        "setcc_movzx",
        "movsd_unrolled",
        "rep_movsd_small",
        "loop_rotated",
        "loop_top_tested",
        "switch_ascending",
        "switch_descending",
    )


def test_setcc_forms():
    counts = count_idioms(SETCC_AND)
    assert list(counts) == list(IDIOMS)
    assert counts["setcc_and"] == 1
    assert counts["setcc_movzx"] == 0
    counts = count_idioms(SETCC_MOVZX)
    assert counts["setcc_movzx"] == 1
    assert counts["setcc_and"] == 0


def test_mask_and_exclude_block_matches():
    # one masked byte anywhere inside the match drops it: first, middle and last byte
    for offset in (SETCC_AND_START, SETCC_AND_START + 3, SETCC_AND_END - 1):
        assert count_idioms(SETCC_AND, mask=frozenset({offset}))["setcc_and"] == 0
    # a masked byte just outside the match does not
    for offset in (SETCC_AND_START - 1, SETCC_AND_END):
        assert count_idioms(SETCC_AND, mask=frozenset({offset}))["setcc_and"] == 1
    base = 0x10000
    # an excluded VA range [start, end) overlapping one byte of the match drops it ...
    first = base + SETCC_AND_START
    last = base + SETCC_AND_END - 1
    assert count_idioms(SETCC_AND, base=base, exclude=[(first, first + 1)])["setcc_and"] == 0
    assert count_idioms(SETCC_AND, base=base, exclude=[(last, last + 1)])["setcc_and"] == 0
    assert count_idioms(SETCC_AND, base=base, exclude=[(base - 4, first + 1)])["setcc_and"] == 0
    # ... and a range ending at the match's first byte or starting after its last does not
    assert count_idioms(SETCC_AND, base=base, exclude=[(base, first)])["setcc_and"] == 1
    assert count_idioms(SETCC_AND, base=base, exclude=[(last + 1, last + 9)])["setcc_and"] == 1


def test_empty_and_fully_excluded():
    assert count_idioms(b"") == dict.fromkeys(IDIOMS, 0)
    code = SETCC_AND + SETCC_MOVZX + MOVSD_TWO_RUNS + REP_MOVSD_5 + ROTATED + TOP_TESTED
    code += SWITCH_UP
    assert all(count_idioms(code)[name] >= 1 for name in IDIOMS[:-1])  # nothing descends here
    base = 0x20000
    assert count_idioms(code, base=base, exclude=[(base, base + len(code))]) == dict.fromkeys(
        IDIOMS, 0
    )
    # two ranges that together cover the code exclude everything as well
    split = base + 5
    assert count_idioms(
        code, base=base, exclude=[(base, split), (split, base + len(code))]
    ) == dict.fromkeys(IDIOMS, 0)


# ---- Task 2: struct copies ---------------------------------------------------------------------

# movsd; movsd; nop; movsd; movsd
MOVSD_TWO_RUNS = b"\xa5\xa5\x90\xa5\xa5"
# mov ecx,5; rep movsd
REP_MOVSD_5 = b"\xb9\x05\x00\x00\x00\xf3\xa5"


def test_movsd_runs():
    assert count_idioms(b"\xa5\xa5\xa5")["movsd_unrolled"] == 1  # movsd x3: one run
    assert count_idioms(b"\xa5\xa5\xa5\xa5\xa5")["movsd_unrolled"] == 1  # movsd x5: one run
    assert count_idioms(b"\xf3\xa5\xa5")["movsd_unrolled"] == 0  # rep movsd; movsd
    assert count_idioms(b"\x90\xa5")["movsd_unrolled"] == 0  # a single movsd is no unrolled copy
    assert count_idioms(MOVSD_TWO_RUNS)["movsd_unrolled"] == 2
    # a masked byte inside one run drops only that run
    assert count_idioms(MOVSD_TWO_RUNS, mask=frozenset({4}))["movsd_unrolled"] == 1


def test_rep_movsd_small():
    assert count_idioms(REP_MOVSD_5)["rep_movsd_small"] == 1
    assert count_idioms(REP_MOVSD_5)["movsd_unrolled"] == 0
    assert count_idioms(b"\xb9\x10\x00\x00\x00\xf3\xa5")["rep_movsd_small"] == 1  # mov ecx,16
    assert count_idioms(b"\xb9\x11\x00\x00\x00\xf3\xa5")["rep_movsd_small"] == 0  # mov ecx,17
    assert count_idioms(b"\xb9\x00\x00\x00\x00\xf3\xa5")["rep_movsd_small"] == 0  # mov ecx,0
    assert count_idioms(b"\xb9\x05\x01\x00\x00\xf3\xa5")["rep_movsd_small"] == 0  # mov ecx,105h


MOV_ECX_5 = b"\xb9\x05\x00\x00\x00"  # mov ecx,5
REP_MOVSD = b"\xf3\xa5"  # rep movsd
MOV_EDI_EAX = b"\x89\xc7"  # mov edi,eax (89 /r, ModRM mod=11)
MOV_ESI_EDX = b"\x89\xd6"  # mov esi,edx
# The -3r/-4r struct copy as the probe compiles it: the copy's pointers load between the count
# and the copy.
REP_MOVSD_GAPPED = MOV_ECX_5 + MOV_EDI_EAX + MOV_ESI_EDX + REP_MOVSD


def test_rep_movsd_small_gapped():
    assert count_idioms(REP_MOVSD_GAPPED)["rep_movsd_small"] == 1
    # the other direction of mov: mov edi,eax; mov esi,edx as 8B /r
    assert count_idioms(MOV_ECX_5 + b"\x8b\xf8\x8b\xf2" + REP_MOVSD)["rep_movsd_small"] == 1
    assert count_idioms(MOV_ECX_5 + MOV_EDI_EAX * 4 + REP_MOVSD)["rep_movsd_small"] == 1
    assert count_idioms(MOV_ECX_5 + MOV_EDI_EAX * 5 + REP_MOVSD)["rep_movsd_small"] == 0
    # something other than a register mov between: add eax,edx, or a nop
    for between in (b"\x01\xd0", b"\x90"):
        code = MOV_ECX_5 + MOV_EDI_EAX + between + REP_MOVSD
        assert count_idioms(code)["rep_movsd_small"] == 0
    # a mov with a memory operand: mov eax,[ebp+8] (mod=01) and mov [edi],eax (mod=00)
    for memory in (b"\x8b\x45\x08", b"\x89\x07"):
        assert count_idioms(MOV_ECX_5 + memory + REP_MOVSD)["rep_movsd_small"] == 0
    # a count outside 1..16
    for count in (b"\x00", b"\x11"):
        code = b"\xb9" + count + b"\x00\x00\x00" + MOV_EDI_EAX + REP_MOVSD
        assert count_idioms(code)["rep_movsd_small"] == 0


def test_rep_movsd_small_gapped_mask():
    end = len(REP_MOVSD_GAPPED)
    # a masked byte anywhere from mov ecx to rep movsd drops it, the moves between included ...
    for offset in (0, 1, len(MOV_ECX_5), len(MOV_ECX_5) + 3, end - 1):
        masked = count_idioms(REP_MOVSD_GAPPED, mask=frozenset({offset}))
        assert masked["rep_movsd_small"] == 0
    # ... a masked byte just outside does not
    code = b"\x90" + REP_MOVSD_GAPPED + b"\x90"
    for offset in (0, end + 1):
        assert count_idioms(code, mask=frozenset({offset}))["rep_movsd_small"] == 1


# ---- Task 2: loop shapes -----------------------------------------------------------------------

# A rotated loop: the entry jumps forward to the test at the bottom, which jumps back up.
ROTATED = (
    b"\x31\xc0"  # 0: xor eax,eax
    b"\xeb\x03"  # 2: jmp 7 (forward, to the bottom test)
    b"\x40\x41\x42"  # 4: inc eax; inc ecx; inc edx (the body)
    b"\x39\xd0"  # 7: cmp eax,edx
    b"\x7c\xf9"  # 9: jl 4 (backward, to the instruction after the jmp)
    b"\xc3"  # 11: ret
)
ROTATED_BODY = 5  # offset of inc ecx
ROTATED_JCC = 10  # offset of the jl displacement

# A top-tested loop: the test at the top exits forward, the bottom jumps back unconditionally.
TOP_TESTED = (
    b"\x31\xc0"  # 0: xor eax,eax
    b"\x39\xd0"  # 2: cmp eax,edx (the loop top)
    b"\x7d\x03"  # 4: jge 9 (forward, past the backward jmp)
    b"\x40"  # 6: inc eax (the body)
    b"\xeb\xf9"  # 7: jmp 2 (backward, to the loop top)
    b"\xc3"  # 9: ret
)

# The same two shapes with 32-bit displacements.
ROTATED_REL32 = (
    b"\xe9\x03\x00\x00\x00"  # 0: jmp 8
    b"\x40\x41\x42"  # 5: body
    b"\x39\xd0"  # 8: cmp eax,edx
    b"\x0f\x8c\xf5\xff\xff\xff"  # 10: jl 5 (16 - 11)
)
TOP_TESTED_REL32 = (
    b"\x39\xd0"  # 0: cmp eax,edx
    b"\x0f\x8d\x06\x00\x00\x00"  # 2: jge 14
    b"\x40"  # 8: body
    b"\xe9\xf2\xff\xff\xff"  # 9: jmp 0 (14 - 14)
)


def test_loop_shapes():
    rotated = count_idioms(ROTATED)
    assert (rotated["loop_rotated"], rotated["loop_top_tested"]) == (1, 0)
    top = count_idioms(TOP_TESTED)
    assert (top["loop_rotated"], top["loop_top_tested"]) == (0, 1)
    rotated32 = count_idioms(ROTATED_REL32)
    assert (rotated32["loop_rotated"], rotated32["loop_top_tested"]) == (1, 0)
    top32 = count_idioms(TOP_TESTED_REL32)
    assert (top32["loop_rotated"], top32["loop_top_tested"]) == (0, 1)


def test_loop_mask_reads_only_the_jumps():
    # a fixup in the loop body (a call, a global) leaves the loop countable ...
    assert count_idioms(ROTATED, mask=frozenset({ROTATED_BODY}))["loop_rotated"] == 1
    # ... a masked byte in one of its jumps does not
    assert count_idioms(ROTATED, mask=frozenset({ROTATED_JCC}))["loop_rotated"] == 0


def test_loop_shapes_need_their_partner():
    # a backward jcc whose target is not right after a forward jmp is no rotated loop
    assert count_idioms(b"\x40\x41\x7c\xfc")["loop_rotated"] == 0  # inc; inc; jl 0
    # a backward jmp whose top has no forward exit past it is no top-tested loop
    assert count_idioms(b"\x40\x41\xeb\xfc")["loop_top_tested"] == 0  # inc; inc; jmp 0
    # a top whose exit lands inside the loop is no top-tested loop
    assert count_idioms(b"\x39\xd0\x7d\x01\x40\x41\xeb\xf8")["loop_top_tested"] == 0


# ---- Task 2: switch compare order --------------------------------------------------------------


def _switch(*immediates: int, gap: bytes = b"") -> bytes:
    """cmp eax,imm8 (83 F8 ib), then je rel8 (74 xx), once per immediate."""
    return b"".join(b"\x83\xf8" + bytes([imm]) + gap + b"\x74\x10" for imm in immediates)


SWITCH_UP = _switch(1, 2, 10)


def test_switch_order():
    up = count_idioms(SWITCH_UP)
    assert (up["switch_ascending"], up["switch_descending"]) == (1, 0)
    down = count_idioms(_switch(10, 2, 1))
    assert (down["switch_ascending"], down["switch_descending"]) == (0, 1)
    mixed = count_idioms(_switch(1, 10, 2))
    assert (mixed["switch_ascending"], mixed["switch_descending"]) == (0, 0)
    assert count_idioms(_switch(1, 2))["switch_ascending"] == 0  # two compares are no chain
    assert count_idioms(_switch(1, 2, 3, 10))["switch_ascending"] == 1  # one chain, not two


def test_switch_compare_forms():
    chain = (
        b"\x83\xf8\x02"  # cmp eax,2
        b"\x0f\x82\x10\x00\x00\x00"  # jb rel32
        b"\x3d\x03\x00\x00\x00"  # cmp eax,3
        b"\x76\x10"  # jbe rel8
        b"\x3c\x0a"  # cmp al,10
        b"\x74\x10"  # je rel8
    )
    assert count_idioms(chain)["switch_ascending"] == 1


def test_switch_limits():
    # a jcc more than 6 bytes after its compare does not pair with it
    assert count_idioms(_switch(1, 2, 10, gap=b"\x90" * 7))["switch_ascending"] == 0
    assert count_idioms(_switch(1, 2, 10, gap=b"\x90" * 6))["switch_ascending"] == 1
    # a compare 60 bytes after the pair does not join it
    far = _switch(1, 2) + b"\x90" * 60 + _switch(10)
    assert count_idioms(far)["switch_ascending"] == 0


# cmp al,5; jne rel8: the branch form of `return c == 5` (11.0 at -5), a paired compare.
EQ5_BRANCH = b"\x3c\x05\x75\x06"


def test_switch_compare_before_chain():
    # a compare that turns the direction starts the next chain with the compare before it:
    # 5 then 2, 3, 10 is the ascending chain 2, 3, 10, not [5, 2] and [3, 10]
    up = count_idioms(EQ5_BRANCH + _switch(2, 3, 10))
    assert (up["switch_ascending"], up["switch_descending"]) == (1, 0)
    # the restarted chain reads the compare it kept, not the one it dropped
    assert count_idioms(EQ5_BRANCH + _switch(2, 3, 10), mask=frozenset({0}))[
        "switch_ascending"
    ] == 1  # the 3C of cmp al,5
    for kept in (6, 8):  # the immediate of cmp eax,2 and the displacement of its je
        assert count_idioms(EQ5_BRANCH + _switch(2, 3, 10), mask=frozenset({kept}))[
            "switch_ascending"
        ] == 0
    # cmp al,1; jne, then 10, 3, 2: the descending chain 10, 3, 2
    down = count_idioms(b"\x3c\x01\x75\x06" + _switch(10, 3, 2))
    assert (down["switch_ascending"], down["switch_descending"]) == (0, 1)


def test_switch_step_gap():
    # a compare 30 bytes before the next one (another function) does not join its chain
    far = EQ5_BRANCH + b"\x90" * 30 + _switch(2, 1)
    assert count_idioms(far)["switch_descending"] == 0
    # up to 12 bytes from one compare's jcc to the next compare is one chain, 13 is not
    assert count_idioms(_switch(1) + b"\x90" * 12 + _switch(2, 10))["switch_ascending"] == 1
    assert count_idioms(_switch(1) + b"\x90" * 13 + _switch(2, 10))["switch_ascending"] == 0


def _wide_switch(*immediates: int) -> bytes:
    """cmp eax,imm32 (3D id), six nops, je rel32 (0F 84 cd) and twelve nops per immediate: the
    widest step the counter accepts, 29 bytes from one compare to the next."""
    return b"".join(
        b"\x3d" + imm.to_bytes(4, "little") + b"\x90" * 6 + b"\x0f\x84\x10\x00\x00\x00"
        + b"\x90" * 12
        for imm in immediates
    )


def test_switch_window():
    # the third compare ends at byte 63: inside the 64-byte window
    assert count_idioms(_wide_switch(1, 2, 3))["switch_ascending"] == 1
    # the fourth ends at byte 92: it starts a new chain on its own (only a compare that turns
    # the direction keeps the one before it), so seven compares count as 1-3 and 4-6
    assert count_idioms(_wide_switch(1, 2, 3, 4, 5, 6, 7))["switch_ascending"] == 2


# ---- Task 2: flag sets, stack checks, calibration ----------------------------------------------


def test_flag_sets():
    assert FLAG_SETS == (
        ("-3r", "-s"),
        ("-4r", "-s"),
        ("-5r", "-s"),
        ("-5r",),
        ("-4r", "-s", "-ox"),
        ("-5r", "-s", "-ox"),
        ("-5r", "-s", "-oneatx"),
        ("-5r", "-s", "-os"),
        ("-5r", "-s", "-fpi87"),
        ("-5s", "-s"),
    )


# call __CHK (self-relative to extern 1), call foo_ (self-relative to extern 2),
# then the setcc;and idiom. Default libraries clib3r and emu387.
CALL = b"\xe8\x00\x00\x00\x00"
SYNTHETIC_CODE = CALL + CALL + SETCC_AND
SYNTHETIC_OBJECT = omfimage.module(
    "probe.c",
    omfimage.coment(0x9F, b"clib3r"),
    omfimage.coment(0x9F, b"emu387"),
    omfimage.lnames("", "_TEXT", "CODE", "_DATA", "DATA"),
    omfimage.segdef32(2, 3, len(SYNTHETIC_CODE)),
    omfimage.segdef32(4, 5, 4),
    omfimage.extdef("__CHK", "foo_"),
    omfimage.ledata32(1, 0, SYNTHETIC_CODE),
    omfimage.fixupp32(
        omfimage.fixup(1, segment_relative=False, target=(2, 1)),
        omfimage.fixup(6, segment_relative=False, target=(2, 2)),
    ),
    # a segment-relative fixup to __CHK (an address taken, not a call) does not count
    omfimage.ledata32(2, 0, b"\x00\x00\x00\x00"),
    omfimage.fixupp32(omfimage.fixup(0, segment_relative=True, target=(2, 1))),
)


def test_chk_sites():
    assert chk_sites(omf.read_object(SYNTHETIC_OBJECT)) == 1


def _cell(version: str, flags: tuple[str, ...], sha1: str, **counts: int) -> Cell:
    return Cell(
        version=version,
        flags=flags,
        counts={name: counts.get(name, 0) for name in IDIOMS},
        chk_calls=counts.get("chk", 0),
        default_libraries=("clib3r", "emu387"),
        normalized_sha1=sha1,
    )


def test_ties():
    flags = ("-5r", "-s")
    same = Calibration(
        (_cell("10.5", flags, "a" * 40), _cell("10.6", flags, "a" * 40)), skipped=()
    )
    assert same.ties() == [(flags, ("10.5", "10.6"))]
    apart = Calibration(
        (_cell("10.5", flags, "a" * 40), _cell("10.6", flags, "b" * 40)), skipped=()
    )
    assert apart.ties() == []
    # equal hashes under different flags are no tie
    other = Calibration(
        (_cell("10.5", flags, "a" * 40), _cell("10.6", ("-3r", "-s"), "a" * 40)), skipped=()
    )
    assert other.ties() == []


def test_calibration_format_and_json():
    five, three = ("-5r", "-s"), ("-3r", "-s")
    cells = (
        _cell("10.5", three, "c" * 40, setcc_movzx=1),
        _cell("10.5", five, "a" * 40, setcc_and=1, movsd_unrolled=2, chk=3),
        _cell("10.6", three, "d" * 40, setcc_movzx=1),
        _cell("10.6", five, "a" * 40, setcc_and=1, movsd_unrolled=2, chk=3),
    )
    cal = Calibration(cells, skipped=(("11.0", "Watcom 11.0: gate refused (bad)"),))
    assert cal.cell("10.6", five) is cells[3]
    with pytest.raises(KeyError):
        cal.cell("11.0", five)
    lines = cal.format().splitlines()
    header = lines[0].split()
    assert header[:2] == ["version", "flags"]
    assert all(name in header for name in IDIOMS)
    for line, cell in zip(lines[1:5], cells, strict=True):
        expected = [cell.version, *cell.flags, *(str(cell.counts[n]) for n in IDIOMS)]
        expected += [str(cell.chk_calls), "clib3r,emu387", cell.normalized_sha1]
        assert line.split() == expected
    assert lines[5:] == ["tie: -5r -s: 10.5 10.6", "skipped: 11.0: Watcom 11.0: gate refused (bad)"]

    data = cal.to_json()
    assert json.loads(json.dumps(data)) == data  # plain JSON: numbers and text, no bytes
    assert data["idioms"] == list(IDIOMS)
    assert data["cells"][1] == {
        "version": "10.5",
        "flags": ["-5r", "-s"],
        "counts": cells[1].counts,
        "chk_calls": 3,
        "default_libraries": ["clib3r", "emu387"],
        "normalized_sha1": "a" * 40,
    }
    assert data["ties"] == [{"flags": ["-5r", "-s"], "versions": ["10.5", "10.6"]}]
    assert data["skipped"] == [{"version": "11.0", "reason": "Watcom 11.0: gate refused (bad)"}]


# ---- calibrate() against fake trees and a fake compiler ----------------------------------------


@pytest.fixture
def fake(tmp_path) -> dict:
    """Fake 10.6 and 11.0 trees under tmp_path/w, a manifest without 10.5, and a probe source."""
    watcom = tmp_path / "w"
    for version in ("10.6", "11.0"):
        make_tree(watcom, version)
    manifest = write_watcom_manifest(
        tmp_path / "watcom.toml", {v: TREE_FILES[v] for v in ("10.6", "11.0")}
    )
    src = tmp_path / "probe" / "p.c"
    src.parent.mkdir()
    src.write_text("int x;\n")
    return dict(
        sources=(src,),
        root=tmp_path,
        manifest=manifest,
        watcom_dir=watcom,
        platform="win32",
        log=tmp_path / "cc.log",
        stamps=tmp_path / "stamps",
    )


def test_calibrate_cells_order_and_skips(fake, tmp_path):
    runner = FakeCompiler(obj_bytes=SYNTHETIC_OBJECT)
    flag_sets = (("-5r", "-s"), ("-3r", "-s"))
    cal = calibrate(
        ("11.0", "10.5", "10.6"), flag_sets, out_dir=tmp_path / "out", runner=runner, **fake
    )
    # SWEPT_VERSIONS order, then the flag sets in the order given
    assert [(c.version, c.flags) for c in cal.cells] == [
        ("10.6", ("-5r", "-s")),
        ("10.6", ("-3r", "-s")),
        ("11.0", ("-5r", "-s")),
        ("11.0", ("-3r", "-s")),
    ]
    assert [version for version, _ in cal.skipped] == ["10.5"]
    assert "10.5" in cal.skipped[0][1]
    cell = cal.cells[0]
    assert cell.counts == {name: int(name == "setcc_and") for name in IDIOMS}
    assert cell.chk_calls == 1
    assert cell.default_libraries == ("clib3r", "emu387")
    assert cell.normalized_sha1 == omf.normalized_object_sha1(SYNTHETIC_OBJECT)
    obj = tmp_path / "out" / "11.0" / "3r_s" / "p.obj"
    assert obj.is_file()
    # the fake compiler writes the same object for every cell: every flag set is a tie
    assert cal.ties() == [(f, ("10.6", "11.0")) for f in flag_sets]


def test_calibrate_failed_compile_names_the_cell(fake, tmp_path):
    runner = FakeCompiler(rc=3, write_obj=False)
    with pytest.raises(CompilerError, match=r"10\.6 -5r -s.*p\.c"):
        calibrate(("10.6",), (("-5r", "-s"),), out_dir=tmp_path / "out", runner=runner, **fake)


def test_calibrate_default_sources_are_in_probe_dir():
    assert PROBE_SOURCES == ("cg_basic.c",)
    assert all((PROBE_DIR / name).is_file() for name in PROBE_SOURCES)
