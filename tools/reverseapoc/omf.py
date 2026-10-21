"""Reader for Watcom OMF object modules and LIB libraries (TIS OMF 1.1).

Independent implementation from the TIS OMF 1.1 specification; no Open Watcom or KKND-Decomp code.

A record is a u8 type, a u16 length that counts the body and the checksum byte, the body, and the
checksum (never verified: Watcom tools do not always fill it in). Odd record types are the 32-bit
forms of the even ones. Supported records: THEADR, LNAMES, SEGDEF/SEGDEF32, EXTDEF/LEXTDEF,
PUBDEF/PUBDEF32/LPUBDEF/LPUBDEF32, LEDATA/LEDATA32 and MODEND/MODEND32; in a library, the 0xF0
header (page size = its record length + 3) and the 0xF1 end record. Other record types are
skipped by their length.

Anything malformed (a record running past the data, an index out of range, data past the end of
its segment) raises OMFError naming the record type and its file offset. In a library a module
that fails is recorded in `Library.failures` and the walk goes on with the next module.
"""

from __future__ import annotations

import struct
from collections.abc import Iterator
from dataclasses import dataclass, field

# Record types (TIS OMF 1.1 record names).
REC_THEADR = 0x80  # translator header: the module name
REC_COMENT = 0x88  # comment: class byte, then class-specific text
REC_MODEND = 0x8A  # module end
REC_MODEND32 = 0x8B
REC_EXTDEF = 0x8C  # external names
REC_PUBDEF = 0x90  # public names
REC_PUBDEF32 = 0x91
REC_LNAMES = 0x96  # list of names referenced by SEGDEF/GRPDEF by 1-based index
REC_SEGDEF = 0x98  # segment definition
REC_SEGDEF32 = 0x99
REC_GRPDEF = 0x9A  # group definition
REC_FIXUPP = 0x9C  # fixups for the preceding data record
REC_FIXUPP32 = 0x9D
REC_LEDATA = 0xA0  # logical enumerated data
REC_LEDATA32 = 0xA1
REC_LIDATA = 0xA2  # logical iterated data
REC_LIDATA32 = 0xA3
REC_LEXTDEF = 0xB4  # local (module-private) external names
REC_LPUBDEF = 0xB6  # local public names
REC_LPUBDEF32 = 0xB7
REC_COMDAT32 = 0xC3  # initialized communal data
REC_LIBHDR = 0xF0  # library header
REC_LIBEND = 0xF1  # library end

_REC_NAMES = {
    REC_THEADR: "THEADR",
    REC_COMENT: "COMENT",
    REC_MODEND: "MODEND",
    REC_MODEND32: "MODEND32",
    REC_EXTDEF: "EXTDEF",
    REC_PUBDEF: "PUBDEF",
    REC_PUBDEF32: "PUBDEF32",
    REC_LNAMES: "LNAMES",
    REC_SEGDEF: "SEGDEF",
    REC_SEGDEF32: "SEGDEF32",
    REC_GRPDEF: "GRPDEF",
    REC_FIXUPP: "FIXUPP",
    REC_FIXUPP32: "FIXUPP32",
    REC_LEDATA: "LEDATA",
    REC_LEDATA32: "LEDATA32",
    REC_LIDATA: "LIDATA",
    REC_LIDATA32: "LIDATA32",
    REC_LEXTDEF: "LEXTDEF",
    REC_LPUBDEF: "LPUBDEF",
    REC_LPUBDEF32: "LPUBDEF32",
    REC_COMDAT32: "COMDAT32",
    REC_LIBHDR: "LIBHDR",
    REC_LIBEND: "LIBEND",
}
_MODEND_KINDS = (REC_MODEND, REC_MODEND32)
_WIDE_BIT = 0x01  # odd record types carry 32-bit offsets and lengths

# Record framing.
_REC_TYPE = 0  # u8: record type
_REC_LEN = 1  # u16: body length plus the checksum byte
_REC_BODY = _REC_LEN + 2  # the body follows the length
_CHECKSUM_SIZE = 1  # trailing checksum byte, counted in the length

# OMF index fields: one byte, or two when the high bit of the first is set.
_INDEX_TWO_BYTES = 0x80
_INDEX_HIGH_MASK = 0x7F

# SEGDEF attribute byte (ACBP): alignment in bits 5-7, combination in bits 2-4, B, P.
_SEG_ALIGN_SHIFT = 5
_SEG_ALIGN_ABSOLUTE = 0  # absolute segment: a u16 frame number and a u8 offset follow
_SEG_ABS_FRAME_SIZE = 3
_SEG_BIG = 0x02  # length field is 0 and means 64 KiB (16-bit) or 4 GiB (32-bit)
_SEG_USE32 = 0x01
_SEG_BIG16_LENGTH = 0x10000
MAX_SEGMENT_LENGTH = 1 << 24  # zero-filled buffers are bounded; no library segment comes close

# Library header body (after the record framing).
_LIB_PAGE_EXTRA = _REC_BODY  # page size = header record length + 3
_LIB_MIN_PAGE = 16


class OMFError(ValueError):
    """The data is not a well-formed OMF object module or library."""


@dataclass(frozen=True)
class Record:
    kind: int
    offset: int  # file offset of the type byte
    body: bytes  # without the checksum byte

    @property
    def name(self) -> str:
        return record_name(self.kind)

    @property
    def end(self) -> int:
        """File offset just past the checksum byte."""
        return self.offset + _REC_BODY + len(self.body) + _CHECKSUM_SIZE


@dataclass(frozen=True)
class OMFFixup:
    offset: int  # segment-relative offset of the patched field
    size: int  # bytes patched
    segment_relative: bool  # M bit: segment-relative, else self-relative
    location: int  # location type (9 = 32-bit offset)
    frame_method: int
    target_method: int
    target_kind: str  # "segment", "group", "extern" or "frame"
    target_index: int
    target_name: str
    displacement: int


@dataclass(frozen=True)
class Public:
    name: str
    segment_index: int  # 1-based SEGDEF number, 0 for an absolute public
    offset: int


@dataclass(frozen=True)
class Segment:
    index: int  # 1-based SEGDEF number
    name: str
    class_name: str
    length: int
    use32: bool
    data: bytes  # zero-filled up to `length` where no data record wrote
    fixups: tuple[OMFFixup, ...] = ()
    unmaskable: bool = False  # a FIXUPP addressed iterated data, so the mask is unknown
    backpatched: frozenset[int] = frozenset()

    @property
    def is_code(self) -> bool:
        return self.class_name.upper().endswith("CODE")

    @property
    def mask(self) -> frozenset[int]:
        """Every byte offset a fixup or a backpatch writes: those bytes differ after linking."""
        patched = {i for f in self.fixups for i in range(f.offset, f.offset + f.size)}
        return frozenset(patched | self.backpatched)


@dataclass(frozen=True)
class Module:
    name: str
    offset: int  # file offset of the THEADR record
    segments: tuple[Segment, ...]
    publics: tuple[Public, ...]
    externs: tuple[str, ...]


@dataclass(frozen=True)
class ModuleFailure:
    index: int  # 1-based position of the module in the library
    offset: int  # file offset where the module starts
    message: str


@dataclass(frozen=True)
class Library:
    path: str
    page_size: int
    modules: tuple[Module, ...]
    failures: tuple[ModuleFailure, ...]


def record_name(kind: int) -> str:
    return _REC_NAMES.get(kind, f"record {kind:#04x}")


class _Cursor:
    """Bounds-checked little-endian reader over one record body."""

    def __init__(self, body: bytes) -> None:
        self.body, self.pos = body, 0

    def _take(self, n: int) -> int:
        start = self.pos
        if start + n > len(self.body):
            raise OMFError(f"body is truncated (needs {n} bytes at body offset {start:#x})")
        self.pos += n
        return start

    def at_end(self) -> bool:
        return self.pos >= len(self.body)

    def u8(self) -> int:
        return self.body[self._take(1)]

    def u16(self) -> int:
        return struct.unpack_from("<H", self.body, self._take(2))[0]

    def u32(self) -> int:
        return struct.unpack_from("<I", self.body, self._take(4))[0]

    def skip(self, n: int) -> None:
        self._take(n)

    def index(self) -> int:
        first = self.u8()
        if first & _INDEX_TWO_BYTES:
            return (first & _INDEX_HIGH_MASK) << 8 | self.u8()
        return first

    def name(self) -> str:
        length = self.u8()
        start = self._take(length)
        return self.body[start : start + length].decode("latin-1")

    def rest(self) -> bytes:
        start = self._take(len(self.body) - self.pos)
        return self.body[start:]


@dataclass
class _SegmentBuilder:
    index: int
    name: str
    class_name: str
    length: int
    use32: bool
    data: bytearray

    def freeze(self) -> Segment:
        return Segment(self.index, self.name, self.class_name, self.length, self.use32,
                       bytes(self.data))  # fmt: skip


@dataclass
class _ModuleReader:
    """Accumulates one module's records; each handler below reads one record type."""

    offset: int
    name: str = ""
    lnames: list[str] = field(default_factory=list)
    segments: list[_SegmentBuilder] = field(default_factory=list)
    publics: list[Public] = field(default_factory=list)
    externs: list[str] = field(default_factory=list)

    def feed(self, rec: Record) -> None:
        handler = _HANDLERS.get(rec.kind)
        if handler is None:
            return
        try:
            handler(self, _Cursor(rec.body), rec)
        except OMFError as exc:
            raise OMFError(f"{rec.name} record at {rec.offset:#x}: {exc}") from exc

    def wide(self, rec: Record) -> bool:
        return bool(rec.kind & _WIDE_BIT)

    def offset_field(self, cur: _Cursor, rec: Record) -> int:
        return cur.u32() if self.wide(rec) else cur.u16()

    def lname(self, idx: int) -> str:
        if idx == 0:
            return ""
        if idx > len(self.lnames):
            raise OMFError(f"name index {idx} out of range ({len(self.lnames)} names)")
        return self.lnames[idx - 1]

    def segment(self, idx: int) -> _SegmentBuilder:
        if not 1 <= idx <= len(self.segments):
            raise OMFError(f"segment index {idx} out of range ({len(self.segments)} segments)")
        return self.segments[idx - 1]

    def freeze(self) -> Module:
        return Module(
            name=self.name,
            offset=self.offset,
            segments=tuple(s.freeze() for s in self.segments),
            publics=tuple(self.publics),
            externs=tuple(self.externs),
        )


def _theadr(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    m.name = cur.name()


def _lnames(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    while not cur.at_end():
        m.lnames.append(cur.name())


def _segdef(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    attr = cur.u8()
    if attr >> _SEG_ALIGN_SHIFT == _SEG_ALIGN_ABSOLUTE:
        cur.skip(_SEG_ABS_FRAME_SIZE)
    wide = m.wide(rec)
    length = m.offset_field(cur, rec)
    if attr & _SEG_BIG:
        if wide:
            raise OMFError("a 4 GiB segment (B bit in a 32-bit SEGDEF) is not supported")
        length = _SEG_BIG16_LENGTH
    if length > MAX_SEGMENT_LENGTH:
        raise OMFError(f"segment length {length:#x} exceeds {MAX_SEGMENT_LENGTH:#x}")
    name, class_name = m.lname(cur.index()), m.lname(cur.index())
    cur.index()  # overlay name: unused
    seg = _SegmentBuilder(len(m.segments) + 1, name, class_name, length,
                          bool(attr & _SEG_USE32), bytearray(length))  # fmt: skip
    m.segments.append(seg)


def _pubdef(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    cur.index()  # base group
    seg = cur.index()
    if seg == 0:
        cur.u16()  # base frame of an absolute public
    else:
        m.segment(seg)
    while not cur.at_end():
        name = cur.name()
        offset = m.offset_field(cur, rec)
        cur.index()  # type index
        m.publics.append(Public(name, seg, offset))


def _extdef(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    while not cur.at_end():
        m.externs.append(cur.name())
        cur.index()  # type index


def _ledata(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    seg = m.segment(cur.index())
    offset = m.offset_field(cur, rec)
    data = cur.rest()
    end = offset + len(data)
    if end > seg.length:
        raise OMFError(
            f"data {offset:#x}..{end:#x} runs past segment {seg.name!r} ({seg.length:#x} bytes)"
        )
    seg.data[offset:end] = data


_HANDLERS = {
    REC_THEADR: _theadr,
    REC_LNAMES: _lnames,
    REC_SEGDEF: _segdef,
    REC_SEGDEF32: _segdef,
    REC_PUBDEF: _pubdef,
    REC_PUBDEF32: _pubdef,
    REC_LPUBDEF: _pubdef,
    REC_LPUBDEF32: _pubdef,
    REC_EXTDEF: _extdef,
    REC_LEXTDEF: _extdef,
    REC_LEDATA: _ledata,
    REC_LEDATA32: _ledata,
}


def _read_record(data: bytes, pos: int) -> Record:
    if pos + _REC_BODY > len(data):
        raise OMFError(f"record at {pos:#x} runs past the end of the data ({len(data):#x})")
    kind = data[pos + _REC_TYPE]
    length = struct.unpack_from("<H", data, pos + _REC_LEN)[0]
    end = pos + _REC_BODY + length
    if length < _CHECKSUM_SIZE:
        raise OMFError(f"{record_name(kind)} record at {pos:#x} has length 0")
    if end > len(data):
        raise OMFError(
            f"{record_name(kind)} record at {pos:#x} runs past the end of the data "
            f"(length {length:#x}, data ends at {len(data):#x})"
        )
    return Record(kind, pos, bytes(data[pos + _REC_BODY : end - _CHECKSUM_SIZE]))


def iter_records(data: bytes, start: int = 0) -> Iterator[Record]:
    """Records of one module from `start` up to and including its MODEND."""
    pos = start
    while True:
        if pos >= len(data):
            raise OMFError(f"no MODEND record before the end of the data at {pos:#x}")
        rec = _read_record(data, pos)
        yield rec
        if rec.kind in _MODEND_KINDS:
            return
        pos = rec.end


def _build_module(records: list[Record], offset: int) -> Module:
    reader = _ModuleReader(offset)
    for rec in records:
        reader.feed(rec)
    return reader.freeze()


def read_object(data: bytes, *, offset: int = 0) -> Module:
    """The module whose THEADR is at `offset` (an object file, or one module of a library)."""
    return _build_module(list(iter_records(data, offset)), offset)


def is_omf_library(data: bytes) -> bool:
    """True for an OMF library (header record 0xF0); a COFF `!<arch>` archive is not one."""
    return len(data) > 0 and data[0] == REC_LIBHDR


def _page_size(data: bytes) -> int:
    header = _read_record(data, 0)
    page = len(header.body) + _CHECKSUM_SIZE + _LIB_PAGE_EXTRA  # record length + 3
    if page < _LIB_MIN_PAGE or page & (page - 1):
        raise OMFError(f"library page size {page} is not a power of two of at least 16")
    return page


def read_library(data: bytes, *, path: str = "") -> Library:
    """Every module of an OMF library, walked page by page from the header to the 0xF1 record.

    A module that fails to parse becomes a ModuleFailure and the walk resumes at the next page
    boundary after its MODEND. A module whose records cannot even be framed ends the walk, with
    that failure recorded.
    """
    if not is_omf_library(data):
        raise OMFError(f"{path or 'data'}: not an OMF library (no 0xF0 header record)")
    page = _page_size(data)
    modules: list[Module] = []
    failures: list[ModuleFailure] = []
    pos, number = page, 0
    while True:
        if pos >= len(data):
            raise OMFError(f"{path or 'library'}: no 0xF1 end record before {len(data):#x}")
        if data[pos] == REC_LIBEND:
            break
        number += 1
        try:
            records = list(iter_records(data, pos))
        except OMFError as exc:
            failures.append(ModuleFailure(number, pos, f"{exc}; walk stopped"))
            break
        try:
            modules.append(_build_module(records, pos))
        except OMFError as exc:
            failures.append(ModuleFailure(number, pos, str(exc)))
        pos = -(-records[-1].end // page) * page
    return Library(path, page, tuple(modules), tuple(failures))
