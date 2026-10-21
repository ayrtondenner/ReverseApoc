"""The codegen probe: calibrate which idioms each Watcom version and flag set emits, from our own
clean-room probe (probe/cg_basic.c), so the same idioms can then be counted in the game's
non-library code (CID-03, D-10).

Research found mosura's register claims do not reproduce (04-RESEARCH Pitfall 9), so nothing
here is taken from a published fingerprint table: every idiom is matched by its byte encoding and
calibrated per version and flag set. Counts are evidence, not proof. The matching is byte-level
over raw code, so a hit can also be data or the middle of another instruction (research A7); the
setcc and struct-copy encodings are long enough for that to be rare, while the loop and switch
counts are "not decisive" on their own (research Pattern 6). Output holds counts, library names
and SHA-1s, never object or compiler bytes.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Any, NamedTuple

from . import omf
from .cflags import Rule
from .compiler import OBJ_SUFFIX, CompilerError, Runner, check_gate, compile_rule
from .le import LE
from .libmatch import (
    SWEPT_VERSIONS,
    MatchRange,
    read_runtime_csv,
    runtime_csv_path,
    target_view,
)
from .targets import REPO_ROOT


class ProbeError(ValueError):
    """The probe cannot run on its input (a missing runtime map, a malformed calibration)."""


PROBE_DIR = REPO_ROOT / "probe"
PROBE_SOURCES = ("cg_basic.c",)
DEFAULT_PROBE_OUT = REPO_ROOT / "build" / "probe"
COMPILER = "wcc386"

IDIOMS = (
    "setcc_and",
    "setcc_movzx",
    "movsd_unrolled",
    "rep_movsd_small",
    "loop_rotated",
    "loop_top_tested",
    "switch_ascending",
    "switch_descending",
)

# The flag sets every version is calibrated with (04-RESEARCH Pattern 6 and Pitfall 9). Every
# entry names its CPU option, so wcc386's default CPU (research A5) never matters.
FLAG_SETS = (
    ("-3r", "-s"),  # 386 register convention: setcc;movzx, mov ecx,5 .. rep movsd
    ("-4r", "-s"),  # 486: setcc;and on both versions, mov ecx,5 .. rep movsd
    ("-5r", "-s"),  # Pentium: unrolled movsd; 11.0 branches instead of setcc
    ("-5r",),  # without -s: the __CHK stack-check calls appear
    ("-4r", "-s", "-ox"),  # full optimisation at -4: switch order (ascending on both, measured)
    ("-5r", "-s", "-ox"),  # full optimisation at -5: switch order (ascending on both, measured)
    ("-5r", "-s", "-oneatx"),  # the "fastest code" set: changes loop shape
    ("-5r", "-s", "-os"),  # optimise for size
    ("-5r", "-s", "-fpi87"),  # inline x87 without the emulator: noemu387
    ("-5s", "-s"),  # stack convention: math387s (no CLIB library is requested, measured)
)

Span = tuple[int, int]  # [start, end) offsets inside the code
Match = tuple[Span, ...]  # the pieces of code one idiom hit reads, in code order


# ---- byte patterns -----------------------------------------------------------------------------

# setcc al (0F 90..9F C0); and eax,0FFh (25 FF 00 00 00)
_SETCC_AND = re.compile(rb"\x0f[\x90-\x9f]\xc0\x25\xff\x00\x00\x00")
# setcc al (0F 90..9F C0); movzx eax,al (0F B6 C0)
_SETCC_MOVZX = re.compile(rb"\x0f[\x90-\x9f]\xc0\x0f\xb6\xc0")
# two or more movsd (A5) not preceded by rep (F3) or by another movsd: one unrolled copy per run
# (_movsd_runs reads every fixup byte as _OPERAND_BYTE first)
_MOVSD_RUN = re.compile(rb"(?<![\xf3\xa5])\xa5{2,}")
_OPERAND_BYTE = 0x00  # stands for a fixup byte: an operand, never movsd (A5) or rep (F3)
# mov ecx,imm32 (B9 id) with a count of 1..16 dwords; up to four register-to-register mov
# (89 /r or 8B /r with ModRM mod=11); rep movsd (F3 A5). At -3r and -4r both versions load edi
# and esi between the count and the copy (measured on the probe, so the shape is not adjacent).
_MOV_ECX_IMM32 = 0xB9
_IMM32_SIZE = 4
_MOV_REG_OPCODES = (0x89, 0x8B)  # mov r/m32,r32 and mov r32,r/m32
_MODRM_MOD_REG = range(0xC0, 0x100)  # ModRM mod=11 (bits 7-6): both operands are registers
_REP_MOVSD = bytes((0xF3, 0xA5))  # rep movsd
SMALL_COPY_DWORDS = range(1, 17)  # the ecx counts taken as a small struct copy
SMALL_COPY_MOVES = 4  # register moves allowed between mov ecx and rep movsd


def _byte_class(values: Iterable[int]) -> bytes:
    """A regex class matching one byte of `values`."""
    return b"[" + b"".join(re.escape(bytes((value,))) for value in values) + b"]"


_REP_MOVSD_SMALL = re.compile(
    re.escape(bytes((_MOV_ECX_IMM32,)))
    + _byte_class(SMALL_COPY_DWORDS)
    + re.escape(bytes(_IMM32_SIZE - 1))  # the high bytes of a count below 256
    + b"(?:%b%b){0,%d}"
    % (_byte_class(_MOV_REG_OPCODES), _byte_class(_MODRM_MOD_REG), SMALL_COPY_MOVES)
    + re.escape(_REP_MOVSD)
)
# cmp eax,imm8 (83 F8 ib), cmp eax,imm32 (3D id) or cmp al,imm8 (3C ib); found at every offset
_COMPARE = re.compile(rb"(?=(\x83\xf8.|\x3d.{4}|\x3c.))", re.DOTALL)
_CMP_EAX_IMM32 = 0x3D
_CMP_AL_IMM8 = 0x3C
_CMP_IMM8_AT = 2  # 83 F8 ib: the immediate follows the opcode and the ModRM byte
_CMP_IMM_AT = 1  # 3D id and 3C ib: the immediate follows the opcode

# Jump opcodes (Intel SDM vol. 2, JMP and Jcc).
_JMP_REL8 = 0xEB  # jmp rel8
_JMP_REL32 = 0xE9  # jmp rel32
_JCC_REL8 = range(0x70, 0x80)  # jcc rel8 (jo .. jg)
_TWO_BYTE = 0x0F  # escape: 0F 80..8F is jcc rel32
_JCC_REL32 = range(0x80, 0x90)
_REL8_SIZE, _REL32_SIZE = 1, 4

# Shape limits: the loop top's exit test sits within 16 bytes of the backward jmp's target; a
# switch compare is followed by its jcc within 6 bytes, and the next compare of its chain starts
# within 12 bytes of that jcc (every measured probe chain, 11.0 -ox included, fits); a chain of
# at least 3 compares fits in 64.
LOOP_TOP_WINDOW = 16
SWITCH_JCC_GAP = 6
SWITCH_STEP_GAP = 12
SWITCH_WINDOW = 64
SWITCH_MIN_COMPARES = 3


class _Jump(NamedTuple):
    start: int
    end: int  # one past the displacement: the address the target is relative to
    target: int
    conditional: bool


def _rel(code: bytes, at: int, size: int) -> int:
    return int.from_bytes(code[at : at + size], "little", signed=True)


def _jump_at(code: bytes, i: int) -> _Jump | None:
    """The jmp or jcc whose opcode starts at `i`, if the bytes there encode one."""
    op = code[i]
    if op in (_JMP_REL8, _JMP_REL32) or op in _JCC_REL8:
        size = _REL8_SIZE if op != _JMP_REL32 else _REL32_SIZE
        disp, conditional = i + 1, op in _JCC_REL8
    elif op == _TWO_BYTE and i + 1 < len(code) and code[i + 1] in _JCC_REL32:
        size, disp, conditional = _REL32_SIZE, i + 2, True
    else:
        return None
    end = disp + size
    if end > len(code):
        return None
    return _Jump(i, end, end + _rel(code, disp, size), conditional)


def _jumps(code: bytes) -> list[_Jump]:
    """Every byte offset read as a jump opcode (byte-level, research A7)."""
    return [jump for i in range(len(code)) if (jump := _jump_at(code, i)) is not None]


def _span(jump: _Jump) -> Span:
    return (jump.start, jump.end)


# ---- counters: each yields the pieces of every hit ---------------------------------------------


Counter = Callable[[bytes, frozenset[int]], Iterator[Match]]  # (code, fixup mask) -> hits


def _regex_matches(pattern: re.Pattern[bytes]) -> Callable[[bytes], Iterator[Match]]:
    def matches(code: bytes) -> Iterator[Match]:
        return ((match.span(),) for match in pattern.finditer(code))

    return matches


def _code_only(counter: Callable[[bytes], Iterator[Match]]) -> Counter:
    """A counter that reads only the code; count_idioms drops its hits that touch the mask."""

    def matches(code: bytes, mask: frozenset[int]) -> Iterator[Match]:
        return counter(code)

    return matches


def _movsd_runs(code: bytes, mask: frozenset[int]) -> Iterator[Match]:
    """One hit per _MOVSD_RUN run, with every fixup byte read as _OPERAND_BYTE. A fixup byte is
    an operand of the instruction before or after the run, never a movsd or a rep prefix, so it
    ends a run and never blocks one, whatever its relocated value; it is never part of a run.
    Only an unmasked neighbour decides: A5 extends the run, F3 before it makes it rep movsd."""
    view = bytearray(code)
    for offset in (offset for offset in mask if offset < len(view)):
        view[offset] = _OPERAND_BYTE
    return ((match.span(),) for match in _MOVSD_RUN.finditer(view))


def _rotated_loops(code: bytes) -> Iterator[Match]:
    """A forward jmp to a bottom test, and a later backward jcc to the instruction right after
    that jmp; one hit per backward jcc."""
    jumps = _jumps(code)
    forward_by_end: dict[int, list[_Jump]] = {}
    for jump in jumps:
        if not jump.conditional and jump.target > jump.end:
            forward_by_end.setdefault(jump.end, []).append(jump)
    for jcc in jumps:
        if not jcc.conditional or jcc.target >= jcc.start:
            continue
        entry = next(
            (j for j in forward_by_end.get(jcc.target, ()) if j.target <= jcc.start), None
        )
        if entry is not None:
            yield (_span(entry), _span(jcc))


def _top_tested_loops(code: bytes) -> Iterator[Match]:
    """A backward jmp whose target starts, within LOOP_TOP_WINDOW bytes, a forward jcc that
    exits past the backward jmp; one hit per backward jmp."""
    jumps = _jumps(code)
    conditional_at = {jump.start: jump for jump in jumps if jump.conditional}
    for back in jumps:
        if back.conditional or back.target > back.start or back.target < 0:
            continue
        window = range(back.target, min(back.target + LOOP_TOP_WINDOW, back.start))
        candidates = (conditional_at.get(at) for at in window)
        exits = (c for c in candidates if c is not None and c.end <= back.start)
        exit_test = next((c for c in exits if c.target >= back.end), None)
        if exit_test is not None:
            yield (_span(exit_test), _span(back))


class _Compare(NamedTuple):
    start: int
    end: int
    value: int
    jcc: _Jump  # the first jcc within SWITCH_JCC_GAP bytes after the compare


def _compare_value(raw: bytes) -> int:
    """The immediate: imm8 of 83 F8 is sign-extended, imm32 of 3D is signed, imm8 of 3C (al) is
    unsigned."""
    if raw[0] == _CMP_AL_IMM8:
        return raw[_CMP_IMM_AT]
    at = _CMP_IMM_AT if raw[0] == _CMP_EAX_IMM32 else _CMP_IMM8_AT
    return int.from_bytes(raw[at:], "little", signed=True)


def _paired_compares(code: bytes) -> Iterator[_Compare]:
    for match in _COMPARE.finditer(code):
        raw = match.group(1)
        start, end = match.start(), match.start() + len(raw)
        jcc = next(
            (
                jump
                for at in range(end, min(end + SWITCH_JCC_GAP + 1, len(code)))
                if (jump := _jump_at(code, at)) is not None and jump.conditional
            ),
            None,
        )
        if jcc is not None:
            yield _Compare(start, end, _compare_value(raw), jcc)


def _direction(a: int, b: int) -> int:
    return (b > a) - (b < a)


def _step(prev: _Compare, cmp: _Compare) -> int:
    """+1 or -1, the direction from prev to cmp, when cmp starts within SWITCH_STEP_GAP bytes of
    prev's jcc; 0 when it starts further away (another function) or compares the same value."""
    if cmp.start - prev.jcc.end > SWITCH_STEP_GAP:
        return 0
    return _direction(prev.value, cmp.value)


def _switch_chains(code: bytes) -> Iterator[tuple[int, Match]]:
    """(direction, pieces) of every chain of at least SWITCH_MIN_COMPARES compares, each paired
    with a jcc and starting within SWITCH_STEP_GAP bytes of the previous jcc, all within
    SWITCH_WINDOW bytes, immediates strictly monotonic. A compare that turns the direction ends
    the chain and starts the next one together with the compare before it."""
    chain: list[_Compare] = []

    def finished() -> Iterator[tuple[int, Match]]:
        if len(chain) >= SWITCH_MIN_COMPARES:
            pieces = tuple(p for c in chain for p in ((c.start, c.end), _span(c.jcc)))
            yield _direction(chain[0].value, chain[1].value), pieces

    for cmp in _paired_compares(code):
        if chain and cmp.start < chain[-1].jcc.end:
            continue  # overlaps the previous compare or its jcc: not an instruction
        step = _step(chain[-1], cmp) if chain else 0
        heading = _direction(chain[0].value, chain[1].value) if len(chain) > 1 else step
        if step and step == heading and cmp.end - chain[0].start <= SWITCH_WINDOW:
            chain.append(cmp)
            continue
        yield from finished()
        chain = [chain[-1], cmp] if step and step != heading else [cmp]
    yield from finished()


def _switches(direction: int) -> Callable[[bytes], Iterator[Match]]:
    def matches(code: bytes) -> Iterator[Match]:
        return (pieces for d, pieces in _switch_chains(code) if d == direction)

    return matches


_COUNTERS: dict[str, Counter] = {
    "setcc_and": _code_only(_regex_matches(_SETCC_AND)),
    "setcc_movzx": _code_only(_regex_matches(_SETCC_MOVZX)),
    "movsd_unrolled": _movsd_runs,
    "rep_movsd_small": _code_only(_regex_matches(_REP_MOVSD_SMALL)),
    "loop_rotated": _code_only(_rotated_loops),
    "loop_top_tested": _code_only(_top_tested_loops),
    "switch_ascending": _code_only(_switches(1)),
    "switch_descending": _code_only(_switches(-1)),
}


def _allowed(match: Match, *, base: int, exclude: Sequence[Span], mask: frozenset[int]) -> bool:
    """False when a piece of the match touches a masked offset, or when the match (from its
    first piece to its last) overlaps an excluded VA range. Bytes between pieces, such as a loop
    body with a call in it, may be masked."""
    if any(offset in mask for start, end in match for offset in range(start, end)):
        return False
    low, high = base + match[0][0], base + match[-1][1]
    return not any(ex_start < high and low < ex_end for ex_start, ex_end in exclude)


def count_idioms(
    code: bytes,
    *,
    base: int = 0,
    exclude: Iterable[Span] = (),
    mask: frozenset[int] = frozenset(),
) -> dict[str, int]:
    """How often each idiom occurs in `code`, in IDIOMS order. `base` is the VA of code[0];
    `exclude` holds VA ranges [start, end) (e.g. the runtime library map) and `mask` code
    offsets (fixup sites); a match touching either by one byte is not counted."""
    exclude = tuple(exclude)
    return {
        name: sum(
            1
            for match in _COUNTERS[name](code, mask)
            if _allowed(match, base=base, exclude=exclude, mask=mask)
        )
        for name in IDIOMS
    }


# ---- struct copies by size: evidence for the -4/-5 CPU question, not a calibrated idiom ---------
#
# The probe calibrates one struct size (five dwords). Clean-room copies of other sizes (04-10
# review fix round 1) unroll at small sizes and use rep at large ones whatever the CPU option, so
# movsd_unrolled and rep_movsd_small alone cannot say -4 or -5; these counts say which sizes the
# game copies each way. A size key is the dword count n, or "n+k" when k more bytes follow at
# once by movsw (2), movsb (1) or both (3): the struct is 4n+k bytes. Nothing reads them in
# consistent_cells.

RUN_LONG = 6  # unrolled runs of this many movsd or more share one key
RUN_LONG_KEY = f">={RUN_LONG}"
REP_OTHER_KEY = "other"  # a rep copy whose count lies outside SMALL_COPY_DWORDS
# Setup bytes allowed between the end of mov ecx,imm32 and rep movsd. Every byte must belong to
# a recognised setup instruction (below); the longest setup measured in the game is 15 bytes.
REP_COPY_WINDOW = 24

# Setup instructions (Intel SDM vol. 2, MOV and LEA): the copy's esi/edi loads, and loads or
# stores of other registers the compiler schedules between, in any addressing form. Anything
# that writes ecx, or any other instruction (arithmetic, byte or word moves, push, pop, call,
# a prefix), ends the walk: such a copy is not counted.
_MOV_RM_R = 0x89  # mov r/m32,r32: writes the ModRM r/m operand
_MOV_R_RM = 0x8B  # mov r32,r/m32: writes the ModRM reg register
_LEA = 0x8D  # lea r32,m: writes the ModRM reg register; a memory operand only
_MOV_R_IMM32 = range(0xB8, 0xC0)  # B8+rd id: mov r32,imm32 writes register rd
_ECX = 1  # register number of ecx (SDM vol. 2, table 2-2)
_NO_SETUP = -1  # _written's answer for an encoding that is no setup instruction
_MOD_SHIFT, _REG_SHIFT, _FIELD = 6, 3, 0b111  # ModRM: mod (bits 7-6), reg (5-3), r/m (2-0)
_MOD_NO_DISP, _MOD_DISP8, _MOD_DISP32 = 0b00, 0b01, 0b10  # memory operand forms
_MOD_REGISTER = 0b11  # mod=11: the r/m operand is a register
_RM_SIB = 0b100  # r/m=100 with a memory operand: a SIB byte follows
_RM_DISP32 = 0b101  # mod=00 with r/m=101: a disp32 and no base register
_SIB_NO_BASE = 0b101  # mod=00 with SIB base=101: a disp32 and no base register
_DISP8_SIZE, _DISP32_SIZE = 1, 4
_DISP_BY_MOD = {_MOD_NO_DISP: 0, _MOD_DISP8: _DISP8_SIZE, _MOD_DISP32: _DISP32_SIZE}
# What may follow the last movsd at once: movsw (operand-size prefix, movs) copies a word, then
# movsb a byte. Their bytes must be unmasked: a fixup byte is an operand, never movsw or movsb.
_TAILS = ((bytes((0x66, 0xA5)), 2), (bytes((0xA4,)), 1))  # (encoding, bytes copied)


@dataclass(frozen=True)
class CopySizes:
    """Struct copies by size key ("n" or "n+k"), only the sizes found, smallest first."""

    runs: dict[str, int]  # unrolled movsd runs (the movsd_unrolled runs) by length
    reps: dict[str, int]  # mov ecx,n .. rep movsd copies by n


class _Setup(NamedTuple):
    read: Span  # the opcode, ModRM and SIB bytes: the only bytes whose values are read
    end: int  # one past the displacement or immediate, whose value is never read


def _modrm_ends(code: bytes, at: int) -> tuple[int, int] | None:
    """(end of the ModRM and SIB bytes, end of the displacement) for a ModRM byte at `at`."""
    if at >= len(code):
        return None
    mod, rm = code[at] >> _MOD_SHIFT, code[at] & _FIELD
    read = at + 1
    if mod == _MOD_REGISTER:
        return read, read
    disp = _DISP_BY_MOD[mod]
    if rm == _RM_SIB:
        if read >= len(code):
            return None
        if mod == _MOD_NO_DISP and code[read] & _FIELD == _SIB_NO_BASE:
            disp = _DISP32_SIZE
        read += 1
    elif mod == _MOD_NO_DISP and rm == _RM_DISP32:
        disp = _DISP32_SIZE
    return read, read + disp


def _written(op: int, modrm: int) -> int | None:
    """The register a ModRM-form setup writes (None: memory), or _NO_SETUP."""
    mod, reg, rm = modrm >> _MOD_SHIFT, (modrm >> _REG_SHIFT) & _FIELD, modrm & _FIELD
    if op == _MOV_RM_R:
        return rm if mod == _MOD_REGISTER else None
    if op == _LEA and mod == _MOD_REGISTER:
        return _NO_SETUP  # lea takes a memory operand only
    return reg


def _setup_at(code: bytes, at: int) -> _Setup | None:
    """The setup instruction at `at`, if the bytes there encode one that leaves ecx alone. Its
    read span becomes a piece of the copy, so count_idioms' rule drops a copy whose opcode, ModRM
    or SIB bytes are masked; its displacement or immediate lies between pieces and may be masked
    (a relocated address): only its length, which the opcode and ModRM fix, is used."""
    if at >= len(code):
        return None
    op = code[at]
    if op in _MOV_R_IMM32:
        written, ends = op - _MOV_R_IMM32.start, (at + 1, at + 1 + _IMM32_SIZE)
    elif op in (_MOV_RM_R, _MOV_R_RM, _LEA) and (ends := _modrm_ends(code, at + 1)):
        written = _written(op, code[at + 1])
    else:
        return None
    read_end, end = ends
    if written in (_ECX, _NO_SETUP) or end > len(code):
        return None
    return _Setup((at, read_end), end)


def _setup_to_rep(code: bytes, at: int) -> tuple[int, list[Span]] | None:
    """(offset of the rep movsd, read spans of the setup) when setup instructions lead from `at`
    to a rep movsd starting at most REP_COPY_WINDOW bytes later."""
    pieces: list[Span] = []
    limit = at + REP_COPY_WINDOW
    while at <= limit:
        if code[at : at + len(_REP_MOVSD)] == _REP_MOVSD:
            return at, pieces
        setup = _setup_at(code, at)
        if setup is None:
            return None
        pieces.append(setup.read)
        at = setup.end
    return None


def _tail(code: bytes, at: int, mask: frozenset[int]) -> tuple[int, tuple[Span, ...]]:
    """(bytes copied, pieces) of a movsw and/or movsb starting at `at`; (0, ()) without one."""
    copied, end = 0, at
    for encoding, size in _TAILS:
        stop = end + len(encoding)
        if code[end:stop] == encoding and mask.isdisjoint(range(end, stop)):
            copied, end = copied + size, stop
    return copied, ((at, end),) if copied else ()


Size = tuple[int, int]  # (dwords, tail bytes)


def _sized_runs(code: bytes, mask: frozenset[int]) -> Iterator[tuple[Size, Match]]:
    """(size, pieces) of every movsd_unrolled run; one movsd is one A5 byte."""
    for ((start, end),) in _movsd_runs(code, mask):
        tail, pieces = _tail(code, end, mask)
        yield (end - start, tail), ((start, end), *pieces)


def _offsets(code: bytes, byte: int) -> Iterator[int]:
    """Every offset of `byte` in `code` (byte-level, research A7)."""
    at = code.find(byte)
    while at >= 0:
        yield at
        at = code.find(byte, at + 1)


def _sized_reps(code: bytes, mask: frozenset[int]) -> Iterator[tuple[Size, int, Match]]:
    """(size, offset of the rep movsd, pieces) of every mov ecx,imm32 whose setup reaches a rep
    movsd. The pieces are mov ecx,imm32 (its count is read), the read bytes of each setup
    instruction, rep movsd and the tail; a setup's displacement or immediate lies between."""
    for start in _offsets(code, _MOV_ECX_IMM32):
        count_end = start + 1 + _IMM32_SIZE
        found = _setup_to_rep(code, count_end) if count_end <= len(code) else None
        if found is None:
            continue
        rep, setup = found
        rep_end = rep + len(_REP_MOVSD)
        tail, tail_pieces = _tail(code, rep_end, mask)
        count = int.from_bytes(code[start + 1 : count_end], "little")
        yield (count, tail), rep, ((start, count_end), *setup, (rep, rep_end), *tail_pieces)


def _first_per_rep(hits: Iterable[tuple[Size, int, Match]]) -> Iterator[Size]:
    """One copy per rep movsd: a mov ecx,imm32 read inside an earlier copy's setup (the B9 of
    `mov edi,[ecx+5]`, say) reaching the same rep movsd is not counted again."""
    seen: set[int] = set()
    for size, rep, _ in hits:
        if rep not in seen:
            seen.add(rep)
            yield size


def _size_key(dwords: int, tail: int) -> str:
    return f"{dwords}+{tail}" if tail else str(dwords)


def _run_key(size: Size) -> tuple[Size, str]:
    """(sort key, size key) of a run: its length and tail, or RUN_LONG_KEY from RUN_LONG on."""
    if size[0] >= RUN_LONG:
        return (RUN_LONG, 0), RUN_LONG_KEY
    return size, _size_key(*size)


def _rep_key(size: Size) -> tuple[Size, str]:
    """(sort key, size key) of a rep copy: its count and tail, or REP_OTHER_KEY for a count
    outside SMALL_COPY_DWORDS."""
    if size[0] not in SMALL_COPY_DWORDS:
        return (SMALL_COPY_DWORDS.stop, 0), REP_OTHER_KEY
    return size, _size_key(*size)


def _histogram(keys: Iterable[tuple[Size, str]]) -> dict[str, int]:
    """Copies per size key, smallest size first."""
    counts: dict[tuple[Size, str], int] = {}
    for key in keys:
        counts[key] = counts.get(key, 0) + 1
    return {label: n for (_, label), n in sorted(counts.items())}


def copy_sizes(
    code: bytes,
    *,
    base: int = 0,
    exclude: Iterable[Span] = (),
    mask: frozenset[int] = frozenset(),
) -> CopySizes:
    """The unrolled movsd runs and the mov ecx,n .. rep movsd copies in `code` by size, under
    count_idioms' rules: a hit whose pieces touch `mask`, or whose extent (first piece to last)
    touches an `exclude` range, is not counted. The runs are exactly the movsd_unrolled runs."""
    exclude = tuple(exclude)

    def allowed(match: Match) -> bool:
        return _allowed(match, base=base, exclude=exclude, mask=mask)

    runs = (size for size, match in _sized_runs(code, mask) if allowed(match))
    reps = _first_per_rep(hit for hit in _sized_reps(code, mask) if allowed(hit[2]))
    return CopySizes(_histogram(map(_run_key, runs)), _histogram(map(_rep_key, reps)))


def object_code(data: bytes) -> list[tuple[bytes, frozenset[int]]]:
    """(bytes, fixup mask) of every CODE segment of one OMF object, in SEGDEF order."""
    return [(seg.data, seg.mask) for seg in omf.read_object(data).segments if seg.is_code]


def chk_sites(module: omf.Module) -> int:
    """Self-relative fixups to the extern __CHK: the stack-check calls a build without -s has."""
    fixups = [f for seg in module.segments for f in seg.fixups]
    fixups += [f for comdat in module.comdats for f in comdat.fixups]
    return sum(
        1
        for f in fixups
        if not f.segment_relative and f.target_kind == "extern" and f.target_name == "__CHK"
    )


# ---- calibration -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Cell:
    """What one version and flag set emits for the probe sources."""

    version: str
    flags: tuple[str, ...]
    counts: dict[str, int]  # IDIOMS order, summed over every CODE segment of every source
    chk_calls: int
    default_libraries: tuple[str, ...]
    normalized_sha1: str


@dataclass(frozen=True)
class Calibration:
    cells: tuple[Cell, ...]  # SWEPT_VERSIONS order, then flag-set order
    skipped: tuple[tuple[str, str], ...]  # (version, reason) for versions the gate refused

    def cell(self, version: str, flags: Sequence[str]) -> Cell:
        flags = tuple(flags)
        found = next((c for c in self.cells if (c.version, c.flags) == (version, flags)), None)
        if found is None:
            raise KeyError(f"no calibration cell for {version} {' '.join(flags)}")
        return found

    def ties(self) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
        """(flags, versions) for versions whose objects are equal after normalization under the
        same flags (D-10: stated as a tie, never merged or voted apart), in cell order."""
        groups: dict[tuple[tuple[str, ...], str], list[str]] = {}
        for c in self.cells:
            groups.setdefault((c.flags, c.normalized_sha1), []).append(c.version)
        return [(flags, tuple(vs)) for (flags, _), vs in groups.items() if len(vs) > 1]

    def format(self) -> str:
        header = ["version", f"{'flags':<20}", *IDIOMS, "chk", "default_libraries", "sha1"]
        lines = ["  ".join(header)]
        for c in self.cells:
            counts = (f"{c.counts[name]:>{len(name)}}" for name in IDIOMS)
            libraries = ",".join(c.default_libraries) or "-"
            row = [f"{c.version:<7}", f"{' '.join(c.flags):<20}", *counts]
            lines.append("  ".join([*row, f"{c.chk_calls:>3}", libraries, c.normalized_sha1]))
        lines += [f"tie: {' '.join(flags)}: {' '.join(vs)}" for flags, vs in self.ties()]
        lines += [f"skipped: {version}: {reason}" for version, reason in self.skipped]
        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        """The same numbers as format(): counts, library names and SHA-1s, never bytes."""
        return {
            "idioms": list(IDIOMS),
            "cells": [
                {
                    "version": c.version,
                    "flags": list(c.flags),
                    "counts": dict(c.counts),
                    "chk_calls": c.chk_calls,
                    "default_libraries": list(c.default_libraries),
                    "normalized_sha1": c.normalized_sha1,
                }
                for c in self.cells
            ],
            "ties": [{"flags": list(f), "versions": list(vs)} for f, vs in self.ties()],
            "skipped": [{"version": v, "reason": r} for v, r in self.skipped],
        }

    @classmethod
    def from_json(cls, data: Any) -> Calibration:
        """The calibration to_json() wrote. Refuses (ProbeError naming the problem) any other
        shape, and idioms other than IDIOMS: a calibration from other counters cannot be
        compared with this scan. "ties" is derived from the cells and not read."""
        _check(isinstance(data, dict), "the calibration is not an object")
        _check(data.get("idioms") == list(IDIOMS), f"idioms are not {list(IDIOMS)}; recalibrate")
        cells = data.get("cells")
        skipped = data.get("skipped", [])
        _check(isinstance(cells, list), "cells is not a list")
        _check(isinstance(skipped, list), "skipped is not a list")
        return cls(
            tuple(_cell_from_json(n, cell) for n, cell in enumerate(cells, start=1)),
            tuple(_skip_from_json(n, skip) for n, skip in enumerate(skipped, start=1)),
        )


def _check(condition: bool, problem: str) -> None:
    if not condition:
        raise ProbeError(problem)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _cell_from_json(n: int, cell: Any) -> Cell:
    _check(isinstance(cell, dict), f"cell {n} is not an object")
    counts = cell.get("counts")
    _check(isinstance(cell.get("version"), str), f"cell {n}: version is not a string")
    _check(_is_strings(cell.get("flags")), f"cell {n}: flags is not a list of strings")
    _check(
        isinstance(counts, dict) and list(counts) == list(IDIOMS)
        and all(_is_int(v) for v in counts.values()),
        f"cell {n}: counts does not hold one integer per idiom, in IDIOMS order",
    )  # fmt: skip
    _check(_is_int(cell.get("chk_calls")), f"cell {n}: chk_calls is not an integer")
    _check(_is_strings(cell.get("default_libraries")),
           f"cell {n}: default_libraries is not a list of strings")  # fmt: skip
    _check(isinstance(cell.get("normalized_sha1"), str), f"cell {n}: normalized_sha1 is missing")
    return Cell(cell["version"], tuple(cell["flags"]), dict(counts), cell["chk_calls"],
                tuple(cell["default_libraries"]), cell["normalized_sha1"])  # fmt: skip


def _skip_from_json(n: int, skip: Any) -> tuple[str, str]:
    _check(
        isinstance(skip, dict) and isinstance(skip.get("version"), str)
        and isinstance(skip.get("reason"), str),
        f"skipped entry {n} lacks a version or a reason",
    )  # fmt: skip
    return skip["version"], skip["reason"]


def _version_order(versions: Iterable[str]) -> list[str]:
    """SWEPT_VERSIONS order, then any other version by name; duplicates dropped."""
    rank = {version: i for i, version in enumerate(SWEPT_VERSIONS)}
    return sorted(set(versions), key=lambda v: (rank.get(v, len(rank)), v))


def flag_id(flags: Sequence[str]) -> str:
    """The directory name of a flag set: the flags without dashes, joined by "_"."""
    return "_".join(flag.lstrip("-") for flag in flags)


def _combined_sha1(hashes: list[str]) -> str:
    """One source: its normalized SHA-1. Several: a SHA-1 over theirs, in source order."""
    if len(hashes) == 1:
        return hashes[0]
    return hashlib.sha1("\n".join(hashes).encode("ascii")).hexdigest()


def _cell(version: str, flags: tuple[str, ...], objects: list[tuple[Path, str]]) -> Cell:
    """Sum the counts and stack checks over the objects; join their default libraries."""
    counts = dict.fromkeys(IDIOMS, 0)
    chk_calls = 0
    libraries: list[str] = []
    for obj, _ in objects:
        data = obj.read_bytes()
        for code, mask in object_code(data):
            for name, count in count_idioms(code, mask=mask).items():
                counts[name] += count
        module = omf.read_object(data)
        chk_calls += chk_sites(module)
        libraries += [lib for lib in module.default_libraries if lib not in libraries]
    sha1 = _combined_sha1([normalized for _, normalized in objects])
    return Cell(version, flags, counts, chk_calls, tuple(libraries), sha1)


def calibrate(
    versions: Iterable[str] = SWEPT_VERSIONS,
    flag_sets: Iterable[Sequence[str]] = FLAG_SETS,
    *,
    sources: Iterable[str | Path] = PROBE_SOURCES,
    out_dir: Path | str = DEFAULT_PROBE_OUT,
    root: Path | str | None = None,
    manifest: Path | str | None = None,
    watcom_dir: Path | str | None = None,
    runner: Runner | None = None,
    platform: str | None = None,
    log: Path | str | None = None,
    stamps: Path | str | None = None,
) -> Calibration:
    """Compile every probe source with every version whose gate passes and every flag set, into
    out_dir/<version>/<flag id>/<stem>.obj, and record one Cell per (version, flags). A version
    the gate refuses is listed as skipped with the reason; a failed compile raises CompilerError
    naming the cell. Sources are names under PROBE_DIR, or paths."""
    out_dir = Path(out_dir)
    sources = [PROBE_DIR / source for source in sources]
    flag_sets = [tuple(flags) for flags in flag_sets]
    options: dict[str, Any] = dict(
        manifest=manifest, watcom_dir=watcom_dir, runner=runner, platform=platform, stamps=stamps
    )
    cells: list[Cell] = []
    skipped: list[tuple[str, str]] = []
    for version in _version_order(versions):
        try:
            check_gate(COMPILER, version, **options)
        except CompilerError as exc:
            skipped.append((version, str(exc)))
            continue
        for flags in flag_sets:
            rule = Rule("*", COMPILER, version, flags, 0)
            cell_dir = out_dir / version / flag_id(flags)
            objects = [_compile_probe(rule, src, cell_dir, root, log, options) for src in sources]
            cells.append(_cell(version, flags, objects))
    return Calibration(tuple(cells), tuple(skipped))


def _compile_probe(
    rule: Rule,
    src: Path,
    cell_dir: Path,
    root: Path | str | None,
    log: Path | str | None,
    options: dict[str, Any],
) -> tuple[Path, str]:
    """(object, normalized SHA-1) of one probe source compiled into cell_dir/<stem>.obj."""
    obj = cell_dir / f"{src.stem}{OBJ_SUFFIX}"
    result = compile_rule(rule, src, obj, root=root, log=log, **options)
    if not result.ok or result.normalized_sha1 is None:
        raise CompilerError(
            f"probe compile failed: {rule.version} {' '.join(rule.flags)} {src}: "
            f"exit {result.returncode}\n{result.output}"
        )
    return obj, result.normalized_sha1


# ---- scanning an EXE's non-library code (CID-03, D-06, D-10) ------------------------------------


@dataclass(frozen=True)
class ExeScan:
    """The idioms counted in one EXE's code object outside every runtime.csv range."""

    exe: str
    code_base: int  # linear address of the code object
    code_size: int
    nonlib_bytes: int  # code bytes outside every runtime row
    lib_bytes: int  # code bytes inside a runtime row
    counts: dict[str, int]  # IDIOMS order, non-library code only
    chk_calls: int = 0  # push imm32; call __CHK in non-library code
    chk_blocks: tuple[tuple[int, int], ...] = ()  # (64 KiB block, calls), by block
    evidence: tuple[str, ...] = ()  # one line per observable flag (D-08)
    # struct copies by size in non-library code: cpu -4/-5 evidence, never read by the verdict
    copy_sizes: CopySizes = field(default_factory=lambda: CopySizes({}, {}))

    def format(self) -> str:
        """A header line, one indented line per idiom, then the evidence lines."""
        end = self.code_base + self.code_size
        lines = [
            f"{self.exe}: code {self.code_base:#010x}..{end:#010x}, {self.code_size} bytes: "
            f"{self.nonlib_bytes} non-library, {self.lib_bytes} in runtime rows"
        ]
        width = max(len(name) for name in IDIOMS)
        lines += [f"  {name:<{width}}  {self.counts[name]}" for name in IDIOMS]
        lines += self.evidence
        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        """The same numbers as format(): counts, addresses and block numbers, never bytes."""
        return {
            "exe": self.exe,
            "code_base": self.code_base,
            "code_size": self.code_size,
            "nonlib_bytes": self.nonlib_bytes,
            "lib_bytes": self.lib_bytes,
            "counts": dict(self.counts),
            "struct_copy_sizes": {
                "movsd_runs": dict(self.copy_sizes.runs),
                "rep_movsd": dict(self.copy_sizes.reps),
            },
            "chk_calls": self.chk_calls,
            "chk_blocks": [{"block": block, "calls": n} for block, n in self.chk_blocks],
            "evidence": list(self.evidence),
        }


def runtime_rows(name: str, runtime: Path | str | None = None) -> list[MatchRange]:
    """The runtime map of manifest target `name` (default config/<stem>/runtime.csv, D-06). A
    missing map is refused rather than counting the whole code object as game code."""
    path = Path(runtime) if runtime is not None else runtime_csv_path(name)
    if not path.is_file():
        raise ProbeError(
            f"runtime map {path} not found; run `uv run reverseapoc libmatch {name} --write` "
            "(or --output PATH, then pass --runtime PATH)"
        )
    return read_runtime_csv(path)


def _covered(ranges: Iterable[Span], low: int, high: int) -> int:
    """Bytes of [low, high) that lie in at least one of `ranges`."""
    total, reach = 0, low
    for start, end in sorted(ranges):
        start, end = max(start, reach), min(end, high)
        if end > start:
            total += end - start
            reach = end
    return total


def _overlaps(low: int, high: int, ranges: Iterable[Span]) -> bool:
    return any(start < high and low < end for start, end in ranges)


# push imm32 (68 id) directly followed by call rel32 (E8 cd): Watcom's stack-check prologue,
# `push <frame size>; call __CHK`, in every function built without -s. Found at every offset.
_PUSH_IMM32 = 0x68
_CALL_REL32 = 0xE8
_PUSH_SIZE = 1 + _IMM32_SIZE
_CALL_SIZE = 1 + _REL32_SIZE
_CHK_CALL = re.compile(
    b"(?=%b.{%d}%b.{%d})"
    % (re.escape(bytes((_PUSH_IMM32,))), _IMM32_SIZE, re.escape(bytes((_CALL_REL32,))),
       _REL32_SIZE),
    re.DOTALL,
)  # fmt: skip
CHK_PUBLIC = "__CHK"
CHK_BLOCK = 0x10000  # call sites are grouped by 64 KiB block of linear address (D-08)


def _chk_sites(
    code: bytes, base: int, targets: Sequence[Span], exclude: Sequence[Span]
) -> Iterator[int]:
    """The linear address of every push of a push/call pair whose call lands in `targets` and
    whose ten bytes lie outside `exclude`."""
    for match in _CHK_CALL.finditer(code):
        site = base + match.start()
        if _overlaps(site, site + _PUSH_SIZE + _CALL_SIZE, exclude):
            continue
        call_end = site + _PUSH_SIZE + _CALL_SIZE
        target = call_end + _rel(code, match.start() + _PUSH_SIZE + 1, _REL32_SIZE)
        if _overlaps(target, target + 1, targets):
            yield site


def chk_calls(
    code: bytes, base: int, rows: Iterable[MatchRange], exclude: Iterable[Span]
) -> tuple[int, tuple[tuple[int, int], ...]]:
    """(calls, ((block, calls), ...)) for every `push imm32; call rel32` in `code` (linear
    address `base`) whose call target lies in a runtime row publishing __CHK and whose site lies
    outside `exclude`; blocks are 64 KiB aligned and sorted."""
    targets = [(r.start, r.end) for r in rows if CHK_PUBLIC in r.publics]
    blocks: dict[int, int] = {}
    for site in _chk_sites(code, base, targets, tuple(exclude)):
        block = site - site % CHK_BLOCK
        blocks[block] = blocks.get(block, 0) + 1
    return sum(blocks.values()), tuple(sorted(blocks.items()))


# ---- the verdict: which calibration cells the game code is consistent with (D-07, D-10) --------

# The idiom families whose calibrated forms decide a cell. Loop and switch shapes are byte-level
# and not decisive on their own (research A7, Pattern 6): they are reported, never used here.
DECISIVE_FAMILIES = {
    "byte_compare": ("setcc_and", "setcc_movzx"),
    "struct_copy": ("movsd_unrolled", "rep_movsd_small"),
}


def _cell_consistent(cell: Cell, scan: ExeScan) -> bool:
    """False when some decisive family shows idioms in the EXE and the cell emits none of
    them; a family the EXE shows nothing of removes nothing."""
    for family in DECISIVE_FAMILIES.values():
        shown = [name for name in family if scan.counts.get(name, 0) > 0]
        if shown and not any(cell.counts.get(name, 0) > 0 for name in shown):
            return False
    return True


def consistent_cells(calibration: Calibration, scan: ExeScan) -> list[Cell]:
    """The calibration cells (in calibration order) the EXE's non-library idioms are consistent
    with. Nothing is voted: several cells, versions included, may stay (D-07, D-10)."""
    return [cell for cell in calibration.cells if _cell_consistent(cell, scan)]


# ---- one evidence line per observable flag (D-08, D-09) ----------------------------------------

_CONVENTION_SUFFIX = re.compile(r"\d([RS])$")  # CLIB3R, MATH387S, PLIB3R: the convention letter
_OBJ_BIG = 0x2000  # LE object flag: 32-bit ("big") object
_CPU_IDIOMS = ("setcc_and", "setcc_movzx", "movsd_unrolled", "rep_movsd_small")
_SHAPE_IDIOMS = ("loop_rotated", "loop_top_tested", "switch_ascending", "switch_descending")


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _stems(r: MatchRange) -> list[str]:
    return [PurePosixPath(library).stem.upper() for library in r.libraries]


def _fpu_family(stem: str) -> str | None:
    for prefix in ("NOEMU", "EMU", "MATH387", "MATH3"):  # NOEMU before EMU, MATH387 before MATH3
        if stem.startswith(prefix):
            return prefix
    return None


def _convention_line(rows: Sequence[MatchRange]) -> str:
    letters = [{m.group(1) for s in _stems(r) if (m := _CONVENTION_SUFFIX.search(s))} for r in rows]
    r_only = sum(1 for found in letters if found == {"R"})
    s_only = sum(1 for found in letters if found == {"S"})
    both = sum(1 for found in letters if found == {"R", "S"})
    if r_only and s_only:
        reading = "mixed: rows only in 3R and rows only in 3S libraries"
    elif r_only or s_only:
        reading = "register (r) convention" if r_only else "stack (s) convention"
    else:
        reading = "no evidence"
    return (
        f"calling convention: 3R only {_count(r_only, 'row')}, 3S only {_count(s_only, 'row')}, "
        f"both {_count(both, 'row')} (source: runtime rows); {reading}"
    )


def _fpu_line(rows: Sequence[MatchRange]) -> str:
    families = [{_fpu_family(s) for s in _stems(r)} for r in rows]
    emu, noemu, m387, m3 = (sum(1 for f in families if name in f)
                            for name in ("EMU", "NOEMU", "MATH387", "MATH3"))  # fmt: skip
    m3_only = sum(1 for f in families if "MATH3" in f and "MATH387" not in f)
    return (
        f"fpu: EMU387 {_count(emu, 'row')}, NOEMU387 {_count(noemu, 'row')}; "
        f"MATH387 {_count(m387, 'row')}, MATH3 {_count(m3, 'row')} ({m3_only} only in MATH3) "
        "(source: runtime rows); an EMU387 row means some object requested emu387 (-fpi), and "
        "-fpi87 modules linked beside it would not show (research A3)"
    )


def _cpu_line(scan: ExeScan) -> str:
    counts = ", ".join(f"{name} {scan.counts[name]}" for name in _CPU_IDIOMS)
    return (
        f"cpu: {counts} (source: idiom counts in non-library code); read against the "
        "calibration cells (probe calibrate)"
    )


# What the sizes mean, measured on throwaway clean-room struct copies of 2-6, 8 and 16 dwords
# with 0-3 tail bytes, copied through a pointer, into a global, an array element and a local, and
# passed by value, with 10.6 and 11.0 (04-10 review fix round 1; counts in the 04-10 SUMMARY).
COPY_SIZE_READING = (
    "on clean-room copies (10.6, 11.0) only n=5 (20-23 bytes) separates -4 (rep at -4r, -4r -ox) "
    "from -5 (unrolled at -5r with -s, -ox, -oneatx, -os and without -s); 2-4 dwords unroll and "
    "6 or more use rep at both, except -os, which also unrolls 6 and 7 (04-10 review fix round 1)"
)


def _sizes_text(sizes: dict[str, int]) -> str:
    return ", ".join(f"{key}: {n}" for key, n in sizes.items()) or "none"


def _copy_sizes_line(scan: ExeScan) -> str:
    """The cpu line's sibling: struct copies by size, labelled as not calibrated by the probe."""
    sizes = scan.copy_sizes
    return (
        "struct-copy sizes (cpu -4/-5 evidence, not a calibrated idiom): unrolled movsd runs by "
        f"length {_sizes_text(sizes.runs)}; mov ecx,n .. rep movsd by n {_sizes_text(sizes.reps)} "
        "(source: sized struct-copy counts in non-library code; n+k is n dwords then k bytes by "
        "movsw/movsb; a rep copy's setup is mov or lea writing any register but ecx, within "
        f"{REP_COPY_WINDOW} bytes); {COPY_SIZE_READING}"
    )


def _stack_line(rows: Sequence[MatchRange], scan: ExeScan) -> str:
    modules = sorted({r.module for r in rows if CHK_PUBLIC in r.publics})
    if not modules:
        return f"stack checks: {scan.chk_calls} __CHK calls; no runtime row publishes __CHK"
    blocks = ", ".join(f"{block:#010x} {n}" for block, n in scan.chk_blocks) or "none"
    return (
        f"stack checks: {scan.chk_calls} __CHK calls (push imm32; call __CHK) in non-library "
        f"code, by block {blocks} (source: idiom counts, __CHK from runtime row "
        f"{', '.join(modules)}); each call is a function built without -s (research A6)"
    )


def _memory_line(le: LE) -> str:
    objects = le.objects
    big = sum(1 for obj in objects if obj.flags & _OBJ_BIG)
    reading = "; flat 32-bit layout (-mf)" if objects and big == len(objects) else ""
    return (
        f"memory model: {_count(len(objects), 'object')}, {big} with the 32-bit flag "
        f"(source: LE object table){reading}"
    )


def _shapes_line(scan: ExeScan) -> str:
    counts = ", ".join(f"{name} {scan.counts[name]}" for name in _SHAPE_IDIOMS)
    return (
        f"shapes (not decisive): {counts} (source: idiom counts in non-library code; byte-level, "
        "research A7; switch compares cover eax/al only: cmp eax,imm8, cmp eax,imm32, "
        "cmp al,imm8)"
    )


def flag_evidence(le: LE, rows: Iterable[MatchRange], scan: ExeScan) -> tuple[str, ...]:
    """One line per observable flag (D-08), each naming its source and its counts: calling
    convention, fpu, cpu and its struct-copy sizes, stack checks, memory model, then the
    non-decisive loop and switch shapes. A mix of evidence is reported as a mix (D-07)."""
    rows = list(rows)
    return (
        _convention_line(rows),
        _fpu_line(rows),
        _cpu_line(scan),
        _copy_sizes_line(scan),
        _stack_line(rows, scan),
        _memory_line(le),
        _shapes_line(scan),
    )


def scan_exe(le: LE, rows: Iterable[MatchRange], *, exe: str) -> ExeScan:
    """Count IDIOMS in the EXE's code object with every runtime row excluded (a hit touching a
    row by one byte is dropped) and every LE fixup byte masked (a relocated operand is never read
    as an idiom); count the struct copies by size under the same rules and the __CHK calls by
    block, and derive the evidence lines."""
    rows = list(rows)
    view = target_view(le)
    end = view.base + len(view.code)
    exclude = [(r.start, r.end) for r in rows]
    mask = frozenset(va - view.base for va in view.fixup_bytes if view.base <= va < end)
    counts = count_idioms(view.code, base=view.base, exclude=exclude, mask=mask)
    sizes = copy_sizes(view.code, base=view.base, exclude=exclude, mask=mask)
    lib_bytes = _covered(exclude, view.base, end)
    calls, blocks = chk_calls(view.code, view.base, rows, exclude)
    scan = ExeScan(exe, view.base, len(view.code), len(view.code) - lib_bytes, lib_bytes, counts,
                   calls, blocks, copy_sizes=sizes)  # fmt: skip
    return replace(scan, evidence=flag_evidence(le, rows, scan))
