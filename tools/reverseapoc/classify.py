# Derived from NHL95PC tools/match/classify_diff.py (its register pattern), https://github.com/abdulahmad/NHL95PC
# (owner's permission; no licence file)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Failure classes and routes: what differs in a row that is not exact, and which tool takes it.

`classify_pair` compares batch.tokens of our function and the original's under wider and wider
masks, so the widest mask a row needs names it. `route` reads a record and its class. `with_class`
runs at batch time, while the object is on disk, because a class needs both byte strings and a
record holds none.

This is never a match: a class ranks work and decides nothing. A record gains two label strings
and no byte, and `exact` stays the word of `batch.judge`, which is check's own verdict.

`full_diff` (attempt check's class line, attempt diff) aligns our whole function with the
original's and gives each differing run its own class from the same masks (`diff_runs`), beside
the function's class. It holds addresses, mnemonics and operands, never a byte.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import batch
from .check import ExeInputs, compare_bytes
from .relocs import RelocResult
from .x86 import Insn, decode

CLASSES = ("tail", "slot", "size", "register", "branch", "mixed")
ROUTES = ("converter", "search", "agent")
NEAR = 90.0  # the raw score from which a row is a near miss
_REFUSED = "refused: "  # how a refused record's key starts
_FRAME = ("sub esp, ", "add esp, ")
# Every general register but esp, which no allocator picks: a stack operand stays one.
_REGISTER = re.compile(r"\b(?:e?[abcd]x|[abcd][lh]|e?[sd]i|e?bp)\b")
_JUMP = re.compile(r"^j\w+")
_BYTES_PROBLEM = "differing bytes outside the relocated fields"  # relocs.check_function's words
_LENGTH_PROBLEM = "length differs:"


def _texts(code: bytes, va: int, masked: set[int], *, stack: bool = False) -> list[str]:
    return [token for token, _, _ in batch.tokens(code, va, masked, stack=stack)]


def _frames(texts: list[str]) -> list[str]:
    return [text for text in texts if text.startswith(_FRAME)]


def _jump_shape(code: bytes, va: int, masked: set[int]) -> list[int | None]:
    """Each jump's target as an instruction index, so a shifted body still compares equal. A
    relocated jump reads None: its target is the relocation check's, and ours is a placeholder."""
    insns = list(decode(code, va))
    index = {insn.va: n for n, insn in enumerate(insns)}
    jumps = [insn for insn in insns if insn.branch_target is not None and not insn.is_call]
    return [None if masked.intersection(range(jump.va, jump.va + jump.size))
            else index.get(jump.branch_target) for jump in jumps]  # fmt: skip


def _strict_prefix(short: list[str], long: list[str]) -> bool:
    return 0 < len(short) < len(long) and long[: len(short)] == short


def _decodes_whole(code: bytes, va: int) -> bool:
    return sum(insn.size for insn in decode(code, va)) == len(code)


def _widest_mask(ours: list[str], theirs: list[str]) -> str | None:
    """The class of two stack-masked token lists, each mask adding to the last, or None."""
    if ours == theirs:
        return "slot"
    ours = [_REGISTER.sub("R", text) for text in ours]
    theirs = [_REGISTER.sub("R", text) for text in theirs]
    if ours == theirs:
        return "register"
    ours = [_JUMP.sub("jcc", text) for text in ours]
    theirs = [_JUMP.sub("jcc", text) for text in theirs]
    return "branch" if ours == theirs else None


def classify_pair(
    ours: bytes, theirs: bytes, va: int, masked: set[int], exact_trim: bool = False
) -> str:
    """The class of a pair that is not exact. `tail`: exact up to the row's trailing filler, or
    one side's tokens are a strict prefix of the other's. `size`: another frame, which no
    permutation reaches, or another length no mask explains. `slot`, `register`, `branch`: equal
    once stack offsets, then register names, then jump mnemonics are masked; `slot` also needs
    every jump to land on the same instruction, because tokens hide jump targets. `mixed`: none
    of these. Equal tokens mean no mask has anything to explain, as in a relocation-only failure,
    so such a pair is `size` or `mixed` and never `slot`. So is a body that does not decode to its
    end: decode stops there, and what it read says nothing about what it did not."""
    if exact_trim:
        return "tail"
    unmasked = "size" if len(ours) != len(theirs) else "mixed"
    if not (_decodes_whole(ours, va) and _decodes_whole(theirs, va)):
        return unmasked
    a = _texts(ours, va, masked)
    b = _texts(theirs, va, masked)
    if _strict_prefix(a, b) or _strict_prefix(b, a):
        return "tail"
    if _frames(a) != _frames(b):
        return "size"
    klass = None
    if a != b:
        klass = _widest_mask(_texts(ours, va, masked, stack=True),
                             _texts(theirs, va, masked, stack=True))  # fmt: skip
    if klass == "slot" and _jump_shape(ours, va, masked) != _jump_shape(theirs, va, masked):
        klass = None
    return klass or unmasked


def route(record: dict[str, Any], klass: str | None, *, hole: bool = False) -> str:
    """The tool for a record: an agent for a draft holding a hole, which can never be exact and
    is never searched, then exact, class slot, and the near and refused rows."""
    if hole:
        return "agent"
    if record["exact"]:
        return "converter"
    if klass == "slot":
        return "search"
    if record["score"] >= NEAR or record["key"].startswith(_REFUSED):
        return "converter"
    return "agent"


def best_cell(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """The cell a row's route is read from: exact first, then the higher raw score."""
    return max(records, key=lambda record: (record["exact"], record["score"]))


def _may_hide_a_difference(reloc: RelocResult) -> bool:
    """Whether a relocated field may hide what differs. The check fails on any byte outside a
    field, which is what a class explains, so that problem says nothing of the fields. A length
    problem stops it before it reads them, so a row holding any stays unknown."""
    problems = [problem for problem in reloc.problems if _BYTES_PROBLEM not in problem]
    if any(_LENGTH_PROBLEM in problem for problem in problems):
        return bool(reloc.ours or reloc.theirs)
    return bool(problems)


def _without_filler(code: bytes, va: int) -> bytes:
    """`code` without its trailing alignment filler. A body that does not decode to its end stays
    whole: decode stops at what it cannot read, and a cut there would hide those bytes from
    classify_pair's own decode check."""
    if not _decodes_whole(code, va):
        return code
    end = len(code)
    for insn in reversed(list(decode(code, va))):
        if not batch.is_alignment_filler(insn):
            break
        end -= insn.size
    return code[:end]


def _class_of(exe: ExeInputs, start: int, obj: Path, exact_trim: bool) -> str:
    """The class of our object `obj`'s function at `start`, from both byte strings and the
    relocation mask as `judge` reads them. No function in the object leaves nothing to compare,
    and no class fits that. Nor is `slot` a row whose relocated fields may differ: the mask hid
    them, and no search reaches them. Filler explains a length difference, whether or not
    `judge` accepts it, so no class reads it as one. Both sides are cut, because our object
    keeps filler of another register or form, and a pair whose bytes differ by filler alone is
    `tail`."""
    body = batch.function_body(exe, obj, start)
    if isinstance(body, str):
        return "mixed"
    row = batch.row_at(exe, start)
    ((defined, reloc),) = batch.with_relocs(body.module, [body.defined], body.rows, exe)
    theirs = exe.flat[row.start : row.end]
    ours, cut = _without_filler(defined.ours, start), _without_filler(theirs, start)
    if ours == cut and defined.ours != theirs:
        return "tail"
    klass = classify_pair(ours, cut, start, batch._reloc_mask(reloc), exact_trim)
    return "mixed" if klass == "slot" and _may_hide_a_difference(reloc) else klass


def with_class(
    record: dict[str, Any],
    exe: ExeInputs,
    start: int,
    compiled: batch.Compiled | None,
    *,
    hole: bool = False,
) -> dict[str, Any]:
    """`record` plus its `route`, and its `class` when it compiled and is not exact: a refused,
    failed or exact record has nothing to class. A draft holding a `hole` keeps its class, which
    still says what differs. The record itself is not changed."""
    if not record["compiled"] or record["exact"]:
        return {**record, "route": route(record, None, hole=hole)}
    klass = _class_of(exe, start, compiled.job.obj, record["exact_trim"])
    return {**record, "class": klass, "route": route(record, klass, hole=hole)}


# ---- the full aligned diff (attempt check's class line, attempt diff) ----


@dataclass(frozen=True)
class DiffInsn:
    """One instruction of a run: its address, mnemonic and operands, never its bytes, and
    whether one of its bytes is in a relocated field of either side (check's window rule)."""

    va: int
    mnemonic: str
    operands: str
    relocated: bool

    def to_json(self) -> dict[str, Any]:
        return {"va": f"0x{self.va:08X}", "mnemonic": self.mnemonic, "operands": self.operands,
                "relocated": self.relocated}  # fmt: skip


@dataclass(frozen=True)
class DiffRun:
    """One differing run: our instructions beside the original's (either side may be empty)."""

    klass: str
    ours: tuple[DiffInsn, ...]
    original: tuple[DiffInsn, ...]

    def to_json(self) -> dict[str, Any]:
        return {"class": self.klass, "ours": [insn.to_json() for insn in self.ours],
                "original": [insn.to_json() for insn in self.original]}  # fmt: skip


@dataclass(frozen=True)
class FullDiff:
    """The function's class (`_class_of`), every differing run, and check's own byte count and
    first differing address, which tie the diff to the check it explains. `whole`: both sides
    decode to their end, so the runs cover every instruction."""

    klass: str
    runs: tuple[DiffRun, ...]
    differing: int
    first_va: int | None
    whole: bool

    def to_json(self) -> dict[str, Any]:
        first = None if self.first_va is None else f"0x{self.first_va:08X}"
        return {"class": self.klass, "differing": self.differing, "first_va": first,
                "whole": self.whole, "runs": [run.to_json() for run in self.runs]}  # fmt: skip


Span = tuple[int, int, int, int]  # ours [i1, i2) beside the original's [j1, j2)
Opcode = tuple[str, int, int, int, int]  # difflib's (tag, i1, i2, j1, j2)


@dataclass(frozen=True)
class _Side:
    """One side's instructions, with each one's alignment key, token and stack-masked token."""

    insns: list[Insn]
    keys: list[tuple[str, bytes | int]]
    tokens: list[str]
    stack: list[str]
    masked: set[int]

    @classmethod
    def of(cls, code: bytes, va: int, masked: set[int]) -> _Side:
        insns = list(decode(code, va))
        tokens = _texts(code, va, masked)
        keys = [(token, _key_bytes(insn, masked))
                for insn, token in zip(insns, tokens, strict=True)]  # fmt: skip
        return cls(insns, keys, tokens, _texts(code, va, masked, stack=True), masked)

    def index(self) -> dict[int, int]:
        """Instruction address -> index; the address past the last instruction is the end."""
        index = {insn.va + insn.size: len(self.insns) for insn in self.insns[-1:]}
        index.update((insn.va, n) for n, insn in enumerate(self.insns))
        return index

    def relocated(self, insn: Insn) -> bool:
        return not self.masked.isdisjoint(range(insn.va, insn.va + insn.size))

    def cells(self, low: int, high: int) -> tuple[DiffInsn, ...]:
        return tuple(DiffInsn(insn.va, insn.mnemonic, insn.op_str, self.relocated(insn))
                     for insn in self.insns[low:high])  # fmt: skip


def _key_bytes(insn: Insn, masked: set[int]) -> bytes | int:
    """What a key adds to the token, which hides relocated operands and jump targets: a jump's
    size (its target is compared after the alignment), else its bytes with every relocated byte
    zeroed, so another encoding of the same text is still a run."""
    if insn.branch_target is not None:
        return insn.size
    return bytes(0 if insn.va + i in masked else byte for i, byte in enumerate(insn.raw))


def _run_class(a: _Side, b: _Side, span: Span) -> str:
    """A run's class by classify_pair's masks: `tail` when one side is empty at the end of both,
    `size` when one side is empty elsewhere, `slot`, `register` or `branch` when that mask makes
    the run equal, `size` for another instruction count, else `mixed`. Equal tokens (another
    encoding) leave no mask anything to explain."""
    i1, i2, j1, j2 = span
    if i1 == i2 or j1 == j2:
        return "tail" if (i2, j2) == (len(a.insns), len(b.insns)) else "size"
    klass = None
    if a.tokens[i1:i2] != b.tokens[j1:j2]:
        klass = _widest_mask(a.stack[i1:i2], b.stack[j1:j2])
    return klass or ("size" if i2 - i1 != j2 - j1 else "mixed")


def _widen(aligned: dict[int, tuple[int, int]], i: int, low: int, high: int) -> None:
    old_low, old_high = aligned.get(i, (low, high))
    aligned[i] = (min(old_low, low), max(old_high, high))


def _landings(a: _Side, b: _Side, opcodes: Sequence[Opcode]) -> dict[int, tuple[int, int]]:
    """Our instruction index -> the span of the original's indexes a jump there lands alike on:
    the pair of an equal instruction; inside a run or on its edges, the original's whole run
    (the run already shows that place); the end of both sides."""
    aligned: dict[int, tuple[int, int]] = {}
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            for k in range(i2 - i1):
                _widen(aligned, i1 + k, j1 + k, j1 + k)
            continue
        for i in range(i1, i2 + 1):
            _widen(aligned, i, j1, j2)
    _widen(aligned, len(a.insns), len(b.insns), len(b.insns))
    return aligned


def _equal_pairs(opcodes: Sequence[Opcode]) -> Iterator[tuple[int, int]]:
    for tag, i1, i2, j1, _ in opcodes:
        if tag == "equal":
            yield from ((i1 + k, j1 + k) for k in range(i2 - i1))


def _lands_alike(mine: Insn, other: Insn, indexes: tuple[dict[int, int], dict[int, int]],
                 aligned: dict[int, tuple[int, int]]) -> bool:  # fmt: skip
    """Whether two aligned jumps land alike: on aligned instructions (`indexes` are both sides'
    _Side.index, `aligned` _landings'), or, outside the function, on the same address."""
    ours, theirs = indexes
    target = ours.get(mine.branch_target)
    if target is None:
        return mine.branch_target == other.branch_target
    landed = theirs.get(other.branch_target)
    low, high = aligned[target]
    return landed is not None and low <= landed <= high


def _strayed_jumps(a: _Side, b: _Side, opcodes: Sequence[Opcode]) -> Iterator[Span]:
    """Each aligned jump pair that lands elsewhere, which its tokens hide. A call is not a
    jump, and a relocated jump is the relocation check's."""
    aligned, indexes = _landings(a, b, opcodes), (a.index(), b.index())
    for i, j in _equal_pairs(opcodes):
        mine, other = a.insns[i], b.insns[j]
        if mine.branch_target is None or mine.is_call or a.relocated(mine):
            continue
        if not _lands_alike(mine, other, indexes, aligned):
            yield i, i + 1, j, j + 1


def diff_runs(ours: bytes, theirs: bytes, va: int, masked: set[int]) -> tuple[DiffRun, ...]:
    """Every differing run of our function against the original's, in our order: difflib's
    alignment of batch.tokens (plus each instruction's unrelocated bytes), then each aligned
    jump that lands elsewhere as a run of its own, class `branch`. It decides nothing."""
    a, b = _Side.of(ours, va, masked), _Side.of(theirs, va, masked)
    opcodes = difflib.SequenceMatcher(a=a.keys, b=b.keys, autojunk=False).get_opcodes()
    spans = [((i1, i2, j1, j2), _run_class(a, b, (i1, i2, j1, j2)))
             for tag, i1, i2, j1, j2 in opcodes if tag != "equal"]  # fmt: skip
    spans += [(span, "branch") for span in _strayed_jumps(a, b, opcodes)]
    return tuple(DiffRun(klass, a.cells(i1, i2), b.cells(j1, j2))
                 for (i1, i2, j1, j2), klass in sorted(spans))  # fmt: skip


def full_diff(exe: ExeInputs, obj: Path, start: int) -> FullDiff | str:
    """The full diff of our object `obj`'s function at `start` against the original row, or
    judge's failure key when the object holds no such function. The original's trailing filler
    that check keeps as ours (07-48) is left out, as check's byte compare leaves it out."""
    body = batch.function_body(exe, obj, start)
    if isinstance(body, str):
        return body
    row = batch.row_at(exe, start)
    ((defined, reloc),) = batch.with_relocs(body.module, [body.defined], body.rows, exe)
    same = compare_bytes(defined.ours, row, exe.flat, reloc)
    theirs = exe.flat[row.start : row.end - reloc.filler]
    klass = _class_of(exe, start, obj, batch.judge(exe, obj, start).exact_trim)
    runs = diff_runs(defined.ours, theirs, start, batch._reloc_mask(reloc))
    whole = _decodes_whole(defined.ours, start) and _decodes_whole(theirs, start)
    return FullDiff(klass, runs, same.differing, same.first_va, whole)
