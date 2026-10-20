# Derived from KKND-Decomp tools/le.py (CC0 1.0), https://github.com/Wyrelade/KKND-Decomp
"""Linear Executable (LE) reader for DOS/4GW-bound Watcom executables.

A bound DOS/4GW Professional executable is: the DOS/4GW loader (an MZ program with the extender
appended) + the Watcom MZ stub + the LE header and its loader/fixup tables + the data pages.
The e_lfanew field (0x3C) of the *first* MZ does not point at the LE header in that layout, so
the header is found by scanning for an "LE\\0\\0" signature that some MZ header's e_lfanew
points at. That MZ is the "stub" that owns the LE image: the data-pages offset in the LE header
is relative to it, not to the start of the file. Its file offset is the size of the bound
extender in front of it (`stub_offset`, reported as `stub_size`).

Only what Watcom's flat-model wlink emits is supported: physical pages and internal-reference
fixups. Iterated/zero-filled/invalid pages, imported (ordinal or name) fixups, entry-table
targets, additive and chained fixups raise `LEUnsupportedError` instead of being mis-parsed.

Fixups are returned as `Fixup(src_va, kind, target_va, target_obj, target_off, size)`: `src_va`
is the linear address of the patched field, `target_va` the linear address it resolves to
(target object base + offset). Pages in the file hold *unrelocated* bytes, which is what
matching wants; `load_flat(relocate=True)` applies the linear fixups like the loader would.
"""

from __future__ import annotations

import hashlib
import os
import struct
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LE_SIGNATURE = b"LE\x00\x00"  # "LE", little-endian byte order, little-endian word order

# Fixup source types (low nibble of the source byte).
SRC_BYTE = 0x00
SRC_SEL16 = 0x02
SRC_PTR1616 = 0x03
SRC_OFF16 = 0x05
SRC_PTR1632 = 0x06
SRC_OFF32 = 0x07
SRC_REL32 = 0x08
SRC_SIZE = {
    SRC_BYTE: 1,
    SRC_SEL16: 2,
    SRC_PTR1616: 4,
    SRC_OFF16: 2,
    SRC_PTR1632: 6,
    SRC_OFF32: 4,
    SRC_REL32: 4,
}
SRC_NAME = {
    SRC_BYTE: "byte",
    SRC_SEL16: "sel16",
    SRC_PTR1616: "ptr16:16",
    SRC_OFF16: "off16",
    SRC_PTR1632: "ptr16:32",
    SRC_OFF32: "off32",
    SRC_REL32: "rel32",
}
SRC_ALIAS = 0x10  # fixup to a 16:16 alias; does not change the record layout, ignored
SRC_LIST = 0x20  # a source offset list follows the target data

# Fixup target flags.
TGT_TYPE_MASK = 0x03
TGT_INTERNAL = 0x00
TGT_IMPORT_ORDINAL = 0x01
TGT_IMPORT_NAME = 0x02
TGT_ENTRY = 0x03
TGT_ADDITIVE = 0x04
TGT_CHAIN = 0x08
TGT_OFF32 = 0x10
TGT_OBJ16 = 0x40

# LE header fields that place data outside the loader and fixup sections (offsets relative to
# the LE header). Read only so that a file using them can be refused instead of mis-tiled.
_HDR_NONRES_NAME_TABLE_OFFSET = 0x88  # u32: non-resident name table offset
_HDR_NONRES_NAME_TABLE_LENGTH = 0x8C  # u32: non-resident name table length in bytes
_HDR_DEBUG_INFO_OFFSET = 0x98  # u32: debug information offset
_HDR_DEBUG_INFO_LENGTH = 0x9C  # u32: debug information length in bytes

PAGE_PHYSICAL = 0x00
PAGE_FLAG_NAMES = {0: "physical", 1: "iterated", 2: "invalid", 3: "zero-filled", 4: "range"}

_OBJ_FLAG_WORDS = [
    (0x0008, "resource"),
    (0x0010, "discard"),
    (0x0020, "shared"),
    (0x0040, "preload"),
    (0x0080, "invalid"),
    (0x0100, "zerofill"),
    (0x0200, "resident"),
    (0x0400, "lockable"),
    (0x1000, "alias16"),
    (0x2000, "big"),
    (0x4000, "conforming"),
    (0x8000, "iopl"),
]


class LEError(ValueError):
    """The file is not a well-formed LE executable."""


class LEUnsupportedError(LEError):
    """The file uses an LE feature this parser deliberately does not handle."""


@dataclass(frozen=True)
class LEObject:
    index: int  # 1-based object number
    vsize: int
    base: int  # relocation base address (linear)
    flags: int
    page_index: int  # first logical page (1-based) in the object page map
    page_count: int
    reserved: int = 0

    @property
    def end(self) -> int:
        return self.base + self.vsize

    def contains(self, va: int) -> bool:
        return self.base <= va < self.end

    @property
    def flags_text(self) -> str:
        f = self.flags
        rwx = ("R" if f & 1 else "-") + ("W" if f & 2 else "-") + ("X" if f & 4 else "-")
        words = [name for bit, name in _OBJ_FLAG_WORDS if f & bit]
        known = 0x7 | sum(bit for bit, _ in _OBJ_FLAG_WORDS)
        if f & ~known:
            words.append(f"{f & ~known:#x}")
        return " ".join([rwx, *words])


@dataclass(frozen=True)
class LEPage:
    logical: int  # 1-based index in the object page map
    number: int  # 1-based physical page number in the data pages
    flags: int
    file_offset: int
    size: int


@dataclass(frozen=True, order=True)
class Fixup:
    src_va: int
    kind: int
    target_va: int
    target_obj: int
    target_off: int
    size: int

    @property
    def kind_name(self) -> str:
        return SRC_NAME.get(self.kind, f"type{self.kind:#x}")


class _Cursor:
    """Bounds-checked little-endian reader over one page's fixup records."""

    def __init__(self, data: bytes, pos: int, stop: int, logical: int) -> None:
        self.data, self.pos, self.stop, self.logical = data, pos, stop, logical
        self.record = pos

    def _take(self, fmt: str, n: int) -> int:
        if self.pos + n > self.stop:
            raise LEError(
                f"fixup record at {self.record:#x} overruns the record range of logical page "
                f"{self.logical} (ends at {self.stop:#x})"
            )
        value = struct.unpack_from(fmt, self.data, self.pos)[0]
        self.pos += n
        return value

    def u8(self) -> int:
        return self._take("<B", 1)

    def u16(self) -> int:
        return self._take("<H", 2)

    def s16(self) -> int:
        return self._take("<h", 2)

    def u32(self) -> int:
        return self._take("<I", 4)


class LE:
    """Parsed LE executable. `source` is a path or the raw file bytes."""

    def __init__(self, source: bytes | bytearray | memoryview | str | os.PathLike[str]) -> None:
        if isinstance(source, (bytes, bytearray, memoryview)):
            self.path: Path | None = None
            self.data = bytes(source)
        else:
            self.path = Path(source)
            self.data = self.path.read_bytes()
        self._fixups: list[Fixup] | None = None

        self.le_offset, self.stub_offset = self._locate_header()
        h = self._header_u32
        self.num_pages = h(0x14)
        self.eip_obj, self.eip = h(0x18), h(0x1C)
        self.esp_obj, self.esp = h(0x20), h(0x24)
        self.page_size = h(0x28)
        self.last_page_size = h(0x2C)
        self.fixup_section_size = h(0x30)
        self.loader_section_size = h(0x38)
        self.object_table_offset = self.le_offset + h(0x40)
        self.num_objects = h(0x44)
        self.page_map_offset = self.le_offset + h(0x48)
        self.fixup_page_table_offset = self.le_offset + h(0x68)
        self.fixup_record_table_offset = self.le_offset + h(0x6C)
        # Unlike the other table offsets, the data-pages offset is relative to the MZ stub that
        # owns this LE header (0x352A4 in UFO2P/TACP, behind the bound DOS/4GW loader).
        self.data_pages_offset = self.stub_offset + h(0x80)
        # Raw values; a reader that tiles the file refuses them when non-zero.
        self.nonres_name_table_offset = h(_HDR_NONRES_NAME_TABLE_OFFSET)
        self.nonres_name_table_length = h(_HDR_NONRES_NAME_TABLE_LENGTH)
        self.debug_info_offset = h(_HDR_DEBUG_INFO_OFFSET)
        self.debug_info_length = h(_HDR_DEBUG_INFO_LENGTH)

        if self.page_size == 0 or self.page_size & (self.page_size - 1):
            raise LEError(f"page size {self.page_size:#x} is not a power of two")
        self.objects = self._read_objects()
        self.pages = self._read_page_map()
        for obj in (self.eip_obj, self.esp_obj):
            if obj > len(self.objects):
                raise LEError(f"entry/stack object {obj} does not exist")

    # -- locating and reading tables ---------------------------------------------------------

    def _u32(self, off: int) -> int:
        if off < 0 or off + 4 > len(self.data):
            raise LEError(f"truncated file: need 4 bytes at {off:#x}, size {len(self.data):#x}")
        return struct.unpack_from("<I", self.data, off)[0]

    def _header_u32(self, field: int) -> int:
        return self._u32(self.le_offset + field)

    def _locate_header(self) -> tuple[int, int]:
        d = self.data
        if len(d) < 0x40 or d[:2] != b"MZ":
            raise LEError("not an MZ executable")
        lfanew = self._u32(0x3C)
        if d[lfanew : lfanew + 4] == LE_SIGNATURE:
            return lfanew, 0
        # Bound executable: find an LE signature that some later MZ header points at.
        pos = d.find(LE_SIGNATURE)
        while pos >= 0:
            owner = self._owning_mz(pos)
            if owner is not None:
                return pos, owner
            pos = d.find(LE_SIGNATURE, pos + 1)
        raise LEError("no LE header found (no MZ header's e_lfanew points at an LE signature)")

    def _owning_mz(self, le_off: int) -> int | None:
        d = self.data
        i = le_off
        while True:
            i = d.rfind(b"MZ", 0, i)
            if i < 0:
                return None
            if i + 0x40 <= len(d) and i + self._u32(i + 0x3C) == le_off:
                return i

    def _read_objects(self) -> list[LEObject]:
        objects = []
        for i in range(self.num_objects):
            off = self.object_table_offset + 24 * i
            if off + 24 > len(self.data):
                raise LEError(f"truncated file: object table entry {i + 1} at {off:#x}")
            vsize, base, flags, page_index, page_count, reserved = struct.unpack_from(
                "<6I", self.data, off
            )
            last_page = page_index + page_count - 1
            if page_count and not (1 <= page_index and last_page <= self.num_pages):
                raise LEError(
                    f"object {i + 1} pages {page_index}..{last_page} "
                    f"are outside the page map (1..{self.num_pages})"
                )
            objects.append(LEObject(i + 1, vsize, base, flags, page_index, page_count, reserved))
        return objects

    def _read_page_map(self) -> list[LEPage]:
        pages = []
        for logical in range(1, self.num_pages + 1):
            off = self.page_map_offset + 4 * (logical - 1)
            if off + 4 > len(self.data):
                raise LEError(f"truncated file: page map entry {logical} at {off:#x}")
            hi, mid, lo, flags = self.data[off : off + 4]
            number = (hi << 16) | (mid << 8) | lo
            size = self.last_page_size if number == self.num_pages else self.page_size
            file_offset = self.data_pages_offset + (number - 1) * self.page_size
            pages.append(LEPage(logical, number, flags, file_offset, size))
        return pages

    # -- queries -----------------------------------------------------------------------------

    @property
    def entry_va(self) -> int | None:
        if self.eip_obj == 0:
            return None
        return self.objects[self.eip_obj - 1].base + self.eip

    @property
    def pages_end(self) -> int:
        """File offset just past the last data page (the short last page included)."""
        if self.num_pages == 0:
            return self.data_pages_offset
        return self.data_pages_offset + (self.num_pages - 1) * self.page_size + self.last_page_size

    @property
    def stack_va(self) -> int | None:
        if self.esp_obj == 0:
            return None
        return self.objects[self.esp_obj - 1].base + self.esp

    def obj_of_va(self, va: int) -> LEObject | None:
        for obj in self.objects:
            if obj.contains(va):
                return obj
        return None

    def page_va(self, logical: int) -> int:
        """Linear address of logical page `logical` (1-based)."""
        for obj in self.objects:
            if obj.page_index <= logical < obj.page_index + obj.page_count:
                return obj.base + (logical - obj.page_index) * self.page_size
        raise LEError(f"logical page {logical} belongs to no object")

    # -- fixups ------------------------------------------------------------------------------

    def fixups(self) -> list[Fixup]:
        """All fixups, sorted by source address. A field that straddles a page boundary is
        listed on both pages in the file; it is returned once."""
        if self._fixups is None:
            self._fixups = self._parse_fixups()
        return list(self._fixups)

    def _parse_fixups(self) -> list[Fixup]:
        found: dict[int, Fixup] = {}
        table = self.fixup_page_table_offset
        records = self.fixup_record_table_offset
        for logical in range(1, self.num_pages + 1):
            start = self._u32(table + 4 * (logical - 1))
            end = self._u32(table + 4 * logical)
            if end < start:
                raise LEError(f"fixup page table entry {logical} ends before it starts")
            if records + end > len(self.data):
                raise LEError(f"truncated file: fixup records of logical page {logical}")
            if start == end:
                continue
            page_va = self.page_va(logical)
            cur = _Cursor(self.data, records + start, records + end, logical)
            while cur.pos < cur.stop:
                cur.record = cur.pos
                for fx in self._parse_record(cur, page_va):
                    prev = found.setdefault(fx.src_va, fx)
                    if prev != fx:
                        raise LEError(f"conflicting fixups at {fx.src_va:#x}: {prev} vs {fx}")
        return sorted(found.values())

    def _parse_record(self, cur: _Cursor, page_va: int) -> list[Fixup]:
        where = f"fixup record at {cur.record:#x} (logical page {cur.logical})"
        src, flg = cur.u8(), cur.u8()
        kind = src & 0x0F
        if kind not in SRC_SIZE:
            raise LEUnsupportedError(f"{where}: source type {kind:#x} is not supported")
        target_type = flg & TGT_TYPE_MASK
        if target_type == TGT_IMPORT_ORDINAL:
            raise LEUnsupportedError(f"{where}: imported ordinal fixups are not supported")
        if target_type == TGT_IMPORT_NAME:
            raise LEUnsupportedError(f"{where}: imported name fixups are not supported")
        if target_type == TGT_ENTRY:
            raise LEUnsupportedError(f"{where}: entry table fixups are not supported")
        if flg & TGT_ADDITIVE:
            raise LEUnsupportedError(f"{where}: additive fixups are not supported")
        if flg & TGT_CHAIN:
            raise LEUnsupportedError(f"{where}: chained fixups are not supported")

        count = cur.u8() if src & SRC_LIST else 0
        offsets = [] if src & SRC_LIST else [cur.s16()]
        target_obj = cur.u16() if flg & TGT_OBJ16 else cur.u8()
        if kind == SRC_SEL16:
            target_off = 0  # a selector fixup has no target offset
        else:
            target_off = cur.u32() if flg & TGT_OFF32 else cur.u16()
        if src & SRC_LIST:
            offsets = [cur.s16() for _ in range(count)]
        if not 1 <= target_obj <= len(self.objects):
            raise LEError(f"{where}: target object {target_obj} does not exist")
        target_va = self.objects[target_obj - 1].base + target_off
        size = SRC_SIZE[kind]
        return [Fixup(page_va + o, kind, target_va, target_obj, target_off, size) for o in offsets]

    # -- loading -----------------------------------------------------------------------------

    def load_flat(self, relocate: bool = False) -> bytearray:
        """Return a zero-filled bytearray indexed by linear address with every object's page
        data copied in at its base (bytes past an object's page data, i.e. bss, stay zero).

        With `relocate=True` the linear fixups are applied: off32 and the offset half of
        ptr16:32 get the target address, rel32 gets target - (field + 4). Selector, byte and
        16-bit fields keep their raw file contents."""
        if not self.objects:
            return bytearray()
        flat = bytearray(max(obj.end for obj in self.objects))
        for obj in self.objects:
            for k in range(obj.page_count):
                dst = k * self.page_size
                if dst >= obj.vsize:
                    break
                page = self.pages[obj.page_index + k - 1]
                self.check_loadable(obj, page)
                n = min(page.size, obj.vsize - dst)
                flat[obj.base + dst : obj.base + dst + n] = self.data[
                    page.file_offset : page.file_offset + n
                ]
        if relocate:
            self._relocate(flat)
        return flat

    def check_loadable(self, obj: LEObject, page: LEPage) -> None:
        """Raise unless `page` of `obj` is a physical page whose bytes lie inside the file."""
        if page.flags != PAGE_PHYSICAL:
            name = PAGE_FLAG_NAMES.get(page.flags, "unknown")
            raise LEUnsupportedError(
                f"object {obj.index}: page {page.logical} is {name} (page map flags "
                f"{page.flags:#x}); only physical pages are supported"
            )
        if not 1 <= page.number <= self.num_pages:
            raise LEError(f"page {page.logical} maps to physical page {page.number}")
        end = page.file_offset + page.size
        if end > len(self.data):
            raise LEError(
                f"truncated file: page {page.logical} needs bytes {page.file_offset:#x}.."
                f"{end:#x}, file is {len(self.data):#x} bytes"
            )

    def _relocate(self, flat: bytearray) -> None:
        for fx in self.fixups():
            if fx.kind in (SRC_OFF32, SRC_PTR1632):
                value = fx.target_va
            elif fx.kind == SRC_REL32:
                value = (fx.target_va - (fx.src_va + 4)) & 0xFFFFFFFF
            else:
                continue
            if not 0 <= fx.src_va <= len(flat) - 4:
                raise LEError(f"fixup field at {fx.src_va:#x} lies outside the loaded image")
            struct.pack_into("<I", flat, fx.src_va, value)

    # -- reporting ---------------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Layout summary as plain JSON-serialisable data."""
        fixups = self.fixups()
        kinds = Counter(fx.kind for fx in fixups)
        return {
            "file": str(self.path) if self.path else None,
            "file_size": len(self.data),
            "stub_size": self.stub_offset,
            "le_offset": self.le_offset,
            "page_size": self.page_size,
            "last_page_size": self.last_page_size,
            "num_pages": self.num_pages,
            "data_pages_offset": self.data_pages_offset,
            "entry": {"object": self.eip_obj, "offset": self.eip, "linear": self.entry_va},
            "stack": {"object": self.esp_obj, "offset": self.esp, "linear": self.stack_va},
            "objects": [
                {
                    "index": obj.index,
                    "base": obj.base,
                    "vsize": obj.vsize,
                    "end": obj.end,
                    "flags": obj.flags,
                    "flags_text": obj.flags_text,
                    "first_page": obj.page_index,
                    "pages": obj.page_count,
                }
                for obj in self.objects
            ],
            "fixup_count": len(fixups),
            "fixup_kinds": {SRC_NAME[k]: kinds[k] for k in sorted(kinds)},
            "trailer": self._trailer(),
        }

    def _trailer(self) -> dict[str, Any]:
        """The bytes after the last page as offset, length and SHA-1, never the bytes (D-11).
        A truncated file reports length 0 instead of raising."""
        return {
            "offset": self.pages_end,
            "length": max(0, len(self.data) - self.pages_end),
            "sha1": hashlib.sha1(self.data[self.pages_end :]).hexdigest(),
        }


def _hex(value: int | None) -> str:
    return "-" if value is None else f"{value:#010x}"


def format_summary(s: dict[str, Any]) -> str:
    """Render `LE.summary()` as aligned text."""
    rows = [
        ("file", f"{s['file'] or '<bytes>'} ({s['file_size']} bytes)"),
        ("stub size", f"{_hex(s['stub_size'])} ({s['stub_size']} bytes before the LE's MZ stub)"),
        ("LE header", _hex(s["le_offset"])),
        (
            "pages",
            f"{s['num_pages']} x {s['page_size']} bytes (last page {s['last_page_size']}), "
            f"data at {_hex(s['data_pages_offset'])}",
        ),
    ]
    t = s["trailer"]
    rows.append(("trailer", f"{t['length']} bytes at {_hex(t['offset'])}, sha1 {t['sha1']}"))
    for key in ("entry", "stack"):
        e = s[key]
        rows.append((key, f"object {e['object']} + {_hex(e['offset'])} = {_hex(e['linear'])}"))
    kinds = ", ".join(f"{name} {n}" for name, n in s["fixup_kinds"].items())
    width = max(len(label) for label, _ in rows) + 2
    lines = [f"{label:<{width}}{value}" for label, value in rows]

    table = [("#", "base", "vsize", "end", "flags", "pages", "attributes")]
    for o in s["objects"]:
        last = o["first_page"] + o["pages"] - 1
        table.append(
            (
                str(o["index"]),
                _hex(o["base"]),
                _hex(o["vsize"]),
                _hex(o["end"]),
                f"{o['flags']:#06x}",
                f"{o['first_page']}-{last} ({o['pages']})",
                o["flags_text"],
            )
        )
    widths = [max(len(row[i]) for row in table) for i in range(len(table[0]))]
    lines.append("objects")
    for row in table:
        cells = (cell.ljust(w) for cell, w in zip(row, widths, strict=True))
        lines.append(("  " + "  ".join(cells)).rstrip())
    lines.append(f"{'fixups':<{width}}{s['fixup_count']} ({kinds})")
    return "\n".join(lines)
