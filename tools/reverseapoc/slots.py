# SPDX-License-Identifier: GPL-3.0-or-later
"""The model of wcc386 10.6's frame slots, calibrated only on our clean-room probe/cg_slots.c
under `-4r -s -fpi` and `-4r -oneatx -s -fpi` (D-02); `-fpi` matches the real rules, and
docs/matching.md measured `-fpi` and `-fpi87` identical. No matched row is an input to it.

Offsets count from esp after the prologue. What the probe measured, the same in both cells:

- M1: memory locals sort by size, the largest at the lowest offset.
- M2: among equal sizes the first declared takes the highest offset.
- M3: each takes its size padded to 4, and nothing aligns past that (a double sits at 0xC).
- M4: an earlier block sits lower, by its place in the source and not by its depth, and blocks
  share no slot, siblings included.
- M5: a register candidate ignores declaration and scope. It is not modelled: assignment order,
  use order, type and loop weight move it, which is the register allocator. What can be said is
  where it lands: a spill sorts by size with the memory locals, above an int and below a short.
  One exception: shorts spilled beside a short in memory do move with their declarations
  (pr_spill_short), so a caller must not read M5 as covering locals under 4 bytes. M5 covers
  integers and pointers. A volatile sits in the frame like a memory local (pr_slot_volatile).
  So does a float or a double live across a call, sorted by size, but with no address taken a
  float in a tie leaves M2 (pr_float_tie), and a double moves the ints beside it by its use alone
  (pr_double_called): a caller must keep a float in a tie away from order_is_known.

M1 and M3 always held. M2 and M4 hold only where order_is_known says so: past that a tie leaves
declaration order, and locals outside the tie change how. pr_tie_three_int only adds an int to
pr_tie_three, and its three arrays take other offsets. Local.array carries the shapes that leave
M2 or M4 in a frame of one size: three or more multi-element arrays alone (pr_arr_char4_x3), an
array of 2 bytes beside plain locals (pr_arr_two_one_small, pr_arr_one_two_small), and two arrays
beside a later block (pr_arr_two_block). No standard sort reproduces these orders and a table by
count would not hold either, so the model refuses them, and some frames it refuses hold.

This is never a match: nothing here lands, writes status.csv or edits config/cflags.txt. A match
is still claimed only by `reverseapoc check` / `gate` (D-16).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

SLOT_ALIGN = 4  # M3: a `char` and a `short` each took a 4-byte slot
_ORDERED_SIZES = frozenset((1, 2, 4))  # the only sizes a tie follows M2 at, alone in the frame
_MEASURED_ARRAYS = 2  # the most multi-element arrays one frame of one size kept M2 with
_BLOCK_ORDERED_SIZE = 4  # M4: chars and shorts do not follow their blocks


@dataclass(frozen=True)
class Local:
    """One local held in memory. A sequence of them is in declaration order."""

    name: str
    size: int
    scope: int = 0  # orders blocks as the source does: a later block has a greater one
    array: bool = False  # it holds more than one element: `char v[1]` does not count


def order_is_known(locals_: Sequence[Local]) -> bool:
    """M2 and M4 decide this frame: no two sizes tie, or every local has one size, 1, 2 or 4,
    and no more than _MEASURED_ARRAYS of them are arrays. Only size 4 keeps its order across
    blocks, with at most one array, and under size 4 the locals are all arrays or none."""
    sizes = {local.size for local in locals_}
    if len(sizes) == len(locals_):
        return True
    if len(sizes) != 1 or not sizes <= _ORDERED_SIZES:
        return False
    arrays = sum(local.array for local in locals_)
    one_block = len({local.scope for local in locals_}) == 1
    if arrays > _MEASURED_ARRAYS:
        return False
    if sizes == {_BLOCK_ORDERED_SIZE}:
        return one_block or arrays < 2
    return one_block and arrays in (0, len(locals_))


def _padded(size: int) -> int:
    return -(-size // SLOT_ALIGN) * SLOT_ALIGN


def frame_size(locals_: Iterable[Local]) -> int:
    """What the memory locals take: M1 and M3 alone, so it holds with no known order too."""
    return sum(_padded(local.size) for local in locals_)


def frame_layout(locals_: Sequence[Local]) -> dict[str, int]:
    """Each local's offset from esp after the prologue, with no spill in the frame. ValueError
    past order_is_known: an offset the probe proves wrong is worse than none."""
    if not order_is_known(locals_):
        sizes = sorted(local.size for local in locals_)
        raise ValueError(f"no known order for a tie among the sizes {sizes}")
    ascending = sorted(enumerate(locals_),
                       key=lambda pair: (-pair[1].size, pair[1].scope, -pair[0]))  # fmt: skip
    layout = {}
    offset = 0
    for _, local in ascending:
        layout[local.name] = offset
        offset += _padded(local.size)
    return layout


def declaration_order(
    locals_: Sequence[Local], target: Mapping[str, int]
) -> tuple[str, ...] | None:
    """The names of `locals_` in the order whose frame_layout equals `target`, or None when no
    order can reach it. Only a tie has anything to move, and no local leaves its block. `locals_`
    must have a known order."""
    ties: dict[tuple[int, int], list[Local]] = {}
    for local in locals_:
        ties.setdefault((local.size, local.scope), []).append(local)
    for tie in ties.values():
        tie.sort(key=lambda local: -target[local.name])  # M2: the first declared is highest
    order = [ties[local.size, local.scope].pop(0) for local in locals_]
    return tuple(local.name for local in order) if frame_layout(order) == target else None


def scalar_slots(
    locals_: Sequence[Local], mismatched: Iterable[int], frame: int
) -> tuple[int, ...]:
    """The offsets of `mismatched` no memory local explains, in order and each once. These hold
    scalars, and declaration moves cannot reach them. Spills sort by size with the locals, so they
    lie between the locals of 4 bytes or more and the smaller ones at the top of a `frame` this
    size (pr_spill_memory, pr_spill_small). What falls outside it is slot_map's shifted reading."""
    bottom = frame_size(local for local in locals_ if local.size >= SLOT_ALIGN)
    top = frame - frame_size(local for local in locals_ if local.size < SLOT_ALIGN)
    return tuple(sorted({offset for offset in mismatched if bottom <= offset < top}))
