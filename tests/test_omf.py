"""OMF object and LIB reader, checked against synthetic records built in tests/omfimage.py."""

from __future__ import annotations

import pytest

from omfimage import extdef, ledata32, library, lnames, module, pubdef32, record, segdef32, theadr
from reverseapoc.omf import (
    ModuleFailure,
    OMFError,
    Public,
    is_omf_library,
    read_library,
    read_object,
)

CODE8 = bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88])


def text_module(module_name: str = "m", *extra: bytes, length: int = 8) -> bytes:
    """A module with one 32-bit _TEXT/CODE segment of `length` bytes and two publics."""
    return module(
        module_name,
        lnames("", "_TEXT", "CODE"),
        segdef32(2, 3, length),
        pubdef32(1, [("f_", 0), ("g_", 4)]),
        *extra,
    )


def test_read_object_segments_and_publics():
    mod = read_object(text_module("m", ledata32(1, 0, CODE8)))
    assert mod.name == "m"
    assert mod.offset == 0
    [seg] = mod.segments
    assert (seg.index, seg.name, seg.class_name, seg.length) == (1, "_TEXT", "CODE", 8)
    assert seg.use32
    assert seg.data == CODE8
    assert seg.is_code
    assert list(mod.publics) == [Public("f_", 1, 0), Public("g_", 1, 4)]


def test_externs_are_kept_in_order():
    mod = read_object(text_module("m", extdef("puts_", "exit_")))
    assert mod.externs == ("puts_", "exit_")


def test_two_ledata_records_fill_one_segment():
    mod = read_object(text_module("m", ledata32(1, 0, CODE8[:4]), ledata32(1, 4, CODE8[4:])))
    assert mod.segments[0].data == CODE8


def test_gap_stays_zero_filled_up_to_segdef_length():
    mod = read_object(text_module("m", ledata32(1, 2, b"\x99\x98"), length=8))
    assert mod.segments[0].data == b"\x00\x00\x99\x98\x00\x00\x00\x00"


def test_ledata_past_segdef_length_raises():
    with pytest.raises(OMFError, match="LEDATA32"):
        read_object(text_module("m", ledata32(1, 6, b"\x01\x02\x03"), length=8))


def test_read_library_walks_page_aligned_modules():
    mods = [text_module(n, ledata32(1, 0, CODE8)) for n in ("m1", "m2", "m3")]
    lib = read_library(library(mods, page_size=16), path="SYN.LIB")
    assert lib.path == "SYN.LIB"
    assert lib.page_size == 16
    assert [m.name for m in lib.modules] == ["m1", "m2", "m3"]
    assert all(m.offset % 16 == 0 for m in lib.modules)
    assert lib.modules[0].offset == 16
    assert lib.failures == ()


def test_read_library_page_size_512():
    mods = [text_module(n, ledata32(1, 0, CODE8)) for n in ("m1", "m2")]
    lib = read_library(library(mods, page_size=512))
    assert lib.page_size == 512
    assert [m.offset for m in lib.modules] == [512, 1024]


def test_library_end_record_stops_walk():
    data = library([text_module("m1")]) + text_module("after_end") + b"\xa5" * 32
    lib = read_library(data)
    assert [m.name for m in lib.modules] == ["m1"]


def test_truncated_record_raises():
    data = theadr("m") + bytes([0x96, 0x20, 0x00, 0x01])  # LNAMES claims 0x20 bytes
    with pytest.raises(OMFError, match=r"\b0x6\b"):
        read_object(data)


def test_missing_modend_raises():
    with pytest.raises(OMFError, match="MODEND"):
        read_object(theadr("m") + lnames("", "_TEXT"))


def test_bad_module_is_recorded_not_dropped():
    bad = module(
        "bad", lnames("", "_TEXT", "CODE"), segdef32(2, 3, 8), pubdef32(5, [("h_", 0)])
    )
    mods = [text_module("m1"), bad, text_module("m3")]
    data = library(mods, page_size=16)
    lib = read_library(data)
    assert [m.name for m in lib.modules] == ["m1", "m3"]
    bad_offset = 16 + len(mods[0]) + (-len(mods[0]) % 16)
    [failure] = lib.failures
    assert isinstance(failure, ModuleFailure)
    assert (failure.index, failure.offset) == (2, bad_offset)
    assert "PUBDEF32" in failure.message


def test_is_omf_library():
    assert is_omf_library(library([text_module("m1")]))
    assert not is_omf_library(b"!<arch>\n" + b"\x00" * 60)
    assert not is_omf_library(b"")


def test_unknown_records_are_skipped_by_length():
    mod = read_object(text_module("m", record(0x7E, b"\x01\x02\x03"), ledata32(1, 0, CODE8)))
    assert mod.segments[0].data == CODE8
