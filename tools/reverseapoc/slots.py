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
M2 or M4 in a frame of one size: three or more multi-element arrays unless they are declared
first and a plain local follows them in one block (line C of quick 261112-fdx; alone they leave,
pr_arr_char4_x3, as after an int, pr_arr_int_three), an array of 2 bytes beside plain locals
unless it is the only one and declared first (line A; pr_arr_two_one_small, pr_arr_one_two_small
leave), and two arrays beside a later block unless they are declared first and a plain local
follows them in the top block (line B; pr_arr_two_block, pr_arr_int_two_block leave). No
standard sort reproduces these orders and a table by count would not hold either, so the model
refuses them, and some frames it refuses hold.
07.2-14 measured past the 07.1 sweep and moved nothing: a `char[4]` beside a `short[2]` keeps M2
(pr_arr_c4_s2), two `char[4]` beside a `short[2]` leave it (pr_arr_c4x2_s2), a `char[4]` and an
`int` beside a `char[2]` hold (pr_arr_c4_c2_int, refused then, on line D since its refit), and
three `int[1]` keep M2
(pr_arr_int1_x3), which is why the lifter declares a 4-byte address-taken slot that way. Quick
261112-fdx measured the pr_line_ frames past the sweep against four lines fixed beforehand, and
drew A, B and C above. Line D, a 4-byte array and an int beside one 2-byte local, broke on
pr_line_d_c4_i_c2 and pr_line_d_i_c4_h, which leave. The pr_line_k_ frames, called known, sit as
modelled. The refit of 2026-11-13 drew a narrower line D from new pr_line_d_ frames, one change
apart: in a frame of two sizes, 4-byte locals keep M2 beside one local of 1 or 2 bytes, all in
the function's own block, with at most two arrays, unless the small local is declared last and
it, or any local after the first, is an array (_one_small_local). Every other frame of two
sizes stays refused, and some of those hold.

This is never a match: nothing here lands, writes status.csv or edits config/cflags.txt. A match
is still claimed only by `reverseapoc check` / `gate` (D-16).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

SLOT_ALIGN = 4  # M3: a `char` and a `short` each took a 4-byte slot
_ORDERED_SIZES = frozenset((1, 2, 4))  # the only sizes a tie follows M2 at, alone in the frame
_MEASURED_ARRAYS = 2  # the most multi-element arrays the model calls known at one size
_BLOCK_ORDERED_SIZE = 4  # M4: chars and shorts do not follow their blocks
_LEADING_SMALL_ARRAYS = 1  # line A: the arrays under 4 bytes keep M2 beside plain locals, if first
_SMALL_SIZES = frozenset((1, 2))  # line D: the size of the one local beside the 4-byte tie
_LINE_D_ARRAYS = 2  # line D: the most arrays beside that local, itself counted
_TOP_SCOPE = 0  # the function's own block, as search.memory_locals numbers it


@dataclass(frozen=True)
class Local:
    """One local held in memory. A sequence of them is in declaration order."""

    name: str
    size: int
    scope: int = 0  # orders blocks as the source does: a later block has a greater one
    array: bool = False  # it holds more than one element: `char v[1]` does not count


def order_is_known(locals_: Sequence[Local]) -> bool:
    """M2 and M4 decide this frame: no two sizes tie, or of two sizes the frame is one that
    _one_small_local admits (line D), or every local has one size, 1, 2 or 4,
    and no more than _MEASURED_ARRAYS of them are arrays, or more that _arrays_then_ints admits
    at size 4 (line C). Only size 4 keeps its order across
    blocks: with at most one array, or with two that _two_arrays_then_ints admits (line B).
    Under size 4 the locals sit in one block and are all arrays or none, or one array is declared
    first (line A: pr_line_a_c2_h to pr_line_a_c2_h11 and pr_arr_one_three_small, from 1 to 11
    shorts after it; measured as `char[2]` and, in pr_line_a_uc2_h3, `unsigned char[2]`, beside
    `short`, `unsigned short` and `short[1]`). Measured in both cells: two arrays of 4 bytes of
    any element type hold (pr_arr_char4_x2, pr_arr_short2_x2, pr_arr_c4_s2), three do not
    (pr_arr_char4_x3, pr_arr_c4x2_s2), and `int[1]` is no array (pr_arr_int1_x3)."""
    sizes = {local.size for local in locals_}
    if len(sizes) == len(locals_):
        return True
    if len(sizes) == 2:
        return _one_small_local(locals_, sizes)
    if len(sizes) != 1 or not sizes <= _ORDERED_SIZES:
        return False
    arrays = sum(local.array for local in locals_)
    one_block = len({local.scope for local in locals_}) == 1
    if arrays > _MEASURED_ARRAYS:
        return sizes == {_BLOCK_ORDERED_SIZE} and one_block and _arrays_then_ints(locals_, arrays)
    if sizes == {_BLOCK_ORDERED_SIZE}:
        return one_block or arrays < 2 or _two_arrays_then_ints(locals_)
    leading = arrays == _LEADING_SMALL_ARRAYS and locals_[0].array
    return one_block and (arrays in (0, len(locals_)) or leading)


def _two_arrays_then_ints(locals_: Sequence[Local]) -> bool:
    """Line B, for a frame of 4-byte locals with at most _MEASURED_ARRAYS arrays: the first two
    declared are arrays in the function's own block, and a plain local follows them there. Every
    local after them is plain. Measured in both cells as two `char[4]` (pr_line_b_c4x2_i_blk,
    _i3_blk, _i_blk5, _i_blk_blk and _i_blk_late, and the 07.1 sweep's c4 c4 i | i to
    c4 c4 i i | i i i), two `short[2]` (the sweep's s2 twins of those only) and one of each
    (pr_line_b_c4_s2_i_blk alone), beside `int`: 1 to 3 ints in the top block, 1 to 5 in a later
    one, and up to two later blocks. Without the int in the top block it leaves (pr_arr_two_block),
    and so does an int before the arrays (pr_arr_int_two_block)."""
    first, second, *rest = locals_
    in_top = [local for local in rest if local.scope == _TOP_SCOPE]
    arrays_lead = first.array and second.array and first.scope == second.scope == _TOP_SCOPE
    return arrays_lead and bool(in_top) and not any(local.array for local in rest)


def _arrays_then_ints(locals_: Sequence[Local], arrays: int) -> bool:
    """Line C, for a frame of 4-byte locals in one block with more than _MEASURED_ARRAYS arrays:
    the arrays are the first declared, and a plain local follows them. Measured in both cells as
    `char[4]` (pr_arr_three_int, pr_line_c_c4x3_i2, _c4x4_i and _c4x3_i_late) and two `char[4]`
    then a `short[2]` (pr_line_c_c4x2_s2_i), beside `int`: 3 or 4 arrays, then 1 or 2 ints.
    Arrays alone leave (pr_arr_char4_x3), and so does an int before them (pr_arr_int_three)."""
    return arrays < len(locals_) and all(local.array for local in locals_[:arrays])


def _one_small_local(locals_: Sequence[Local], sizes: set[int]) -> bool:
    """Line D, for a frame of the two `sizes`: 4-byte locals beside one local of 1 or 2 bytes, all
    in the function's own block, with at most _LINE_D_ARRAYS arrays, the small local counted. It
    holds when the small local is not declared last, and when it is last, plain, and no local
    after the first is an array. Measured in both cells, from the pr_line_d_ frames and
    pr_arr_c4_c2_int and its twin, as `char[4]` or `short[2]` beside `int`, `short` or `char` and
    a `char[2]`: 2 to 9 locals of 4 bytes, the small one in every place. Last, it leaves after an
    array in second place or later (pr_line_d_i_c4_h, _c4x2_h, _c4x2_i2_h, though _c4x2_i_h
    holds) and as an array (pr_line_d_c4_i_c2, _i2_c2); three arrays leave (pr_line_d_c4x2_c2_i,
    _c4_h_c4x2), and so do two small locals (pr_line_d_c4_h_i_h, pr_tie_sizes). A later block
    is not on the line (only `c4 h | i` was measured, and it held), nor is a nested block alone."""
    if _BLOCK_ORDERED_SIZE not in sizes or not sizes - {_BLOCK_ORDERED_SIZE} <= _SMALL_SIZES:
        return False
    small = [n for n, local in enumerate(locals_) if local.size != _BLOCK_ORDERED_SIZE]
    if len(small) != 1:
        return False
    (place,) = small
    top_block = all(local.scope == _TOP_SCOPE for local in locals_)
    if not top_block or sum(local.array for local in locals_) > _LINE_D_ARRAYS:
        return False
    if place < len(locals_) - 1:
        return True
    return not any(local.array for local in locals_[1:])  # the small local among them


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
    must have a known order. ValueError when the one order M2 would need is past order_is_known:
    lines A to D turn on where a local is declared, so a known frame can need a refused order
    (pr_line_d_c4_i_h's tie swapped is pr_line_d_i_c4_h), and the model cannot say whether it
    reaches `target`."""
    ties: dict[tuple[int, int], list[Local]] = {}
    for local in locals_:
        ties.setdefault((local.size, local.scope), []).append(local)
    for tie in ties.values():
        tie.sort(key=lambda local: -target[local.name])  # M2: the first declared is highest
    order = [ties[local.size, local.scope].pop(0) for local in locals_]
    if not order_is_known(order):
        raise ValueError(f"the order {[local.name for local in order]} has no known layout")
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
