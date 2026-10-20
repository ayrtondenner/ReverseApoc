"""Round trip, control mutation and fixup masking on the real executables.

These tests run only where orig/NAME exists (conftest.ORIG_DIR, or the REVERSEAPOC_ORIG override
pointing at a main checkout's orig/); each manifest target skips on its own when its file is
absent, and they never run in CI because the game files are never committed. They write only
under tmp_path, never to orig/ or build/. They assert on offsets, VAs, counts, booleans and
filecmp results, never on byte slices of the real files, so a failure never prints game bytes:
a mismatch shows up as a list of failing VAs.

The expected SHA-1 of each file is read through load_manifest() (D-15); no hash is copied here.
"""

from __future__ import annotations

import filecmp
import hashlib
from bisect import bisect_left, bisect_right
from collections import Counter

import pytest

from conftest import ORIG_DIR
from reverseapoc.le import (
    LE,
    PAGE_PHYSICAL,
    SRC_OFF32,
    SRC_PTR1632,
    SRC_REL32,
    SRC_SEL16,
    SRC_SIZE,
    Fixup,
    LEObject,
)
from reverseapoc.splice import (
    REGION_PADDING,
    REGION_TRAILER,
    check_tiling,
    layout,
    rebuild_target,
    splice,
)
from reverseapoc.targets import load_manifest

TARGETS = load_manifest()
PARAMS = [
    pytest.param(
        target,
        id=target.name,
        marks=pytest.mark.skipif(
            not (ORIG_DIR / target.name).is_file(),
            reason=f"orig/{target.name} not present (run uv run reverseapoc ingest)",
        ),
    )
    for target in TARGETS
]
MAX_FIELD = max(SRC_SIZE.values())

# Measured layout facts per target, as spikes 001 (pages and fixups) and 002 (region tiling)
# confirmed them with an independent raw reader, and spike 003 the trailer (D-10): offsets,
# lengths and counts only. "trailer" is (offset, length), or None when the pages run to EOF.
FACTS = {
    "UFO2P.EXE": {
        "pages": 303,
        "extender_end": 0x352A4,
        "data_pages": 0x724A4,
        "padding": 362,
        "obj1_tail_past_vsize": 0x523,
        "trailer": (0x1A0723, 27),
        "straddlers": (
            0x1EFFD, 0x28FFD, 0x36FFE, 0x62FFF, 0x67FFE, 0x6AFFE, 0x7FFFF,
            0x98FFF, 0x9FFFF, 0xA3FFE, 0xB0FFD, 0xB4FFF, 0xC6FFD, 0xC8FFF,
        ),
        "cut_fields": ((0x13E27C, 3),),
        "kinds": {SRC_OFF32: 28_183, SRC_SEL16: 10, SRC_PTR1632: 4, SRC_REL32: 0},
    },
    "TACP.EXE": {
        "pages": 666,
        "extender_end": 0x352A4,
        "data_pages": 0x6A8A4,
        "padding": 403,
        "obj1_tail_past_vsize": 0xAB1,
        "trailer": (0x303DDF, 27),
        "straddlers": (
            0x39FFD, 0x3BFFF, 0x42FFD, 0x43FFE, 0x52FFD, 0x6DFFE,
            0x89FFD, 0x8AFFF, 0x9EFFD, 0xA8FFD, 0xB8FFD,
        ),
        "cut_fields": ((0x2B6538, 3),),
        "kinds": {SRC_OFF32: 24_424, SRC_SEL16: 10, SRC_PTR1632: 4, SRC_REL32: 0},
    },
    "SMKP.EXE": {
        "pages": 21,
        "extender_end": 0x26654,
        "data_pages": 0x2D454,
        "padding": 223,
        "obj1_tail_past_vsize": 0xC80,
        "trailer": None,
        "straddlers": (0x11FFD, 0x1CFFE),
        "cut_fields": ((0x32FF6, 2),),
        "kinds": {SRC_OFF32: 2_297, SRC_SEL16: 0, SRC_PTR1632: 0, SRC_REL32: 0},
    },
}


@pytest.fixture(scope="module", params=PARAMS)
def real(request):
    """(target, LE) for one manifest target, parsed once per module."""
    target = request.param
    return target, LE(ORIG_DIR / target.name)


# ---- helpers ------------------------------------------------------------------------------------


def _object(le: LE, va: int) -> LEObject:
    obj = le.obj_of_va(va)
    assert obj is not None, f"{va:#x} is in no object"
    return obj


def _page_offset(le: LE, obj: LEObject, va: int) -> int:
    """File offset of linear address `va` in a page of `obj` (also past its vsize), through
    the object's page and LEPage.file_offset, never recomputed from the logical number."""
    k, rest = divmod(va - obj.base, le.page_size)
    return le.pages[obj.page_index + k - 1].file_offset + rest


def _file_offset(le: LE, va: int) -> int:
    """File offset of linear address `va` inside an object."""
    return _page_offset(le, _object(le, va), va)


def _page_backed_end(le: LE, obj: LEObject) -> int:
    """Linear address just past the last byte of `obj` that a page in the file backs."""
    if obj.page_count == 0:
        return obj.base
    last = le.pages[obj.page_index + obj.page_count - 2]
    return obj.base + (obj.page_count - 1) * le.page_size + last.size


def _covered(fixups: list[Fixup], srcs: list[int], va: int) -> bool:
    """Whether some fixup field (sorted by src_va, `srcs` their addresses) covers `va`."""
    lo, hi = bisect_left(srcs, va - MAX_FIELD + 1), bisect_right(srcs, va)
    return any(fx.src_va + fx.size > va for fx in fixups[lo:hi])


def _backed_end(le: LE, fx: Fixup) -> int:
    return min(fx.src_va + fx.size, _page_backed_end(le, _object(le, fx.src_va)))


def _straddles(le: LE, fx: Fixup) -> bool:
    """The first and last page-backed byte of the field lie in different pages."""
    base = _object(le, fx.src_va).base
    first = (fx.src_va - base) // le.page_size
    last = (_backed_end(le, fx) - 1 - base) // le.page_size
    return first != last


def _straddlers(le: LE) -> tuple[int, ...]:
    """Source VAs of every fixup field whose page-backed bytes cross a page boundary."""
    return tuple(fx.src_va for fx in le.fixups() if _straddles(le, fx))


def _cut_fields(le: LE) -> tuple[tuple[int, int], ...]:
    """(source VA, backed bytes) of every field that runs past its object's page data."""
    return tuple(
        (fx.src_va, _backed_end(le, fx) - fx.src_va)
        for fx in le.fixups()
        if _backed_end(le, fx) < fx.src_va + fx.size
    )


def _inverted(le: LE, va: int, length: int) -> bytes:
    """A patch for [va, va + length) whose every byte differs from the original."""
    return bytes(le.data[_file_offset(le, a)] ^ 0xFF for a in range(va, va + length))


def _changed(le: LE, out: bytes, start: int, end: int) -> list[str]:
    """VAs in [start, end) whose byte in `out` differs from the original file."""
    offsets = ((a, _file_offset(le, a)) for a in range(start, end))
    return [f"{a:#x}" for a, off in offsets if out[off] != le.data[off]]


def _fixup_index(le: LE) -> tuple[list[Fixup], list[int]]:
    fixups = le.fixups()
    return fixups, [fx.src_va for fx in fixups]


# ---- round trip ---------------------------------------------------------------------------------


def test_layout_tiles_real_file(real):
    _, le = real
    regions = layout(le)
    check_tiling(regions, len(le.data))
    has_trailer = any(r.kind == REGION_TRAILER for r in regions)
    assert has_trailer == (le.pages_end < len(le.data))


def test_every_manifest_target_round_trips(real):
    target, le = real
    assert hashlib.sha1(splice(le, {}).data).hexdigest() == target.sha1


def test_rebuild_writes_identical_file(real, tmp_path):
    target, _ = real
    result = rebuild_target(target, ORIG_DIR, tmp_path)
    assert result.status == "ok"
    assert filecmp.cmp(tmp_path / target.name, ORIG_DIR / target.name, shallow=False)


# ---- control mutation (D-13) --------------------------------------------------------------------


def _control_va(le: LE) -> int:
    """A mid-page address of object 1's middle page that no fixup field covers."""
    obj = le.objects[0]
    fixups, srcs = _fixup_index(le)
    va = obj.base + (obj.page_count // 2) * le.page_size + le.page_size // 2
    while _covered(fixups, srcs, va):
        va += 1
    return va


def test_control_mutation_is_reported(real, tmp_path):
    target, le = real
    obj = le.objects[0]
    va = _control_va(le)
    k = (va - obj.base) // le.page_size
    page = le.pages[obj.page_index + k - 1]
    page_va = obj.base + k * le.page_size
    assert page_va <= va < page_va + page.size

    patches = {va: _inverted(le, va, 1)}
    result = rebuild_target(target, ORIG_DIR, tmp_path / "patched", patches=patches)
    assert result.status == "mismatch"
    assert result.first_diff == page.file_offset + (va - page_va)
    assert result.first_diff_va == va
    assert result.first_diff_region.startswith(f"page {page.logical} of object 1")
    assert (result.diff_bytes, result.masked_fields) == (1, 0)

    assert rebuild_target(target, ORIG_DIR, tmp_path / "plain").status == "ok"


# ---- fixup masking (D-02) -----------------------------------------------------------------------


def test_straddling_fields_are_masked(real):
    _, le = real
    straddlers = [fx for fx in le.fixups() if _straddles(le, fx)]
    if not straddlers:
        pytest.skip(f"{real[0].name} has no page-straddling fixup field")
    patches = {fx.src_va - 1: _inverted(le, fx.src_va - 1, fx.size + 2) for fx in straddlers}

    result = splice(le, patches)

    kept = [_changed(le, result.data, fx.src_va, fx.src_va + fx.size) for fx in straddlers]
    assert [vas for vas in kept if vas] == []
    reported = {m.fixup.src_va for m in result.masked if m.straddles_page}
    assert [f"{fx.src_va:#x}" for fx in straddlers if fx.src_va not in reported] == []
    # The bytes either side of each field were written unless another field covers them.
    fixups, srcs = _fixup_index(le)
    edges = [a for fx in straddlers for a in (fx.src_va - 1, fx.src_va + fx.size)]
    free = [a for a in edges if not _covered(fixups, srcs, a)]
    assert free
    assert [f"{a:#x}" for a in free if not _changed(le, result.data, a, a + 1)] == []


def test_fields_cut_by_page_data_are_clipped(real):
    _, le = real
    cut = [fx for fx in le.fixups() if _backed_end(le, fx) < fx.src_va + fx.size]
    if not cut:
        pytest.skip(f"{real[0].name} has no fixup field cut by the end of page data")
    for fx in cut:
        obj = _object(le, fx.src_va)
        start = fx.src_va - 2
        end = min(_page_backed_end(le, obj), obj.end)
        result = splice(le, {start: _inverted(le, start, end - start)})

        assert _changed(le, result.data, fx.src_va, _backed_end(le, fx)) == []
        field = next((m for m in result.masked if m.fixup == fx), None)
        assert field is not None, f"{fx.src_va:#x} not reported as masked"
        assert field.clipped
        assert field.backed_end == _backed_end(le, fx)


# ---- measured facts (RT-05) ---------------------------------------------------------------------


def _region(le: LE, kind: str) -> tuple[int, int] | None:
    """(start, length) of the region of `kind`, or None when the file has none."""
    r = next((r for r in layout(le) if r.kind == kind), None)
    return None if r is None else (r.start, r.end - r.start)


def _obj1_tail(le: LE) -> list[int]:
    """File offsets of object 1's page bytes past its vsize."""
    obj = le.objects[0]
    return [_page_offset(le, obj, va) for va in range(obj.end, _page_backed_end(le, obj))]


def test_measured_facts(real):
    target, le = real
    facts = FACTS[target.name]

    assert len(le.pages) == facts["pages"]
    assert [p.logical for p in le.pages if p.flags != PAGE_PHYSICAL] == []
    assert [p.logical for p in le.pages if p.number != p.logical] == []
    assert (le.stub_offset, le.data_pages_offset) == (facts["extender_end"], facts["data_pages"])

    start, length = _region(le, REGION_PADDING)
    assert length == facts["padding"]
    assert not any(le.data[start : start + length])  # all-zero padding, as a boolean
    tail = _obj1_tail(le)
    assert len(tail) == facts["obj1_tail_past_vsize"]
    assert not any(le.data[off] for off in tail)

    assert _region(le, REGION_TRAILER) == facts["trailer"]
    trailer = le.summary()["trailer"]
    assert (trailer["offset"], trailer["length"]) == (facts["trailer"] or (le.pages_end, 0))

    assert _straddlers(le) == facts["straddlers"]
    assert _cut_fields(le) == facts["cut_fields"]
    kinds = Counter(fx.kind for fx in le.fixups())
    assert {kind: kinds[kind] for kind in facts["kinds"]} == facts["kinds"]
