"""Test-only builder of tiny synthetic wpack archives; made-up content, own literals.

Written from docs/research/wpack-format.md, independently of tools/reverseapoc/wpack.py, so the
tests check the decoder against the format and not against its own constants.

Tokens for the stream builders: an `int` is a literal byte, a `(length, position)` tuple is a
match that copies `length` bytes starting `position + 1` bytes back.
"""

from __future__ import annotations

import struct
import zlib

STAMP = 0x2155_6C20  # made-up DOS date/time
HEADER_LEN = 12

Token = int | tuple[int, int]

# The upper 6 bits of a match position, grouped by prefix length (format doc section 5):
# (number of upper values in the group, prefix length in bits).
_POSITION_GROUPS = [(1, 3), (3, 4), (8, 5), (12, 6), (24, 7), (16, 8)]


def _position_prefixes() -> list[tuple[int, int]]:
    """(prefix bits, prefix length) for each upper value 0..63."""
    out, start = [], 0
    for count, length in _POSITION_GROUPS:
        for _ in range(count):
            out.append((start >> (8 - length), length))
            start += 1 << (8 - length)
    assert start == 256 and len(out) == 64
    return out


_PREFIXES = _position_prefixes()


class BitWriter:
    """Most significant bit first; the last byte is padded with zero bits."""

    def __init__(self) -> None:
        self._bits: list[int] = []

    def put(self, value: int, width: int) -> None:
        assert 0 <= value < (1 << width), (value, width)
        self._bits.extend((value >> (width - 1 - k)) & 1 for k in range(width))

    def position(self, pos: int) -> None:
        assert 0 <= pos < 4096
        prefix, length = _PREFIXES[pos >> 6]
        self.put(prefix, length)
        self.put(pos & 0x3F, 6)

    def getvalue(self) -> bytes:
        bits = self._bits + [0] * (-len(self._bits) % 8)
        return bytes(
            int("".join(map(str, bits[i : i + 8])), 2) for i in range(0, len(bits), 8)
        )


def no_shannon_stream(tokens: list[Token]) -> bytes:
    """A "no Shannon" member stream: 0 + 8-bit literal, or 1 + 6-bit count + position."""
    w = BitWriter()
    for tok in tokens:
        if isinstance(tok, int):
            w.put(0, 1)
            w.put(tok, 8)
        else:
            length, pos = tok
            w.put(1, 1)
            w.put(length, 6)
            w.position(pos)
    return w.getvalue()


def archive(
    members: list[tuple[str, bytes, bytes, bool]],
    *,
    signature: int = 0x2403,
    header_extra: bytes = b"",
) -> bytes:
    """A whole archive from (name, original bytes, compressed stream, shannon) tuples.

    `header_extra` is inserted after the 12-byte header (to fake the 16-byte header variant);
    the members' disk addresses account for it.
    """
    data = bytearray()
    table = bytearray()
    addr = HEADER_LEN + len(header_extra)
    for name, original, stream, shannon in members:
        raw = name.encode("ascii")
        namelen = len(raw) | (0 if shannon else 0x80)
        table += struct.pack("<IIIIB", len(original), addr, STAMP, zlib.crc32(stream), namelen)
        table += raw
        data += stream
        addr += len(stream)
    header = struct.pack("<HBBHHI", signature, 1, 1, len(members), len(table), addr)
    return header + header_extra + bytes(data) + bytes(table)
