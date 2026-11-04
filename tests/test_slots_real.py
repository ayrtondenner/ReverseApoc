"""The slot model against the real wcc386 10.6: probe/cg_slots.c under both cells (D-02).

These tests skip without capstone, a compiler runner or an installed Watcom 10.6 the gate accepts.
They write only under build/test-slots/ (the compiler refuses objects outside the repository, so
pytest's tmp_path cannot be used) and assert on offsets and counts, never on bytes. The C is our
own clean-room probe: no game byte is read here.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

import reverseapoc
from conftest import REPO_ROOT, WATCOM_DIR, requires_capstone, requires_runner, requires_version
from reverseapoc import batch, omf, x86
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
    at: int = 0  # where in the local the marker lies


DOUBLE = Marked("d", 8, 0x40040000, HIGH_DWORD)  # 2.5
SAME_SIZE = (Marked("a", 4, 0x11), Marked("b", 4, 0x22), Marked("c", 4, 0x33), Marked("d", 4, 0x44))
MIXED = (Marked("a", 1, 0x11), Marked("b", 4, 0x22), Marked("c", 2, 0x33), DOUBLE)
# Each function's locals in declaration order.
SHAPES = {
    "pr_slot_same_size": SAME_SIZE,
    "pr_slot_same_size_rev": SAME_SIZE[::-1],
    "pr_slot_mixed": MIXED,
    "pr_slot_mixed_rev": MIXED[::-1],
}

_IMMEDIATE = re.compile(r"(?:0x[0-9a-f]+|\d+)$")
_MEMORY_STORE = re.compile(r"\w+ ptr \[esp[^\]]*\], (?P<source>\w+)$")


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
    from batch._frame_slots, which keeps track of the depth."""
    slots, _ = batch._frame_slots(code, 0)
    constants: dict[str, int] = {}
    for insn, slot in zip(x86.decode(code, 0), slots, strict=True):
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


@pytest.mark.parametrize("cell", CELLS)
@pytest.mark.parametrize("name", SHAPES)
def test_model_reproduces_every_memory_shape(modules, cell, name):
    shape = SHAPES[name]
    measured = _offsets(modules[cell], name, cell, shape)
    declared = tuple(reverseapoc.slots.Local(one.name, one.size) for one in shape)
    assert measured == reverseapoc.slots.frame_layout(declared)
