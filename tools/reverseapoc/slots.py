# SPDX-License-Identifier: GPL-3.0-or-later
"""The model of wcc386 10.6's frame slots, calibrated only on our clean-room probe/cg_slots.c
under `-4r -s -fpi` and `-4r -oneatx -s -fpi` (D-02); `-fpi` matches the real rules, and
docs/matching.md measured `-fpi` and `-fpi87` identical. No matched row is an input to it.

Offsets count from esp after the prologue. Locals sort by size, the largest at the lowest offset
(M1), the first declared of equal sizes highest (M2), and each takes its size padded to 4 (M3).

This is never a match: nothing here lands, writes status.csv or edits config/cflags.txt. A match
is still claimed only by `reverseapoc check` / `gate` (D-16).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

SLOT_ALIGN = 4  # M3: a `char` and a `short` each took a 4-byte slot


@dataclass(frozen=True)
class Local:
    """One local held in memory. A sequence of them is in declaration order."""

    name: str
    size: int
    scope: int = 0


def _padded(size: int) -> int:
    return -(-size // SLOT_ALIGN) * SLOT_ALIGN


def frame_layout(locals_: Sequence[Local]) -> dict[str, int]:
    """Each local's offset from esp after the prologue: pr_slot_same_size and pr_slot_mixed."""
    ascending = sorted(enumerate(locals_), key=lambda pair: (-pair[1].size, -pair[0]))
    layout = {}
    offset = 0
    for _, local in ascending:
        layout[local.name] = offset
        offset += _padded(local.size)
    return layout
