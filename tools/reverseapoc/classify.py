# SPDX-License-Identifier: GPL-3.0-or-later
"""Failure classes and routes: what differs in a row that is not exact, and which tool takes it.

`classify_pair` compares batch.tokens of our function and the original's. `route` reads a record
and its class. `with_class` runs at batch time, while the object is on disk, because a class needs
both byte strings and a record holds none.

This is never a match: a class ranks work and decides nothing. A record gains two label strings
and no byte, and `exact` stays the word of `batch.judge`, which is check's own verdict.
"""

from __future__ import annotations

from typing import Any

from . import batch
from .check import ExeInputs

CLASSES = ("tail", "slot", "size", "register", "branch", "mixed")
ROUTES = ("converter", "search", "agent")
NEAR = 90.0  # the raw score from which a row is a near miss
_REFUSED = "refused: "  # how a refused record's key starts
_FRAME = "sub esp, "


def _texts(code: bytes, va: int, masked: set[int], *, stack: bool = False) -> list[str]:
    return [token for token, _, _ in batch.tokens(code, va, masked, stack=stack)]


def _frames(texts: list[str]) -> list[str]:
    return [text for text in texts if text.startswith(_FRAME)]


def classify_pair(
    ours: bytes, theirs: bytes, va: int, masked: set[int], exact_trim: bool = False
) -> str:
    """The class of a pair that is not exact."""
    same_frame = _frames(_texts(ours, va, masked)) == _frames(_texts(theirs, va, masked))
    if same_frame and _texts(ours, va, masked, stack=True) == _texts(
        theirs, va, masked, stack=True
    ):
        return "slot"
    return "mixed"


def route(record: dict[str, Any], klass: str | None) -> str:
    """The tool for a record: exact first, then class slot, then the near and refused rows."""
    if record["exact"]:
        return "converter"
    if klass == "slot":
        return "search"
    if record["score"] >= NEAR or record["key"].startswith(_REFUSED):
        return "converter"
    return "agent"


def _class_of(exe: ExeInputs, start: int, compiled: batch.Compiled, exact_trim: bool) -> str:
    """The class of a compiled cell, from both byte strings and the relocation mask as `judge`
    reads them. No function in the object leaves nothing to compare, and no class fits that."""
    body = batch.function_body(exe, compiled.job.obj, start)
    if isinstance(body, str):
        return "mixed"
    row = batch.row_at(exe, start)
    ((defined, reloc),) = batch.with_relocs(body.module, [body.defined], body.rows, exe)
    theirs = exe.flat[row.start : row.end]
    return classify_pair(defined.ours, theirs, start, batch._reloc_mask(reloc), exact_trim)


def with_class(
    record: dict[str, Any], exe: ExeInputs, start: int, compiled: batch.Compiled | None
) -> dict[str, Any]:
    """`record` plus its `route`, and its `class` when it compiled and is not exact: a refused,
    failed or exact record has nothing to class. The record itself is not changed."""
    if not record["compiled"] or record["exact"]:
        return {**record, "route": route(record, None)}
    klass = _class_of(exe, start, compiled, record["exact_trim"])
    return {**record, "class": klass, "route": route(record, klass)}
