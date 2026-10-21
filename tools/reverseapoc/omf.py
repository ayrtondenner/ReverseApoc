"""Reader for Watcom OMF object modules and LIB libraries (TIS OMF 1.1).

Independent implementation from the TIS OMF 1.1 specification; no Open Watcom or KKND-Decomp code.

A record is a u8 type, a u16 length that counts the body and the checksum byte, the body, and the
checksum (never verified: Watcom tools do not always fill it in). Odd record types are the 32-bit
forms of the even ones. Supported records:

- THEADR (module name), LNAMES, SEGDEF/SEGDEF32, GRPDEF;
- EXTDEF/LEXTDEF, COMDEF/LCOMDEF and CEXTDEF, which together number the externals 1, 2, ...;
- PUBDEF/PUBDEF32/LPUBDEF/LPUBDEF32;
- LEDATA/LEDATA32, LIDATA/LIDATA32 (expanded, nesting capped at LIDATA_MAX_DEPTH, size bounded
  by the segment length), FIXUPP/FIXUPP32 with THREAD state, BAKPAT/BAKPAT32 (applied);
  NBKPAT/NBKPAT32 are only counted;
- COMDAT32 (named blocks with continuations and their fixups; C++ libraries keep code there);
- COMENT class 0x9B (memory model), 0x9F (default library), 0xAA (Easy OMF: the 16-bit-numbered
  records carry 32-bit offsets and lengths, while LIDATA repeat counts stay 16-bit),
  0xE9 (dependency: ignored);
- MODEND/MODEND32; in a library, the 0xF0 header (page size = its record length + 3) and the
  0xF1 end record.

Other record types are skipped by their length. Anything malformed (a record running past the
data, an index out of range, data past the end of its segment, an unknown fixup location) raises
OMFError naming the record type and its file offset. In a library a module that fails is
recorded in `Library.failures` and the walk goes on with the next module.

`normalized_object_sha1` hashes an object without its THEADR and COMENT 0xE9 records, which
carry the source path and timestamps, so compiles on different hosts can be compared.
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Iterator
from dataclasses import dataclass, field

# Record types (TIS OMF 1.1 record names).
REC_THEADR = 0x80  # translator header: the module name
REC_COMENT = 0x88  # comment: type byte, class byte, then class-specific text
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
REC_COMDEF = 0xB0  # communal names; they take external numbers
REC_BAKPAT = 0xB2  # backpatch: add values to already-written data
REC_BAKPAT32 = 0xB3
REC_LEXTDEF = 0xB4  # local (module-private) external names
REC_LPUBDEF = 0xB6  # local public names
REC_LPUBDEF32 = 0xB7
REC_LCOMDEF = 0xB8  # local communal names
REC_CEXTDEF = 0xBC  # COMDAT external names (LNAMES indexes)
REC_COMDAT32 = 0xC3  # initialized communal data
REC_NBKPAT = 0xC8  # named backpatch (COMDAT data)
REC_NBKPAT32 = 0xC9
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
    REC_COMDEF: "COMDEF",
    REC_BAKPAT: "BAKPAT",
    REC_BAKPAT32: "BAKPAT32",
    REC_LEXTDEF: "LEXTDEF",
    REC_LPUBDEF: "LPUBDEF",
    REC_LPUBDEF32: "LPUBDEF32",
    REC_LCOMDEF: "LCOMDEF",
    REC_CEXTDEF: "CEXTDEF",
    REC_COMDAT32: "COMDAT32",
    REC_NBKPAT: "NBKPAT",
    REC_NBKPAT32: "NBKPAT32",
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

# GRPDEF component descriptor.
_GRP_SEGMENT_INDEX = 0xFF  # a segment index follows

# COMENT body: comment type byte, class byte, then the text.
_COMENT_CLASS = 1
COMENT_MODEL = 0x9B  # memory model text, e.g. "3fOp"
COMENT_DEFAULT_LIBRARY = 0x9F  # default library name, e.g. "clib3r"
COMENT_EASY_OMF = 0xAA  # Phar Lap Easy OMF: 16-bit-numbered records carry 32-bit fields
COMENT_DEPENDENCY = 0xE9  # source dependency with a timestamp (differs between builds)

# FIXUPP subrecords. The first byte decides: FIXUP (high bit set) or THREAD.
LOCAT_FIXUP = 0x80  # subrecord is a FIXUP; clear = THREAD
LOCAT_M = 0x40  # segment-relative fixup; clear = self-relative
_LOCAT_TYPE_SHIFT = 2  # location type in bits 2-5 of the first locat byte
_LOCAT_TYPE_MASK = 0x0F
_LOCAT_OFFSET_MASK = 0x03FF  # 10-bit data-record offset across both locat bytes
THREAD_D = 0x40  # THREAD subrecord: frame thread; clear = target thread
_THREAD_METHOD_SHIFT = 2
_THREAD_METHOD_MASK = 0x07
_THREAD_NUMBER_MASK = 0x03
FIXDAT_F = 0x80  # frame comes from a frame thread
_FIXDAT_FRAME_SHIFT = 4
_FIXDAT_FRAME_MASK = 0x07
FIXDAT_T = 0x08  # target comes from a target thread
FIXDAT_P = 0x04  # no target displacement; also bit 2 of the target method (T4-T6)
_FIXDAT_TARGET_MASK = 0x03
_FRAME_DATUM_METHODS = 3  # frame methods F0-F2 carry an index; F4/F5 do not
_TARGET_FRAME_NUMBER = 3  # target method T3: the datum is a u16 frame number
_TARGET_KINDS = {0: "segment", 1: "group", 2: "extern", 3: "frame"}

# Fixup location types and the bytes each patches.
LOC_OFFSET32 = 9
LOC_POINTER48 = 11
LOC_SIZES = {
    0: 1,  # low byte
    1: 2,  # 16-bit offset
    2: 2,  # 16-bit base (selector)
    3: 4,  # 16:16 pointer
    4: 1,  # high byte
    5: 2,  # 16-bit loader-resolved offset
    LOC_OFFSET32: 4,  # 32-bit offset
    LOC_POINTER48: 6,  # 16:32 pointer
    13: 4,  # 32-bit loader-resolved offset
}

LIDATA_MAX_DEPTH = 8  # nesting levels of LIDATA blocks accepted

# BAKPAT location types and the bytes each patches.
_BAKPAT_SIZES = {0: 1, 1: 2, 2: 4}

# COMDEF: data type byte, then one communal length (two for FAR data).
_COMDEF_FAR = 0x61  # number of elements, then element size
_COMLEN_SHORT_MAX = 0x80  # a first byte up to 0x80 is the length itself
_COMLEN_WIDTHS = {0x81: 2, 0x84: 3, 0x88: 4}  # first byte -> width of the length that follows

# COMDAT32 header: flags, attributes, alignment, enumerated data offset, type index, public base
# (explicit allocation only), public name index, then the data.
COMDAT_CONTINUATION = 0x01  # flags: more data for the block of the same name
COMDAT_ITERATED = 0x02  # flags: the data is LIDATA-style blocks
_COMDAT_ALLOCATION_MASK = 0x0F  # attributes low nibble: allocation type
_COMDAT_EXPLICIT = 0  # explicit allocation: group index, segment index (frame if both 0)

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
    frame_method: int  # F0-F5
    target_method: int  # T0-T6; 4-6 are T0-T2 without a displacement
    target_kind: str  # "segment", "group", "extern" or "frame"
    target_index: int  # 1-based index of that kind (a frame number for "frame")
    target_name: str
    displacement: int  # 0 when the record has none


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
        return _patched(self.fixups) | self.backpatched


@dataclass(frozen=True)
class Comdat:
    """A named COMDAT32 block (C++ libraries keep their code in these)."""

    name: str
    segment_index: int  # 1-based SEGDEF number; 0 when not explicitly allocated
    alignment: int  # 0 = the segment's, 1 byte, 2 word, 3 paragraph, 4 page, 5 dword
    data: bytes
    fixups: tuple[OMFFixup, ...] = ()
    unmaskable: bool = False  # a FIXUPP addressed iterated data, so the mask is unknown

    @property
    def mask(self) -> frozenset[int]:
        """Every byte offset a fixup writes."""
        return _patched(self.fixups)


def _patched(fixups: tuple[OMFFixup, ...]) -> frozenset[int]:
    return frozenset(i for f in fixups for i in range(f.offset, f.offset + f.size))


@dataclass(frozen=True)
class Module:
    name: str
    offset: int  # file offset of the THEADR record
    segments: tuple[Segment, ...]
    publics: tuple[Public, ...]
    externs: tuple[str, ...]  # in external-number order (EXTDEF, COMDEF, CEXTDEF, ...)
    comdats: tuple[Comdat, ...] = ()
    model: str = ""
    default_libraries: tuple[str, ...] = ()
    easy_omf: bool = False
    nbkpat_records: int = 0  # NBKPAT/NBKPAT32 records seen (not applied)


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

    def raw(self, n: int) -> bytes:
        start = self._take(n)
        return self.body[start : start + n]

    def skip(self, n: int) -> None:
        self._take(n)

    def index(self) -> int:
        first = self.u8()
        if first & _INDEX_TWO_BYTES:
            return (first & _INDEX_HIGH_MASK) << 8 | self.u8()
        return first

    def name(self) -> str:
        return self.raw(self.u8()).decode("latin-1")

    def rest(self) -> bytes:
        return self.raw(len(self.body) - self.pos)


@dataclass
class _SegmentBuilder:
    index: int
    name: str
    class_name: str
    length: int
    use32: bool
    data: bytearray
    fixups: list[OMFFixup] = field(default_factory=list)
    unmaskable: bool = False
    backpatched: set[int] = field(default_factory=set)

    def check_range(self, offset: int, size: int, what: str) -> None:
        if offset + size > self.length:
            raise OMFError(
                f"{what} {offset:#x}..{offset + size:#x} runs past segment {self.name!r} "
                f"({self.length:#x} bytes)"
            )

    def check_write(self, offset: int, size: int, what: str) -> None:
        self.check_range(offset, size, what)

    def freeze(self) -> Segment:
        return Segment(self.index, self.name, self.class_name, self.length, self.use32,
                       bytes(self.data), tuple(self.fixups), self.unmaskable,
                       frozenset(self.backpatched))  # fmt: skip


@dataclass
class _ComdatBuilder:
    """A COMDAT block; it grows as its records (first and continuations) write into it."""

    name: str
    segment_index: int
    alignment: int
    data: bytearray = field(default_factory=bytearray)
    fixups: list[OMFFixup] = field(default_factory=list)
    unmaskable: bool = False

    def check_range(self, offset: int, size: int, what: str) -> None:
        if offset + size > len(self.data):
            raise OMFError(
                f"{what} {offset:#x}..{offset + size:#x} runs past COMDAT {self.name!r} "
                f"({len(self.data):#x} bytes)"
            )

    def check_write(self, offset: int, size: int, what: str) -> None:
        """Bounds the block like a segment, then zero-extends it to cover the write."""
        if offset + size > MAX_SEGMENT_LENGTH:
            raise OMFError(
                f"{what} {offset:#x}..{offset + size:#x} exceeds {MAX_SEGMENT_LENGTH:#x}"
            )
        self.data.extend(bytes(max(0, offset + size - len(self.data))))

    def freeze(self) -> Comdat:
        return Comdat(self.name, self.segment_index, self.alignment, bytes(self.data),
                      tuple(self.fixups), self.unmaskable)  # fmt: skip


@dataclass(frozen=True)
class _DataRecord:
    """The data record a following FIXUPP refers to."""

    target: _SegmentBuilder | _ComdatBuilder
    offset: int  # offset in the target where the record's data starts
    iterated: bool  # LIDATA-style data: fixup offsets address the record, not the expanded bytes


@dataclass
class _ModuleReader:
    """Accumulates one module's records; each handler below reads one record type."""

    offset: int
    name: str = ""
    lnames: list[str] = field(default_factory=list)
    segments: list[_SegmentBuilder] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    publics: list[Public] = field(default_factory=list)
    externs: list[str] = field(default_factory=list)
    comdats: list[_ComdatBuilder] = field(default_factory=list)
    comdat_by_name: dict[str, _ComdatBuilder] = field(default_factory=dict)  # for continuations
    model: str = ""
    default_libraries: list[str] = field(default_factory=list)
    easy_omf: bool = False
    nbkpat_records: int = 0
    frame_threads: dict[int, tuple[int, int]] = field(default_factory=dict)
    target_threads: dict[int, tuple[int, int]] = field(default_factory=dict)
    last_data: _DataRecord | None = None

    def feed(self, rec: Record) -> None:
        handler = _HANDLERS.get(rec.kind)
        if handler is None:
            return
        try:
            handler(self, _Cursor(rec.body), rec)
        except OMFError as exc:
            raise OMFError(f"{rec.name} record at {rec.offset:#x}: {exc}") from exc

    def wide(self, rec: Record) -> bool:
        """32-bit fields: an odd record type, or any record of an Easy OMF module."""
        return bool(rec.kind & _WIDE_BIT) or self.easy_omf

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

    def group(self, idx: int) -> str:
        if not 1 <= idx <= len(self.groups):
            raise OMFError(f"group index {idx} out of range ({len(self.groups)} groups)")
        return self.groups[idx - 1]

    def extern(self, idx: int) -> str:
        if not 1 <= idx <= len(self.externs):
            raise OMFError(f"extern index {idx} out of range ({len(self.externs)} externs)")
        return self.externs[idx - 1]

    def datum_name(self, method: int, idx: int) -> str:
        """Name of a frame or target datum: methods 0-2 name a segment, group or extern."""
        kind = method & _FIXDAT_TARGET_MASK
        if kind == 0:
            return self.segment(idx).name
        if kind == 1:
            return self.group(idx)
        if kind == 2:
            return self.extern(idx)
        return ""

    def freeze(self) -> Module:
        return Module(
            name=self.name,
            offset=self.offset,
            segments=tuple(s.freeze() for s in self.segments),
            publics=tuple(self.publics),
            externs=tuple(self.externs),
            comdats=tuple(c.freeze() for c in self.comdats),
            model=self.model,
            default_libraries=tuple(self.default_libraries),
            easy_omf=self.easy_omf,
            nbkpat_records=self.nbkpat_records,
        )


def _theadr(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    m.name = cur.name()


def _coment(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    cur.u8()  # comment type flags
    if cur.at_end():
        return
    cls = cur.u8()
    if cls == COMENT_EASY_OMF:
        m.easy_omf = True
    elif cls == COMENT_MODEL:
        m.model = cur.rest().decode("latin-1")
    elif cls == COMENT_DEFAULT_LIBRARY:
        m.default_libraries.append(cur.rest().decode("latin-1"))


def _lnames(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    while not cur.at_end():
        m.lnames.append(cur.name())


def _segdef(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    attr = cur.u8()
    if attr >> _SEG_ALIGN_SHIFT == _SEG_ALIGN_ABSOLUTE:
        cur.skip(_SEG_ABS_FRAME_SIZE)
    length = m.offset_field(cur, rec)
    if attr & _SEG_BIG:
        if m.wide(rec):
            raise OMFError("a 4 GiB segment (B bit in a 32-bit SEGDEF) is not supported")
        length = _SEG_BIG16_LENGTH
    if length > MAX_SEGMENT_LENGTH:
        raise OMFError(f"segment length {length:#x} exceeds {MAX_SEGMENT_LENGTH:#x}")
    name, class_name = m.lname(cur.index()), m.lname(cur.index())
    cur.index()  # overlay name: unused; an Easy OMF access byte may follow and is ignored
    seg = _SegmentBuilder(len(m.segments) + 1, name, class_name, length,
                          bool(attr & _SEG_USE32), bytearray(length))  # fmt: skip
    m.segments.append(seg)


def _grpdef(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    name = m.lname(cur.index())
    while not cur.at_end():
        kind = cur.u8()
        if kind != _GRP_SEGMENT_INDEX:
            raise OMFError(f"group component type {kind:#04x} is not a segment index")
        m.segment(cur.index())
    m.groups.append(name)


def _pubdef(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    group, seg = cur.index(), cur.index()
    if group:
        m.group(group)
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


def _communal_length(cur: _Cursor) -> int:
    first = cur.u8()
    if first <= _COMLEN_SHORT_MAX:
        return first
    width = _COMLEN_WIDTHS.get(first)
    if width is None:
        raise OMFError(f"communal length prefix {first:#04x} is not 0x81, 0x84 or 0x88")
    return int.from_bytes(cur.raw(width), "little")


def _comdef(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    while not cur.at_end():
        m.externs.append(cur.name())
        cur.index()  # type index
        data_type = cur.u8()
        _communal_length(cur)
        if data_type == _COMDEF_FAR:
            _communal_length(cur)


def _cextdef(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    while not cur.at_end():
        m.externs.append(m.lname(cur.index()))
        cur.index()  # type index


def _ledata(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    seg = m.segment(cur.index())
    offset = m.offset_field(cur, rec)
    data = cur.rest()
    seg.check_write(offset, len(data), "data")
    seg.data[offset : offset + len(data)] = data
    m.last_data = _DataRecord(seg, offset, iterated=False)


# A parsed LIDATA block: (repeat count, content bytes or nested blocks).
type _Block = tuple[int, bytes | list[_Block]]


def _lidata_block(cur: _Cursor, repeat32: bool, depth: int) -> _Block:
    if depth > LIDATA_MAX_DEPTH:
        raise OMFError(f"iterated data nesting depth exceeds {LIDATA_MAX_DEPTH}")
    repeat = cur.u32() if repeat32 else cur.u16()
    count = cur.u16()
    if count == 0:
        return repeat, cur.raw(cur.u8())
    return repeat, [_lidata_block(cur, repeat32, depth + 1) for _ in range(count)]


def _block_size(block: _Block) -> int:
    repeat, content = block
    if isinstance(content, bytes):
        return repeat * len(content)
    return repeat * sum(_block_size(b) for b in content)


def _expand(block: _Block) -> bytes:
    repeat, content = block
    if isinstance(content, bytes):
        return content * repeat
    return b"".join(_expand(b) for b in content) * repeat


def _write_iterated(
    target: _SegmentBuilder | _ComdatBuilder, offset: int, cur: _Cursor, rec: Record
) -> None:
    """Expands the remaining blocks of `cur` into `target` at `offset`."""
    # Easy OMF widens the data offset of record 0xA2 but not its repeat counts: only the 32-bit
    # records have 32-bit ones (a real Easy OMF LIDATA record parses to its last byte only so).
    repeat32 = bool(rec.kind & _WIDE_BIT)
    blocks: list[_Block] = []
    while not cur.at_end():
        blocks.append(_lidata_block(cur, repeat32, 1))
    size = sum(_block_size(b) for b in blocks)  # checked before anything is expanded
    target.check_write(offset, size, "iterated data")
    target.data[offset : offset + size] = b"".join(_expand(b) for b in blocks)


def _lidata(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    seg = m.segment(cur.index())
    offset = m.offset_field(cur, rec)
    _write_iterated(seg, offset, cur, rec)
    m.last_data = _DataRecord(seg, offset, iterated=True)


def _comdat_block(m: _ModuleReader, flags: int, name: str, seg: int, align: int) -> _ComdatBuilder:
    if flags & COMDAT_CONTINUATION:
        block = m.comdat_by_name.get(name)
        if block is None:
            raise OMFError(f"continuation of COMDAT {name!r} with no first record")
        return block
    block = _ComdatBuilder(name, seg, align)
    m.comdats.append(block)
    m.comdat_by_name[name] = block
    return block


def _comdat(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    flags, attributes, alignment = cur.u8(), cur.u8(), cur.u8()
    offset = m.offset_field(cur, rec)  # enumerated data offset
    cur.index()  # type index
    seg = 0
    if attributes & _COMDAT_ALLOCATION_MASK == _COMDAT_EXPLICIT:
        group, seg = cur.index(), cur.index()
        if group:
            m.group(group)
        if seg:
            m.segment(seg)
        elif not group:
            cur.u16()  # base frame
    block = _comdat_block(m, flags, m.lname(cur.index()), seg, alignment)
    iterated = bool(flags & COMDAT_ITERATED)
    if iterated:
        _write_iterated(block, offset, cur, rec)
    else:
        data = cur.rest()
        block.check_write(offset, len(data), "data")
        block.data[offset : offset + len(data)] = data
    m.last_data = _DataRecord(block, offset, iterated)


def _thread(m: _ModuleReader, cur: _Cursor, first: int) -> None:
    method = first >> _THREAD_METHOD_SHIFT & _THREAD_METHOD_MASK
    number = first & _THREAD_NUMBER_MASK
    if first & THREAD_D:
        idx = cur.index() if method < _FRAME_DATUM_METHODS else 0
        m.frame_threads[number] = (method, idx)
        return
    method &= _FIXDAT_TARGET_MASK  # the P bit of each FIXUP supplies bit 2
    idx = cur.u16() if method == _TARGET_FRAME_NUMBER else cur.index()
    m.target_threads[number] = (method, idx)


def _frame(m: _ModuleReader, cur: _Cursor, fixdat: int) -> int:
    field_value = fixdat >> _FIXDAT_FRAME_SHIFT & _FIXDAT_FRAME_MASK
    if fixdat & FIXDAT_F:
        number = field_value & _THREAD_NUMBER_MASK
        if number not in m.frame_threads:
            raise OMFError(f"frame thread {number} is not defined")
        return m.frame_threads[number][0]
    if field_value < _FRAME_DATUM_METHODS:
        m.datum_name(field_value, cur.index())  # validates the index
    return field_value


def _target(m: _ModuleReader, cur: _Cursor, fixdat: int) -> tuple[int, int]:
    """(low two bits of the target method, datum index)."""
    low = fixdat & _FIXDAT_TARGET_MASK
    if fixdat & FIXDAT_T:
        if low not in m.target_threads:
            raise OMFError(f"target thread {low} is not defined")
        return m.target_threads[low]
    idx = cur.u16() if low == _TARGET_FRAME_NUMBER else cur.index()
    return low, idx


def _fixup(m: _ModuleReader, cur: _Cursor, rec: Record, first: int) -> None:
    data = m.last_data
    if data is None:
        raise OMFError("FIXUP subrecord with no preceding LEDATA, LIDATA or COMDAT record")
    locat = first << 8 | cur.u8()
    location = first >> _LOCAT_TYPE_SHIFT & _LOCAT_TYPE_MASK
    size = LOC_SIZES.get(location)
    if size is None:
        raise OMFError(f"unknown location type {location}")
    fixdat = cur.u8()
    frame_method = _frame(m, cur, fixdat)
    low, target_index = _target(m, cur, fixdat)
    target_name = m.datum_name(low, target_index)
    displacement = 0 if fixdat & FIXDAT_P else m.offset_field(cur, rec)
    if data.iterated:
        data.target.unmaskable = True  # the offset addresses the iterated record itself
        return
    offset = data.offset + (locat & _LOCAT_OFFSET_MASK)
    data.target.check_range(offset, size, "fixup")
    data.target.fixups.append(
        OMFFixup(
            offset=offset,
            size=size,
            segment_relative=bool(first & LOCAT_M),
            location=location,
            frame_method=frame_method,
            target_method=low | (fixdat & FIXDAT_P),
            target_kind=_TARGET_KINDS[low],
            target_index=target_index,
            target_name=target_name,
            displacement=displacement,
        )
    )


def _fixupp(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    while not cur.at_end():
        first = cur.u8()
        if first & LOCAT_FIXUP:
            _fixup(m, cur, rec, first)
        else:
            _thread(m, cur, first)


def _bakpat(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    seg = m.segment(cur.index())
    location = cur.u8()
    size = _BAKPAT_SIZES.get(location)
    if size is None:
        raise OMFError(f"unknown backpatch location type {location}")
    while not cur.at_end():
        offset, value = m.offset_field(cur, rec), m.offset_field(cur, rec)
        seg.check_range(offset, size, "backpatch")
        old = int.from_bytes(seg.data[offset : offset + size], "little")
        new = (old + value) & ((1 << 8 * size) - 1)
        seg.data[offset : offset + size] = new.to_bytes(size, "little")
        seg.backpatched.update(range(offset, offset + size))


def _nbkpat(m: _ModuleReader, cur: _Cursor, rec: Record) -> None:
    m.nbkpat_records += 1


_HANDLERS = {
    REC_THEADR: _theadr,
    REC_COMENT: _coment,
    REC_LNAMES: _lnames,
    REC_SEGDEF: _segdef,
    REC_SEGDEF32: _segdef,
    REC_GRPDEF: _grpdef,
    REC_PUBDEF: _pubdef,
    REC_PUBDEF32: _pubdef,
    REC_LPUBDEF: _pubdef,
    REC_LPUBDEF32: _pubdef,
    REC_EXTDEF: _extdef,
    REC_LEXTDEF: _extdef,
    REC_COMDEF: _comdef,
    REC_LCOMDEF: _comdef,
    REC_CEXTDEF: _cextdef,
    REC_LEDATA: _ledata,
    REC_LEDATA32: _ledata,
    REC_LIDATA: _lidata,
    REC_LIDATA32: _lidata,
    REC_FIXUPP: _fixupp,
    REC_FIXUPP32: _fixupp,
    REC_BAKPAT: _bakpat,
    REC_BAKPAT32: _bakpat,
    REC_NBKPAT: _nbkpat,
    REC_NBKPAT32: _nbkpat,
    REC_COMDAT32: _comdat,
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


def _host_specific(rec: Record) -> bool:
    """THEADR and COMENT 0xE9 name the source path and its timestamp."""
    if rec.kind == REC_THEADR:
        return True
    return (
        rec.kind == REC_COMENT
        and len(rec.body) > _COMENT_CLASS
        and rec.body[_COMENT_CLASS] == COMENT_DEPENDENCY
    )


def normalized_object_sha1(data: bytes) -> str:
    """SHA-1 over the raw bytes of every record up to MODEND except the host-specific ones."""
    digest = hashlib.sha1()
    for rec in iter_records(data):
        if not _host_specific(rec):
            digest.update(data[rec.offset : rec.end])
    return digest.hexdigest()


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
