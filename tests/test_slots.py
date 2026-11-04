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


@pytest.mark.parametrize("sizes", [(1, 1, 2, 2, 4, 4), (4, 4, 4), (1, 2, 4), (3, 5, 7, 4), (12, 8)])
def test_order_is_known_with_small_sizes_or_no_tie(sizes):
    declared = _locals(*((f"v{n}", size) for n, size in enumerate(sizes)))
    assert slots.order_is_known(declared) is True


@pytest.mark.parametrize("sizes", [(8, 8), (8, 8, 4), (4, 4, 8), (3, 3), (6, 6, 6), (8, 8, 2, 2)])
def test_order_is_not_known_for_a_tie_the_probe_could_not_order(sizes):
    declared = _locals(*((f"v{n}", size) for n, size in enumerate(sizes)))
    assert slots.order_is_known(declared) is False


def test_frame_layout_refuses_an_order_nothing_measured():
    with pytest.raises(ValueError, match="no known order"):
        slots.frame_layout(_locals(("a", 8), ("b", 8)))


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


def test_declaration_order_keeps_locals_of_other_sizes_in_place():
    """Only a tie needs moving: the char keeps its place between the two ints."""
    declared = _locals(("a", 4), ("c", 1), ("b", 4))
    assert slots.declaration_order(declared, {"a": 0, "b": 4, "c": 8}) == ("b", "c", "a")


def test_declaration_order_keeps_each_local_in_its_block():
    declared = (slots.Local("a", 4), slots.Local("b", 4), slots.Local("c", 4, 1))
    assert slots.declaration_order(declared, {"a": 0, "b": 4, "c": 8}) == ("b", "a", "c")
    assert slots.declaration_order(declared, {"a": 8, "b": 4, "c": 0}) is None


def test_declaration_order_refuses_a_layout_size_cannot_give():
    """No order puts the smaller local below the larger one."""
    declared = _locals(("big", 4), ("small", 2))
    assert slots.declaration_order(declared, {"small": 0, "big": 4}) is None


def test_scalar_slots_are_the_ones_no_memory_local_explains():
    """0 and 8 lie inside the array and 0xC is the int; 0x10 and up lie above every local."""
    declared = _locals(("array", 12), ("one", 4))
    assert slots.scalar_slots(declared, (0x14, 0, 8, 0xC, 0x10)) == (0x10, 0x14)


def test_with_no_memory_local_every_slot_is_a_scalar():
    assert slots.scalar_slots((), (8, 0)) == (0, 8)


def test_scalar_slots_leave_out_a_negative_slot():
    """A negative slot is slot_map's shifted reading under a push, not a place in the frame."""
    assert slots.scalar_slots((), (-4, 4)) == (4,)
