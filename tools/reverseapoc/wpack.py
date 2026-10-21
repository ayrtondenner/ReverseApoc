"""Independent implementation of the Watcom 10.x wpack format from docs/research/wpack-format.md.
Open Watcom bld/wpack (OWPL) is cited as the format reference only, and no code or comments were
copied (D-15).

The 10.5 CD packs its real `BINW/WCC386.EXE` in a two-part wpack archive. `join_parts` joins the
parts, `read_archive` lists the members, and `decode_member` checks one member's CRC-32 and
decodes it into memory. The decoder returns bytes only; it never writes a file and never uses an
archive-supplied name as a path. Section numbers below refer to the format document.
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Iterable
from dataclasses import dataclass

SIGNATURE = 0x2403

# Archive header (section 2): 12 bytes on the 10.5 disc, no access-key field.
_HDR_SIGNATURE = 0  # u16
_HDR_MAJOR = 2  # u8
_HDR_MINOR = 3  # u8
_HDR_NUM_FILES = 4  # u16
_HDR_INFO_LEN = 6  # u16: bytes in the file-info table
_HDR_INFO_OFFSET = 8  # u32: archive offset of the file-info table
HEADER_SIZE = _HDR_INFO_OFFSET + 4

# File-info record (section 3): fixed part, then the name.
_FI_LENGTH = 0  # u32: uncompressed size
_FI_DISK_ADDR = 4  # u32: archive offset of the compressed stream
_FI_STAMP = 8  # u32: DOS date/time
_FI_CRC = 12  # u32: CRC-32 of the compressed stream
_FI_NAMELEN = 16  # u8: name length, bit 7 = no Shannon code
_FI_NAME = _FI_NAMELEN + 1
NO_SHANNON = 0x80
NAMELEN_MASK = 0x7F

# LZSS window (section 5).
WINDOW = 4096
LOOKAHEAD = 60
THRESHOLD = 2
NUM_SYMBOLS = 256 - THRESHOLD + LOOKAHEAD
WINDOW_START = WINDOW - LOOKAHEAD
WINDOW_FILL = 0x20

# Bit-field widths of the streams (sections 5 and 6).
_FLAG_BITS = 1
_LITERAL_BITS = 8
_COUNT_BITS = 6
_POS_INDEX_BITS = 8  # bits that index D_CODE / D_LEN
_POS_LOW_BITS = 6  # raw low bits of a position
_POS_LOW_MASK = (1 << _POS_LOW_BITS) - 1


def _position_tables() -> tuple[bytes, bytes]:
    """D_CODE and D_LEN, rebuilt from their runs (section 5): for each row, the number of table
    entries per upper value, how many upper values the row holds, and the prefix length."""
    rows = ((32, 1, 3), (16, 3, 4), (8, 8, 5), (4, 12, 6), (2, 24, 7), (1, 16, 8))
    code, length, upper = bytearray(), bytearray(), 0
    for per_value, values, prefix_len in rows:
        for _ in range(values):
            code += bytes([upper]) * per_value
            length += bytes([prefix_len]) * per_value
            upper += 1
    return bytes(code), bytes(length)


# The classic LZHUF position tables (Haruyasu Yoshizaki, 1988, after Haruhiko Okumura's LZSS).
D_CODE, D_LEN = _position_tables()


class WpackError(ValueError):
    """The archive is malformed, truncated, damaged, or does not hold the requested member."""


@dataclass(frozen=True)
class Member:
    name: str
    length: int  # uncompressed size
    disk_addr: int  # archive offset of the compressed stream
    stamp: int  # DOS date/time, unused by the decoder
    crc: int  # CRC-32 of the compressed stream
    shannon: bool  # False: the "no Shannon" stream format


def join_parts(parts: Iterable[bytes]) -> bytes:
    """One archive from its disk parts (`.1`, `.2`, ...), given in order: a plain concatenation."""
    parts = list(parts)
    if not parts:
        raise WpackError("no archive parts given")
    return b"".join(parts)


def read_archive(data: bytes) -> list[Member]:
    """The members of an archive, in table order."""
    return _parse(data)[0]


def _parse(data: bytes) -> tuple[list[Member], int]:
    """The members and the offset of the file-info table, which ends the last member's stream."""
    if len(data) < HEADER_SIZE:
        raise WpackError(f"archive is truncated ({len(data)} bytes, a header is {HEADER_SIZE})")
    (signature,) = struct.unpack_from("<H", data, _HDR_SIGNATURE)
    if signature != SIGNATURE:
        raise WpackError(f"not a wpack archive (signature {signature:#06x}, need {SIGNATURE:#06x})")
    (count,) = struct.unpack_from("<H", data, _HDR_NUM_FILES)
    (info_len,) = struct.unpack_from("<H", data, _HDR_INFO_LEN)
    (info_offset,) = struct.unpack_from("<I", data, _HDR_INFO_OFFSET)
    if info_offset < HEADER_SIZE:
        raise WpackError(f"file-info table at {info_offset} overlaps the header")
    if info_offset + info_len > len(data):
        raise WpackError(
            f"archive is truncated (file-info table at {info_offset}+{info_len} lies beyond the "
            f"end of the {len(data)} bytes)"
        )
    members = list(_info_records(data[info_offset : info_offset + info_len], count))
    _check_extents(members, info_offset)
    return members, info_offset


def _info_records(table: bytes, count: int) -> Iterable[Member]:
    pos = 0
    for _ in range(count):
        if pos + _FI_NAME > len(table):
            raise WpackError("file-info table is truncated")
        length, disk_addr, stamp, crc = struct.unpack_from("<4I", table, pos + _FI_LENGTH)
        namelen = table[pos + _FI_NAMELEN]
        name_end = pos + _FI_NAME + (namelen & NAMELEN_MASK)
        if name_end > len(table):
            raise WpackError("file-info table is truncated (a name runs past its end)")
        try:
            name = table[pos + _FI_NAME : name_end].decode("ascii")
        except UnicodeDecodeError as exc:
            raise WpackError("member name is not ASCII") from exc
        yield Member(name, length, disk_addr, stamp, crc, not namelen & NO_SHANNON)
        pos = name_end
    if pos != len(table):
        raise WpackError(f"file-info table has {len(table) - pos} bytes after its last record")


def _check_extents(members: list[Member], info_offset: int) -> None:
    """Streams follow the header in table order and end before the file-info table (section 4).
    The first stream starting right after 12 bytes is what proves the 10.5 header layout."""
    if members and members[0].disk_addr != HEADER_SIZE:
        raise WpackError(
            f"first member starts at {members[0].disk_addr}, not right after the 12-byte header "
            "(the 16-byte header variant is not supported)"
        )
    previous = HEADER_SIZE
    for member in members:
        if not previous <= member.disk_addr <= info_offset:
            raise WpackError(f"member {member.name!r} starts at {member.disk_addr}, out of order")
        previous = member.disk_addr


def decode_member(data: bytes, name: str, *, expected_size: int) -> bytes:
    """Decode one member (name matched without case). Its length must equal `expected_size`
    and its compressed stream must match its CRC-32 before any decoding starts; the output
    never grows past `expected_size` bytes."""
    members, info_offset = _parse(data)
    index = next(
        (i for i, m in enumerate(members) if m.name.casefold() == name.casefold()), None
    )
    if index is None:
        raise WpackError(f"no member {name!r} in the archive")
    member = members[index]
    if member.length != expected_size:
        raise WpackError(
            f"member {member.name!r} is {member.length} bytes, expected {expected_size}"
        )
    end = members[index + 1].disk_addr if index + 1 < len(members) else info_offset
    crc = zlib.crc32(memoryview(data)[member.disk_addr : end])
    if crc != member.crc:
        raise WpackError(
            f"member {member.name!r}: CRC mismatch (stored {member.crc:#010x}, "
            f"computed {crc:#010x})"
        )
    try:
        return _decode(data[member.disk_addr : end], member.shannon, expected_size)
    except WpackError as exc:
        raise WpackError(f"{exc} (member {member.name!r})") from exc


def _decode(stream: bytes, shannon: bool, size: int) -> bytes:
    out = _Output(size)
    if size == 0:
        return out.result()
    bits = _BitReader(stream)
    if shannon:
        raise WpackError("Shannon-coded members are decoded in Task 2")
    _decode_plain(bits, out)
    return out.result()


class _BitReader:
    """Most-significant-bit-first reader over one compressed stream. A look-ahead may run past
    the end (those bits read as 0); consuming past the end is an error."""

    _PAD = 3  # bytes of zero padding: a peek of up to 16 bits spans at most 3 bytes

    def __init__(self, stream: bytes) -> None:
        self._buf = stream + bytes(self._PAD)
        self._limit = len(stream) * 8
        self._pos = 0  # in bits

    def peek(self, width: int) -> int:
        byte, bit = divmod(self._pos, 8)
        buf = self._buf
        chunk = (buf[byte] << 16) | (buf[byte + 1] << 8) | buf[byte + 2]
        return (chunk >> (24 - bit - width)) & ((1 << width) - 1)

    def skip(self, width: int) -> None:
        self._pos += width
        if self._pos > self._limit:
            raise WpackError("compressed stream ends early")

    def read(self, width: int) -> int:
        value = self.peek(width)
        self.skip(width)
        return value


class _Output:
    """The decoded bytes, preceded by the initial window in output order (section 5): a match
    copies from `position + 1` bytes back, so no ring buffer is needed."""

    def __init__(self, size: int) -> None:
        self._buf = bytearray(LOOKAHEAD) + bytearray([WINDOW_FILL]) * WINDOW_START
        self._end = WINDOW + size

    def done(self) -> bool:
        return len(self._buf) >= self._end

    def literal(self, value: int) -> None:
        self._buf.append(value)

    def copy(self, length: int, position: int) -> None:
        buf = self._buf
        if len(buf) + length > self._end:
            raise WpackError("a match runs past the member length")
        src = len(buf) - position - 1
        if src + length <= len(buf):
            buf += buf[src : src + length]
            return
        for k in range(length):  # overlapping: each copied byte feeds the next
            buf.append(buf[src + k])

    def result(self) -> bytes:
        return bytes(self._buf[WINDOW:])


def _read_position(bits: _BitReader) -> int:
    """A 12-bit match position: table-coded upper 6 bits, raw lower 6 bits (section 5)."""
    index = bits.peek(_POS_INDEX_BITS)
    low = bits.read(D_LEN[index] + _POS_LOW_BITS) & _POS_LOW_MASK
    return (D_CODE[index] << _POS_LOW_BITS) | low


def _decode_plain(bits: _BitReader, out: _Output) -> None:
    """The "no Shannon" stream (section 6)."""
    while not out.done():
        if bits.read(_FLAG_BITS):
            count = bits.read(_COUNT_BITS)
            out.copy(count, _read_position(bits))
        else:
            out.literal(bits.read(_LITERAL_BITS))
