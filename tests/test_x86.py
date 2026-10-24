"""Tests for the shared capstone decode helpers (tools/reverseapoc/x86.py).

Every byte string here is made up for the test: hand-assembled instructions at made-up
addresses, never bytes copied from a game executable.
"""

from __future__ import annotations

import importlib.metadata
import struct

import pytest

from reverseapoc import x86

VA = 0x00400000  # made-up load address


def _rel32(opcode: bytes, rel: int) -> bytes:
    return opcode + struct.pack("<i", rel)


def test_capstone_pin(monkeypatch):
    assert importlib.metadata.version("capstone") == x86.CAPSTONE_VERSION == "5.0.9"
    x86.check_capstone()
    monkeypatch.setattr(x86.metadata, "version", lambda _name: "5.0.7")
    with pytest.raises(x86.X86Error) as err:
        x86.check_capstone()
    assert "5.0.7" in str(err.value)
    assert "5.0.9" in str(err.value)


@pytest.mark.parametrize("rel", [0x1234, -0x20])
def test_call_rel32(rel):
    insn = x86.decode_one(_rel32(b"\xe8", rel), VA)
    assert insn is not None
    assert (insn.va, insn.size, insn.mnemonic) == (VA, 5, "call")
    assert insn.is_call
    assert not insn.is_jump
    assert not insn.is_terminal
    assert insn.branch_target == VA + 5 + rel
    assert insn.rel32_field == VA + 1


def test_jumps():
    short = x86.decode_one(b"\xeb\x10", VA)
    assert short.branch_target == VA + 2 + 0x10
    assert short.is_jump and short.is_terminal and not short.is_conditional
    assert short.rel32_field is None  # rel8: no 32-bit field to relocate

    jcc = x86.decode_one(_rel32(b"\x0f\x84", 0x300), VA)
    assert jcc.branch_target == VA + 6 + 0x300
    assert jcc.is_jump and jcc.is_conditional and not jcc.is_terminal
    assert jcc.rel32_field == VA + 2

    jcc8 = x86.decode_one(b"\x75\xfe", VA)  # jne to itself
    assert (jcc8.branch_target, jcc8.is_conditional) == (VA, True)

    near = x86.decode_one(_rel32(b"\xe9", -0x100), VA)
    assert near.branch_target == VA + 5 - 0x100
    assert near.is_terminal and not near.is_conditional
    assert near.rel32_field == VA + 1


@pytest.mark.parametrize("code", [b"\xc3", b"\xc2\x08\x00", b"\xff\xe0"])
def test_terminal_without_target(code):
    # ret, ret 8 and jmp eax end the flow and have no static branch target.
    insn = x86.decode_one(code, VA)
    assert insn.is_terminal
    assert insn.branch_target is None
    assert insn.rel32_field is None


def test_plain_instruction_is_not_a_branch():
    insn = x86.decode_one(b"\x89\xc1", VA)  # mov ecx, eax
    assert (insn.mnemonic, insn.op_str) == ("mov", "ecx, eax")
    assert not (insn.is_call or insn.is_jump or insn.is_terminal or insn.is_conditional)
    assert insn.branch_target is None
    assert insn.raw == b"\x89\xc1"


def test_decode_runs_to_the_end():
    code = b"\x90" + b"\x89\xc1" + b"\xc3"  # nop; mov ecx, eax; ret
    got = [(i.va, i.size) for i in x86.decode(code, VA)]
    assert got == [(VA, 1), (VA + 1, 2), (VA + 3, 1)]


def test_data_site_stops_decoding():
    # A fixup at an instruction start means the bytes are inline data (a jump table), not code.
    code = b"\x90" + b"\x89\xc1" + struct.pack("<I", 0x00401000) + b"\xc3"
    third = VA + 3
    got = [i.va for i in x86.decode(code, VA, data_sites={third})]
    assert got == [VA, VA + 1]


def test_data_site_inside_an_instruction_does_not_stop():
    code = _rel32(b"\xe8", 0x10) + b"\xc3"
    got = [i.va for i in x86.decode(code, VA, data_sites={VA + 1})]
    assert got == [VA, VA + 5]


@pytest.mark.parametrize(
    ("code", "filler"),
    [
        (b"\x90", True),  # nop
        (b"\x89\xc0", True),  # mov eax, eax
        (b"\x8b\xc0", True),  # mov eax, eax (other direction)
        (b"\x8d\x40\x00", True),  # lea eax, [eax+0]
        (b"\x89\xc1", False),  # mov ecx, eax
        (b"\x8d\x00", False),  # lea eax, [eax]: not a Watcom filler encoding
    ],
)
def test_filler(code, filler):
    assert x86.is_filler(x86.decode_one(code, VA)) is filler


def test_undecodable_stops():
    code = b"\x90" + b"\x0f\x0a" + b"\x90"  # 0f 0a is an undefined opcode
    assert [i.va for i in x86.decode(code, VA)] == [VA]
    assert x86.decode_one(b"\x0f\x0a", VA) is None
    assert x86.decode_one(b"", VA) is None
