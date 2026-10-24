# Derived from Theme Hospital decomp tools/x86scan.py (GPLv3), https://github.com/matteo-pacini/theme-hospital-decomp
"""Shared x86-32 decoding on top of capstone, for discovery, asm listings, scoring and targets.

Every decoding module goes through `decode` / `decode_one`, so they all see the same
instruction boundaries and the same branch facts:

- `branch_target` is the static destination of a call or jump with an immediate operand
  (rel8 or rel32); indirect branches (`jmp eax`, `call [ebx]`) and returns have none.
- `rel32_field` is the linear address of the 4-byte displacement of a rel32 call or jump: the
  field a PC32 relocation patches. A rel8 branch has none.
- `is_terminal` marks an instruction after which flow does not fall through: ret, iret and every
  unconditional jmp (direct, indirect or far).

Both come from capstone's operand detail (`imm`, `imm_offset`, `imm_size`), never from
hand-decoded opcodes. Decoding stops at the end of the bytes, at a byte capstone cannot decode,
and at an instruction start that is a data site: objdiff and the Theme Hospital scanner treat a
relocation that sits where an instruction would start as inline data (a jump table), not code.

`is_filler` recognises the padding Watcom puts after a terminal instruction to align the next
function: nop, both encodings of mov eax, eax, and lea eax, [eax+0].

The installed capstone is checked through `importlib.metadata`, never through the package's own
version attribute, which reports 5.0.7 for the 5.0.9 release.
"""

from __future__ import annotations

import functools
from collections.abc import Container, Iterator
from dataclasses import dataclass
from importlib import metadata

from capstone import (
    CS_ARCH_X86,
    CS_GRP_CALL,
    CS_GRP_IRET,
    CS_GRP_JUMP,
    CS_GRP_RET,
    CS_MODE_32,
    Cs,
    CsInsn,
)
from capstone.x86 import X86_INS_JMP, X86_INS_LJMP, X86_OP_IMM

CAPSTONE_VERSION = "5.0.9"  # the pin in pyproject.toml and docs/tools.md

_REL32_SIZE = 4  # bytes of a rel32 displacement field
_ADDRESS_MASK = 0xFFFFFFFF  # linear addresses are 32-bit
_RETURN_GROUPS = frozenset({CS_GRP_RET, CS_GRP_IRET})
_UNCONDITIONAL_JUMPS = frozenset({X86_INS_JMP, X86_INS_LJMP})

# Watcom alignment filler after a terminal instruction.
FILLER_NOP = b"\x90"  # nop
FILLER_MOV_EAX_EAX = b"\x89\xc0"  # mov eax, eax (89 /r)
FILLER_MOV_EAX_EAX_ALT = b"\x8b\xc0"  # mov eax, eax (8b /r)
FILLER_LEA_EAX_EAX0 = b"\x8d\x40\x00"  # lea eax, [eax+0] (disp8 0)
FILLER_ENCODINGS = frozenset(
    {FILLER_NOP, FILLER_MOV_EAX_EAX, FILLER_MOV_EAX_EAX_ALT, FILLER_LEA_EAX_EAX0}
)


class X86Error(ValueError):
    """The decoder cannot be trusted (wrong or missing capstone)."""


def check_capstone() -> None:
    """Raise X86Error unless the installed capstone distribution is CAPSTONE_VERSION."""
    try:
        installed = metadata.version("capstone")
    except metadata.PackageNotFoundError as exc:
        raise X86Error(f"capstone is not installed; expected {CAPSTONE_VERSION}") from exc
    if installed != CAPSTONE_VERSION:
        raise X86Error(f"capstone {installed} is installed; expected {CAPSTONE_VERSION}")


@dataclass(frozen=True, slots=True)
class Insn:
    va: int
    size: int
    mnemonic: str
    op_str: str
    raw: bytes  # the instruction's bytes
    branch_target: int | None  # static destination of a direct call or jump
    rel32_field: int | None  # linear address of a rel32 call/jump displacement
    is_call: bool
    is_jump: bool  # any jump: jmp, jcc, loop, jecxz
    is_conditional: bool  # a jump that may fall through
    is_terminal: bool  # flow does not fall through: ret, iret, unconditional jmp


@functools.cache
def _disassembler() -> Cs:
    """The one 32-bit capstone instance, built on first use after the version check."""
    check_capstone()
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    return md


def _branch_target(ci: CsInsn) -> int | None:
    """The destination of a call or jump whose only operand is an immediate, else None."""
    if not (ci.group(CS_GRP_CALL) or ci.group(CS_GRP_JUMP)):
        return None
    operands = ci.operands
    if len(operands) != 1 or operands[0].type != X86_OP_IMM:
        return None
    return operands[0].imm & _ADDRESS_MASK


def _insn(ci: CsInsn) -> Insn:
    target = _branch_target(ci)
    rel32_field = None
    if target is not None and ci.imm_size == _REL32_SIZE:
        rel32_field = ci.address + ci.imm_offset
    is_jump = ci.group(CS_GRP_JUMP)
    unconditional = ci.id in _UNCONDITIONAL_JUMPS
    returns = any(ci.group(g) for g in _RETURN_GROUPS)
    return Insn(
        va=ci.address,
        size=ci.size,
        mnemonic=ci.mnemonic,
        op_str=ci.op_str,
        raw=bytes(ci.bytes),
        branch_target=target,
        rel32_field=rel32_field,
        is_call=ci.group(CS_GRP_CALL),
        is_jump=is_jump,
        is_conditional=is_jump and not unconditional,
        is_terminal=returns or unconditional,
    )


def decode(
    code: bytes, va: int, *, data_sites: Container[int] = frozenset()
) -> Iterator[Insn]:
    """Instructions of `code` loaded at `va`, in order. Stops at the end of `code`, at a byte
    capstone cannot decode, or at an instruction start that is in `data_sites`."""
    for ci in _disassembler().disasm(code, va):
        if ci.address in data_sites:
            return
        yield _insn(ci)


def decode_one(code: bytes, va: int) -> Insn | None:
    """The instruction at the start of `code` (loaded at `va`), or None when it does not
    decode."""
    return next(decode(code, va), None)


def is_filler(insn: Insn) -> bool:
    """True for the Watcom alignment filler encodings (see FILLER_ENCODINGS)."""
    return insn.raw in FILLER_ENCODINGS
