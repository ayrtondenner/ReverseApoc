# SPDX-License-Identifier: GPL-3.0-or-later
"""The control-flow shape of one function (todo structure-first-large-functions): basic blocks,
branches, loops and switch tables, from instructions decoded through `reverseapoc.x86`.

Two readers share one block split:

- `outline`, the context pack's section for a row of MIN_SIZE bytes and up: one line per block
  with its exit, then the loops (back edges). Switch cases come from the caller (asm.case_targets
  reads them from the LE's table fixups).
- `shape`, the counts `check` records for our candidate and for the original (code length,
  blocks, branches), so `attempt check` can print them side by side. No table is resolved
  there, on either side, so the two counts stay comparable.

A block starts at the first instruction, at an in-row jump target, after any jump or return,
and at a switch case. Trailing alignment filler is not code (the length stops before it), and a
block of filler alone (padding before a loop head) is no block. A branch is any jump
instruction: conditional, unconditional, or a table jump.
"""

from __future__ import annotations

from collections.abc import Callable, Container, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .le import SRC_OFF32, SRC_SIZE
from .x86 import Insn, decode, is_alignment_filler

MIN_SIZE = 256  # the owner's line for large rows (the region board's BOARD_MIN_SIZE too)
_FIELD = SRC_SIZE[SRC_OFF32]  # a relocated field at an instruction start: inline table data

type Target = Callable[[Insn], int | None]  # a jump's static destination, or None


def wanted(size: int) -> bool:
    """A row of `size` bytes gets an outline in its pack."""
    return size >= MIN_SIZE


@dataclass(frozen=True, slots=True)
class Shape:
    length: int  # bytes up to the end of the last instruction that is not trailing filler
    blocks: int
    branches: int

    def to_json(self) -> dict[str, Any]:
        return {"length": self.length, "blocks": self.blocks, "branches": self.branches}


@dataclass(frozen=True, slots=True)
class _Block:
    insns: tuple[Insn, ...]

    @property
    def start(self) -> int:
        return self.insns[0].va

    @property
    def end(self) -> int:
        return self.insns[-1].va + self.insns[-1].size

    @property
    def last(self) -> Insn:
        return self.insns[-1]


def instructions(code: bytes, va: int, sites: Container[int]) -> list[Insn]:
    """The instructions of `code` loaded at `va`. A relocated field (`sites`, by field address)
    at an instruction start is inline data and skipped, as is a byte capstone cannot decode.
    asm.walk does the same over LE Fixup objects; check's two sides have only field addresses
    (relocs' RelocResult.ours and .theirs, each field one off32 wide), hence this form."""
    end = va + len(code)
    pos = va
    found: list[Insn] = []
    while pos < end:
        if pos in sites:
            pos += _FIELD
            continue
        before = pos
        for insn in decode(code[pos - va :], pos, data_sites=sites):
            found.append(insn)
            pos = insn.va + insn.size
        if pos == before:
            pos += 1
    return found


def _code(insns: Sequence[Insn]) -> list[Insn]:
    """`insns` without their trailing alignment filler."""
    kept = list(insns)
    while kept and is_alignment_filler(kept[-1]):
        kept.pop()
    return kept


def _inside(va: int | None, start: int, end: int) -> bool:
    return va is not None and start <= va < end


def _leaders(
    insns: Sequence[Insn], start: int, end: int, target: Target, cases: Iterable[int]
) -> set[int]:
    leaders = {insns[0].va, *cases}
    for insn, after in zip(insns, insns[1:], strict=False):
        if insn.is_jump or insn.is_terminal:
            leaders.add(after.va)
    for insn in insns:
        dest = target(insn) if insn.is_jump else None
        if _inside(dest, start, end):
            leaders.add(dest)
    return leaders


def _blocks(
    insns: Sequence[Insn], start: int, end: int, target: Target, cases: Iterable[int] = ()
) -> list[_Block]:
    """The basic blocks of `insns` (trailing filler dropped), each of filler alone left out."""
    code = _code(insns)
    if not code:
        return []
    leaders = _leaders(code, start, end, target, cases)
    runs: list[list[Insn]] = []
    for insn in code:
        if insn.va in leaders or not runs:
            runs.append([])
        runs[-1].append(insn)
    return [_Block(tuple(run)) for run in runs if not all(map(is_alignment_filler, run))]


def _branch_count(blocks: Sequence[_Block]) -> int:
    return sum(1 for block in blocks for insn in block.insns if insn.is_jump)


def shape(code: bytes, va: int, sites: Container[int]) -> Shape:
    """The counts of `code` loaded at `va` with its relocated fields `sites`. A jump whose rel32
    field is relocated has no destination in the row: its raw value says nothing."""
    insns = instructions(code, va, sites)

    def target(insn: Insn) -> int | None:
        return None if insn.rel32_field in sites else insn.branch_target

    blocks = _blocks(insns, va, va + len(code), target)
    length = blocks[-1].end - va if blocks else 0
    return Shape(length, len(blocks), _branch_count(blocks))


# ---- the outline ----


def _count(n: int, word: str, plural: str | None = None) -> str:
    return f"{n} {word if n == 1 else plural or word + 's'}"


class _Names:
    """Block numbers by start address."""

    def __init__(self, blocks: Sequence[_Block]) -> None:
        self.by_start = {block.start: n for n, block in enumerate(blocks)}

    def of(self, va: int | None) -> str:
        n = self.by_start.get(va) if va is not None else None
        return "out" if n is None else f"B{n}"


def _exit(block: _Block, following: _Block | None, names: _Names, target: Target,
          cases: Mapping[int, Sequence[int]]) -> str:  # fmt: skip
    """What ends `block`: its last instruction's flow, in words."""
    last = block.last
    falls = names.of(following.start) if following is not None else None
    if last.va in cases:
        found = cases[last.va]
        return f"switch, {_count(len(found), 'case')} -> {' '.join(map(names.of, found))}"
    if last.is_jump:
        dest = target(last)
        if dest is None:
            return f"{last.mnemonic} (indirect)"
        where = names.of(dest)
        if not last.is_conditional:
            return f"jmp -> {where}" if where != "out" else "jmp out of the row (a tail call)"
        return f"{last.mnemonic} -> {where} else {falls or 'the row end'}"
    if last.is_terminal:
        return last.mnemonic
    return f"falls into {falls}" if falls else "falls off the row end"


def _block_line(n: int, block: _Block, text: str) -> str:
    calls = sum(1 for insn in block.insns if insn.is_call)
    count = _count(len(block.insns), "insn") + (f", {_count(calls, 'call')}" if calls else "")
    return f"B{n}  0x{block.start:08X}..0x{block.end:08X}  {count}: {text}"


def _back_edges(blocks: Sequence[_Block], names: _Names, target: Target) -> list[str]:
    """`B<tail> -> B<head>` for each jump onto its own block or an earlier one."""
    edges = []
    for n, block in enumerate(blocks):
        last = block.last
        dest = target(last) if last.is_jump else None
        if dest is not None and dest <= last.va and names.of(dest) != "out":
            edges.append(f"B{n} -> {names.of(dest)}")
    return edges


def outline(
    insns: Sequence[Insn],
    start: int,
    end: int,
    *,
    target: Target,
    cases: Mapping[int, Sequence[int]] | None = None,
) -> str:
    """The outline of the row [start, end): a count line, one line per block, then the loops.
    `target` gives a jump's destination; `cases` maps a table jump's address to its case
    targets, in case order."""
    cases = cases or {}
    in_row = [va for found in cases.values() for va in found if _inside(va, start, end)]
    blocks = _blocks(insns, start, end, target, in_row)
    names = _Names(blocks)
    lines = []
    for n, block in enumerate(blocks):
        following = blocks[n + 1] if n + 1 < len(blocks) else None
        lines.append(_block_line(n, block, _exit(block, following, names, target, cases)))
    loops = _back_edges(blocks, names, target)
    head = _head(blocks, start, len(loops), cases)
    return "\n".join([head, *lines, f"loops (back edges): {', '.join(loops) or 'none'}"])


def _head(
    blocks: Sequence[_Block], start: int, loops: int, cases: Mapping[int, Sequence[int]]
) -> str:
    """The outline's count line."""
    insns = [insn for block in blocks for insn in block.insns]
    switches = [cases[insn.va] for insn in insns if insn.va in cases]
    length = blocks[-1].end - start if blocks else 0
    conditional = sum(1 for insn in insns if insn.is_conditional)
    calls = sum(1 for insn in insns if insn.is_call)
    returns = sum(1 for insn in insns if insn.is_terminal and not insn.is_jump)
    tables = f" ({_count(sum(map(len, switches)), 'case')})" if switches else ""
    return (f"{length} bytes: {_count(len(blocks), 'block')}, "
            f"{_count(_branch_count(blocks), 'branch', 'branches')} ({conditional} conditional), "
            f"{_count(loops, 'loop')}, {_count(len(switches), 'switch', 'switches')}{tables}, "
            f"{_count(calls, 'call')}, {_count(returns, 'return')}")  # fmt: skip
