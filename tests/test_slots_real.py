"""The slot model against the real wcc386 10.6: probe/cg_slots.c under both cells (D-02).

These tests skip without capstone, a compiler runner or an installed Watcom 10.6 the gate accepts.
They write only under build/test-slots/ (the compiler refuses objects outside the repository, so
pytest's tmp_path cannot be used) and assert on offsets and counts, never on bytes. The C is our
own clean-room probe: no game byte is read here.

Besides the shapes the model reproduces, TIES holds the shapes it refuses: their order is proven
here to break declaration order, so the refusal cannot outlive the measurement behind it.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

import pytest

from conftest import REPO_ROOT, WATCOM_DIR, requires_capstone, requires_runner, requires_version
from reverseapoc import batch, omf, search, slots, x86
from reverseapoc.cflags import Rule
from reverseapoc.compiler import CompilerError, check_gate
from reverseapoc.probe import PROBE_DIR

BUILD_ROOT = REPO_ROOT / "build" / "test-slots"
VERSION = "10.6"
CELLS = {"plain": ("-4r", "-s", "-fpi"), "oneatx": ("-4r", "-oneatx", "-s", "-fpi")}
HIGH_DWORD = 4  # where a double's marker lies: the low dword of 2.5 is 0


@dataclass(frozen=True)
class Marked:
    name: str
    size: int
    marker: int  # the constant the probe stores in it
    scope: int = 0
    at: int = 0  # where in the local the marker lies
    array: bool = False  # it holds more than one element


def _arrays(size: int, *markers: int) -> tuple[Marked, ...]:
    """Arrays of `size` bytes each, named from a, as the `pr_arr_` shapes declare them."""
    return tuple(Marked(name, size, marker, array=True)
                 for name, marker in zip("abcd", markers, strict=False))  # fmt: skip


def _shorts(names: str, first: int) -> tuple[Marked, ...]:
    """Plain 2-byte locals, their markers counted up from `first` as the `pr_line_a_` frames do."""
    return tuple(Marked(name, 2, first + n) for n, name in enumerate(names))


DOUBLE = Marked("d", 8, 0x40040000, at=HIGH_DWORD)  # 2.5
SAME_SIZE = (Marked("a", 4, 0x11), Marked("b", 4, 0x22), Marked("c", 4, 0x33), Marked("d", 4, 0x44))
MIXED = (Marked("a", 1, 0x11), Marked("b", 4, 0x22), Marked("c", 2, 0x33), DOUBLE)
ARRAY = (Marked("a", 12, 0x11, array=True), Marked("b", 8, 0x22, array=True),
         Marked("c", 6, 0x33, array=True))  # fmt: skip
STRUCT = (Marked("a", 3, 0x11), Marked("b", 6, 0x22), Marked("c", 12, 0x33), Marked("d", 4, 0x44))
ODD = (Marked("a", 3, 0x11, array=True), Marked("b", 5, 0x22, array=True),
       Marked("c", 7, 0x33, array=True), Marked("d", 4, 0x44))  # fmt: skip
BYTES = (Marked("a", 1, 0x11), Marked("b", 1, 0x22), Marked("c", 1, 0x33))
SHORTS = (Marked("a", 2, 0x11), Marked("b", 2, 0x22), Marked("c", 2, 0x33))
VOLATILE = (Marked("a", 4, 0x11), Marked("v", 4, 0x22), Marked("b", 4, 0x33))
FLOAT_1_5, FLOAT_2_5, FLOAT_3_5 = 0x3FC00000, 0x40200000, 0x40600000
FLOATS = (Marked("a", 4, FLOAT_1_5), Marked("b", 4, FLOAT_2_5), Marked("c", 4, FLOAT_3_5))
TWO_TWO = (*_arrays(4, 0x3B, 0x3C), Marked("c", 4, 0x3D), Marked("d", 4, 0x3E))
C4_S2 = (*_arrays(4, 0x6F), Marked("b", 4, 0x70, array=True))  # char a[4]; short b[2]
C4_C2_INT = (*_arrays(4, 0x71), Marked("b", 2, 0x72, array=True), Marked("c", 4, 0x73))
C4X2_S2 = _arrays(4, 0x74, 0x75, 0x76)  # char a[4]; char b[4]; short c[2]
INT1_X3 = (Marked("a", 4, 0x6C), Marked("b", 4, 0x6D), Marked("c", 4, 0x6E))  # int x[1]
ONE_THREE = (*_arrays(4, 0x3F), Marked("b", 4, 0x40), Marked("c", 4, 0x41), Marked("d", 4, 0x42))
# Each function's locals in declaration order. A scope counts blocks in source order.
SHAPES = {
    "pr_slot_same_size": SAME_SIZE,
    "pr_slot_same_size_rev": SAME_SIZE[::-1],
    "pr_slot_mixed": MIXED,
    "pr_slot_mixed_rev": MIXED[::-1],
    "pr_slot_array": ARRAY,
    "pr_slot_array_rev": ARRAY[::-1],
    "pr_slot_struct": STRUCT,
    "pr_slot_struct_rev": STRUCT[::-1],
    "pr_slot_odd": ODD,
    "pr_slot_odd_rev": ODD[::-1],
    "pr_slot_unaligned": (Marked("a", 12, 0x11, array=True), DOUBLE, Marked("b", 4, 0x22)),
    "pr_slot_bytes": BYTES,
    "pr_slot_bytes_rev": BYTES[::-1],
    "pr_slot_shorts": SHORTS,
    "pr_slot_shorts_rev": SHORTS[::-1],
    "pr_slot_flat": SAME_SIZE[:3],
    "pr_slot_scope": (Marked("a", 4, 0x11), Marked("b", 4, 0x22, 1), Marked("c", 4, 0x33, 2)),
    "pr_slot_scope_pairs": (Marked("a", 4, 0x11), Marked("b", 4, 0x22),
                            Marked("c", 4, 0x33, 1), Marked("d", 4, 0x44, 1)),  # fmt: skip
    "pr_slot_siblings": (Marked("a", 4, 0x11), Marked("b", 4, 0x22, 1), Marked("c", 4, 0x33, 2),
                         Marked("d", 4, 0x44, 3)),  # fmt: skip
    "pr_slot_block_order": (Marked("a", 4, 0x11), Marked("b", 4, 0x22, 1), Marked("d", 4, 0x44, 2),
                            Marked("c", 4, 0x33, 3)),  # fmt: skip
    "pr_slot_unused": (Marked("a", 4, 0x11),),
    "pr_slot_volatile": VOLATILE,
    "pr_slot_volatile_rev": VOLATILE[::-1],
    "pr_slot_volatile_init": (Marked("v", 4, 0x22), Marked("a", 4, 0x11)),
    "pr_slot_float_taken": FLOATS,
    "pr_slot_float_array": (Marked("f", 4, FLOAT_1_5), Marked("v", 8, 0x11, array=True)),
    "pr_slot_double_int": (Marked("a", 4, 0x11), DOUBLE),
    "pr_arr_char4_x2": _arrays(4, 0x23, 0x24),
    "pr_arr_one_int": (*_arrays(4, 0x25), Marked("b", 4, 0x26), Marked("c", 4, 0x27)),
    "pr_arr_one_int1": (*_arrays(4, 0x28), Marked("b", 4, 0x29), Marked("c", 4, 0x2A)),
    "pr_arr_two_int": (*_arrays(4, 0x2B, 0x2C), Marked("c", 4, 0x2D)),
    "pr_arr_two_int1": (*_arrays(4, 0x2E, 0x2F), Marked("c", 4, 0x30)),
    "pr_arr_short2_x2": _arrays(4, 0x31, 0x32),
    "pr_arr_char2_x2": _arrays(2, 0x34, 0x35),
    "pr_arr_short2_int": (*_arrays(4, 0x36), Marked("b", 4, 0x37), Marked("c", 4, 0x38)),
    "pr_arr_one_one": (*_arrays(4, 0x39), Marked("b", 4, 0x3A)),
    "pr_arr_two_two": TWO_TWO,
    "pr_arr_two_two_rev": TWO_TWO[::-1],
    "pr_arr_one_three": ONE_THREE,
    "pr_arr_one_three_rev": ONE_THREE[::-1],
    "pr_arr_one_block": (*_arrays(4, 0x6A), Marked("b", 4, 0x6B, 1)),
    "pr_arr_int1_x3": INT1_X3,  # the lifter's 4-byte taken slot keeps M2 (07.2-14)
    "pr_arr_int1_x3_rev": INT1_X3[::-1],
    "pr_arr_c4_s2": C4_S2,  # a char[4] beside a short[2]: two arrays of one size (07.2-14)
    "pr_arr_c4_s2_rev": C4_S2[::-1],
    # Line A (quick 261112-fdx): one 2-byte array declared first, then 2-byte plain locals.
    "pr_arr_one_three_small": (*_arrays(2, 0x48), Marked("b", 2, 0x49), Marked("c", 2, 0x4A),
                               Marked("d", 2, 0x4B)),  # fmt: skip
    "pr_line_a_c2_h": (*_arrays(2, 0x77), Marked("b", 2, 0x177)),
    "pr_line_a_c2_h8": (*_arrays(2, 0x78), *_shorts("bcdefghi", 0x178)),
    "pr_line_a_c2_h11": (*_arrays(2, 0x79), *_shorts("bcdefghijkl", 0x180)),
    "pr_line_a_uc2_h3": (*_arrays(2, 0x7A), *_shorts("bcd", 0x18B)),
    "pr_line_a_c2_mixed": (*_arrays(2, 0x7B), *_shorts("bcde", 0x18E)),
    "pr_line_a_c2_h3_late": (*_arrays(2, 0x7C), *_shorts("bcd", 0x192)),
    "pr_line_a_c2_h3_split": (*_arrays(2, 0x7D), *_shorts("bcd", 0x195)),
}
PAIR = (Marked("a", 8, 0x11, array=True), Marked("b", 8, 0x22, array=True))
THREE = (*PAIR, Marked("c", 8, 0x33, array=True))
CHAR4_X3 = _arrays(4, 0x12, 0x13, 0x14)
TWO_ONE_SMALL = (*_arrays(2, 0x4C, 0x4D), Marked("c", 2, 0x4E))
TWO_BLOCK = (*_arrays(4, 0x52, 0x53), Marked("c", 4, 0x54, 1))
# What the model refuses: every one of these leaves declaration order.
TIES = {
    "pr_tie_three": THREE,
    "pr_tie_three_int": (*THREE, Marked("d", 4, 0x44)),
    "pr_tie_pair": (*PAIR, Marked("c", 4, 0x33)),
    "pr_tie_small": (Marked("d", 8, 0x44, array=True), Marked("e", 8, 0x55, array=True),
                     Marked("c", 4, 0x33), Marked("b", 4, 0x22), Marked("a", 4, 0x11)),  # fmt: skip
    "pr_tie_double": (DOUBLE, *PAIR),
    "pr_tie_sizes": (Marked("a", 4, 0x11), Marked("b", 4, 0x22), Marked("c", 2, 0x33),
                     Marked("d", 2, 0x44)),  # fmt: skip
    "pr_tie_scope_sizes": (Marked("a", 4, 0x11), Marked("b", 2, 0x22),
                           Marked("c", 4, 0x33, 1), Marked("d", 2, 0x44, 1),
                           Marked("e", 4, 0x55, 2), Marked("f", 2, 0x66, 2)),  # fmt: skip
    "pr_tie_scope_shorts": (Marked("a", 2, 0x11), Marked("b", 2, 0x22, 1), Marked("c", 2, 0x33, 2)),
    "pr_arr_char4_x3": CHAR4_X3,
    "pr_arr_char4_x3_rev": CHAR4_X3[::-1],
    "pr_arr_char4_x4": _arrays(4, 0x15, 0x16, 0x17, 0x18),
    "pr_arr_uchar4_x3": _arrays(4, 0x19, 0x1A, 0x1B),
    "pr_arr_short2_x3": _arrays(4, 0x1C, 0x1D, 0x1E),
    "pr_arr_char2_x3": _arrays(2, 0x1F, 0x20, 0x21),
    "pr_arr_two_one_small": TWO_ONE_SMALL,
    "pr_arr_two_one_small_rev": TWO_ONE_SMALL[::-1],
    "pr_arr_one_two_small": (Marked("a", 2, 0x4F), Marked("b", 2, 0x50),
                             Marked("c", 2, 0x51, array=True)),  # fmt: skip
    "pr_arr_two_block": TWO_BLOCK,
    "pr_arr_two_block_rev": (TWO_BLOCK[1], TWO_BLOCK[0], TWO_BLOCK[2]),
    "pr_arr_short2_block": (*_arrays(4, 0x56, 0x57), Marked("c", 4, 0x58, 1)),
    "pr_arr_int_two_block": (Marked("a", 4, 0x59), Marked("b", 4, 0x5A, array=True),
                             Marked("c", 4, 0x5B, array=True),
                             Marked("d", 4, 0x5C, 1)),  # fmt: skip
    "pr_arr_int_three": (Marked("a", 4, 0x5D), Marked("b", 4, 0x5E, array=True),
                         Marked("c", 4, 0x5F, array=True),
                         Marked("d", 4, 0x60, array=True)),  # fmt: skip
    "pr_arr_c4x2_s2": C4X2_S2,  # three arrays of 4 bytes, a short[2] among them (07.2-14)
    "pr_arr_c4x2_s2_rev": C4X2_S2[::-1],
}
# Frames the model refuses though they keep declaration order: the compiler's line runs through
# no count, so the refusal is wider than it, on the safe side.
REFUSED_HOLDING = {
    "pr_arr_two_two_small": (*_arrays(2, 0x43, 0x45), Marked("c", 2, 0x46), Marked("d", 2, 0x47)),
    "pr_arr_three_int": (*_arrays(4, 0x61, 0x62, 0x63), Marked("d", 4, 0x64)),
    "pr_arr_two_two_block": (*_arrays(4, 0x65, 0x67), Marked("c", 4, 0x68, 1),
                             Marked("d", 4, 0x69, 1)),  # fmt: skip
    "pr_arr_c4_c2_int": C4_C2_INT,  # two sizes: a char[4] and an int tie beside a char[2]
    "pr_arr_c4_c2_int_rev": C4_C2_INT[::-1],
}
# Where the refused array ties sit, the same in both cells.
ARRAY_TIES = {
    "pr_arr_char4_x3": {"a": 4, "b": 8, "c": 0},
    "pr_arr_char4_x3_rev": {"c": 4, "b": 8, "a": 0},
    "pr_arr_char4_x4": {"a": 4, "b": 0xC, "c": 8, "d": 0},
    "pr_arr_uchar4_x3": {"a": 4, "b": 8, "c": 0},
    "pr_arr_short2_x3": {"a": 4, "b": 8, "c": 0},
    "pr_arr_char2_x3": {"a": 0, "b": 8, "c": 4},
    "pr_arr_two_one_small": {"a": 4, "b": 8, "c": 0},
    "pr_arr_two_block": {"a": 8, "b": 4, "c": 0},
    "pr_arr_short2_block": {"a": 8, "b": 4, "c": 0},
    "pr_arr_int_two_block": {"a": 0xC, "b": 8, "c": 4, "d": 0},
    "pr_arr_int_three": {"a": 4, "b": 0xC, "c": 8, "d": 0},
    "pr_arr_c4x2_s2": {"a": 4, "b": 8, "c": 0},
    "pr_arr_c4x2_s2_rev": {"c": 4, "b": 8, "a": 0},
}
# A float with no address taken in a tie: order_is_known cannot see that, so the search refuses it.
FLOAT_TIES = {
    "pr_float_ints": (Marked("a", 4, 0x11), Marked("b", 4, 0x22), Marked("f", 4, FLOAT_1_5)),
    "pr_float_tie": FLOATS,
    "pr_float_tie_rev": FLOATS[::-1],
}
SPILL_MEMORY = (Marked("m", 4, 0x711), Marked("q", 12, 0x722, array=True))
SPILL_SMALL = (Marked("m", 2, 0x711), Marked("n", 2, 0x722))
SAME_CODE = (("pr_spill_decl", "pr_spill_decl_rev"), ("pr_spill_decl", "pr_spill_scoped"))
MOVED_CODE = (
    ("pr_spill_decl", "pr_spill_assign"),
    ("pr_spill_decl", "pr_spill_use"),
    ("pr_spill_decl", "pr_spill_type"),
    ("pr_spill_loop", "pr_spill_loop_late"),
)
# Real maps of two clean-room functions, ours then theirs: batch.slot_map needs no EXE.
COMPUTED_TWIN = ("pr_twin_abc", "pr_twin_bca")
FALLBACK_TWINS = (
    ("pr_twin_ints_double", "pr_twin_double_ints"),  # a double beside the tie
    ("pr_float_tie", "pr_float_tie_rev"),  # a float in the tie
    ("pr_thin_ours", "pr_thin_theirs"),  # a map that cannot place c
    ("pr_arr_char4_x3", "pr_arr_char4_x3_rev"),  # three arrays in a tie
    ("pr_arr_two_one_small", "pr_arr_two_one_small_rev"),  # an array beside a short
    ("pr_arr_two_block", "pr_arr_two_block_rev"),  # two arrays beside a later block
)

_IMMEDIATE = re.compile(r"(?:0x[0-9a-f]+|\d+)$")
_MEMORY_STORE = re.compile(r"\w+ ptr \[esp[^\]]*\], (?P<source>\w+)$")
_RETURNED = "ax"  # the register family a call returns an int or a pointer in


@pytest.fixture(scope="module")
def modules() -> dict[str, omf.Module]:
    """probe/cg_slots.c compiled once per cell, by cell name."""
    requires_capstone()
    requires_runner()
    requires_version(VERSION)
    try:
        check_gate("wcc386", VERSION, watcom_dir=WATCOM_DIR)
    except CompilerError as exc:
        pytest.skip(f"Watcom {VERSION}: gate refused ({exc})")
    shutil.rmtree(BUILD_ROOT, ignore_errors=True)
    src = PROBE_DIR / "cg_slots.c"
    jobs = [batch.Job(src, BUILD_ROOT / cell / "cg_slots.obj",
                      Rule("*", "wcc386", VERSION, flags, 0))
            for cell, flags in CELLS.items()]  # fmt: skip
    compiled = batch.compile_batch(jobs, len(jobs), watcom_dir=WATCOM_DIR).compiled
    for one in compiled:
        assert one.ok, one.output
    return {cell: omf.read_object(one.job.obj.read_bytes())
            for cell, one in zip(CELLS, compiled, strict=True)}  # fmt: skip


def _function(module: omf.Module, name: str) -> bytes:
    """The code of `name`, up to the next public at a greater offset: under -4r -s, functions
    with identical bodies share one offset."""
    ((index, segment),) = [(n, seg) for n, seg in enumerate(module.segments, 1) if seg.is_code]
    publics = [public for public in module.publics if public.segment_index == index]
    (start,) = [public.offset for public in publics if public.name == f"{name}_"]
    end = min([public.offset for public in publics if public.offset > start],
              default=len(segment.data))  # fmt: skip
    return segment.data[start:end]


def _family(register: str) -> str:
    """The register `register` is a part of: `edx`, `dx` and `dl` all read `dx`."""
    name = register.removeprefix("e")
    return f"{name[0]}x" if name[1] in "lh" else name


def _stores(code: bytes) -> Iterator[tuple[int, int]]:
    """(value, slot) of each constant stored in a slot. -oneatx loads a marker into a register
    first and may store it after pushes, so register constants are followed and each slot comes
    from batch._frame_slots, which keeps track of the depth. A call keeps every register but eax,
    the only one the probe's externs return in (a double comes back in st0), and -oneatx loads a
    marker before a call to store it after (pr_line_a_c2_h3_split)."""
    frame_slots, _ = batch._frame_slots(code, 0)
    constants: dict[str, int] = {}
    for insn, slot in zip(x86.decode(code, 0), frame_slots, strict=True):
        if insn.is_call:
            constants.pop(_RETURNED, None)
        if insn.mnemonic != "mov":
            continue
        target, source = insn.op_str.split(", ", 1)
        if "[" not in target and _IMMEDIATE.match(source) is not None:
            constants[_family(target)] = int(source, 0)
        store = _MEMORY_STORE.match(insn.op_str)
        if store is None or slot is None:
            continue
        source = store["source"]
        value = int(source, 0) if _IMMEDIATE.match(source) else constants.get(_family(source))
        if value is not None:
            yield value, slot


def _offsets(module: omf.Module, name: str, cell: str, shape: tuple[Marked, ...]) -> dict[str, int]:
    """Each local's offset, read from its marker. A marker that is missing means the shape did
    not force the local into memory."""
    found = dict(_stores(_function(module, name)))
    missing = [one.name for one in shape if one.marker not in found]
    assert not missing, f"{name} under {cell}: no store of a marker for {missing}"
    return {one.name: found[one.marker] - one.at for one in shape}


def _declared(shape: Sequence[Marked]) -> tuple[slots.Local, ...]:
    return tuple(slots.Local(one.name, one.size, one.scope, one.array) for one in shape)


def _frame(module: omf.Module, name: str) -> int:
    return batch._frame_slots(_function(module, name), 0)[1]


def _text(module: omf.Module, name: str) -> list[str]:
    """The function's instructions as text: equal text is equal code here."""
    return [f"{insn.mnemonic} {insn.op_str}" for insn in x86.decode(_function(module, name), 0)]


def _by_declaration(shape: Sequence[Marked]) -> dict[str, int]:
    """M1 to M3 applied to a tie the model refuses: what declaration order alone would give."""
    ascending = sorted(enumerate(shape),
                       key=lambda pair: (-pair[1].size, pair[1].scope, -pair[0]))  # fmt: skip
    layout = {}
    offset = 0
    for _, one in ascending:
        layout[one.name] = offset
        offset += slots.frame_size(_declared([one]))
    return layout


@pytest.mark.parametrize("cell", CELLS)
@pytest.mark.parametrize("name", SHAPES)
def test_model_reproduces_every_memory_shape(modules, cell, name):
    """Every shape the model accepts. The `pr_tie_` and `pr_arr_` shapes it refuses are held by
    test_a_refused_tie_leaves_declaration_order_and_keeps_sizes."""
    shape = SHAPES[name]
    measured = _offsets(modules[cell], name, cell, shape)
    declared = _declared(shape)
    assert slots.order_is_known(declared) is True
    assert measured == slots.frame_layout(declared)
    assert _frame(modules[cell], name) == slots.frame_size(declared)


@pytest.mark.parametrize("cell", CELLS)
@pytest.mark.parametrize("name", TIES)
def test_a_refused_tie_leaves_declaration_order_and_keeps_sizes(modules, cell, name):
    """The limit is real: the model refuses it, declaration order would be wrong, and M1 and M3
    still hold, each size together, the largest lowest, the frame as padded."""
    shape = TIES[name]
    measured = _offsets(modules[cell], name, cell, shape)
    declared = _declared(shape)
    assert slots.order_is_known(declared) is False
    assert measured != _by_declaration(shape)
    sizes = {one.name: one.size for one in shape}
    ascending = sorted(measured, key=measured.__getitem__)
    assert [sizes[local] for local in ascending] == sorted(sizes.values(), reverse=True)
    assert _frame(modules[cell], name) == slots.frame_size(declared)


@pytest.mark.parametrize("cell", CELLS)
@pytest.mark.parametrize("name", REFUSED_HOLDING)
def test_a_frame_the_model_refuses_may_still_hold(modules, cell, name):
    """The refusal is wider than the compiler's line: these keep declaration order, and the
    model refuses them anyway, because no count separates them from the ones that leave it."""
    shape = REFUSED_HOLDING[name]
    assert slots.order_is_known(_declared(shape)) is False
    assert _offsets(modules[cell], name, cell, shape) == _by_declaration(shape)


@pytest.mark.parametrize("cell", CELLS)
@pytest.mark.parametrize("name", ARRAY_TIES)
def test_array_ties_sit_where_measured(modules, cell, name):
    """Three or more arrays of one size leave M2, and these offsets say how."""
    assert _offsets(modules[cell], name, cell, TIES[name]) == ARRAY_TIES[name]


@pytest.mark.parametrize("cell", CELLS)
def test_a_local_outside_the_tie_changes_it(modules, cell):
    """pr_tie_three_int only adds an int after pr_tie_three, and a, b and c take other offsets:
    so no table of orders by count can hold."""
    alone = _offsets(modules[cell], "pr_tie_three", cell, TIES["pr_tie_three"])
    beside = _offsets(modules[cell], "pr_tie_three_int", cell, TIES["pr_tie_three_int"])
    assert alone != {name: beside[name] for name in alone}


@pytest.mark.parametrize("cell", CELLS)
@pytest.mark.parametrize("name", FLOAT_TIES)
def test_a_float_in_a_tie_leaves_declaration_order(modules, cell, name):
    """Why search._readable refuses these: M2 would be wrong, and the frame is still as padded."""
    shape = FLOAT_TIES[name]
    declared = _declared(shape)
    assert _offsets(modules[cell], name, cell, shape) != slots.frame_layout(declared)
    assert _frame(modules[cell], name) == slots.frame_size(declared)


@pytest.mark.parametrize("cell", CELLS)
def test_declarations_still_move_a_float_in_a_tie(modules, cell):
    """So those slots are not out of reach, and the search must keep its plain moves for them."""
    module = modules[cell]
    tie = _offsets(module, "pr_float_tie", cell, FLOATS)
    assert tie != _offsets(module, "pr_float_tie_rev", cell, FLOATS[::-1])


@pytest.mark.parametrize("cell", CELLS)
def test_a_double_changes_a_tie_of_ints_by_its_use_alone(modules, cell):
    """One declaration list, and a and b swap: order_is_known must see d to refuse this frame."""
    ints = (Marked("b", 4, 0x22), Marked("a", 4, 0x11))
    called = _offsets(modules[cell], "pr_double_called", cell, ints)
    assert called != _offsets(modules[cell], "pr_double_stored", cell, ints)
    assert slots.order_is_known((*_declared(ints), slots.Local("d", 8))) is False


def test_a_short_beside_a_short_moves_with_its_declaration(modules):
    """The exception to M5, and why the search leaves plain locals under 4 bytes to its moves."""
    one, other = "pr_spill_short", "pr_spill_short_rev"
    assert any(_text(module, one) != _text(module, other) for module in modules.values())


@pytest.mark.parametrize("cell", CELLS)
@pytest.mark.parametrize("pair", SAME_CODE)
def test_scalars_ignore_declarations_and_scope(modules, cell, pair):
    one, other = pair
    assert _text(modules[cell], one) == _text(modules[cell], other)


@pytest.mark.parametrize("pair", MOVED_CODE)
def test_assignment_use_and_type_move_scalars(modules, pair):
    one, other = pair
    assert any(_text(module, one) != _text(module, other) for module in modules.values())


def _other_slots(module: omf.Module, name: str, measured: dict[str, int]) -> set[int]:
    """Every slot `name` reads or writes that is not the start of a memory local."""
    read, _ = batch._frame_slots(_function(module, name), 0)
    return {slot for slot in read if slot is not None} - set(measured.values())


@pytest.mark.parametrize("cell", CELLS)
def test_spills_sit_above_locals_of_four_bytes_or_more(modules, cell):
    """The memory locals keep the model's offsets from 0, and scalar_slots names the rest."""
    module = modules[cell]
    measured = _offsets(module, "pr_spill_memory", cell, SPILL_MEMORY)
    declared = _declared(SPILL_MEMORY)
    assert measured == slots.frame_layout(declared)
    others = _other_slots(module, "pr_spill_memory", measured)
    assert others
    frame = _frame(module, "pr_spill_memory")
    assert slots.scalar_slots(declared, others, frame) == tuple(sorted(others))


@pytest.mark.parametrize("cell", CELLS)
def test_spills_sit_below_smaller_locals(modules, cell):
    """Spills sort by size too: these shorts take the top of the frame, in the model's order,
    and scalar_slots keeps both the slots below them and none of theirs."""
    module = modules[cell]
    measured = _offsets(module, "pr_spill_small", cell, SPILL_SMALL)
    declared = _declared(SPILL_SMALL)
    frame = _frame(module, "pr_spill_small")
    base = frame - slots.frame_size(declared)
    assert base > 0
    layout = slots.frame_layout(declared)
    assert measured == {name: base + offset for name, offset in layout.items()}
    others = _other_slots(module, "pr_spill_small", measured)
    assert others
    assert max(others) < base
    mismatched = [*others, *measured.values()]
    assert slots.scalar_slots(declared, mismatched, frame) == tuple(sorted(others))


@pytest.fixture(scope="module")
def source() -> str:
    return (PROBE_DIR / "cg_slots.c").read_text(encoding="ascii")


def _real_map(module: omf.Module, ours: str, theirs: str) -> batch.SlotMap:
    return batch.slot_map(_function(module, ours), _function(module, theirs), 0, set())


def _declaration_lines(text: str, name: str) -> list[str]:
    lines = text.split("\n")
    return [lines[n].strip() for n in search.declarations(text, search.function_span(text, name))]


@pytest.mark.parametrize("cell", CELLS)
def test_the_axis_computes_a_declaration_twin_from_a_real_map(modules, source, cell):
    """Must-have truth 4 on real input: the one order the other function's slots need."""
    ours, theirs = COMPUTED_TWIN
    slot_map = _real_map(modules[cell], ours, theirs)
    (move,) = search.declaration_axis(source, search.function_span(source, ours), slot_map)
    assert _declaration_lines(move.text, ours) == _declaration_lines(source, theirs)


@pytest.mark.parametrize("cell", CELLS)
@pytest.mark.parametrize("twin", FALLBACK_TWINS)
def test_the_axis_keeps_its_plain_moves_on_a_real_map_it_cannot_answer(modules, source, cell, twin):
    """Real maps are partial and conflicting where stubbed ones are tidy."""
    ours, theirs = twin
    slot_map = _real_map(modules[cell], ours, theirs)
    assert any(one != other for one, other in slot_map.pairs)
    span = search.function_span(source, ours)
    moves = list(search.declaration_axis(source, span, slot_map))
    assert moves
    assert moves == list(search.declaration_moves(source, span))
