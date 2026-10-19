"""Layout facts of the real executables (byte scan of 2026-10-19).

Skipped unless orig/UFO2P.EXE and orig/TACP.EXE exist (`uv run reverseapoc ingest`); they never
run in CI because the game files are never committed.
"""

from __future__ import annotations

import pytest

from conftest import ORIG_DIR
from reverseapoc.le import LE

UFO2P = ORIG_DIR / "UFO2P.EXE"
TACP = ORIG_DIR / "TACP.EXE"

pytestmark = pytest.mark.skipif(
    not (UFO2P.is_file() and TACP.is_file()),
    reason="orig/UFO2P.EXE and orig/TACP.EXE not present (run `uv run reverseapoc ingest`)",
)

STUB_SIZE = 0x352A4  # bound DOS/4GW Professional loader in front of the Watcom MZ stub
LE_OFFSET = 0x37F34


@pytest.fixture(scope="module")
def ufo2p() -> LE:
    return LE(UFO2P)


@pytest.fixture(scope="module")
def tacp() -> LE:
    return LE(TACP)


@pytest.fixture(params=[("ufo2p", 0xD0000), ("tacp", 0xE0000)], ids=["UFO2P", "TACP"])
def exe(request) -> tuple[LE, int]:
    name, data_base = request.param
    return request.getfixturevalue(name), data_base


def test_stub_and_header(exe):
    le, _ = exe
    assert le.stub_offset == STUB_SIZE == 217764
    assert le.le_offset == LE_OFFSET
    assert le.page_size == 4096


def test_two_objects_at_expected_bases(exe):
    le, data_base = exe
    assert len(le.objects) == 2
    code, data = le.objects
    assert code.base == 0x10000
    assert data.base == data_base
    assert code.flags & 0x4  # executable
    assert data.flags & 0x2  # writable


def test_summary_matches_attributes(exe):
    le, data_base = exe
    s = le.summary()
    assert (s["stub_size"], s["le_offset"], s["page_size"]) == (STUB_SIZE, LE_OFFSET, 4096)
    assert [o["base"] for o in s["objects"]] == [0x10000, data_base]
    assert s["fixup_count"] > 0


def test_ufo2p_entry_point(ufo2p):
    assert (ufo2p.eip_obj, ufo2p.eip) == (1, 0xB0784)
    assert ufo2p.entry_va == 0x10000 + 0xB0784


def test_tacp_entry_point(tacp):
    assert (tacp.eip_obj, tacp.eip) == (1, 0xB28B0)


def test_load_flat_covers_both_objects(exe):
    le, _ = exe
    flat = le.load_flat()
    code, data = le.objects
    assert len(flat) == data.end
    for obj in (code, data):
        first = le.pages[obj.page_index - 1]
        assert flat[obj.base : obj.base + 64] == le.data[first.file_offset : first.file_offset + 64]
        assert any(flat[obj.base : obj.base + obj.page_count * le.page_size])


def test_all_fixups_are_internal_and_inside_objects(exe):
    le, _ = exe
    fixups = le.fixups()
    assert fixups
    for fx in fixups:
        assert le.obj_of_va(fx.src_va) is not None, hex(fx.src_va)
