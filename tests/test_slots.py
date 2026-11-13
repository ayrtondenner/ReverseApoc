"""The slot model as pure functions: no compiler runs here. The rules were measured on
probe/cg_slots.c; tests/test_slots_real.py holds them against the real wcc386 10.6.
"""

from __future__ import annotations

import pytest

from reverseapoc import slots


def _locals(*sizes: tuple[str, int]) -> tuple:
    return tuple(slots.Local(name, size) for name, size in sizes)


def test_equal_sizes_take_offsets_by_declaration():
    layout = slots.frame_layout(_locals(("a", 4), ("b", 4), ("c", 4), ("d", 4)))
    assert layout == {"a": 0xC, "b": 8, "c": 4, "d": 0}


@pytest.mark.parametrize("reverse", [False, True])
def test_larger_locals_sit_lower(reverse):
    declared = [("c", 1), ("i", 4), ("s", 2), ("f", 8)]
    layout = slots.frame_layout(_locals(*(declared[::-1] if reverse else declared)))
    assert layout == {"f": 0, "i": 8, "s": 0xC, "c": 0x10}


def test_sizes_pad_to_four():
    assert slots.frame_layout(_locals(("s", 2), ("c", 1))) == {"s": 0, "c": 4}


def test_scope_changes_the_order():
    """pr_slot_flat against pr_slot_scope: an earlier block sits lower, and no slot is shared."""
    flat = _locals(("a", 4), ("b", 4), ("c", 4))
    nested = (slots.Local("a", 4), slots.Local("b", 4, 1), slots.Local("c", 4, 2))
    assert slots.frame_layout(flat) == {"a": 8, "b": 4, "c": 0}
    assert slots.frame_layout(nested) == {"a": 0, "b": 4, "c": 8}
    assert slots.frame_size(flat) == slots.frame_size(nested) == 0xC


def test_inside_a_block_the_first_declared_is_highest():
    declared = (slots.Local("a", 4), slots.Local("b", 4),
                slots.Local("c", 4, 1), slots.Local("d", 4, 1))  # fmt: skip
    assert slots.frame_layout(declared) == {"b": 0, "a": 4, "d": 8, "c": 0xC}


def test_size_comes_before_scope():
    declared = (slots.Local("a", 2), slots.Local("b", 4, 1))
    assert slots.frame_layout(declared) == {"b": 0, "a": 4}


def test_arrays_sort_by_total_size():
    declared = _locals(("c", 6), ("b", 8), ("a", 12))
    assert slots.frame_layout(declared) == {"a": 0, "b": 0xC, "c": 0x14}
    assert slots.frame_size(declared) == 0x1C


def test_nothing_aligns_past_four():
    """pr_slot_unaligned: the double sits at 0xC."""
    assert slots.frame_layout(_locals(("a", 12), ("d", 8), ("b", 4)))["d"] == 0xC


@pytest.mark.parametrize("sizes", [(1, 1, 1), (2, 2), (4, 4, 4), (1, 2, 4), (3, 5, 7, 4), (12, 8)])
def test_order_is_known_with_one_small_size_or_no_tie(sizes):
    declared = _locals(*((f"v{n}", size) for n, size in enumerate(sizes)))
    assert slots.order_is_known(declared) is True


@pytest.mark.parametrize(
    "sizes",
    [(8, 8), (8, 8, 4), (4, 4, 8), (3, 3), (6, 6, 6), (8, 8, 2, 2), (4, 4, 2, 2), (2, 2, 1),
     (1, 1, 2, 2, 4, 4)],
)  # fmt: skip
def test_order_is_not_known_for_a_tie_the_probe_could_not_order(sizes):
    declared = _locals(*((f"v{n}", size) for n, size in enumerate(sizes)))
    assert slots.order_is_known(declared) is False


@pytest.mark.parametrize(("size", "known"), [(4, True), (2, False), (1, False)])
def test_only_a_tie_of_ints_keeps_its_order_across_blocks(size, known):
    declared = (slots.Local("a", size), slots.Local("b", size, 1))
    assert slots.order_is_known(declared) is known


def test_no_tie_needs_no_block_rule():
    assert slots.order_is_known((slots.Local("a", 2), slots.Local("b", 1, 1))) is True


def test_frame_layout_refuses_an_order_nothing_measured():
    with pytest.raises(ValueError, match="no known order"):
        slots.frame_layout(_locals(("a", 8), ("b", 8)))


@pytest.mark.parametrize(("size", "count"), [(4, 3), (4, 4), (2, 3), (4, 14)])
def test_three_or_more_arrays_in_one_size_have_no_known_order(size, count):
    declared = tuple(slots.Local(f"v{n}", size, array=True) for n in range(count))
    assert slots.order_is_known(declared) is False


def test_frame_layout_refuses_three_arrays_of_one_size():
    declared = tuple(slots.Local(name, 4, array=True) for name in "abc")
    with pytest.raises(ValueError, match="no known order"):
        slots.frame_layout(declared)


def test_three_arrays_beside_a_scalar_have_no_known_order():
    declared = (slots.Local("a", 4), *(slots.Local(name, 4, array=True) for name in "bcd"))
    assert slots.order_is_known(declared) is False


@pytest.mark.parametrize(("arrays", "plain"), [(1, 1), (1, 2), (2, 1), (2, 2), (1, 7)])
def test_an_array_beside_plain_locals_of_two_bytes_has_no_known_order(arrays, plain):
    declared = (*(slots.Local(f"p{n}", 2) for n in range(plain)),
                *(slots.Local(f"v{n}", 2, array=True) for n in range(arrays)))  # fmt: skip
    assert slots.order_is_known(declared) is False


def test_two_arrays_across_blocks_have_no_known_order():
    declared = (slots.Local("a", 4, array=True), slots.Local("b", 4, array=True),
                slots.Local("c", 4, 1))  # fmt: skip
    assert slots.order_is_known(declared) is False


def test_one_array_across_blocks_keeps_the_rule():
    declared = (slots.Local("a", 4, array=True), slots.Local("b", 4, 1))
    assert slots.order_is_known(declared) is True
    assert slots.frame_layout(declared) == {"a": 0, "b": 4}


@pytest.mark.parametrize(
    ("size", "arrays", "plain"), [(4, 2, 0), (2, 2, 0), (4, 2, 1), (4, 1, 2)]
)
def test_two_arrays_in_one_size_keep_the_rule(size, arrays, plain):
    declared = (*(slots.Local(f"v{n}", size, array=True) for n in range(arrays)),
                *(slots.Local(f"p{n}", size) for n in range(plain)))  # fmt: skip
    assert slots.order_is_known(declared) is True
    layout = slots.frame_layout(declared)
    assert max(layout, key=layout.__getitem__) == declared[0].name


def test_arrays_of_distinct_sizes_stay_known():
    """pr_slot_array holds three arrays and no tie, so M1 places them."""
    declared = (slots.Local("a", 12, array=True), slots.Local("b", 8, array=True),
                slots.Local("c", 6, array=True))  # fmt: skip
    assert slots.order_is_known(declared) is True
    assert slots.frame_layout(declared) == {"a": 0, "b": 0xC, "c": 0x14}


def test_frame_size_needs_no_order():
    assert slots.frame_size(_locals(("a", 8), ("b", 8), ("c", 3))) == 0x14


@pytest.mark.parametrize(
    ("target", "order"),
    [
        ({"a": 8, "b": 4, "c": 0}, ("a", "b", "c")),
        ({"a": 0, "b": 4, "c": 8}, ("c", "b", "a")),
        ({"a": 4, "b": 0, "c": 8}, ("c", "a", "b")),
    ],
)
def test_declaration_order_round_trips(target, order):
    declared = _locals(("a", 4), ("b", 4), ("c", 4))
    found = slots.declaration_order(declared, target)
    assert found == order
    by_name = {local.name: local for local in declared}
    assert slots.frame_layout([by_name[name] for name in found]) == target


def test_declaration_order_of_distinct_sizes_moves_nothing():
    declared = _locals(("a", 1), ("b", 4), ("c", 2))
    assert slots.declaration_order(declared, slots.frame_layout(declared)) == ("a", "b", "c")


def test_declaration_order_keeps_each_local_in_its_block():
    declared = (slots.Local("a", 4), slots.Local("b", 4), slots.Local("c", 4, 1))
    assert slots.declaration_order(declared, {"a": 0, "b": 4, "c": 8}) == ("b", "a", "c")
    assert slots.declaration_order(declared, {"a": 8, "b": 4, "c": 0}) is None


def test_declaration_order_refuses_a_layout_size_cannot_give():
    """No order puts the smaller local below the larger one."""
    declared = _locals(("big", 4), ("small", 2))
    assert slots.declaration_order(declared, {"small": 0, "big": 4}) is None


def test_scalar_slots_are_the_ones_no_memory_local_explains():
    """0 and 8 lie inside the array and 0xC is the int; from 0x10 up lie spills."""
    declared = _locals(("array", 12), ("one", 4))
    assert slots.scalar_slots(declared, (0x14, 0, 8, 0xC, 0x10), 0x18) == (0x10, 0x14)


def test_scalar_slots_leave_a_smaller_local_at_the_top_of_the_frame():
    """pr_spill_small: spills sort by size too, so the short sits above them."""
    declared = _locals(("array", 12), ("short", 2))
    assert slots.scalar_slots(declared, (0, 0xC, 0x10, 0x14), 0x18) == (0xC, 0x10)


def test_with_no_memory_local_every_slot_is_a_scalar():
    assert slots.scalar_slots((), (8, 0), 0x10) == (0, 8)


def test_scalar_slots_name_a_slot_with_two_targets_once():
    """SlotMap.pairs can hold one of our slots twice: the conflict `bijection` reports."""
    assert slots.scalar_slots(_locals(("b", 4)), [8, 8], 0x10) == (8,)


def test_scalar_slots_leave_out_a_slot_outside_the_frame():
    """Negative or past the frame: slot_map's shifted reading, not a place in it."""
    assert slots.scalar_slots((), (-4, 4, 0x10), 0x10) == (4,)


# The frames 07.2-14 measured past the 07.1 sweep (probe/cg_slots.c, both cells).


def test_a_char4_beside_a_short2_keeps_the_rule():
    """pr_arr_c4_s2 and its twin: two arrays of 4 bytes, the first declared highest."""
    declared = (slots.Local("a", 4, array=True), slots.Local("b", 4, array=True))
    assert slots.order_is_known(declared) is True
    assert slots.frame_layout(declared) == {"a": 4, "b": 0}
    assert slots.frame_layout(declared[::-1]) == {"b": 4, "a": 0}


def test_three_int1_keep_the_rule():
    """pr_arr_int1_x3: one element is no array, so three of them follow M2."""
    declared = _locals(("a", 4), ("b", 4), ("c", 4))
    assert slots.order_is_known(declared) is True
    assert slots.frame_layout(declared) == {"a": 8, "b": 4, "c": 0}


def test_two_char4_beside_a_short2_have_no_known_order():
    """pr_arr_c4x2_s2 sits at 4, 8, 0, as three char[4] do."""
    declared = tuple(slots.Local(name, 4, array=True) for name in "abc")
    assert slots.order_is_known(declared) is False
    with pytest.raises(ValueError, match="no known order"):
        slots.frame_layout(declared)


def test_a_char4_and_an_int_beside_a_char2_keep_the_rule():
    """pr_arr_c4_c2_int and its twin hold in both cells, on line D: the char[2] is not last."""
    declared = (slots.Local("a", 4, array=True), slots.Local("b", 2, array=True),
                slots.Local("c", 4))  # fmt: skip
    assert slots.order_is_known(declared) is True
    assert slots.frame_layout(declared) == {"a": 4, "c": 0, "b": 8}
    assert slots.frame_layout(declared[::-1]) == {"c": 4, "a": 0, "b": 8}


# The lines quick 261112-fdx drew past the 07.1 sweep, each fixed before its frames were measured
# (probe/cg_slots.c pr_line_*, both cells).


# (size, scope, array) in the probe's notation: | opens a later block, numbered by its scope.
C2, H = (2, 0, True), (2, 0, False)
C4, INT, INT1, INT2, C4_1 = (4, 0, True), (4, 0, False), (4, 1, False), (4, 2, False), (4, 1, True)


def _shape(*specs: tuple[int, int, bool]) -> tuple[slots.Local, ...]:
    """Locals named from a in declaration order, as the pr_line_ frames declare them."""
    names = "abcdefghijkl"
    return tuple(slots.Local(name, *spec) for name, spec in zip(names, specs, strict=False))


@pytest.mark.parametrize("plain", [1, 3, 8, 11])
def test_one_two_byte_array_declared_first_keeps_the_rule(plain):
    """Line A: pr_line_a_c2_h to pr_line_a_c2_h11 and pr_arr_one_three_small hold."""
    declared = (slots.Local("a", 2, array=True),
                *(slots.Local(f"p{n}", 2) for n in range(plain)))  # fmt: skip
    assert slots.order_is_known(declared) is True
    expected = {"a": 4 * plain} | {f"p{n}": 4 * (plain - 1 - n) for n in range(plain)}
    assert slots.frame_layout(declared) == expected


@pytest.mark.parametrize(
    "shape",
    [
        (H, C2),  # the sweep's h c2: it held, off the line
        (H, H, C2),  # pr_arr_one_two_small: it leaves
        (H, H, H, C2, H),  # the sweep: it leaves
        (C2, C2, H),  # pr_arr_two_one_small: it leaves
    ],
)
def test_a_two_byte_array_not_declared_first_stays_refused(shape):
    assert slots.order_is_known(_shape(*shape)) is False


@pytest.mark.parametrize(
    ("shape", "layout"),
    [
        ((C4, C4, INT, INT1), {"a": 8, "b": 4, "c": 0, "d": 0xC}),  # pr_line_b_c4x2_i_blk
        ((C4, C4, INT, INT, INT, INT1), {"a": 0x10, "b": 0xC, "c": 8, "d": 4, "e": 0, "f": 0x14}),
        ((C4, C4, INT, INT1, INT1, INT1, INT1, INT1),
         {"a": 8, "b": 4, "c": 0, "d": 0x1C, "e": 0x18, "f": 0x14, "g": 0x10, "h": 0xC}),
        ((C4, C4, INT, INT1, INT2), {"a": 8, "b": 4, "c": 0, "d": 0xC, "e": 0x10}),
    ],
)  # fmt: skip
def test_two_arrays_then_an_int_keep_the_rule_across_blocks(shape, layout):
    """Line B: pr_line_b_c4x2_i_blk, _i3_blk, _i_blk5 and _i_blk_blk hold, as do the sweep's
    c4 c4 i | i to c4 c4 i i | i i i and their s2 twins."""
    declared = _shape(*shape)
    assert slots.order_is_known(declared) is True
    assert slots.frame_layout(declared) == layout


@pytest.mark.parametrize(
    "shape",
    [
        (C4, C4, INT1),  # pr_arr_two_block: it leaves
        (C4, C4, INT1, INT1),  # pr_arr_two_two_block: it holds, off the line
        (INT, C4, C4, INT1),  # pr_arr_int_two_block: it leaves
        (C4, INT, C4, INT1),
        (C4, C4, INT, C4_1),
    ],
)
def test_two_arrays_off_line_b_stay_refused(shape):
    assert slots.order_is_known(_shape(*shape)) is False


@pytest.mark.parametrize(
    ("shape", "layout"),
    [
        ((C4, C4, C4, INT), {"a": 0xC, "b": 8, "c": 4, "d": 0}),  # pr_arr_three_int
        ((C4, C4, C4, INT, INT), {"a": 0x10, "b": 0xC, "c": 8, "d": 4, "e": 0}),
        ((C4, C4, C4, C4, INT), {"a": 0x10, "b": 0xC, "c": 8, "d": 4, "e": 0}),
    ],
)
def test_three_or_more_arrays_then_ints_keep_the_rule(shape, layout):
    """Line C: pr_arr_three_int, pr_line_c_c4x2_s2_i, _c4x3_i2, _c4x4_i and _c4x3_i_late hold."""
    declared = _shape(*shape)
    assert slots.order_is_known(declared) is True
    assert slots.frame_layout(declared) == layout


@pytest.mark.parametrize(
    "shape",
    [
        (INT, C4, C4, C4),  # pr_arr_int_three: it leaves
        (C4, C4, C4),  # pr_arr_char4_x3: it leaves
        (C4, C4, INT, C4),
        (C4, C4, C4, INT, INT1),
    ],
)
def test_arrays_off_line_c_stay_refused(shape):
    assert slots.order_is_known(_shape(*shape)) is False


# Line D, refit on 2026-11-13 from the pr_line_d_ frames, each one change from a neighbour
# (probe/cg_slots.c, both cells): 4-byte locals beside one local of 1 or 2 bytes, in one block.
CHAR = (1, 0, False)


@pytest.mark.parametrize(
    ("shape", "layout"),
    [
        ((C4, H, INT), {"a": 4, "b": 8, "c": 0}),  # pr_line_d_c4_h_i
        ((H, C4, INT), {"a": 8, "b": 4, "c": 0}),  # pr_line_d_h_c4_i
        ((C2, C4, INT), {"a": 8, "b": 4, "c": 0}),  # pr_line_d_c2_c4_i
        ((C4, H, C4), {"a": 4, "b": 8, "c": 0}),  # pr_line_d_c4_h_c4
        ((C4, C4, H, INT, INT), {"a": 0xC, "b": 8, "c": 0x10, "d": 4, "e": 0}),  # _c4x2_h_i2
        ((INT, CHAR, C4, INT), {"a": 8, "b": 0xC, "c": 4, "d": 0}),  # pr_line_d_i_c_c4_i
        ((H, C4, INT, INT, INT, INT, INT, C4),
         {"a": 0x1C, "b": 0x18, "c": 0x14, "d": 0x10, "e": 0xC, "f": 8, "g": 4,
          "h": 0}),  # pr_line_d_h_c4_i5_c4
    ],
)  # fmt: skip
def test_one_small_local_not_declared_last_keeps_the_rule(shape, layout):
    """Line D: up to two arrays, the small local among them or not, anywhere but last."""
    declared = _shape(*shape)
    assert slots.order_is_known(declared) is True
    assert slots.frame_layout(declared) == layout


@pytest.mark.parametrize(
    ("shape", "layout"),
    [
        ((INT, INT, H), {"a": 4, "b": 0, "c": 8}),  # pr_line_d_i2_h
        ((C4, INT, H), {"a": 4, "b": 0, "c": 8}),  # pr_line_d_c4_i_h
        ((C4, INT, CHAR), {"a": 4, "b": 0, "c": 8}),  # pr_line_d_s2_i_c, as a char[4]
        ((C4, INT, INT, INT, INT, INT, INT, INT, INT, H),
         {"a": 0x20, "b": 0x1C, "c": 0x18, "d": 0x14, "e": 0x10, "f": 0xC, "g": 8, "h": 4,
          "i": 0, "j": 0x24}),  # pr_line_d_c4_i8_h
        ((INT, INT, INT, INT, INT, INT, H),
         {"a": 0x14, "b": 0x10, "c": 0xC, "d": 8, "e": 4, "f": 0, "g": 0x18}),  # _i6_h
    ],
)  # fmt: skip
def test_one_plain_small_local_declared_last_keeps_the_rule_after_plain_locals(shape, layout):
    """Line D: declared last, the small local holds when no local after the first is an array."""
    declared = _shape(*shape)
    assert slots.order_is_known(declared) is True
    assert slots.frame_layout(declared) == layout


@pytest.mark.parametrize(
    "shape",
    [
        (C4, INT, C2),  # pr_line_d_c4_i_c2: it leaves
        (INT, C4, H),  # pr_line_d_i_c4_h: it leaves
        (C4, C4, H),  # pr_line_d_c4x2_h: it leaves
        (C4, C4, INT, H),  # pr_line_d_c4x2_i_h: it holds, off the line
        (C4, C4, INT, INT, H),  # pr_line_d_c4x2_i2_h: it leaves
        (INT, INT, C2),  # pr_line_d_i2_c2: it leaves
        (C4, C4, C2, INT),  # pr_line_d_c4x2_c2_i: three arrays, it leaves
        (H, C4, C4, C4),  # pr_line_d_h_c4x3: it holds, off the line
        (C4, H, INT, H),  # pr_line_d_c4_h_i_h: two small locals, it leaves
        (C4, H, INT1),  # a later block: it held in the refit's sweep, off the line
        ((4, 1, True), (2, 1, False), (4, 1, False)),  # a nested block alone: not measured
        ((8, 0, True), (8, 0, True), H),  # a tie of 8 bytes: not line D
    ],
)
def test_frames_off_line_d_stay_refused(shape):
    assert slots.order_is_known(_shape(*shape)) is False


def test_declaration_order_refuses_an_order_past_the_lines():
    """pr_line_d_c4_i_h is known, and the int-first order this target needs is pr_line_d_i_c4_h,
    which leaves: the model cannot say whether it reaches the target."""
    declared = _shape(C4, INT, H)
    with pytest.raises(ValueError, match="no known layout"):
        slots.declaration_order(declared, {"a": 0, "b": 4, "c": 8})
