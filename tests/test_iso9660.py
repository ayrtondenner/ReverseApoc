"""Stdlib ISO9660 reader, exercised on synthetic images."""

from __future__ import annotations

import io
import os
import struct
from datetime import UTC, datetime

import pytest

from isoimage import SECTOR, build_iso, record_offset
from reverseapoc.iso9660 import ISO9660, ISOError, clean_name, extract_all

TREE = {
    "README.": b"hello",
    "BINNT/WCC386.EXE": b"MZ" + b"\x01" * 100,
    "BINNT/SUB/DEEP.TXT": b"deep",
    "H/WATCOM.H": b"#define X 1\n",
}


def open_image(image: bytes) -> ISO9660:
    return ISO9660(io.BytesIO(image))


def test_volume_id():
    assert open_image(build_iso(TREE, volume_id="WATCOM_C")).volume_id == "WATCOM_C"


def test_missing_cd001_is_rejected():
    image = bytearray(build_iso(TREE))
    image[16 * SECTOR + 1 : 16 * SECTOR + 6] = b"XXXXX"
    with pytest.raises(ISOError, match="CD001"):
        open_image(bytes(image))


def test_block_size_other_than_2048_is_rejected():
    image = bytearray(build_iso(TREE))
    image[16 * SECTOR + 128 : 16 * SECTOR + 130] = struct.pack("<H", 512)
    with pytest.raises(ISOError, match="block size"):
        open_image(bytes(image))


def test_walk_is_depth_first_parents_first_and_cleans_names():
    entries = list(open_image(build_iso(TREE)).walk())
    assert [(e.path, e.is_dir) for e in entries] == [
        ("BINNT", True),
        ("BINNT/SUB", True),
        ("BINNT/SUB/DEEP.TXT", False),
        ("BINNT/WCC386.EXE", False),
        ("H", True),
        ("H/WATCOM.H", False),
        ("README", False),
    ]
    assert {e.path: e.size for e in entries}["BINNT/WCC386.EXE"] == 102


def test_directory_spanning_several_sectors_walks_completely():
    tree = {f"BIG/FILE{i:03d}.DAT": bytes([i]) for i in range(60)}
    iso = open_image(build_iso(tree))
    assert iso.find("BIG").size == 2 * SECTOR  # 60 records of 46 bytes do not fit in one sector
    assert [e.path for e in iso.walk() if not e.is_dir] == sorted(tree)


@pytest.mark.parametrize("size", [0, 1, 2048, 5000])
def test_files_copy_byte_exact(size):
    data = bytes(i % 251 for i in range(size))
    iso = open_image(build_iso({"D/F.BIN": data, "G.BIN": b"other"}))
    out = io.BytesIO()
    iso.copy_to(iso.find("D/F.BIN"), out, chunk=700)
    assert out.getvalue() == data


def test_find_is_exact_case_and_raises_when_absent():
    iso = open_image(build_iso(TREE))
    assert iso.find("BINNT").is_dir
    with pytest.raises(ISOError, match="not found"):
        iso.find("binnt/wcc386.exe")


def test_mtime_is_an_aware_datetime():
    when = datetime(1996, 2, 29, 7, 6, 5, tzinfo=UTC)
    (entry,) = open_image(build_iso({"A.TXT": b"x"}, mtime=when)).walk()
    assert entry.mtime == when
    assert entry.mtime.tzinfo is not None


def test_all_zero_date_means_unknown():
    image = bytearray(build_iso({"A.TXT": b"x"}))
    off = record_offset(bytes(image), b"A.TXT;1")
    image[off + 18 : off + 25] = bytes(7)
    (entry,) = open_image(bytes(image)).walk()
    assert entry.mtime is None


@pytest.mark.parametrize(
    "raw",
    [b"", b".", b"..", b"A/B", b"A\\B", b"C:X", b"A\x00B", b"CON", b"con.txt", b"NUL;1",
     b"COM1.EXE", b"LPT9", b"AUX.", b"PRN.H.BAK"],
)  # fmt: skip
def test_clean_name_rejects_unsafe_names(raw):
    with pytest.raises(ISOError):
        clean_name(raw)


@pytest.mark.parametrize(
    ("raw", "clean"),
    [(b"WCC386.EXE;1", "WCC386.EXE"), (b"README.;1", "README"), (b"DIR", "DIR"),
     (b"COM10.EXE", "COM10.EXE"), (b"CONSOLE.H;1", "CONSOLE.H")],
)  # fmt: skip
def test_clean_name_accepts_ordinary_names(raw, clean):
    assert clean_name(raw) == clean


def test_extract_all_writes_tree_and_timestamps(tmp_path):
    when = datetime(1996, 2, 29, 7, 6, tzinfo=UTC)
    iso_path = tmp_path / "w.iso"
    iso_path.write_bytes(build_iso(TREE, mtime=when))
    dest = tmp_path / "out"

    entries = extract_all(iso_path, dest)

    assert len(entries) == 7
    for path, data in TREE.items():
        assert (dest / path.rstrip(".")).read_bytes() == data
    assert (dest / "BINNT" / "SUB").is_dir()
    for target in ("README", "BINNT", "BINNT/SUB/DEEP.TXT"):
        assert int((dest / target).stat().st_mtime) == int(when.timestamp())


def test_extract_all_can_skip_timestamps(tmp_path):
    iso_path = tmp_path / "w.iso"
    iso_path.write_bytes(build_iso({"A.TXT": b"x"}))
    extract_all(iso_path, tmp_path / "out", timestamps=False)
    stamp = (tmp_path / "out" / "A.TXT").stat().st_mtime
    assert stamp > datetime(2000, 1, 1).timestamp()  # not the 1996 on-disc date


def test_extract_all_refuses_traversal_name(tmp_path):
    iso_path = tmp_path / "evil.iso"
    iso_path.write_bytes(build_iso({"A.TXT": b"x"}, raw_names={"A.TXT": b"..;1"}))
    dest = tmp_path / "out"
    with pytest.raises(ISOError):
        extract_all(iso_path, dest)
    assert not (tmp_path / "A.TXT").exists()
    assert not os.path.lexists(tmp_path / "..;1")


def test_self_referencing_directory_is_rejected():
    image = bytearray(build_iso({"SUB/A.TXT": b"x"}))
    off = record_offset(bytes(image), b"SUB")
    image[off + 2 : off + 6] = struct.pack("<I", 18)  # SUB now points back at the root extent
    with pytest.raises(ISOError, match="loop"):
        list(open_image(bytes(image)).walk())


def test_truncated_image_is_rejected():
    image = build_iso({"A.BIN": bytes(5000)})
    iso = open_image(image[: -2 * SECTOR])
    with pytest.raises(ISOError, match="truncated"):
        list(iso.walk())


def test_multi_extent_file_is_rejected():
    image = bytearray(build_iso({"A.BIN": b"x"}))
    off = record_offset(bytes(image), b"A.BIN;1")
    image[off + 25] |= 0x80
    with pytest.raises(ISOError, match="multi-extent"):
        list(open_image(bytes(image)).walk())
