"""OMF object and LIB reader, checked against synthetic records built in tests/omfimage.py."""

from __future__ import annotations

import hashlib

import pytest

from omfimage import (
    bakpat32,
    cextdef,
    comdat32,
    comdef,
    coment,
    extdef,
    fixup,
    fixupp16,
    fixupp32,
    grpdef,
    ledata16,
    ledata32,
    library,
    lidata16,
    lidata32,
    lidata_blocks32,
    lnames,
    module,
    pubdef16,
    pubdef32,
    record,
    segdef16,
    segdef32,
    segdef_easy,
    theadr,
    thread,
)
from reverseapoc import omf
from reverseapoc.omf import (
    ModuleFailure,
    OMFError,
    OMFFixup,
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


# --- FIXUPP, LIDATA, Easy OMF, BAKPAT, COMENT and GRPDEF ---

NAMES = lnames("", "_TEXT", "CODE", "_DATA", "DATA", "DGROUP")  # indexes 1..6


def two_segment_module(*records: bytes) -> bytes:
    """_TEXT (segment 1) and _DATA (segment 2), DGROUP = {_DATA}, one extern "puts_"."""
    return module(
        "fx",
        NAMES,
        segdef32(2, 3, 0x40),
        segdef32(4, 5, 0x40),
        grpdef(6, 2),
        extdef("puts_"),
        *records,
    )


def only_fixup(*records: bytes) -> OMFFixup:
    [fx] = read_object(two_segment_module(*records)).segments[0].fixups
    return fx


def test_fixup_offset32_segment_relative():
    mod = read_object(
        two_segment_module(
            ledata32(1, 0x10, bytes(8)),
            fixupp32(fixup(2, frame=(1, 1), target=(0, 2), displacement=0x20)),
        )
    )
    text = mod.segments[0]
    assert text.fixups == (
        OMFFixup(
            offset=0x12,
            size=4,
            segment_relative=True,
            location=9,
            frame_method=1,
            target_method=0,
            target_kind="segment",
            target_index=2,
            target_name="_DATA",
            displacement=0x20,
        ),
    )
    assert text.mask == frozenset(range(0x12, 0x16))


def test_fixup_self_relative_extern():
    fx = only_fixup(
        ledata32(1, 0x10, bytes(8)), fixupp32(fixup(4, segment_relative=False, target=(2, 1)))
    )
    assert fx.offset == 0x14
    assert (fx.target_kind, fx.target_index, fx.target_name) == ("extern", 1, "puts_")
    assert not fx.segment_relative
    assert (fx.target_method, fx.displacement) == (6, 0)  # P bit set: no displacement


def test_fixup_threads():
    fx = only_fixup(
        ledata32(1, 0, bytes(8)),
        fixupp32(
            thread("target", 0, 2, 1),
            thread("frame", 1, 5),
            fixup(0, frame=("thread", 1), target=("thread", 0)),
        ),
    )
    assert (fx.target_kind, fx.target_name, fx.frame_method, fx.target_method) == (
        "extern",
        "puts_",
        5,
        6,
    )


def test_fixup_threads_persist_across_records():
    fx = only_fixup(
        fixupp32(thread("target", 3, 0, 2)),
        ledata32(1, 0, bytes(8)),
        fixupp32(fixup(4, target=("thread", 3), displacement=0x30)),
    )
    assert (fx.target_kind, fx.target_name, fx.target_method, fx.displacement) == (
        "segment",
        "_DATA",
        0,
        0x30,
    )


def test_fixup_undefined_thread_raises():
    with pytest.raises(OMFError, match="thread"):
        read_object(
            two_segment_module(ledata32(1, 0, bytes(8)), fixupp32(fixup(0, target=("thread", 2))))
        )


def test_fixup_without_data_record_raises():
    with pytest.raises(OMFError, match="FIXUPP32"):
        read_object(two_segment_module(fixupp32(fixup(0, target=(0, 1), displacement=0))))


def test_fixup_extern_index_counts_comdef_and_cextdef():
    mod = read_object(
        module(
            "ext",
            lnames("", "_TEXT", "CODE", "c_"),
            segdef32(2, 3, 0x10),
            extdef("a_"),
            comdef(("b_", 4)),
            cextdef(4),
            ledata32(1, 0, bytes(8)),
            fixupp32(fixup(0, target=(2, 3), displacement=0)),
        )
    )
    assert mod.externs == ("a_", "b_", "c_")
    assert mod.segments[0].fixups[0].target_name == "c_"


@pytest.mark.parametrize(
    ("location", "size"),
    [(0, 1), (1, 2), (2, 2), (3, 4), (4, 1), (5, 2), (9, 4), (11, 6), (13, 4)],
)
def test_location_sizes(location: int, size: int):
    fx = only_fixup(
        ledata32(1, 0, bytes(8)),
        fixupp32(fixup(0, location=location, target=(0, 2), displacement=0)),
    )
    assert (fx.location, fx.size) == (location, size)


def test_unknown_location_type_raises():
    with pytest.raises(OMFError, match="location type 6"):
        read_object(
            two_segment_module(
                ledata32(1, 0, bytes(8)),
                fixupp32(fixup(0, location=6, target=(0, 2), displacement=0)),
            )
        )


def test_lidata_expands_repeated_content():
    mod = read_object(two_segment_module(lidata32(2, 0, [(3, b"ab")])))
    assert mod.segments[1].data[:7] == b"ababab\x00"


def test_lidata_expands_nested_blocks():
    mod = read_object(two_segment_module(lidata32(2, 4, [(2, [(2, b"x"), (1, b"yz")])])))
    assert mod.segments[1].data[4:12] == b"xxyzxxyz"


def test_lidata_past_segdef_length_raises():
    with pytest.raises(OMFError, match="LIDATA32"):
        read_object(two_segment_module(lidata32(2, 0x3E, [(2, b"ab")])))


def test_lidata_huge_repeat_raises_without_expanding():
    with pytest.raises(OMFError, match="LIDATA32"):
        read_object(two_segment_module(lidata32(2, 0, [(0xFFFFFFFF, [(0xFFFFFFFF, b"ab")])])))


def nested_block(depth: int) -> tuple:
    block: tuple = (1, b"a")
    for _ in range(depth - 1):
        block = (1, [block])
    return block


def test_lidata_depth_cap():
    mod = read_object(two_segment_module(lidata32(2, 0, [nested_block(omf.LIDATA_MAX_DEPTH)])))
    assert mod.segments[1].data[:1] == b"a"
    with pytest.raises(OMFError, match="depth"):
        read_object(two_segment_module(lidata32(2, 0, [nested_block(omf.LIDATA_MAX_DEPTH + 1)])))


def test_fixup_after_lidata_marks_unmaskable():
    mod = read_object(
        two_segment_module(
            ledata32(1, 0, bytes(8)),
            lidata32(2, 0, [(4, b"\x01\x02\x03\x04")]),
            fixupp32(fixup(0, target=(0, 1), displacement=0)),
        )
    )
    text, data = mod.segments
    assert data.unmaskable
    assert data.fixups == ()
    assert not text.unmaskable


@pytest.mark.parametrize("access", [None, 0x03], ids=["no-access-byte", "access-byte"])
def test_easy_omf_reads_16bit_numbered_records_as_32bit(access: int | None):
    mod = read_object(
        module(
            "easy",
            coment(0xAA, b"80386"),
            lnames("", "_TEXT", "CODE"),
            segdef_easy(2, 3, 0x12345, access=access),
            pubdef16(1, [("e_", 0x12340)], offset32=True),
            ledata16(1, 0x12340, b"\x0a\x0b\x0c\x0d", offset32=True),
            fixupp16(fixup(0, target=(0, 1), displacement=0x100000)),
        )
    )
    assert mod.easy_omf
    [seg] = mod.segments
    assert seg.length == 0x12345
    assert seg.use32
    assert seg.data[0x12340:0x12344] == b"\x0a\x0b\x0c\x0d"
    assert mod.publics == (Public("e_", 1, 0x12340),)
    assert seg.fixups[0].offset == 0x12340
    assert seg.fixups[0].displacement == 0x100000


def test_easy_omf_lidata_keeps_16bit_repeat_counts():
    # Easy OMF widens the data offset of record 0xA2, not its repeat counts (shape seen in a
    # real Easy OMF LIDATA record: it parses to the last byte only this way)
    mod = read_object(
        module(
            "easy",
            coment(0xAA, b"80386"),
            lnames("", "_DATA", "DATA"),
            segdef_easy(2, 3, 0x20),
            lidata16(1, 0x10, [(3, b"ab"), (2, [(1, b"x"), (1, b"y")])], offset32=True),
        )
    )
    assert mod.segments[0].data[0x10:0x1A] == b"abababxyxy"


def test_lidata16_without_easy_omf():
    mod = read_object(two_segment_module(lidata16(2, 4, [(2, b"cd")])))
    assert mod.segments[1].data[4:8] == b"cdcd"


def test_without_easy_omf_16bit_records_have_16bit_fields():
    mod = read_object(
        module(
            "plain",
            lnames("", "_TEXT", "CODE"),
            segdef16(2, 3, 0x40),
            pubdef16(1, [("e_", 0x10)]),
            ledata16(1, 0x10, b"\x0a\x0b\x0c\x0d"),
            fixupp16(fixup(0, target=(0, 1), displacement=0x1234, use32=False)),
        )
    )
    assert not mod.easy_omf
    [seg] = mod.segments
    assert (seg.length, seg.use32) == (0x40, False)
    assert seg.data[0x10:0x14] == b"\x0a\x0b\x0c\x0d"
    assert mod.publics == (Public("e_", 1, 0x10),)
    assert seg.fixups[0].displacement == 0x1234


def test_bakpat_applies_and_masks():
    dword = bytes([0, 0, 0, 0, 0x05, 0, 0, 0])
    mod = read_object(two_segment_module(ledata32(1, 0, dword), bakpat32(1, 2, [(4, 0x10)])))
    text = mod.segments[0]
    assert text.data[:8] == bytes([0, 0, 0, 0, 0x15, 0, 0, 0])
    assert text.backpatched == frozenset(range(4, 8))
    assert text.mask == frozenset(range(4, 8))


def test_bakpat_wraps():
    dword = bytes([0xF0, 0xFF, 0xFF, 0xFF])
    mod = read_object(two_segment_module(ledata32(1, 0, dword), bakpat32(1, 2, [(0, 0x20)])))
    assert mod.segments[0].data[:4] == bytes([0x10, 0, 0, 0])


def test_bakpat_past_segment_raises():
    with pytest.raises(OMFError, match="BAKPAT32"):
        read_object(two_segment_module(bakpat32(1, 2, [(0x3E, 1)])))


def test_coment_metadata():
    mod = read_object(
        module(
            "meta",
            coment(0x9B, b"3fOp"),
            coment(0x9F, b"clib3r"),
            coment(0x9F, b"math387r"),
            coment(0xE9, b"\x01\x02\x03\x04\x05\x06x.h"),
        )
    )
    assert mod.model == "3fOp"
    assert mod.default_libraries == ("clib3r", "math387r")
    assert not mod.easy_omf


def test_grpdef_names():
    fx = only_fixup(
        ledata32(1, 0, bytes(8)), fixupp32(fixup(0, frame=(1, 1), target=(1, 1), displacement=0))
    )
    assert (fx.target_kind, fx.target_index, fx.target_name) == ("group", 1, "DGROUP")


def test_grpdef_index_out_of_range_raises():
    with pytest.raises(OMFError, match="group index 2"):
        read_object(
            two_segment_module(
                ledata32(1, 0, bytes(8)), fixupp32(fixup(0, target=(1, 2), displacement=0))
            )
        )


# --- COMDAT32 and the normalized object hash ---

COMDAT_NAMES = lnames("", "_TEXT", "CODE", "f_")  # indexes 1..4
CALL_RET = bytes([0xE8, 0, 0, 0, 0, 0xC3])


def comdat_module(*records: bytes) -> bytes:
    """One empty _TEXT segment, one extern "g_", then the given COMDAT records."""
    return module("cd", COMDAT_NAMES, segdef32(2, 3, 0), extdef("g_"), *records)


def test_comdat32_block():
    mod = read_object(
        comdat_module(
            comdat32(4, CALL_RET, alignment=1, seg=1),
            fixupp32(fixup(1, segment_relative=False, target=(2, 1))),
        )
    )
    call = OMFFixup(
        offset=1,
        size=4,
        segment_relative=False,
        location=9,
        frame_method=5,
        target_method=6,
        target_kind="extern",
        target_index=1,
        target_name="g_",
        displacement=0,
    )
    assert mod.comdats == (
        omf.Comdat(name="f_", segment_index=1, alignment=1, data=CALL_RET, fixups=(call,)),
    )
    assert mod.comdats[0].mask == frozenset(range(1, 5))
    assert mod.segments[0].fixups == ()


def test_comdat32_continuation_appends():
    mod = read_object(
        comdat_module(
            comdat32(4, b"\x01\x02\x03"),
            comdat32(4, b"\x04\x05", flags=0x01, offset=3),
            fixupp32(fixup(0, location=1, target=(2, 1), displacement=0)),
        )
    )
    [block] = mod.comdats
    assert block.data == b"\x01\x02\x03\x04\x05"
    assert [(f.offset, f.size) for f in block.fixups] == [(3, 2)]  # continuation offset 3


def test_comdat32_fixup_past_block_raises():
    with pytest.raises(OMFError, match="COMDAT 'f_'"):
        read_object(
            comdat_module(
                comdat32(4, b"\x01\x02\x03"),
                fixupp32(fixup(2, location=1, target=(2, 1), displacement=0)),
            )
        )


def test_comdat32_continuation_without_start_raises():
    with pytest.raises(OMFError, match="COMDAT32"):
        read_object(comdat_module(comdat32(4, b"\x01", flags=0x01, offset=0)))


def test_comdat32_without_public_base():
    mod = read_object(comdat_module(comdat32(4, CALL_RET, attributes=0x03)))
    assert (mod.comdats[0].name, mod.comdats[0].segment_index) == ("f_", 0)


def test_comdat32_iterated_data_expands_and_is_unmaskable():
    blocks = lidata_blocks32([(3, b"ab")])
    mod = read_object(
        comdat_module(
            comdat32(4, blocks, flags=0x02),
            fixupp32(fixup(0, target=(2, 1), displacement=0)),
        )
    )
    [block] = mod.comdats
    assert block.data == b"ababab"
    assert block.unmaskable
    assert block.fixups == ()


def dependency_object(path: str, dependency: bytes = b"", code: int = 0x90) -> bytes:
    return module(
        path,
        coment(0xE9, dependency),
        lnames("", "_TEXT", "CODE"),
        segdef32(2, 3, 4),
        ledata32(1, 0, bytes([code, 0x01, 0x02, 0x03])),
    )


def test_normalized_hash_ignores_theadr_and_dependency_comments():
    host = dependency_object("C:\\work\\a.c", b"\x11\x22\x33\x44\x03a.h")
    wibo = dependency_object("/src/a.c", b"\x55\x66\x77\x88\x03b.h")
    assert omf.normalized_object_sha1(host) == omf.normalized_object_sha1(wibo)
    kept = dependency_object("x")
    kept = kept[len(theadr("x")) + len(coment(0xE9, b"")) :]
    assert omf.normalized_object_sha1(host) == hashlib.sha1(kept).hexdigest()


def test_normalized_hash_sees_data_and_other_comments():
    base = omf.normalized_object_sha1(dependency_object("a.c"))
    assert omf.normalized_object_sha1(dependency_object("a.c", code=0x91)) != base
    with_model = module("a.c", coment(0x9B, b"3fOp"), lnames(""))
    without_model = module("a.c", lnames(""))
    assert omf.normalized_object_sha1(with_model) != omf.normalized_object_sha1(without_model)


def test_normalized_hash_stops_at_modend():
    obj = dependency_object("a.c")
    assert omf.normalized_object_sha1(obj + b"\xa5" * 16) == omf.normalized_object_sha1(obj)
