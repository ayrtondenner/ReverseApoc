"""LE parser tests against tiny synthetic images built by tests/conftest.py."""

from __future__ import annotations

import hashlib
import json
import struct

import pytest

from conftest import (
    DEFAULT_DECODED,
    DEFAULT_FIXUPS,
    LAST_PAGE_SIZE,
    OBJECTS,
    OUTER_STUB_SIZE,
    PAGE_SIZE,
    SYNTHETIC_TRAILER,
    build_le_image,
    fixup_record,
    page_fill,
)
from reverseapoc.le import (
    LE,
    SRC_OFF32,
    Fixup,
    LEError,
    LEUnsupportedError,
    format_summary,
)


def test_finds_le_header_behind_bound_extender(synthetic_le):
    le = LE(synthetic_le.data)
    assert le.stub_offset == OUTER_STUB_SIZE
    assert le.le_offset == synthetic_le.le_offset
    assert le.data_pages_offset == synthetic_le.data_pages_offset


def test_unbound_le_uses_e_lfanew_of_first_mz(le_builder):
    img = le_builder(bound=False)
    le = LE(img.data)
    assert le.stub_offset == 0
    assert le.le_offset == img.le_offset


def test_accepts_path_str_and_bytes(synthetic_le, synthetic_le_path):
    for source in (synthetic_le_path, str(synthetic_le_path), synthetic_le.data):
        assert LE(source).le_offset == synthetic_le.le_offset
    assert LE(synthetic_le_path).path == synthetic_le_path


_MZ_E_LFARLC = 0x18  # MZ header: file offset of the relocation table (u16)
_MZ_E_LFANEW = 0x3C  # MZ header: file offset of the new-format header (u32)


@pytest.mark.parametrize("bound", [True, False])
def test_ghidra_loadable_image(bound):
    # Ghidra's LeLoader takes e_lfanew only when the first MZ has e_lfarlc == 0x40 (05-RESEARCH
    # Pitfall 5). That MZ then owns the LE header, so le.py must still read the same image.
    img = build_le_image(bound=bound, ghidra_loadable=True)
    default = build_le_image(bound=bound)
    assert struct.unpack_from("<H", img.data, _MZ_E_LFARLC)[0] == 0x40
    assert struct.unpack_from("<I", img.data, _MZ_E_LFANEW)[0] == img.le_offset
    le, ref = LE(img.data), LE(default.data)
    assert le.le_offset == img.le_offset
    assert le.objects == ref.objects
    assert le.entry_va == ref.entry_va
    assert le.data_pages_offset == img.data_pages_offset
    assert le.load_flat() == ref.load_flat()
    assert le.fixups() == ref.fixups()


def test_header_fields(synthetic_le):
    le = LE(synthetic_le.data)
    assert le.page_size == PAGE_SIZE
    assert le.last_page_size == LAST_PAGE_SIZE
    assert le.num_pages == 3
    assert (le.eip_obj, le.eip) == (1, 0x123)
    assert le.entry_va == 0x10123
    assert (le.esp_obj, le.esp) == (2, 0x3000)


def test_object_table(synthetic_le):
    le = LE(synthetic_le.data)
    got = [(o.vsize, o.base, o.flags, o.page_index, o.page_count) for o in le.objects]
    assert got == OBJECTS
    assert [o.index for o in le.objects] == [1, 2]
    assert le.objects[0].flags_text == "R-X preload big"
    assert le.objects[1].flags_text == "RW- preload big"
    assert le.obj_of_va(0x117FF).index == 1
    assert le.obj_of_va(0x11800) is None
    assert le.obj_of_va(0x22FFF).index == 2


def test_page_map(synthetic_le):
    le = LE(synthetic_le.data)
    assert [p.number for p in le.pages] == [1, 2, 3]
    assert [p.flags for p in le.pages] == [0, 0, 0]
    assert [p.file_offset for p in le.pages] == synthetic_le.page_offsets
    assert [p.size for p in le.pages] == [PAGE_SIZE, PAGE_SIZE, LAST_PAGE_SIZE]
    assert le.page_va(1) == 0x10000
    assert le.page_va(2) == 0x11000
    assert le.page_va(3) == 0x20000
    with pytest.raises(LEError):
        le.page_va(4)


def test_pages_end(synthetic_le):
    assert LE(synthetic_le.data).pages_end == synthetic_le.page_offsets[-1] + LAST_PAGE_SIZE
    trailed = build_le_image(trailer=SYNTHETIC_TRAILER)
    le = LE(trailed.data)
    assert le.pages_end == trailed.page_offsets[-1] + LAST_PAGE_SIZE == trailed.trailer_offset
    assert len(le.data) - le.pages_end == len(SYNTHETIC_TRAILER)


def test_check_loadable_is_public(le_builder):
    le = LE(le_builder(page_flags=(0, 0, 2)).data)
    le.check_loadable(le.objects[0], le.pages[0])  # physical: no error
    with pytest.raises(LEUnsupportedError, match="invalid"):
        le.check_loadable(le.objects[1], le.pages[2])


def test_header_table_fields(synthetic_le):
    le = LE(synthetic_le.data)
    names = ("nonres_name_table_offset", "nonres_name_table_length")
    names += ("debug_info_offset", "debug_info_length")
    assert [getattr(le, n) for n in names] == [0, 0, 0, 0]
    values = {0x88: 0x11, 0x8C: 0x22, 0x98: 0x33, 0x9C: 0x44}
    le = LE(build_le_image(extra_header_fields=values).data)
    assert [getattr(le, n) for n in names] == [0x11, 0x22, 0x33, 0x44]


def test_fixups_decoded_deduplicated_and_sorted(synthetic_le):
    fixups = LE(synthetic_le.data).fixups()
    assert all(isinstance(f, Fixup) for f in fixups)
    got = [(f.src_va, f.kind, f.target_va, f.target_obj, f.target_off, f.size) for f in fixups]
    assert got == DEFAULT_DECODED


def test_fixup_kind_names(synthetic_le):
    names = {f.src_va: f.kind_name for f in LE(synthetic_le.data).fixups()}
    assert names[0x10010] == "off32"
    assert names[0x10030] == "rel32"
    assert names[0x11010] == "sel16"
    assert names[0x11020] == "ptr16:32"
    assert names[0x20000] == "byte"
    assert names[0x20008] == "off16"


def test_load_flat_places_objects_at_their_base(synthetic_le):
    le = LE(synthetic_le.data)
    flat = le.load_flat()
    assert isinstance(flat, bytearray)
    assert len(flat) == 0x20000 + 0x3000
    assert flat[:0x10000] == bytes(0x10000)  # below the first object
    assert flat[0x10000:0x11000] == bytes([page_fill(1)]) * PAGE_SIZE
    assert flat[0x11000:0x11800] == bytes([page_fill(2)]) * 0x800  # cut at vsize 0x1800
    assert flat[0x11800:0x20000] == bytes(0x20000 - 0x11800)
    assert flat[0x20000:0x20200] == bytes([page_fill(3)]) * LAST_PAGE_SIZE  # short last page
    assert flat[0x20200:0x23000] == bytes(0x2E00)  # bss


def test_load_flat_relocate_patches_linear_fields(synthetic_le):
    le = LE(synthetic_le.data)
    flat = le.load_flat(relocate=True)

    def u32(va: int) -> int:
        return struct.unpack_from("<I", flat, va)[0]

    assert u32(0x10010) == 0x20100  # off32
    assert u32(0x10FFE) == 0x20040  # off32 straddling a page boundary
    assert u32(0x11040) == u32(0x11044) == 0x20200  # source list
    assert u32(0x10030) == (0x10800 - (0x10030 + 4)) & 0xFFFFFFFF  # rel32
    assert u32(0x11020) == 0x10000  # ptr16:32 offset part
    assert flat[0x11024:0x11026] == bytes([page_fill(2)]) * 2  # selector left raw
    assert flat[0x11010:0x11012] == bytes([page_fill(2)]) * 2  # sel16 left raw
    raw = le.load_flat()
    assert raw[0x10010:0x10014] == bytes([page_fill(1)]) * 4


def test_summary(synthetic_le):
    s = LE(synthetic_le.data).summary()
    assert s["le_offset"] == synthetic_le.le_offset
    assert s["stub_size"] == OUTER_STUB_SIZE
    assert s["page_size"] == PAGE_SIZE
    assert s["num_pages"] == 3
    assert s["entry"] == {"object": 1, "offset": 0x123, "linear": 0x10123}
    assert s["fixup_count"] == len(DEFAULT_DECODED)
    assert s["fixup_kinds"] == {
        "byte": 1,
        "sel16": 1,
        "off16": 1,
        "ptr16:32": 1,
        "off32": 6,
        "rel32": 1,
    }
    objects = [
        (o["index"], o["base"], o["vsize"], o["flags"], o["first_page"], o["pages"])
        for o in s["objects"]
    ]
    assert objects == [(1, 0x10000, 0x1800, 0x2045, 1, 2), (2, 0x20000, 0x3000, 0x2043, 3, 1)]
    json.dumps(s)  # must be JSON-serialisable as is


def test_format_summary_is_aligned_text(synthetic_le):
    text = format_summary(LE(synthetic_le.data).summary())
    assert "0x00010000" in text and "0x00020000" in text
    assert "R-X preload big" in text
    assert "fixups" in text and "11" in text
    assert "entry" in text and "0x00010123" in text


def test_summary_reports_trailer():
    img = build_le_image(trailer=SYNTHETIC_TRAILER)
    assert LE(img.data).summary()["trailer"] == {
        "offset": img.trailer_offset,
        "length": len(SYNTHETIC_TRAILER),
        "sha1": hashlib.sha1(SYNTHETIC_TRAILER).hexdigest(),
    }


def test_summary_trailer_absent_is_zero_length(synthetic_le):
    trailer = LE(synthetic_le.data).summary()["trailer"]
    assert trailer == {
        "offset": synthetic_le.page_offsets[-1] + LAST_PAGE_SIZE,
        "length": 0,
        "sha1": hashlib.sha1(b"").hexdigest(),
    }


def test_summary_trailer_clamped_on_truncated_file(synthetic_le):
    trailer = LE(synthetic_le.data[:-0x100]).summary()["trailer"]
    assert trailer["length"] == 0
    assert trailer["sha1"] == hashlib.sha1(b"").hexdigest()


def test_format_summary_trailer_row():
    img = build_le_image(trailer=SYNTHETIC_TRAILER)
    text = format_summary(LE(img.data).summary())
    rows = [line for line in text.splitlines() if line.startswith("trailer")]
    assert len(rows) == 1
    assert f"{len(SYNTHETIC_TRAILER)} bytes" in rows[0]
    assert f"{img.trailer_offset:#010x}" in rows[0]
    assert hashlib.sha1(SYNTHETIC_TRAILER).hexdigest() in rows[0]


def test_no_le_header():
    with pytest.raises(LEError, match="no LE header"):
        LE(b"MZ" + bytes(0x200))


def test_truncated_page_data(synthetic_le):
    le = LE(synthetic_le.data[:-0x100])
    with pytest.raises(LEError, match="truncated"):
        le.load_flat()


@pytest.mark.parametrize("flag", [1, 2, 3])
def test_non_physical_pages_fail_loudly(le_builder, flag):
    le = LE(le_builder(page_flags=(0, 0, flag)).data)
    with pytest.raises(LEUnsupportedError, match="page 3"):
        le.load_flat()


def test_iterated_page_message(le_builder):
    le = LE(le_builder(page_flags=(0, 1, 0)).data)
    with pytest.raises(LEUnsupportedError, match="iterated"):
        le.load_flat()


@pytest.mark.parametrize(
    ("target_flags", "message"),
    [(1, "imported ordinal"), (2, "imported name"), (3, "entry table")],
)
def test_import_and_entry_fixups_fail_loudly(le_builder, target_flags, message):
    bad = bytes([SRC_OFF32, target_flags, 0x10, 0x00, 0x01, 0x05, 0x00])
    fixups = [DEFAULT_FIXUPS[0] + bad, DEFAULT_FIXUPS[1], DEFAULT_FIXUPS[2]]
    le = LE(le_builder(fixups=fixups).data)
    with pytest.raises(LEUnsupportedError, match=message):
        le.fixups()


def test_additive_fixup_fails_loudly(le_builder):
    fixups = [fixup_record(7, 0x10, 2, 0x100, flags=0x04), DEFAULT_FIXUPS[1], DEFAULT_FIXUPS[2]]
    with pytest.raises(LEUnsupportedError, match="additive"):
        LE(le_builder(fixups=fixups).data).fixups()


def test_unknown_source_type_fails_loudly(le_builder):
    fixups = [fixup_record(4, 0x10, 2, 0x100), DEFAULT_FIXUPS[1], DEFAULT_FIXUPS[2]]
    with pytest.raises(LEUnsupportedError, match="source type 0x4"):
        LE(le_builder(fixups=fixups).data).fixups()


def test_conflicting_duplicate_fixups_fail(le_builder):
    fixups = [
        fixup_record(7, 0xFFE, 2, 0x40),
        fixup_record(7, -2, 2, 0x44),  # same field, different target
        DEFAULT_FIXUPS[2],
    ]
    with pytest.raises(LEError, match="conflicting fixups"):
        LE(le_builder(fixups=fixups).data).fixups()


def test_fixup_overrunning_its_page_table_entry_fails(le_builder):
    # one byte short: the last record cannot be decoded inside the range the page table gives
    fixups = [DEFAULT_FIXUPS[0][:-1], DEFAULT_FIXUPS[1], DEFAULT_FIXUPS[2]]
    with pytest.raises(LEError, match="overruns"):
        LE(le_builder(fixups=fixups).data).fixups()


# ---- WR-08: a last page larger than the page size is refused when the header is read ----------

OVERSIZED_LAST_PAGE = 0x1400  # larger than PAGE_SIZE


def oversized_last_page_image(**options) -> bytes:
    """The fixture with last_page_size = OVERSIZED_LAST_PAGE, padded so the last page's bytes are
    all in the file: the header field is then the only thing wrong with it."""
    img = build_le_image(extra_header_fields={0x2C: OVERSIZED_LAST_PAGE}, **options)
    pad = bytes(OVERSIZED_LAST_PAGE - LAST_PAGE_SIZE)
    return img.data[: img.trailer_offset] + pad + img.data[img.trailer_offset :]


@pytest.mark.parametrize("options", [{}, {"page_numbers": (3, 2, 1)}], ids=["last", "permuted"])
def test_last_page_larger_than_page_size_is_refused(options):
    with pytest.raises(LEError, match=r"0x2c \(last page size\) is 0x1400.*page size 0x1000"):
        LE(oversized_last_page_image(**options))


def test_last_page_as_large_as_a_page_is_accepted():
    img = build_le_image(extra_header_fields={0x2C: PAGE_SIZE})
    data = img.data + bytes(PAGE_SIZE - LAST_PAGE_SIZE)
    le = LE(data)
    assert le.pages[-1].size == PAGE_SIZE
    assert le.pages_end == len(data)


def test_last_page_size_is_not_checked_without_pages():
    # With no pages the field describes no page, so it is not refused.
    img = build_le_image(
        fixups=[],
        page_flags=(),
        objects=[(0x100, 0x10000, 0x2045, 1, 0), (0x3000, 0x20000, 0x2043, 1, 0)],
        extra_header_fields={0x2C: OVERSIZED_LAST_PAGE},
    )
    le = LE(img.data)
    assert le.pages == []
    assert le.pages_end == le.data_pages_offset
