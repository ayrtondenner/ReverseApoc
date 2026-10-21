"""wpack decoder against tiny synthetic archives (tests/wpackimage.py); no Watcom bytes."""

from __future__ import annotations

import random
import zlib

import pytest

from reverseapoc import wpack
from reverseapoc.wpack import Member, WpackError, decode_member, join_parts, read_archive
from wpackimage import STAMP, archive, no_shannon_stream, shannon_stream

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


# --- Shannon-coded members and the Watcom qsort tie order (Task 2) ---

# Eight coded symbols (fewer than 16, so the builder's small-sort path applies) with a complete
# set of code lengths. 'a' (length 3) sits at sorted position 0 and 'd' (length 2) at position
# 3, so the gap-3 pass swaps them and 'd' gets its code before 'b': a stable sort would not.
LENGTHS = {ord("a"): 3, ord("b"): 2, ord("c"): 3, ord("d"): 2, ord("e"): 4, 256: 3, 257: 5, 258: 5}
SHANNON_TOKENS = [
    (3, 100), ord("a"), ord("b"), ord("c"), (3, 2), ord("d"), (4, 0), ord("e"), (5, 6),
]  # fmt: skip
SHANNON_EXPECTED = b"   abcabcdddddecdddd"


def _by_key(item: tuple[str, int]) -> int:
    return item[1]


def test_watcom_qsort_orders_by_key():
    rng = random.Random(1995)
    for size in (0, 1, 2, 15, 16, 100, 314):
        items = [(f"x{i}", rng.randint(0, 9)) for i in range(size)]
        result = wpack.watcom_qsort(items, _by_key)
        assert sorted(result) == sorted(items), size
        assert [k for _, k in result] == sorted(k for _, k in items), size


def test_watcom_qsort_small_n_order():
    # Format doc 8.1 worked example. Keys 2,1,1,1,2,1 tagged a..f.
    # Gap 3 visits position 3 only: key 1 ('d') < key 2 ('a'), so 'a' and 'd' swap:
    #   d b c a e f
    # Gap 1, insertion sort: 'f' (1) moves back past 'e' (2) and 'a' (2), stops after 'c' (1):
    #   d b c f a e
    items = [("a", 2), ("b", 1), ("c", 1), ("d", 1), ("e", 2), ("f", 1)]
    assert [t for t, _ in wpack.watcom_qsort(items, _by_key)] == list("dbcfae")


def test_watcom_qsort_differs_from_stable_sort():
    rng = random.Random(314)
    items = [(f"s{i}", rng.randint(1, 4)) for i in range(314)]
    assert wpack.watcom_qsort(items, _by_key) != sorted(items, key=_by_key)


def test_code_length_table_rle():
    # 3 entries: skip 2 symbols, 4 symbols of length 3, 1 symbol of length 8; then stream bits.
    lengths, used = wpack.code_lengths(bytes([2, 0x81, 0x32, 0x07]) + b"\xee\xee")
    assert used == 4
    assert lengths[:8] == [0, 0, 3, 3, 3, 3, 8, 0]
    assert len(lengths) == wpack.NUM_SYMBOLS and not any(lengths[7:])


def test_code_length_table_overrun_raises():
    with pytest.raises(WpackError, match="past"):
        # skip 128 + 128 + 57, then a run of 8 symbols from symbol 313: past the last (313)
        wpack.code_lengths(bytes([3, 0xFF, 0xFF, 0xB8, 0x70]))


def test_code_length_table_truncated_raises():
    with pytest.raises(WpackError, match="ends early"):
        wpack.code_lengths(bytes([3, 0x81, 0x32]))


def test_shannon_member_decodes():
    stream = shannon_stream(SHANNON_TOKENS, LENGTHS)
    data = archive([("coded.bin", SHANNON_EXPECTED, stream, True)])
    size = len(SHANNON_EXPECTED)
    assert decode_member(data, "coded.bin", expected_size=size) == SHANNON_EXPECTED
