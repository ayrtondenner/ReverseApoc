"""Test-only builder of a synthetic function pair for the relocation check and the land step: an
original function in a tests/conftest.py LE image, and our compiled function in a tests/omfimage.py
OMF module. Every byte, name and address here is made up.

The LE image has the conftest objects: code at 0x10000 (two pages), data at 0x20000. The game rows
func_00010010 and func_00010020 exist only so their placeholders resolve; their bytes are page fill.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from conftest import PAGE_SIZE, build_le_image, fixup_record
from omfimage import (
    extdef,
    fixup,
    fixupp32,
    grpdef,
    ledata32,
    lnames,
    module,
    pubdef32,
    segdef32,
)
from reverseapoc.functions import FunctionRow, game_name
from reverseapoc.le import LE, SRC_OFF32, Fixup
from reverseapoc.omf import Module, Segment, read_object
from reverseapoc.relocs import FRAME_GROUP
from reverseapoc.symbols import SymbolTable

CODE_BASE = 0x10000  # object 1
DATA_RANGES = [(0x20000, 0x23000)]  # object 2
TEXT_INDEX = 1  # SEGDEF numbers in our module
CONST_INDEX = 2
FLAT_LNAME = "FLAT"  # the group wcc386 10.6 names as the frame of every flat-code fixup
FLAT_GROUP = 1  # its GRPDEF number in our module
FLAT_FRAME = (FRAME_GROUP, FLAT_GROUP)  # F1 FLAT, the frame the real 10.6 objects use (06-03)
_PAGES = 3  # logical pages of the conftest image: two code, one data


def game_row(start: int, end: int) -> FunctionRow:
    return FunctionRow(start, end, game_name(start), "game", "unit", "call")


CALLEES = [game_row(0x10010, 0x10018), game_row(0x10020, 0x10028)]


# ---- the good pair: call func_00010010; mov eax,[0x20004]; ret ----------------------------------

GOOD_ORIGINAL = bytes.fromhex("e80b000000" "a104000000" "c3")  # rel32 to 0x10010; raw off32 = 4
GOOD_OURS = bytes.fromhex("e800000000" "a100000000" "c3")  # placeholders where we relocate
GOOD_ROW = game_row(CODE_BASE, CODE_BASE + len(GOOD_ORIGINAL))
CALL_FIELD = CODE_BASE + 1
LOAD_FIELD = CODE_BASE + 6


def le_off32(field_va: int, target_off: int, *, obj: int = 2) -> bytes:
    """One off32 LE fixup record for a field on the first code page."""
    return fixup_record(SRC_OFF32, field_va - CODE_BASE, obj, target_off, off32=True)


def call(offset: int, extern: int, *, frame: tuple[int, int | None] = FLAT_FRAME) -> bytes:
    """A self-relative fixup of our field at `offset` to extern number `extern`."""
    return fixup(offset, segment_relative=False, frame=frame, target=(2, extern))


def absolute(offset: int, extern: int, *, frame: tuple[int, int | None] = FLAT_FRAME) -> bytes:
    """A segment-relative fixup of our field at `offset` to extern number `extern`."""
    return fixup(offset, frame=frame, target=(2, extern))


def to_segment(offset: int, segment: int, *, relative: bool = False) -> bytes:
    """A fixup of our field at `offset` to one of our own segments (by SEGDEF number)."""
    return fixup(offset, segment_relative=not relative, frame=FLAT_FRAME, target=(0, segment))


def our_segment(
    data: bytes,
    fixups: Sequence[bytes] = (),
    externs: Sequence[str] = (),
    *,
    publics: Sequence[tuple[str, int]] = (("func_00010000_", 0),),
    local: str = "CONST",
) -> Segment:
    """Our `_TEXT` (SEGDEF 1) holding `data`, with a module-local data segment named `local`
    (SEGDEF 2) beside it and the FLAT group (GRPDEF 1) the fixup frames name."""
    obj = our_module(data, fixups, externs, publics=publics, local=local)
    return next(seg for seg in obj.segments if seg.name == "_TEXT")


def our_module(
    data: bytes,
    fixups: Sequence[bytes] = (),
    externs: Sequence[str] = (),
    *,
    publics: Sequence[tuple[str, int]] = (("func_00010000_", 0),),
    local: str = "CONST",
) -> Module:
    """The whole module our_segment's `_TEXT` comes from, for callers that need its publics
    (check.checked_functions)."""
    records = [
        lnames("", "_TEXT", "CODE", local, "DATA", FLAT_LNAME),
        segdef32(2, 3, len(data)),
        segdef32(4, 5, 8),
        grpdef(6),
        pubdef32(TEXT_INDEX, list(publics)),
    ]
    if externs:
        records.append(extdef(*externs))
    records.append(ledata32(TEXT_INDEX, 0, data))
    if fixups:
        records.append(fixupp32(*fixups))
    return read_object(module("unit", *records))


@dataclass(frozen=True)
class Original:
    data: bytes  # the whole synthetic EXE
    le: LE
    flat: bytes
    fixups: list[Fixup]


def original(patches: dict[int, bytes], page1: bytes = b"", page2: bytes = b"") -> Original:
    """The conftest LE image with `patches` written into its pages and the given fixup records
    on code pages 1 and 2. A patch must stay inside one page."""
    for va, blob in patches.items():
        assert (va - CODE_BASE) // PAGE_SIZE == (va + len(blob) - 1 - CODE_BASE) // PAGE_SIZE
    records = [page1, page2] + [b""] * (_PAGES - 2)
    data = build_le_image(fixups=records, patches=patches).data
    le = LE(data)
    return Original(data, le, bytes(le.load_flat(relocate=False)), le.fixups())


def table(*rows: FunctionRow) -> SymbolTable:
    return SymbolTable.build([*rows, *CALLEES], data_ranges=DATA_RANGES)


def good_segment() -> Segment:
    return our_segment(
        GOOD_OURS, [call(1, 1), absolute(6, 2)], ["func_00010010_", "_D_00020004"]
    )


def good_original() -> Original:
    return original({CODE_BASE: GOOD_ORIGINAL}, page1=le_off32(LOAD_FIELD, 0x4))
