"""Test-only synthetic EXEs and libraries for the C vs C++ scan (cppscan).

Every byte is made up. Module "inirt386" stands in for Watcom's init-routine walker: its CODE
segment holds segment-relative off32 fixups to the empty segments XIB, XIE, YIB and YIE. The EXE
plants that code in object 1 at INIT_VA, with LE off32 fixups at the same sites pointing at the
table bounds in object 2, and lays out 6-byte init entries (routine type, priority, routine
pointer) between them, each routine pointer carrying its own LE off32 fixup into object 1.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from pathlib import Path

import omfimage as om
from conftest import build_le_image, fixup_record
from libtree import OBJ1_BASE, OBJ2_BASE, body, planted, write_lib
from reverseapoc.libmatch import STATUS_UNIQUE, MatchRange

INIT_VA = 0x10300  # where the inirt386 code is planted in object 1
INIT_CODE = body(40, seed=0x61)
INIT_SITES = (4, 12, 20, 28)  # fixups to XIB, XIE, YIB, YIE, in that order
BOUND_SEGMENTS = ("XIB", "XIE", "YIB", "YIE")
DEFAULT_BOUNDS = (0x20100, 0x20112, 0x20112, 0x20118)  # XI: 3 entries, YI: 1 entry
ENTRY_SIZE = 6
ROUTINE_FIELD = 2  # offset of the routine pointer in an entry
XI_ROUTINES = (0x10400, 0x10310, 0x10500, 0x10520, 0x10540)  # 0x10310 is inside inirt386
YI_ROUTINES = (0x10600, 0x10620)
LIBRARY = "DOS/CLIB3R.LIB"


def inirt_module() -> bytes:
    """inirt386: CODE segment 1 with off32 fixups to segments 2-5 (XIB, XIE, YIB, YIE)."""
    records = [
        om.lnames("", "_TEXT", "CODE", *BOUND_SEGMENTS, "DATA"),
        om.segdef32(2, 3, len(INIT_CODE)),
        *(om.segdef32(4 + k, 8, 0) for k in range(len(BOUND_SEGMENTS))),
        om.pubdef32(1, [("__InitRtns", 0)]),
        om.ledata32(1, 0, INIT_CODE),
        om.fixupp32(*(om.fixup(site, target=(0, 2 + k)) for k, site in enumerate(INIT_SITES))),
    ]
    return om.module("inirt386", *records)


def write_init_lib(watcom: Path, version: str = "10.6", relpath: str = LIBRARY) -> Path:
    return write_lib(watcom, version, relpath, [inirt_module()])


def inirt_row(**changes) -> MatchRange:
    """The runtime-map row libmatch produces for the planted inirt386 code."""
    fields = dict(start=INIT_VA, end=INIT_VA + len(INIT_CODE), segment="_TEXT",
                  module="inirt386", libraries=(LIBRARY,), versions=("10.6",),
                  publics=("__InitRtns",), status=STATUS_UNIQUE, alternatives=())  # fmt: skip
    fields.update(changes)
    return MatchRange(**fields)


def _entries(start: int, priorities: Sequence[int], routines: Sequence[int]):
    """(patches, page-3 fixup records) for entries at `start` with these priorities."""
    patches, records = {}, b""
    for k, priority in enumerate(priorities):
        va = start + k * ENTRY_SIZE
        patches[va] = bytes([0, priority]) + struct.pack("<I", 0)
        records += fixup_record(7, va + ROUTINE_FIELD - OBJ2_BASE, 1, routines[k] - OBJ1_BASE)
    return patches, records


def init_exe(
    xi: Sequence[int] = (32, 1, 32),
    yi: Sequence[int] = (32,),
    bounds: Sequence[int] = DEFAULT_BOUNDS,
    *,
    extra_data: dict[int, bytes] | None = None,
    data_fixups: bytes = b"",
) -> bytes:
    """A synthetic LE with inirt386 planted at INIT_VA and XI/YI entries of these priorities.
    `extra_data` adds more patches; `data_fixups` more LE fixup records on page 3 (object 2)."""
    code_records = b"".join(
        fixup_record(7, INIT_VA + site - OBJ1_BASE, 2, target - OBJ2_BASE)
        for site, target in zip(INIT_SITES, bounds, strict=True)
    )
    xi_patches, xi_records = _entries(bounds[0], xi, XI_ROUTINES)
    yi_patches, yi_records = _entries(bounds[2], yi, YI_ROUTINES)
    patches = {INIT_VA: planted(INIT_CODE, INIT_SITES), **xi_patches, **yi_patches}
    patches.update(extra_data or {})
    pages = [code_records, b"", xi_records + yi_records + data_fixups]
    return build_le_image(fixups=pages, patches=patches).data
