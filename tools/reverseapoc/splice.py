# Derived from KKND-Decomp tools/build_kknd.py (CC0 1.0), https://github.com/Wyrelade/KKND-Decomp
"""Byte-region map of an LE executable and its reassembly from parts.

`layout(le)` splits the file into regions that tile it from the first byte to the last, every
boundary taken from the file's own LE header: the bound DOS/4GW extender (absent when the
executable is not bound), the Watcom MZ stub, the LE header, the loader tables, the fixup
section, the padding before the data pages, one region per physical page, and the trailer after
the last page (absent when the pages run to the end of the file).

`decompose(le)` turns the page regions into one page-backed image per object: `page_count *
page_size` bytes, each page copied in whole at its place in the object through the page map.
Page bytes past an object's vsize stay in the image, because they are file bytes too.

`reassemble(le, d)` writes every region from its own source into a fresh zero-filled buffer:
non-page regions (and the trailer) from the original bytes, page regions from the object images,
placed at each page's file offset. The buffer is built by `assemble(size, pieces)`, which never
sees the original file, so a rebuild cannot pass by returning a copy of its input. KKND's
`build_kknd.py` copies the original and overwrites it in place; that form passes every round
trip trivially, which is why this module does not use it.

`splice(le, patches)` writes linear-address patches into the object images before reassembly.
Writable bytes are page data clipped to each object's vsize; everything else is refused.

`rebuild(...)` runs this for every target in config/targets.toml, writes build/<NAME>, and checks
the SHA-1 of the file it wrote against the manifest. Messages carry offsets, lengths, names and
SHA-1s only, never file bytes.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

from .le import (
    _HDR_DEBUG_INFO_LENGTH,
    _HDR_DEBUG_INFO_OFFSET,
    _HDR_NONRES_NAME_TABLE_LENGTH,
    _HDR_NONRES_NAME_TABLE_OFFSET,
    LE,
    LEError,
    LEObject,
    LEPage,
    LEUnsupportedError,
)
from .targets import (
    DEFAULT_ORIG,
    REPO_ROOT,
    FileHashes,
    Target,
    check_target,
    hash_file,
    load_manifest,
)

DEFAULT_OUT = REPO_ROOT / "build"

REGION_EXTENDER = "extender"
REGION_STUB = "stub"
REGION_HEADER = "header"
REGION_LOADER = "loader"
REGION_FIXUPS = "fixups"
REGION_PADDING = "padding"
REGION_PAGE = "page"
REGION_TRAILER = "trailer"
REGION_LABELS = {
    REGION_EXTENDER: "DOS/4GW extender",
    REGION_STUB: "MZ stub",
    REGION_HEADER: "LE header",
    REGION_LOADER: "loader tables",
    REGION_FIXUPS: "fixup section",
    REGION_PADDING: "padding",
    REGION_TRAILER: "trailer",
}

# LE header tables the region map has no region for: (LE attribute, header field, field name).
_UNMAPPED_TABLES = (
    ("nonres_name_table_offset", _HDR_NONRES_NAME_TABLE_OFFSET, "non-resident name table offset"),
    ("nonres_name_table_length", _HDR_NONRES_NAME_TABLE_LENGTH, "non-resident name table length"),
    ("debug_info_offset", _HDR_DEBUG_INFO_OFFSET, "debug info offset"),
    ("debug_info_length", _HDR_DEBUG_INFO_LENGTH, "debug info length"),
)


class SpliceError(LEError):
    """A patch or rebuild was refused."""


@dataclass(frozen=True, order=True)
class Region:
    """A half-open byte range [start, end) of the file. Page regions also carry the object and
    page they belong to and the linear address of the page's first byte."""

    start: int
    end: int
    kind: str
    obj: LEObject | None = field(default=None, compare=False)
    page: LEPage | None = field(default=None, compare=False)
    va: int | None = field(default=None, compare=False)

    def va_at(self, offset: int) -> int | None:
        """Linear address of file offset `offset` inside a page region, else None."""
        return None if self.va is None else self.va + offset - self.start

    def describe(self, offset: int) -> str:
        """Where `offset` lies, e.g. "page 3 of object 1, VA 0x00012010" or "trailer"."""
        if self.kind != REGION_PAGE:
            return REGION_LABELS[self.kind]
        text = f"page {self.page.logical} of object {self.obj.index}, VA {self.va_at(offset):#010x}"
        if self.page.number != self.page.logical:
            text += f" (physical page {self.page.number})"
        return text


# ---- region map ---------------------------------------------------------------------------------


def _check_mappable(le: LE) -> None:
    """Refuse header layouts whose bytes the region map would mis-label rather than tile."""
    for attr, header_field, name in _UNMAPPED_TABLES:
        value = getattr(le, attr)
        if value:
            raise LEUnsupportedError(
                f"LE header field {header_field:#x} ({name}) is {value:#x}; the region map has "
                "no region for it"
            )
    loader_end = le.object_table_offset + le.loader_section_size
    fixups_end = le.fixup_page_table_offset + le.fixup_section_size
    if loader_end != fixups_end:
        raise LEUnsupportedError(
            f"loader section ends at {loader_end:#x}, which does not end where the fixup "
            f"section ends ({fixups_end:#x})"
        )


def _owner(le: LE, page: LEPage) -> LEObject:
    obj = next(
        (o for o in le.objects if o.page_index <= page.logical < o.page_index + o.page_count),
        None,
    )
    if obj is None:
        raise LEError(f"logical page {page.logical} belongs to no object")
    return obj


def _page_regions(le: LE) -> Iterator[Region]:
    for page in le.pages:
        obj = _owner(le, page)
        le.check_loadable(obj, page)
        va = obj.base + (page.logical - obj.page_index) * le.page_size
        yield Region(page.file_offset, page.file_offset + page.size, REGION_PAGE, obj, page, va)


def layout(le: LE) -> list[Region]:
    """The regions of `le`'s file, sorted by start. Zero-length regions are left out.

    Raises LEUnsupportedError for a non-resident name table or debug info (D-19), a loader
    section that does not end where the fixup section ends, and any page that is not a
    physical page inside the file (le.check_loadable)."""
    _check_mappable(le)
    fixups_end = le.fixup_page_table_offset + le.fixup_section_size
    # The declared loader section of wlink output includes the fixup section, so the loader
    # tables end where the fixup section starts.
    spans = [
        (0, le.stub_offset, REGION_EXTENDER),
        (le.stub_offset, le.le_offset, REGION_STUB),
        (le.le_offset, le.object_table_offset, REGION_HEADER),
        (le.object_table_offset, le.fixup_page_table_offset, REGION_LOADER),
        (le.fixup_page_table_offset, fixups_end, REGION_FIXUPS),
        (fixups_end, le.data_pages_offset, REGION_PADDING),
        (le.pages_end, len(le.data), REGION_TRAILER),
    ]
    regions = [Region(start, end, kind) for start, end, kind in spans if end > start]
    regions.extend(_page_regions(le))
    return sorted(regions)


def check_tiling(regions: Iterable[Region], size: int) -> None:
    """Raise unless `regions` cover [0, size) exactly, with no gap and no overlap."""
    pos, prev = 0, "start of file"
    for r in sorted(regions):
        if r.start > pos:
            raise SpliceError(f"gap at {pos:#x} between {prev} and {r.kind}")
        if r.start < pos:
            raise SpliceError(f"overlap at {r.start:#x} between {prev} and {r.kind}")
        pos, prev = r.end, r.kind
    if pos != size:
        raise SpliceError(f"regions end at {pos:#x}, file is {size:#x} bytes")


def region_at(regions: list[Region], offset: int) -> Region:
    """The region of sorted, half-open `regions` that holds file offset `offset`."""
    i = bisect_right(regions, offset, key=lambda r: r.start) - 1
    if i < 0 or offset >= regions[i].end:
        end = regions[-1].end if regions else 0
        raise SpliceError(f"offset {offset:#x} lies outside the file regions [0, {end:#x})")
    return regions[i]


# ---- reassembly ---------------------------------------------------------------------------------


def assemble(size: int, pieces: Iterable[tuple[int, bytes]]) -> bytes:
    """Place `pieces` (file offset, bytes) into a fresh zero-filled buffer of `size` bytes.

    The pieces must tile [0, size) exactly; they may come in any order. This function has no
    access to the original file, so it cannot return a copy of it."""
    out = bytearray(size)
    pos = 0
    for offset, chunk in sorted(pieces, key=lambda piece: piece[0]):
        if offset > pos:
            raise SpliceError(f"gap in the rebuilt file at {pos:#x}")
        if offset < pos:
            raise SpliceError(f"overlapping pieces in the rebuilt file at {offset:#x}")
        out[offset : offset + len(chunk)] = chunk
        pos = offset + len(chunk)
    if pos != size:
        raise SpliceError(f"rebuilt pieces end at {pos:#x}, the file is {size:#x} bytes")
    return bytes(out)


@dataclass
class Decomposition:
    regions: list[Region]
    images: dict[int, bytearray]  # object index -> page-backed image


def _object_pages(le: LE, obj: LEObject) -> Iterator[tuple[int, LEPage]]:
    """(offset in the object image, page) for every page of `obj`."""
    for k in range(obj.page_count):
        yield k * le.page_size, le.pages[obj.page_index + k - 1]


def decompose(le: LE) -> Decomposition:
    """The region map of `le` and one page-backed image per object."""
    regions = layout(le)
    check_tiling(regions, len(le.data))
    images = {}
    for obj in le.objects:
        image = bytearray(obj.page_count * le.page_size)
        for off, page in _object_pages(le, obj):
            image[off : off + page.size] = le.data[page.file_offset : page.file_offset + page.size]
        images[obj.index] = image
    return Decomposition(regions, images)


def _pieces(le: LE, d: Decomposition) -> Iterator[tuple[int, bytes]]:
    for r in d.regions:
        if r.kind != REGION_PAGE:
            yield r.start, le.data[r.start : r.end]
            continue
        off = (r.page.logical - r.obj.page_index) * le.page_size
        yield r.start, bytes(d.images[r.obj.index][off : off + r.page.size])


def reassemble(le: LE, d: Decomposition) -> bytes:
    """Rebuild `le`'s file from the regions and object images of `d`."""
    return assemble(len(le.data), _pieces(le, d))


# ---- splice -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Span:
    """Writable linear addresses [va_start, va_end) of one page of an object: the page's data
    clipped to the object's vsize, found at image_offset in the object's page-backed image."""

    va_start: int
    va_end: int
    obj: LEObject
    page: LEPage
    image_offset: int


def _object_spans(le: LE, obj: LEObject) -> Iterator[_Span]:
    for off, page in _object_pages(le, obj):
        va_start = obj.base + off
        va_end = min(va_start + page.size, obj.end)
        if va_end > va_start:
            yield _Span(va_start, va_end, obj, page, off)


def _writable_spans(le: LE) -> list[_Span]:
    """Every writable span of `le`, sorted by linear address."""
    spans = [span for obj in le.objects for span in _object_spans(le, obj)]
    return sorted(spans, key=lambda span: span.va_start)


def _page_backed_end(le: LE, obj: LEObject) -> int:
    """Linear address just past the last page-backed byte of `obj` (its base without pages)."""
    if obj.page_count == 0:
        return obj.base
    last = le.pages[obj.page_index + obj.page_count - 2]
    return obj.base + (obj.page_count - 1) * le.page_size + last.size


def _unwritable_reason(le: LE, addr: int) -> str:
    """Why linear address `addr` lies outside every writable span (D-03, D-18)."""
    obj = le.obj_of_va(addr)
    if obj is not None:
        return f"{addr:#x} is in the BSS of object {obj.index} (past its page data)"
    obj = next((o for o in le.objects if o.base <= addr < _page_backed_end(le, o)), None)
    if obj is not None:
        return (
            f"{addr:#x} is past the end of object {obj.index} (vsize {obj.vsize:#x}) "
            "in its last page"
        )
    return f"{addr:#x} is not in any object"


def _span_at(spans: list[_Span], i: int, addr: int) -> _Span | None:
    if 0 <= i < len(spans) and spans[i].va_start <= addr < spans[i].va_end:
        return spans[i]
    return None


def _runs(
    le: LE, spans: list[_Span], starts: list[int], va: int, length: int
) -> Iterator[tuple[_Span, int, int]]:
    """(span, lo, hi) runs covering [va, va + length) in address order, all inside the object
    of the first byte. Raises SpliceError at the first address that no writable span of that
    object holds."""
    end = va + length
    i = bisect_right(starts, va) - 1
    pos, obj = va, None
    while pos < end:
        span = _span_at(spans, i, pos)
        if span is None:
            raise SpliceError(_unwritable_reason(le, pos))
        if obj is not None and span.obj is not obj:
            raise SpliceError(
                f"crosses from object {obj.index} into object {span.obj.index} at {pos:#x}"
            )
        hi = min(end, span.va_end)
        yield span, pos, hi
        pos, i, obj = hi, i + 1, span.obj


def _checked_patch(va: object, value: object) -> tuple[int, bytes]:
    """One patch as (linear address, a private copy of its bytes). Messages name the address
    and the value's type, never the value."""
    if not isinstance(va, int) or isinstance(va, bool) or va < 0:
        raise SpliceError(f"patch address {va!r} is not a non-negative int linear address")
    if not isinstance(value, bytes | bytearray | memoryview):
        raise SpliceError(f"patch at {va:#x}: value is {type(value).__name__}, not bytes-like")
    data = bytes(value)
    if not data:
        raise SpliceError(f"patch at {va:#x}: empty patch")
    return va, data


def _checked_patches(patches: Mapping[int, bytes]) -> list[tuple[int, bytes]]:
    """The patches sorted by address, validated, copied, and refused when any two overlap,
    even with identical bytes (D-04)."""
    checked = sorted(
        (_checked_patch(va, value) for va, value in patches.items()), key=lambda p: p[0]
    )
    for (a, a_data), (b, b_data) in pairwise(checked):
        if a + len(a_data) > b:
            raise SpliceError(
                f"patches at {a:#x} ({len(a_data)} bytes) and {b:#x} ({len(b_data)} bytes) "
                f"overlap at {b:#x}"
            )
    return checked


@dataclass(frozen=True)
class SpliceResult:
    data: bytes  # the rebuilt file
    regions: list[Region]  # its region map


def _write(d: Decomposition, runs: Iterable[tuple[_Span, int, int]], va: int, data: bytes) -> None:
    """Write the bytes of the patch at `va` into the object images, run by run."""
    for span, lo, hi in runs:
        dst = span.image_offset + lo - span.va_start
        d.images[span.obj.index][dst : dst + hi - lo] = data[lo - va : hi - va]


def splice(le: LE, patches: Mapping[int, bytes]) -> SpliceResult:
    """Rebuild `le`'s file with every patch {linear address: bytes} written into the page data
    of its object (D-01). The output is reassembled into a fresh buffer of the input's length;
    `le.data` and the patch values are never written. An empty mapping is the plain round trip.

    Raises SpliceError for a patch that is not {non-negative int: non-empty bytes-like}, for
    overlapping patches, and for any byte outside page data clipped to its object's vsize: BSS,
    the page tail past vsize, no object, or a run into the next object (D-03, D-04, D-18)."""
    checked = _checked_patches(patches)
    d = decompose(le)
    spans = _writable_spans(le)
    starts = [span.va_start for span in spans]
    for va, data in checked:
        try:
            _write(d, list(_runs(le, spans, starts, va, len(data))), va, data)
        except SpliceError as exc:
            raise SpliceError(f"{exc} (patch at {va:#x}, {len(data)} bytes)") from exc
    return SpliceResult(reassemble(le, d), d.regions)


# ---- rebuild ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RebuildResult:
    target: Target
    status: str  # "ok", "mismatch", "missing" or "refused"
    output: Path | None
    hashes: FileHashes | None = None
    first_diff: int | None = None  # first file offset where the output differs from orig/
    first_diff_region: str | None = None  # the region holding it, e.g. "page 1 of object 1, ..."
    first_diff_va: int | None = None  # its linear address when it lies in a page
    diff_bytes: int = 0  # how many bytes differ

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def format(self, width: int) -> str:
        name = self.target.name.ljust(width)
        if self.status == "ok":
            return f"OK        {name}  sha1 {self.hashes.sha1} == manifest"
        if self.status == "mismatch":
            line = f"MISMATCH  {name}  sha1 {self.hashes.sha1} != manifest {self.target.sha1}"
            if self.first_diff is not None:
                line += (
                    f"; first difference at {self.first_diff:#x} ({self.first_diff_region}), "
                    f"{self.diff_bytes} bytes differ"
                )
            return line
        if self.status == "missing":
            return (
                f"MISSING   {name}  (orig/{self.target.name} not found; "
                "run uv run reverseapoc ingest)"
            )
        return (
            f"REFUSED   {name}  orig/{self.target.name} does not match config/targets.toml; "
            "run uv run reverseapoc check-orig"
        )


@dataclass(frozen=True)
class RebuildReport:
    out_dir: Path
    results: list[RebuildResult]

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    def format(self) -> str:
        width = max((len(r.target.name) for r in self.results), default=0)
        return "\n".join(r.format(width) for r in self.results)


def _check_bare_name(target: Target) -> None:
    name = target.name
    if not name or name in (".", "..") or Path(name).name != name:
        raise SpliceError(f"target name {name!r} is not a bare file name")


def _refuse_inside_orig(path: Path, orig_dir: Path) -> None:
    if path.resolve().is_relative_to(orig_dir.resolve()):
        raise SpliceError(f"refusing to write {path}: it lies inside orig/ ({orig_dir})")


def _first_difference(a: bytes, b: bytes) -> int | None:
    return next((i for i, (x, y) in enumerate(zip(a, b, strict=True)) if x != y), None)


def _count_differences(a: bytes, b: bytes) -> int:
    return sum(x != y for x, y in zip(a, b, strict=True))


def _mismatch(result: SpliceResult, orig: bytes) -> dict[str, int | str | None]:
    """Where the rebuilt file first differs from the original (D-08): offsets, a region label
    and a count, never byte values."""
    offset = _first_difference(result.data, orig)
    if offset is None:
        return {}
    region = region_at(result.regions, offset)
    return {
        "first_diff": offset,
        "first_diff_region": region.describe(offset),
        "first_diff_va": region.va_at(offset),
        "diff_bytes": _count_differences(result.data, orig),
    }


def rebuild_target(
    target: Target,
    orig_dir: Path,
    out_dir: Path,
    patches: Mapping[int, bytes] | None = None,
) -> RebuildResult:
    """Rebuild orig_dir/<name> from its regions, with `patches` spliced in, into out_dir/<name>
    and compare its SHA-1 with the manifest. A mismatch names the first differing file offset,
    its region and the count of differing bytes. Nothing is written when the input is missing
    or does not match the manifest."""
    _check_bare_name(target)
    out_path = out_dir / target.name
    _refuse_inside_orig(out_path, orig_dir)
    check = check_target(target, orig_dir / target.name)
    if check.status == "missing":
        return RebuildResult(target, "missing", None)
    if check.status != "ok":
        return RebuildResult(target, "refused", None)
    try:
        le = LE(check.path)
        result = splice(le, patches or {})
    except LEError as exc:
        raise type(exc)(f"{target.name}: {exc}") from exc
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(result.data)
    hashes = hash_file(out_path)
    if hashes.sha1 == target.sha1:
        return RebuildResult(target, "ok", out_path, hashes)
    return RebuildResult(target, "mismatch", out_path, hashes, **_mismatch(result, le.data))


def rebuild(
    orig_dir: Path | str | None = None,
    out_dir: Path | str | None = None,
    manifest: Path | str | None = None,
) -> RebuildReport:
    """Rebuild every [[targets]] entry of the manifest (default: config/targets.toml) from
    orig_dir (default: orig/) into out_dir (default: build/)."""
    orig_dir = Path(orig_dir) if orig_dir is not None else DEFAULT_ORIG
    out_dir = Path(out_dir) if out_dir is not None else DEFAULT_OUT
    _refuse_inside_orig(out_dir, orig_dir)
    targets = load_manifest(manifest)
    for target in targets:
        _check_bare_name(target)
    return RebuildReport(out_dir, [rebuild_target(t, orig_dir, out_dir) for t in targets])
