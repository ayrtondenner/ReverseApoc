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


def _packed_lengths(lengths: dict[int, int]) -> bytes:
    """The run-length packed code-length table (format doc section 7.2)."""
    syms = sorted(lengths)
    entries, symbol, i = [], 0, 0
    while i < len(syms):
        sym, width = syms[i], lengths[syms[i]]
        while symbol < sym:  # skip entries: bit 7 set, up to 128 symbols each
            gap = min(sym - symbol, 128)
            entries.append(0x80 | (gap - 1))
            symbol += gap
        run = 1  # consecutive symbols of the same length, up to 8 per entry
        while run < 8 and syms[i + run : i + run + 1] == [sym + run]:
            if lengths[sym + run] != width:
                break
            run += 1
        entries.append(((run - 1) << 4) | (width - 1))
        symbol, i = sym + run, i + run
    assert 1 <= len(entries) <= 256
    return bytes([len(entries) - 1, *entries])


def _shell_order(symbols: list[int], lengths: dict[int, int]) -> list[int]:
    """Watcom qsort for fewer than 16 elements (format doc 8.1): gap 3 over positions 0, 3, 6...
    only, then a plain insertion sort; each moves an element back while its predecessor is
    strictly longer."""
    assert len(symbols) < 16, "the builder only knows the shell-sort path"
    a = list(symbols)
    for gap in (3, 1):
        for start in range(gap, len(a), gap):
            k = start
            while k > 0 and lengths[a[k - gap]] > lengths[a[k]]:
                a[k - gap], a[k] = a[k], a[k - gap]
                k -= gap
    return a


def canonical_codes(lengths: dict[int, int]) -> dict[int, tuple[int, int]]:
    """symbol -> (code bits, code length), assigned per format doc section 7.3."""
    order = _shell_order(sorted(lengths), lengths)
    codes, value, step = {}, 0, 0
    for sym in reversed(order):
        value = (value + step) & 0xFFFF
        width = lengths[sym]
        codes[sym] = (value >> (16 - width), width)
        step = 1 << (16 - width)
    return codes


def shannon_stream(tokens: list[Token], lengths: dict[int, int]) -> bytes:
    """A Shannon-coded member stream: packed code-length table, then the coded tokens. Literals
    are symbols 0-255, a match of length n is symbol n + 253 followed by its position. Fewer
    than 16 symbols may be coded (the builder implements only the small-sort path)."""
    codes = canonical_codes(lengths)
    w = BitWriter()
    for tok in tokens:
        if isinstance(tok, int):
            w.put(*codes[tok])
        else:
            length, pos = tok
            w.put(*codes[length + 253])
            w.position(pos)
    return _packed_lengths(lengths) + w.getvalue()


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
