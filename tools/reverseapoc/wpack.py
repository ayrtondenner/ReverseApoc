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
from collections.abc import Callable, Iterable
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

# Shannon-coded streams (section 7).
_MATCH_BASE = 256 - (THRESHOLD + 1)  # symbol 256 is a match of THRESHOLD + 1 bytes
_CODE_BITS = 16  # codes are left-aligned in 16 bits
_CODE_SPACE = 1 << _CODE_BITS
_NO_CODE = 0xFFFF  # first code value recorded for a length nobody uses
_SKIP_FLAG = 0x80  # code-length entry: skip (entry & _SKIP_MASK) + 1 symbols
_SKIP_MASK = 0x7F
_RUN_SHIFT = 4  # otherwise: (entry >> 4) + 1 symbols of length (entry & 0x0F) + 1
_WIDTH_MASK = 0x0F
_SMALL_SORT = 16  # Watcom qsort shell-sorts blocks smaller than this (section 8)


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
    if not shannon:
        _decode_plain(_BitReader(stream), out)
        return out.result()
    lengths, used = code_lengths(stream)
    symbols, widths = _code_table(lengths)
    _decode_shannon(_BitReader(stream, used), out, symbols, widths)
    return out.result()


class _BitReader:
    """Most-significant-bit-first reader over one compressed stream. A look-ahead may run past
    the end (those bits read as 0); consuming past the end is an error."""

    _PAD = 3  # bytes of zero padding: a peek of up to 16 bits spans at most 3 bytes

    def __init__(self, stream: bytes, start: int = 0) -> None:
        self._buf = stream + bytes(self._PAD)
        self._limit = len(stream) * 8
        self._pos = start * 8  # in bits; `start` is a byte offset

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


def _decode_shannon(bits: _BitReader, out: _Output, symbols: list[int], widths: bytes) -> None:
    """The Shannon-coded stream after its code-length table (sections 7.4 and 7.5)."""
    while not out.done():
        view = bits.peek(_CODE_BITS)
        symbol = symbols[view]
        if symbol < 0:
            raise WpackError("invalid code in the compressed stream")
        bits.skip(widths[view])
        if symbol < 256:
            out.literal(symbol)
        else:
            out.copy(symbol - _MATCH_BASE, _read_position(bits))


def code_lengths(stream: bytes) -> tuple[list[int], int]:
    """Unpack the run-length packed code-length table at the start of a Shannon-coded stream
    (section 7.2): the code length of every symbol (0 = no code) and the bytes the table used."""
    if not stream or 1 + stream[0] + 1 > len(stream):
        raise WpackError("code-length table ends early")
    used = 1 + stream[0] + 1
    lengths = [0] * NUM_SYMBOLS
    symbol = 0
    for entry in stream[1:used]:
        if entry & _SKIP_FLAG:
            count, width = (entry & _SKIP_MASK) + 1, 0
        else:
            count, width = (entry >> _RUN_SHIFT) + 1, (entry & _WIDTH_MASK) + 1
        if symbol + count > NUM_SYMBOLS:
            raise WpackError(f"code-length table runs past symbol {NUM_SYMBOLS - 1}")
        if width:
            lengths[symbol : symbol + count] = [width] * count
        symbol += count
    return lengths, used


def _code_table(lengths: list[int]) -> tuple[list[int], bytes]:
    """For every 16-bit look-ahead value, the symbol it decodes to (-1: invalid) and that
    symbol's code length (section 7.3 assignment, section 7.4 lookup rule)."""
    coded = [s for s in range(NUM_SYMBOLS) if lengths[s]]
    if not coded:
        raise WpackError("code-length table assigns no codes")
    walk = watcom_qsort(coded, lengths.__getitem__)[::-1]  # longest codes first
    first, offset = _first_codes(walk, lengths)
    symbols, widths = [-1] * _CODE_SPACE, bytearray(_CODE_SPACE)
    bound = _CODE_SPACE  # values at or above this already have a shorter code
    for width in range(lengths[walk[-1]], _CODE_BITS + 1):
        low = first.get(width, _NO_CODE)
        for view in range(low, bound):
            index = offset[width] + ((view - low) >> (_CODE_BITS - width))
            symbols[view] = walk[index] if index < len(walk) else -1
            widths[view] = width
        bound = min(bound, low)
    return symbols, bytes(widths)


def _first_codes(walk: list[int], lengths: list[int]) -> tuple[dict[int, int], dict[int, int]]:
    """Canonical assignment over the walk order: per code length, the first (smallest) code
    value and the walk index where that length starts."""
    first: dict[int, int] = {}
    offset: dict[int, int] = {}
    value, step = 0, 0
    for index, symbol in enumerate(walk):
        value = (value + step) & (_CODE_SPACE - 1)
        width = lengths[symbol]
        if width not in first:
            first[width], offset[width] = value, index
        step = 1 << (_CODE_BITS - width)
    return first, offset


def watcom_qsort[T](items: Iterable[T], key: Callable[[T], int]) -> list[T]:
    """The items sorted by key exactly as Watcom's C library qsort orders them, equal keys
    included (section 8). It is not a stable sort; wpack's code assignment depends on it."""
    a = list(items)
    pending = [(0, len(a))]
    while pending:
        base, n = pending.pop()
        pending.extend(_sort_block(a, key, base, n))
    return a


def _sort_block[T](a: list[T], key: Callable[[T], int], base: int, n: int) -> list[tuple[int, int]]:
    """Sort one block in place: partition while it is large, keep the smaller-keys or the
    larger-keys side as section 8.2 step 4 says, shell-sort what is left. Returns the blocks
    set aside for later."""
    later = []
    while n >= _SMALL_SORT:
        base, n, aside = _partition(a, key, base, n)
        if aside is not None:
            later.append(aside)
    if n > 1:
        _shell_sort(a, key, base, n)
    return later


def _shell_sort[T](a: list[T], key: Callable[[T], int], base: int, n: int) -> None:
    """Section 8.1: gap 3 over block positions 0, 3, 6, ... only, then gap 1 over all."""
    for gap in (3, 1):
        for pos in range(base + gap, base + n, gap):
            _sift_back(a, key, base, pos, gap)


def _sift_back[T](a: list[T], key: Callable[[T], int], base: int, pos: int, gap: int) -> None:
    """Move the element at pos back in steps of gap while its predecessor's key is greater."""
    while pos > base and key(a[pos - gap]) > key(a[pos]):
        a[pos - gap], a[pos] = a[pos], a[pos - gap]
        pos -= gap


def _median3[T](a: list[T], key: Callable[[T], int], i: int, j: int, k: int) -> int:
    """Section 8.2 step 1: the median of three, with its exact comparison sequence."""
    ki, kj, kk = key(a[i]), key(a[j]), key(a[k])
    if ki > kj:
        if ki > kk:
            return j if kj > kk else k
        return i
    if ki >= kk:
        return i
    return k if kj > kk else j


def _pivot_index[T](a: list[T], key: Callable[[T], int], base: int, n: int) -> int:
    mid = base + n // 2
    if n < 30:
        return mid
    lo, hi = base, base + n - 1
    if n >= 43:
        s = n // 8
        lo = _median3(a, key, lo, lo + s, lo + 2 * s)
        mid = _median3(a, key, mid - s, mid, mid + s)
        hi = _median3(a, key, hi - 2 * s, hi - s, hi)
    return _median3(a, key, lo, mid, hi)


def _partition[T](
    a: list[T], key: Callable[[T], int], base: int, n: int
) -> tuple[int, int, tuple[int, int] | None]:
    """Section 8.2 steps 2-4: three-way partition around a pivot value. Returns the block to
    continue with and the block set aside (or None)."""
    pivot = key(a[_pivot_index(a, key, base, n)])
    pa = pb = base
    pc = pd = base + n - 1
    while True:
        pa, pb = _scan_up(a, key, pivot, pa, pb, pc)
        pc, pd = _scan_down(a, key, pivot, pb, pc, pd)
        if pb > pc:
            break
        a[pb], a[pc] = a[pc], a[pb]
        pb, pc = pb + 1, pc - 1
    end = base + n
    s = min(pa - base, pb - pa)
    a[base : base + s], a[pb - s : pb] = a[pb - s : pb], a[base : base + s]
    s = min(pd - pc, end - pd - 1)
    a[pb : pb + s], a[end - s : end] = a[end - s : end], a[pb : pb + s]
    smaller, larger = pb - pa, pd - pc
    if larger >= smaller:
        return base, smaller, (end - larger, larger)
    if smaller <= 1:
        return base, 0, None
    return end - larger, larger, (base, smaller)


def _scan_up[T](
    a: list[T], key: Callable[[T], int], pivot: int, pa: int, pb: int, pc: int
) -> tuple[int, int]:
    """Advance pb over keys not above the pivot, gathering equal keys at pa."""
    while pb <= pc:
        k = key(a[pb])
        if k > pivot:
            break
        if k == pivot:
            a[pa], a[pb] = a[pb], a[pa]
            pa += 1
        pb += 1
    return pa, pb


def _scan_down[T](
    a: list[T], key: Callable[[T], int], pivot: int, pb: int, pc: int, pd: int
) -> tuple[int, int]:
    """Step pc back over keys not below the pivot, gathering equal keys at pd."""
    while pc >= pb:
        k = key(a[pc])
        if k < pivot:
            break
        if k == pivot:
            a[pc], a[pd] = a[pd], a[pc]
            pd -= 1
        pc -= 1
    return pc, pd
