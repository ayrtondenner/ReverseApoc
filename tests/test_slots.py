"""The slot model as pure functions: no compiler runs here. The rules were measured on
probe/cg_slots.c; tests/test_slots_real.py holds them against the real wcc386 10.6.
"""

from __future__ import annotations

import pytest

import reverseapoc


def _locals(*sizes: tuple[str, int]) -> tuple:
    return tuple(reverseapoc.slots.Local(name, size) for name, size in sizes)


def test_equal_sizes_take_offsets_by_declaration():
    layout = reverseapoc.slots.frame_layout(_locals(("a", 4), ("b", 4), ("c", 4), ("d", 4)))
    assert layout == {"a": 0xC, "b": 8, "c": 4, "d": 0}


@pytest.mark.parametrize("reverse", [False, True])
def test_larger_locals_sit_lower(reverse):
    declared = [("c", 1), ("i", 4), ("s", 2), ("f", 8)]
    layout = reverseapoc.slots.frame_layout(_locals(*(declared[::-1] if reverse else declared)))
    assert layout == {"f": 0, "i": 8, "s": 0xC, "c": 0x10}


def test_sizes_pad_to_four():
    assert reverseapoc.slots.frame_layout(_locals(("s", 2), ("c", 1))) == {"s": 0, "c": 4}
