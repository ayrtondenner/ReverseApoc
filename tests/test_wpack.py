"""wpack decoder against tiny synthetic archives (tests/wpackimage.py); no Watcom bytes."""

from __future__ import annotations

import zlib

import pytest

from reverseapoc import wpack
from reverseapoc.wpack import Member, WpackError, decode_member, join_parts, read_archive
from wpackimage import STAMP, archive, no_shannon_stream

# A NO_SHANNON member: a match into the space-filled initial window, literals, an overlapping
# match, and a long-range match back to the first output byte.
TOKENS = [(3, 0), ord("a"), ord("b"), ord("c"), (6, 2), (4, 11), ord("Z")]
EXPECTED = b"   abcabcabc   aZ"
STREAM = no_shannon_stream(TOKENS)


def _one(name: str = "plain.txt", original: bytes = EXPECTED, stream: bytes = STREAM) -> bytes:
    return archive([(name, original, stream, False)])


def test_read_archive_header_and_members():
    first, second = b"\x01\x02\x03\x04\x05", b"\xaa\xbb\xcc"
    data = archive([("ONE.TXT", b"x" * 40, first, False), ("two.bin", b"y" * 7, second, True)])
    assert read_archive(data) == [
        Member("ONE.TXT", 40, 12, STAMP, zlib.crc32(first), False),
        Member("two.bin", 7, 12 + len(first), STAMP, zlib.crc32(second), True),
    ]


def test_join_parts_is_concatenation():
    assert join_parts([b"abc", b"de", b"f"]) == b"abcdef"
    with pytest.raises(WpackError, match="no archive parts"):
        join_parts([])


def test_bad_signature_raises():
    with pytest.raises(WpackError, match="signature"):
        read_archive(archive([("a", b"", b"", False)], signature=0x1234))


def test_truncated_archive_raises():
    with pytest.raises(WpackError, match="truncated"):
        read_archive(_one()[:-5])


def test_header_shorter_than_twelve_bytes_raises():
    with pytest.raises(WpackError, match="truncated"):
        read_archive(_one()[:7])


def test_sixteen_byte_header_variant_is_refused():
    data = archive([("plain.txt", EXPECTED, STREAM, False)], header_extra=b"\0\0\0\0")
    with pytest.raises(WpackError, match="12-byte header"):
        read_archive(data)


def test_crc_mismatch_raises():
    data = bytearray(_one())
    data[12] ^= 0x40  # first compressed byte
    good, bad = zlib.crc32(STREAM), zlib.crc32(bytes(data[12 : 12 + len(STREAM)]))
    with pytest.raises(WpackError, match="CRC") as exc:
        decode_member(bytes(data), "plain.txt", expected_size=len(EXPECTED))
    assert f"{good:#010x}" in str(exc.value) and f"{bad:#010x}" in str(exc.value)


def test_unknown_member_raises():
    with pytest.raises(WpackError, match="missing.exe"):
        decode_member(_one(), "missing.exe", expected_size=len(EXPECTED))


def test_length_must_equal_expected_size():
    garbage = b"\xff" * 4  # would not decode to EXPECTED; the size check comes first
    data = _one(stream=garbage)
    with pytest.raises(WpackError, match=f"{len(EXPECTED) + 1}"):
        decode_member(data, "plain.txt", expected_size=len(EXPECTED) + 1)


def test_no_shannon_literals_and_matches_round_trip():
    assert decode_member(_one(), "plain.txt", expected_size=len(EXPECTED)) == EXPECTED


def test_member_names_match_without_case():
    assert decode_member(_one(), "PLAIN.TXT", expected_size=len(EXPECTED)) == EXPECTED


def test_stream_that_ends_early_raises():
    short = no_shannon_stream([ord("a"), ord("b")])
    with pytest.raises(WpackError, match="ends early"):
        decode_member(_one(original=b"abcdefgh", stream=short), "plain.txt", expected_size=8)


def test_match_past_the_member_length_raises():
    stream = no_shannon_stream([ord("a"), (5, 0)])
    with pytest.raises(WpackError, match="past"):
        decode_member(_one(original=b"aaa", stream=stream), "plain.txt", expected_size=3)


def test_empty_member_decodes_to_nothing():
    assert decode_member(_one(original=b"", stream=b""), "plain.txt", expected_size=0) == b""


def test_header_size_constant_follows_the_field_layout():
    assert wpack.HEADER_SIZE == 12
    assert wpack.NUM_SYMBOLS == 314
    assert wpack.WINDOW_START == 4036
