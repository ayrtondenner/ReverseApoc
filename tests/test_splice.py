"""Region map, reassembly and rebuild tests against synthetic LE images (tests/conftest.py).

No game bytes: every image here is built by `build_le_image`, and the rebuild tests write only
under pytest's tmp_path.
"""

from __future__ import annotations

import hashlib

import pytest

from conftest import (
    LE_HEADER_SIZE,
    PAGE_SIZE,
    SYNTHETIC_TRAILER,
    build_le_image,
    page_fill,
    write_manifest,
)
from reverseapoc import splice
from reverseapoc.le import LE, LEUnsupportedError
from reverseapoc.splice import (
    Region,
    SpliceError,
    assemble,
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


# ---- Task 3: rebuilt, not copied (D-16) -------------------------------------------------------
# Each test below is proven to fail against one wrong reassembly: a copy of the input, object
# images cut at vsize, or page offsets computed from the logical page number.

MARKER = 0xA5  # differs from every page_fill() value of the 3-page fixture


def test_reassemble_sources_pages_from_images():
    img = build_le_image(trailer=SYNTHETIC_TRAILER)
    le = LE(img.data)
    d = decompose(le)
    for image in d.images.values():
        image[:] = bytes([MARKER]) * len(image)
    out = reassemble(le, d)
    assert len(out) == len(img.data)
    wrong = []
    for r in d.regions:
        if r.kind == "page":
            expected = bytes([MARKER]) * (r.end - r.start)
        else:
            expected = img.data[r.start : r.end]
        if out[r.start : r.end] != expected:
            wrong.append((r.kind, hex(r.start)))
    assert wrong == []


def test_reassemble_places_pages_through_permuted_map():
    img = build_le_image(page_numbers=(2, 1, 3))
    le = LE(img.data)
    d = decompose(le)
    d.images[1][0x10] = page_fill(2) ^ 0xFF  # logical page 1 holds physical page 2's bytes
    out = reassemble(le, d)
    assert len(out) == len(img.data)
    diffs = [i for i, (a, b) in enumerate(zip(out, img.data, strict=True)) if a != b]
    assert diffs == [img.page_offsets[1] + 0x10]


def test_round_trip_keeps_page_tail_past_vsize(synthetic_le):
    # obj1: vsize 0x1800 over two pages, so VA 0x11800..0x12000 is page data past vsize
    le = LE(synthetic_le.data)
    out = reassemble(le, decompose(le))
    page2 = synthetic_le.page_offsets[1]
    assert out[page2 + 0x800 : page2 + PAGE_SIZE] == bytes([page_fill(2)]) * 0x800


ROUND_TRIP_VARIANTS = {
    "bound": {},
    "unbound": {"bound": False},
    "trailer": {"trailer": SYNTHETIC_TRAILER},
    "permuted": {"page_numbers": (2, 1, 3)},
    "contiguous": {
        "objects": [(0x2000, 0x10000, 0x2045, 1, 2), (0x3000, 0x12000, 0x2043, 3, 1)],
    },
}


@pytest.mark.parametrize(
    "options", list(ROUND_TRIP_VARIANTS.values()), ids=list(ROUND_TRIP_VARIANTS)
)
def test_round_trip_variants(options):
    data = build_le_image(**options).data
    le = LE(data)
    out = reassemble(le, decompose(le))
    assert out == data
    assert hashlib.sha1(out).hexdigest() == hashlib.sha1(data).hexdigest()


def test_assemble_accepts_pieces_in_any_order():
    assert assemble(6, [(4, b"ef"), (0, b"ab"), (2, b"cd")]) == b"abcdef"


def test_assemble_accepts_touching_pieces():
    assert assemble(4, [(0, b"ab"), (2, b"cd")]) == b"abcd"
    assert assemble(0, []) == b""


@pytest.mark.parametrize(
    ("second", "message"),
    [(0x11, r"gap .*at 0x10\b"), (0xF, r"overlapping .*at 0xf\b")],
    ids=["gap", "overlap"],
)
def test_assemble_rejects_gap_and_overlap(second, message):
    pieces = [(0, bytes(0x10)), (second, bytes(0x20 - second))]
    with pytest.raises(SpliceError, match=message):
        assemble(0x20, pieces)


def test_assemble_rejects_wrong_end():
    with pytest.raises(SpliceError, match=r"end at 0x10\b.*0x20\b"):
        assemble(0x20, [(0, bytes(0x10))])
    with pytest.raises(SpliceError, match=r"end at 0x21\b.*0x20\b"):
        assemble(0x20, [(0, bytes(0x21))])


# ---- Plan 03-03 Task 1: linear-address patches and the mismatch report -------------------------
# Patches here never hold a value the fixture pages are filled with, so a changed byte is visible.

NO_FIXUPS = [b"", b"", b""]
PATCH_BYTE = 0x5A  # no page of the 3-page fixture is filled with it


def _no_fixups(**options):
    return build_le_image(fixups=NO_FIXUPS, **options)


def _changed(a: bytes, b: bytes) -> list[int]:
    """File offsets where `a` and `b` differ (equal lengths)."""
    assert len(a) == len(b)
    return [i for i, (x, y) in enumerate(zip(a, b, strict=True)) if x != y]


def _sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def test_splice_patch_lands_at_mapped_offset():
    img = _no_fixups()
    out = splice.splice(LE(img.data), {0x10800: bytes([PATCH_BYTE])}).data
    assert len(out) == len(img.data)
    assert _changed(out, img.data) == [img.page_offsets[0] + 0x800]
    assert _sha1(out) != _sha1(img.data)


def test_splice_empty_mapping_is_round_trip(synthetic_le):
    out = splice.splice(LE(synthetic_le.data), {}).data
    assert out == synthetic_le.data
    assert _sha1(out) == _sha1(synthetic_le.data)


def _mutated_rebuild(tmp_path, patches):
    img = _no_fixups()
    orig, manifest = _orig(tmp_path, img.data)
    (target,) = load_manifest(manifest)
    return img, target, rebuild_target(target, orig, tmp_path / "build", patches=patches)


def test_rebuild_target_reports_mutation(tmp_path):
    img, target, result = _mutated_rebuild(tmp_path, {0x10800: bytes([PATCH_BYTE])})
    assert result.status == "mismatch"
    assert not result.ok
    assert result.first_diff == img.page_offsets[0] + 0x800
    assert result.first_diff_region == "page 1 of object 1, VA 0x00010800"
    assert result.first_diff_va == 0x10800
    assert result.diff_bytes == 1
    assert result.hashes.sha1 != target.sha1

    control = rebuild_target(target, tmp_path / "orig", tmp_path / "control")
    assert control.status == "ok"
    assert control.hashes.sha1 == target.sha1


def test_mutation_report_names_offset_without_bytes(tmp_path):
    img, _, result = _mutated_rebuild(tmp_path, {0x10800: bytes([PATCH_BYTE])})
    line = result.format(len(result.target.name))
    assert line.startswith("MISMATCH")
    assert f"first difference at {img.page_offsets[0] + 0x800:#x}" in line
    assert "page 1 of object 1, VA 0x00010800" in line
    assert "1 bytes differ" in line
    assert f"{PATCH_BYTE:#x}" not in line  # the patch byte
    assert f"{page_fill(1):#x}" not in line  # the original page byte


# ---- Plan 03-03 Task 2: refusals and the D-13 page edges ---------------------------------------
# Every refusal test also splices the same fixture with no patch and checks that it round-trips
# (_assert_control), so none of them can pass because splice() always fails.


def _assert_control(img) -> None:
    out = splice.splice(LE(img.data), {}).data
    assert _sha1(out) == _sha1(img.data)


def _refused(img, patches) -> str:
    with pytest.raises(SpliceError) as exc:
        splice.splice(LE(img.data), patches)
    _assert_control(img)
    return str(exc.value)


PAGE_EDGES = {
    "last-byte-of-page-1": (0x10FFF, 1, lambda p: [p[0] + 0xFFF]),
    "first-byte-of-page-2": (0x11000, 1, lambda p: [p[1]]),
    "across-the-boundary": (0x10FFE, 4, lambda p: [p[0] + 0xFFE, p[0] + 0xFFF, p[1], p[1] + 1]),
}


@pytest.mark.parametrize(("va", "n", "offsets"), list(PAGE_EDGES.values()), ids=list(PAGE_EDGES))
def test_mutation_page_edges(va, n, offsets):
    img = _no_fixups()
    out = splice.splice(LE(img.data), {va: bytes([PATCH_BYTE]) * n}).data
    assert _changed(out, img.data) == offsets(img.page_offsets)
    assert _sha1(out) != _sha1(img.data)
    _assert_control(img)


def test_mutation_spanning_permuted_map():
    img = _no_fixups(page_numbers=(2, 1, 3))
    out = splice.splice(LE(img.data), {0x10FFE: bytes([PATCH_BYTE]) * 4}).data
    p = img.page_offsets
    # logical page 1 lives in physical page 2, logical page 2 in physical page 1
    assert _changed(out, img.data) == [p[0], p[0] + 1, p[1] + 0xFFE, p[1] + 0xFFF]
    _assert_control(img)


def test_short_page_last_byte_ok():
    img = _no_fixups()
    out = splice.splice(LE(img.data), {0x201FF: bytes([PATCH_BYTE])}).data
    assert _changed(out, img.data) == [img.page_offsets[2] + 0x1FF]
    _assert_control(img)


def test_refuse_bss_past_short_page():
    message = _refused(_no_fixups(), {0x20200: bytes([PATCH_BYTE])})
    assert "0x20200" in message
    assert "BSS of object 2" in message


@pytest.mark.parametrize(("va", "n"), [(0x11800, 1), (0x117FF, 2)])
def test_refuse_past_vsize_tail(va, n):
    message = _refused(_no_fixups(), {va: bytes([PATCH_BYTE]) * n})
    assert f"patch at {va:#x}, {n} bytes" in message
    assert "0x11800 is past the end of object 1" in message


@pytest.mark.parametrize("va", [0x0FFFF, 0x30000])
def test_refuse_unmapped_va(va):
    message = _refused(_no_fixups(), {va: bytes([PATCH_BYTE])})
    assert f"{va:#x} is not in any object" in message


def test_refuse_cross_object():
    img = _no_fixups(objects=[(0x2000, 0x10000, 0x2045, 1, 2), (0x3000, 0x12000, 0x2043, 3, 1)])
    message = _refused(img, {0x11FFF: bytes([PATCH_BYTE]) * 2})
    assert "crosses from object 1 into object 2 at 0x12000" in message
    assert "patch at 0x11fff" in message


@pytest.mark.parametrize("second", [b"\x5b\x5c\x5d\x5e", b"\x5a\x5a\x5a\x5a"], ids=["diff", "same"])
def test_refuse_overlap(second):
    message = _refused(_no_fixups(), {0x10800: b"\x5a\x5a\x5a\x5a", 0x10802: second})
    assert "0x10800 (4 bytes)" in message
    assert "0x10802 (4 bytes)" in message
    assert "overlap at 0x10802" in message


def test_refuse_empty_patch():
    message = _refused(_no_fixups(), {0x10800: b""})
    assert "0x10800" in message
    assert "empty patch" in message


def test_refuse_non_bytes_patch():
    message = _refused(_no_fixups(), {0x10800: "AB"})
    assert "0x10800" in message
    assert "str" in message
    assert "AB" not in message


@pytest.mark.parametrize("key", [-1, "0x10800", True], ids=["negative", "str", "bool"])
def test_refuse_bad_va(key):
    message = _refused(_no_fixups(), {key: bytes([PATCH_BYTE])})
    assert repr(key) in message
    assert "linear address" in message


WHOLE_OBJECTS = {0x10000: bytes([PATCH_BYTE]) * 0x1800, 0x20000: bytes([PATCH_BYTE]) * 0x200}


def test_splice_keeps_file_length():
    img = _no_fixups(trailer=SYNTHETIC_TRAILER)
    assert len(splice.splice(LE(img.data), WHOLE_OBJECTS).data) == len(img.data)
    _assert_control(img)


def test_whole_object_patch():
    img = _no_fixups()
    out = splice.splice(LE(img.data), WHOLE_OBJECTS).data
    p = img.page_offsets
    assert out[p[0] : p[0] + PAGE_SIZE] == bytes([PATCH_BYTE]) * PAGE_SIZE
    assert out[p[1] : p[1] + 0x800] == bytes([PATCH_BYTE]) * 0x800
    assert out[p[1] + 0x800 : p[1] + PAGE_SIZE] == bytes([page_fill(2)]) * 0x800  # past vsize
    assert out[p[2] : p[2] + 0x200] == bytes([PATCH_BYTE]) * 0x200
    _assert_control(img)


def test_non_page_regions_untouched_by_patches():
    img = _no_fixups(trailer=SYNTHETIC_TRAILER)
    result = splice.splice(LE(img.data), WHOLE_OBJECTS)
    others = [r for r in result.regions if r.kind != "page"]
    assert others[-1].kind == "trailer"
    changed = [r.kind for r in others if result.data[r.start : r.end] != img.data[r.start : r.end]]
    assert changed == []
    _assert_control(img)


def test_splice_refuses_non_physical_page():
    img = build_le_image(page_flags=(0, 1, 0))
    with pytest.raises(LEUnsupportedError, match="page 2"):
        splice.splice(LE(img.data), {})
    _assert_control(_no_fixups())


@pytest.mark.parametrize("kind", [bytes, bytearray, memoryview])
def test_splice_accepts_bytes_like(kind):
    img = _no_fixups()
    out = splice.splice(LE(img.data), {0x10800: kind(b"\x5a\x5b")}).data
    start = img.page_offsets[0] + 0x800
    assert _changed(out, img.data) == [start, start + 1]
    assert out[start : start + 2] == b"\x5a\x5b"


def test_splice_does_not_mutate_input():
    img = _no_fixups()
    le = LE(img.data)
    value = bytearray(b"\x5a\x5b")
    splice.splice(le, {0x10800: value})
    assert value == bytearray(b"\x5a\x5b")
    assert le.data == img.data
    first = splice.splice(le, {0x10800: b"\x5a"}).data
    second = splice.splice(le, {0x10900: b"\x5a"}).data
    assert _changed(first, img.data) == [img.page_offsets[0] + 0x800]
    assert _changed(second, img.data) == [img.page_offsets[0] + 0x900]


ORDERED_PATCHES = [(0x10800, b"\x5a"), (0x10FFE, b"\x5b\x5c\x5d\x5e"), (0x20010, b"\x5f")]


def test_patch_order_independent(synthetic_le):
    le = LE(synthetic_le.data)
    forward = splice.splice(le, dict(ORDERED_PATCHES))
    backward = splice.splice(le, dict(reversed(ORDERED_PATCHES)))
    assert forward.data == backward.data
