"""Region map, reassembly and rebuild tests against synthetic LE images (tests/conftest.py).

No game bytes: every image here is built by `build_le_image`, and the rebuild tests write only
under pytest's tmp_path.
"""

from __future__ import annotations

import pytest

from conftest import LE_HEADER_SIZE, SYNTHETIC_TRAILER, build_le_image, write_manifest
from reverseapoc import splice
from reverseapoc.le import LE, LEUnsupportedError
from reverseapoc.splice import (
    Region,
    SpliceError,
    check_tiling,
    decompose,
    layout,
    reassemble,
    rebuild,
    rebuild_target,
    region_at,
)
from reverseapoc.targets import load_manifest


def _orig(tmp_path, data: bytes, name: str = "SYNTH.EXE"):
    """An orig/ directory holding `data` as `name`, and a manifest that describes it."""
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / name).write_bytes(data)
    manifest = write_manifest(tmp_path / "m.toml", {name: data})
    return orig, manifest


# ---- Task 1: the round trip and the rebuild path ----------------------------------------------


def test_round_trip_reproduces_synthetic_le(synthetic_le):
    le = LE(synthetic_le.data)
    assert reassemble(le, decompose(le)) == synthetic_le.data


def test_rebuild_target_writes_ok_output(tmp_path, synthetic_le, monkeypatch):
    orig, manifest = _orig(tmp_path, synthetic_le.data)
    (target,) = load_manifest(manifest)
    out = tmp_path / "build"
    hashed = []
    real_hash_file = splice.hash_file

    def spy(path):
        hashed.append(path)
        return real_hash_file(path)

    monkeypatch.setattr(splice, "hash_file", spy)
    result = rebuild_target(target, orig, out)
    assert result.status == "ok"
    assert result.ok
    assert result.output == out / "SYNTH.EXE"
    assert (out / "SYNTH.EXE").read_bytes() == synthetic_le.data
    assert result.hashes.sha1 == target.sha1
    assert out / "SYNTH.EXE" in hashed  # the hash covers the file as written


def test_rebuild_is_idempotent(tmp_path, synthetic_le):
    orig, manifest = _orig(tmp_path, synthetic_le.data)
    out = tmp_path / "build"
    first = rebuild(orig, out, manifest)
    first_bytes = (out / "SYNTH.EXE").read_bytes()
    second = rebuild(orig, out, manifest)
    assert first.ok and second.ok
    assert [r.status for r in first.results] == ["ok"]
    assert [r.status for r in second.results] == ["ok"]
    assert (out / "SYNTH.EXE").read_bytes() == first_bytes == synthetic_le.data


# ---- Task 2: the region map tiles the file and labels every offset ----------------------------


def test_layout_regions_tile_the_bound_fixture(synthetic_le):
    img = synthetic_le
    regions = layout(LE(img.data))
    kinds = ["extender", "stub", "header", "loader", "fixups", "padding", "page", "page", "page"]
    assert [r.kind for r in regions] == kinds
    spans = [(r.start, r.end) for r in regions[:6]]
    assert spans == [
        (0, img.stub_offset),
        (img.stub_offset, img.le_offset),
        (img.le_offset, img.le_offset + LE_HEADER_SIZE),
        (img.le_offset + LE_HEADER_SIZE, img.fixup_start),
        (img.fixup_start, img.fixup_end),
        (img.fixup_end, img.data_pages_offset),
    ]
    assert [r.start for r in regions[6:]] == img.page_offsets
    assert regions[-1].end == len(img.data)
    check_tiling(regions, len(img.data))


def test_layout_unbound_has_no_extender():
    img = build_le_image(bound=False)
    regions = layout(LE(img.data))
    assert (regions[0].kind, regions[0].start) == ("stub", 0)
    assert "extender" not in [r.kind for r in regions]
    check_tiling(regions, len(img.data))


def test_layout_trailer_region():
    img = build_le_image(trailer=SYNTHETIC_TRAILER)
    regions = layout(LE(img.data))
    last = regions[-1]
    assert last.kind == "trailer"
    assert last.start == img.trailer_offset
    assert last.end - last.start == len(SYNTHETIC_TRAILER)
    assert last.end == len(img.data)
    check_tiling(regions, len(img.data))


def test_layout_permuted_page_map_in_file_order():
    img = build_le_image(page_numbers=(2, 1, 3))
    pages = [r for r in layout(LE(img.data)) if r.kind == "page"]
    assert [r.start for r in pages] == img.page_offsets
    assert pages[0].page.logical == 2  # physical page 1 holds logical page 2
    assert pages[1].page.logical == 1


def test_check_tiling_accepts_touching_regions():
    regions = [Region(0, 0x10, "header"), Region(0x10, 0x20, "loader")]
    check_tiling(regions, 0x20)
    with pytest.raises(SpliceError, match=r"end at 0x20\b.*0x21\b"):
        check_tiling(regions, 0x21)


def test_check_tiling_rejects_gap():
    regions = [Region(0, 0x10, "header"), Region(0x11, 0x20, "loader")]
    with pytest.raises(SpliceError, match=r"gap at 0x10\b.*header.*loader"):
        check_tiling(regions, 0x20)


def test_check_tiling_rejects_overlap():
    regions = [Region(0, 0x10, "header"), Region(0xF, 0x20, "loader")]
    with pytest.raises(SpliceError, match=r"overlap at 0xf\b.*header.*loader"):
        check_tiling(regions, 0x20)


def test_region_at_labels(synthetic_le):
    regions = layout(LE(synthetic_le.data))
    off = synthetic_le.page_offsets[0] + 0x800
    assert region_at(regions, off).describe(off) == "page 1 of object 1, VA 0x00010800"
    assert region_at(regions, off).va_at(off) == 0x10800
    header = synthetic_le.le_offset + 4
    assert region_at(regions, header).describe(header) == "LE header"
    assert region_at(regions, header).va_at(header) is None

    permuted = build_le_image(page_numbers=(2, 1, 3))
    off = permuted.page_offsets[1] + 0x10  # physical page 2 holds logical page 1
    label = region_at(layout(LE(permuted.data)), off).describe(off)
    assert label == "page 1 of object 1, VA 0x00010010 (physical page 2)"

    trailed = build_le_image(trailer=SYNTHETIC_TRAILER)
    off = trailed.trailer_offset + 3
    assert region_at(layout(LE(trailed.data)), off).describe(off) == "trailer"


def test_region_at_end_belongs_to_next_region(synthetic_le):
    regions = layout(LE(synthetic_le.data))
    for region, following in zip(regions, regions[1:], strict=False):
        assert region_at(regions, region.end) is following
        assert region_at(regions, region.start) is region
    with pytest.raises(SpliceError, match=hex(len(synthetic_le.data))):
        region_at(regions, len(synthetic_le.data))
    with pytest.raises(SpliceError):
        region_at(regions, -1)


@pytest.mark.parametrize(
    ("field", "name"),
    [
        (0x88, "non-resident name table"),
        (0x8C, "non-resident name table"),
        (0x98, "debug info"),
        (0x9C, "debug info"),
    ],
)
def test_layout_refuses_unmapped_header_table(field, name):
    le = LE(build_le_image(extra_header_fields={field: 0x10}).data)
    with pytest.raises(LEUnsupportedError, match=name):
        layout(le)


def test_layout_refuses_loader_section_mismatch():
    too_large = LE(build_le_image().data).loader_section_size + 1
    le = LE(build_le_image(extra_header_fields={0x38: too_large}).data)
    with pytest.raises(LEUnsupportedError, match="loader section"):
        layout(le)


@pytest.mark.parametrize("flag", [1, 2, 3])
def test_layout_refuses_non_physical_page(le_builder, flag):
    le = LE(le_builder(page_flags=(0, flag, 0)).data)
    with pytest.raises(LEUnsupportedError, match="page 2"):
        layout(le)


def test_layout_is_pure(synthetic_le):
    le = LE(synthetic_le.data)
    before = le.data

    def facts(regions):
        return [(r.start, r.end, r.kind, r.obj, r.page, r.va) for r in regions]

    assert facts(layout(le)) == facts(layout(le))
    assert le.data is before
    assert le.data == synthetic_le.data
