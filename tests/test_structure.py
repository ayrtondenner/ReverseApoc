"""The control-flow outline and shape counts (todo structure-first-large-functions). Every
encoding below is written by hand, never game bytes."""

from __future__ import annotations

import pytest

from reverseapoc import structure
from reverseapoc.x86 import Insn

VA = 0x1000
# A made-up function with a loop, an if, a return and a tail jump, then trailing filler:
LOOP = (
    "31c0"  # 0x1000 xor eax, eax                B0
    "40"  # 0x1002 inc eax                        B1 (the loop head)
    "83f805"  # 0x1003 cmp eax, 5
    "7cfa"  # 0x1006 jl 0x1002                    back edge to B1
    "85c0"  # 0x1008 test eax, eax                B2
    "7401"  # 0x100a je 0x100d                    -> B4
    "c3"  # 0x100c ret                            B3
    "e910000000"  # 0x100d jmp 0x1022             B4, out of the row (a tail call)
    "89c0"  # 0x1012 mov eax, eax                 trailing alignment filler
)
LOOP_END = VA + 0x14
LOOP_CODE_LENGTH = 0x12  # up to the filler
JMP_FIELD = VA + 0x0E  # the rel32 field of the jmp at 0x100d
# The same, but the jmp's rel32 lands on the `cmp` at 0x1003 (a second loop head) unless the
# field is a relocation of ours, whose raw value says nothing.
INNER = LOOP.replace("e910000000", "e9f1ffffff")


def _code(text: str) -> bytes:
    return bytes.fromhex(text)


def test_shape_counts_code_length_blocks_and_branches():
    shape = structure.shape(_code(LOOP), VA, frozenset())
    assert shape == structure.Shape(length=LOOP_CODE_LENGTH, blocks=5, branches=3)
    assert shape.to_json() == {"length": LOOP_CODE_LENGTH, "blocks": 5, "branches": 3}


def test_a_jump_into_the_row_starts_a_block():
    assert structure.shape(_code(INNER), VA, frozenset()).blocks == 6


def test_a_relocated_jump_field_is_no_target_in_the_row():
    assert structure.shape(_code(INNER), VA, frozenset({JMP_FIELD})).blocks == 5


def test_instructions_skip_a_relocated_field_at_an_instruction_start():
    """Inline data (a jump table entry) is no code: decoding resumes after its 4 bytes."""
    code = _code("c3" + "00112233" + "40c3")
    insns = structure.instructions(code, VA, frozenset({VA + 1}))
    assert [(insn.va, insn.mnemonic) for insn in insns] == [(VA, "ret"), (VA + 5, "inc"),
                                                            (VA + 6, "ret")]  # fmt: skip


def test_a_block_of_alignment_filler_alone_is_no_block():
    """Watcom pads a loop head after a jmp; a block of filler only is not counted."""
    code = _code("eb02" + "89c0" + "c3")  # jmp +2 over a mov eax, eax; ret
    assert structure.shape(code, VA, frozenset()).blocks == 2


def _decoded(text: str) -> list[Insn]:
    return structure.instructions(_code(text), VA, frozenset())


def test_outline_lists_blocks_exits_and_loops():
    text = structure.outline(_decoded(LOOP), VA, LOOP_END, target=lambda insn: insn.branch_target)
    lines = text.splitlines()
    assert lines[0] == ("18 bytes: 5 blocks, 3 branches (2 conditional), 1 loop, 0 switches, "
                        "0 calls, 1 return")  # fmt: skip
    assert lines[1:6] == [
        "B0  0x00001000..0x00001002  1 insn: falls into B1",
        "B1  0x00001002..0x00001008  3 insns: jl -> B1 else B2",
        "B2  0x00001008..0x0000100C  2 insns: je -> B4 else B3",
        "B3  0x0000100C..0x0000100D  1 insn: ret",
        "B4  0x0000100D..0x00001012  1 insn: jmp out of the row (a tail call)",
    ]
    assert lines[6] == "loops (back edges): B1 -> B1"


SWITCH = (
    "ff248500000000"  # 0x2000 jmp dword ptr [eax*4]    B0, a table jump
    "40"  # 0x2007 inc eax                              B1, case 0
    "40"  # 0x2008 inc eax                              B2, case 1 (reached only by the table)
    "e8f3ffffff"  # 0x2009 call 0x2001
    "c3"  # 0x200e ret
)
SWITCH_VA = 0x2000


def test_outline_names_switch_cases_and_counts_calls():
    insns = structure.instructions(_code(SWITCH), SWITCH_VA, frozenset())
    cases = {SWITCH_VA: (SWITCH_VA + 7, SWITCH_VA + 8)}
    text = structure.outline(insns, SWITCH_VA, SWITCH_VA + 0xF, cases=cases,
                             target=lambda insn: insn.branch_target)  # fmt: skip
    lines = text.splitlines()
    assert lines[0] == ("15 bytes: 3 blocks, 1 branch (0 conditional), 0 loops, 1 switch "
                        "(2 cases), 1 call, 1 return")  # fmt: skip
    assert lines[1] == "B0  0x00002000..0x00002007  1 insn: switch, 2 cases -> B1 B2"
    assert lines[2] == "B1  0x00002007..0x00002008  1 insn: falls into B2"
    assert lines[3] == "B2  0x00002008..0x0000200F  3 insns, 1 call: ret"
    assert lines[4] == "loops (back edges): none"


def test_outline_of_an_indirect_jump_without_a_table():
    insns = structure.instructions(_code("ffe0"), VA, frozenset())  # jmp eax
    text = structure.outline(insns, VA, VA + 2, target=lambda insn: insn.branch_target)
    assert text.splitlines()[1] == "B0  0x00001000..0x00001002  1 insn: jmp (indirect)"


@pytest.mark.parametrize("size", [structure.MIN_SIZE - 1, structure.MIN_SIZE])
def test_min_size_is_the_256_byte_line(size: int):
    assert structure.MIN_SIZE == 256
    assert structure.wanted(size) is (size >= 256)
