"""Independent raw LE reader for the le-round-trip-facts spikes.

struct only: it never imports reverseapoc.le, so the spikes can cross-check le.py against a
second reading of the same bytes. It returns numbers (offsets, sizes, counts, field records);
it never returns or prints page bytes.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

MZ_SIGNATURE = b"MZ"
LE_SIGNATURE = b"LE\x00\x00"

# MZ header fields (offsets from the MZ signature).
MZ_BYTES_ON_LAST_PAGE = 0x02  # e_cblp
MZ_PAGES_IN_FILE = 0x04  # e_cp, 512-byte pages
MZ_LFANEW = 0x3C  # e_lfanew, relative to this MZ header
MZ_PAGE = 512
BW_SIGNATURE = b"BW"  # DOS/4GW bound-extender module header
BW_NEXT_HEADER = 0x1C  # absolute file offset of the next header in the bound chain

# LE header fields (offsets from the LE signature).
LE_NUM_PAGES = 0x14
LE_PAGE_SIZE = 0x28
LE_LAST_PAGE_SIZE = 0x2C
LE_FIXUP_SECTION_SIZE = 0x30
LE_LOADER_SECTION_SIZE = 0x38
LE_OBJECT_TABLE = 0x40
LE_NUM_OBJECTS = 0x44
LE_PAGE_MAP = 0x48
LE_ITER_DATA_MAP = 0x4C
LE_FIXUP_PAGE_TABLE = 0x68
LE_FIXUP_RECORD_TABLE = 0x6C
LE_IMPORT_MODULE_TABLE = 0x70
LE_IMPORT_PROC_TABLE = 0x78
LE_DATA_PAGES = 0x80  # relative to the MZ stub that owns the LE header
LE_NONRES_NAME_TABLE = 0x88
LE_NONRES_NAME_LENGTH = 0x8C
LE_DEBUG_INFO = 0x98
LE_DEBUG_LENGTH = 0x9C

OBJECT_ENTRY = 24
PAGE_MAP_ENTRY = 4

# Fixup record source byte and target flags.
SRC_TYPE_MASK = 0x0F
SRC_LIST = 0x20
SRC_SEL16 = 0x02
TGT_TYPE_MASK = 0x03
TGT_INTERNAL = 0x00
TGT_ADDITIVE = 0x04
TGT_CHAIN = 0x08
TGT_OFF32 = 0x10
TGT_OBJ16 = 0x40
FIELD_SIZE = {0x00: 1, 0x02: 2, 0x03: 4, 0x05: 2, 0x06: 6, 0x07: 4, 0x08: 4}
KIND_NAME = {0x02: "sel16", 0x06: "ptr16:32", 0x07: "off32", 0x08: "rel32"}


def u16(d: bytes, off: int) -> int:
    return struct.unpack_from("<H", d, off)[0]


def u32(d: bytes, off: int) -> int:
    return struct.unpack_from("<I", d, off)[0]


def s16(d: bytes, off: int) -> int:
    return struct.unpack_from("<h", d, off)[0]


def mz_image_size(d: bytes, off: int) -> int:
    """Load-image size an MZ header declares (e_cp, e_cblp): where a bound program ends."""
    cblp = u16(d, off + MZ_BYTES_ON_LAST_PAGE)
    cp = u16(d, off + MZ_PAGES_IN_FILE)
    return cp * MZ_PAGE - (MZ_PAGE - cblp if cblp else 0)


def _points_at_le(d: bytes, mz: int) -> int | None:
    if d[mz : mz + 2] != MZ_SIGNATURE or mz + MZ_LFANEW + 4 > len(d):
        return None
    le = mz + u32(d, mz + MZ_LFANEW)
    return le if d[le : le + 4] == LE_SIGNATURE else None


def locate_by_mz_chain(d: bytes) -> tuple[int, int] | None:
    """Walk the bound extender's header chain until an MZ's e_lfanew points at 'LE'.

    An MZ header is followed by its declared image size; a DOS/4GW 'BW' header by the absolute
    next-header offset at BW_NEXT_HEADER (found by extender_chain.py)."""
    off = 0
    while 0 <= off < len(d):
        le = _points_at_le(d, off)
        if le is not None:
            return off, le
        sig = d[off : off + 2]
        if sig == BW_SIGNATURE:
            nxt = u32(d, off + BW_NEXT_HEADER)
        elif sig == MZ_SIGNATURE:
            nxt = off + mz_image_size(d, off)
        else:
            return None
        if nxt <= off:
            return None
        off = nxt
    return None


def locate_by_forward_scan(d: bytes) -> tuple[int, int] | None:
    """Fallback: the first 'MZ' (in file order) whose e_lfanew points at an LE signature."""
    mz = d.find(MZ_SIGNATURE)
    while mz >= 0:
        le = _points_at_le(d, mz)
        if le is not None:
            return mz, le
        mz = d.find(MZ_SIGNATURE, mz + 1)
    return None


@dataclass(frozen=True)
class RawObject:
    index: int
    vsize: int
    base: int
    flags: int
    page_index: int
    page_count: int


@dataclass(frozen=True)
class RawPage:
    logical: int
    number_be24: int  # bytes 0..2 read as a big-endian 24-bit number
    number_spec: int  # u16 little-endian high word << 8 | byte 2 (the other common reading)
    flags: int


@dataclass(frozen=True)
class RawFixup:
    logical: int  # page whose record list holds this entry
    offset: int  # signed offset from that page's VA
    va: int
    kind: int
    src_byte: int
    tgt_flags: int
    target_obj: int
    target_off: int
    record_at: int  # file offset of the record

    @property
    def size(self) -> int:
        return FIELD_SIZE[self.kind]


class RawLE:
    def __init__(self, data: bytes) -> None:
        self.data = data
        found = locate_by_mz_chain(data)
        self.locate_method = "mz-chain"
        if found is None:
            found = locate_by_forward_scan(data)
            self.locate_method = "forward-scan"
        if found is None:
            raise ValueError("no MZ header points at an LE signature")
        self.stub, self.le = found
        h = self.header
        self.num_pages = h(LE_NUM_PAGES)
        self.page_size = h(LE_PAGE_SIZE)
        self.last_page_size = h(LE_LAST_PAGE_SIZE)
        self.fixup_section_size = h(LE_FIXUP_SECTION_SIZE)
        self.loader_section_size = h(LE_LOADER_SECTION_SIZE)
        self.object_table = self.le + h(LE_OBJECT_TABLE)
        self.num_objects = h(LE_NUM_OBJECTS)
        self.page_map = self.le + h(LE_PAGE_MAP)
        self.fixup_page_table = self.le + h(LE_FIXUP_PAGE_TABLE)
        self.fixup_record_table = self.le + h(LE_FIXUP_RECORD_TABLE)
        self.data_pages = self.stub + h(LE_DATA_PAGES)
        self.objects = [self._object(i) for i in range(self.num_objects)]
        self.pages = [self._page(i) for i in range(1, self.num_pages + 1)]

    def header(self, field: int) -> int:
        return u32(self.data, self.le + field)

    @property
    def pages_end(self) -> int:
        return self.data_pages + (self.num_pages - 1) * self.page_size + self.last_page_size

    def _object(self, i: int) -> RawObject:
        vals = struct.unpack_from("<5I", self.data, self.object_table + OBJECT_ENTRY * i)
        return RawObject(i + 1, *vals)

    def _page(self, logical: int) -> RawPage:
        off = self.page_map + PAGE_MAP_ENTRY * (logical - 1)
        b0, b1, b2, flags = self.data[off : off + PAGE_MAP_ENTRY]
        return RawPage(logical, (b0 << 16) | (b1 << 8) | b2, (u16(self.data, off) << 8) | b2, flags)

    def page_size_of(self, number: int) -> int:
        return self.last_page_size if number == self.num_pages else self.page_size

    def page_file_offset(self, number: int) -> int:
        return self.data_pages + (number - 1) * self.page_size

    def object_of_page(self, logical: int) -> RawObject:
        return next(
            o for o in self.objects if o.page_index <= logical < o.page_index + o.page_count
        )

    def page_va(self, logical: int) -> int:
        obj = self.object_of_page(logical)
        return obj.base + (logical - obj.page_index) * self.page_size

    def backed_end(self, obj: RawObject) -> int:
        """VA end of the bytes the object's pages hold in the file."""
        pages = self.pages[obj.page_index - 1 : obj.page_index - 1 + obj.page_count]
        return obj.base + sum(self.page_size_of(p.number_be24) for p in pages)

    def fixup_records(self) -> list[RawFixup]:
        """Every record entry, page by page, without de-duplication."""
        out: list[RawFixup] = []
        for logical in range(1, self.num_pages + 1):
            start = u32(self.data, self.fixup_page_table + 4 * (logical - 1))
            end = u32(self.data, self.fixup_page_table + 4 * logical)
            pos = self.fixup_record_table + start
            stop = self.fixup_record_table + end
            while pos < stop:
                pos = self._record(logical, pos, out)
        return out

    def _record(self, logical: int, pos: int, out: list[RawFixup]) -> int:
        d = self.data
        at = pos
        src, flg = d[pos], d[pos + 1]
        pos += 2
        kind = src & SRC_TYPE_MASK
        if flg & TGT_TYPE_MASK != TGT_INTERNAL or flg & (TGT_ADDITIVE | TGT_CHAIN):
            raise ValueError(f"record at {at:#x}: target flags {flg:#x} are not plain internal")
        if kind not in FIELD_SIZE:
            raise ValueError(f"record at {at:#x}: source type {kind:#x}")
        count = 0
        offsets: list[int] = []
        if src & SRC_LIST:
            count = d[pos]
            pos += 1
        else:
            offsets.append(s16(d, pos))
            pos += 2
        if flg & TGT_OBJ16:
            obj = u16(d, pos)
            pos += 2
        else:
            obj = d[pos]
            pos += 1
        toff = 0
        if kind != SRC_SEL16:
            toff = u32(d, pos) if flg & TGT_OFF32 else u16(d, pos)
            pos += 4 if flg & TGT_OFF32 else 2
        for _ in range(count):
            offsets.append(s16(d, pos))
            pos += 2
        base = self.page_va(logical)
        for o in offsets:
            out.append(RawFixup(logical, o, base + o, kind, src, flg, obj, toff, at))
        return pos
