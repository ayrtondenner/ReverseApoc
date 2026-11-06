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
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from . import batch
from .check import ExeInputs
from .relocs import RelocResult
from .x86 import decode

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


def _class_of(exe: ExeInputs, start: int, compiled: batch.Compiled, exact_trim: bool) -> str:
    """The class of a compiled cell, from both byte strings and the relocation mask as `judge`
    reads them. No function in the object leaves nothing to compare, and no class fits that. Nor
    is `slot` a row whose relocated fields may differ: the mask hid them, and no search reaches
    them. `judge` takes the row's filler as no difference, so no class may read it as one: only
    `tail` needs the whole row, where a pair that differs by filler alone is a strict prefix."""
    body = batch.function_body(exe, compiled.job.obj, start)
    if isinstance(body, str):
        return "mixed"
    row = batch.row_at(exe, start)
    ((defined, reloc),) = batch.with_relocs(body.module, [body.defined], body.rows, exe)
    theirs = exe.flat[row.start : row.end]
    masked = batch._reloc_mask(reloc)
    klass = classify_pair(defined.ours, theirs, start, masked, exact_trim)
    if klass != "tail":
        klass = classify_pair(defined.ours, _without_filler(theirs, start), start, masked)
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
    klass = _class_of(exe, start, compiled, record["exact_trim"])
    return {**record, "class": klass, "route": route(record, klass, hole=hole)}
