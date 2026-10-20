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

`rebuild(...)` runs this for every target in config/targets.toml, writes build/<NAME>, and checks
the SHA-1 of the file it wrote against the manifest. Messages carry offsets, lengths, names and
SHA-1s only, never file bytes.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .le import LE, LEError, LEObject, LEPage
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


# ---- region map ---------------------------------------------------------------------------------


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
    """The regions of `le`'s file, sorted by start. Zero-length regions are left out."""
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


# ---- rebuild ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RebuildResult:
    target: Target
    status: str  # "ok", "mismatch", "missing" or "refused"
    output: Path | None
    hashes: FileHashes | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def format(self, width: int) -> str:
        name = self.target.name.ljust(width)
        if self.status == "ok":
            return f"OK        {name}  sha1 {self.hashes.sha1} == manifest"
        if self.status == "mismatch":
            return f"MISMATCH  {name}  sha1 {self.hashes.sha1} != manifest {self.target.sha1}"
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


def rebuild_target(target: Target, orig_dir: Path, out_dir: Path) -> RebuildResult:
    """Rebuild orig_dir/<name> from its regions into out_dir/<name> and compare its SHA-1 with
    the manifest. Nothing is written when the input is missing or does not match the manifest."""
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
        data = reassemble(le, decompose(le))
    except LEError as exc:
        raise type(exc)(f"{target.name}: {exc}") from exc
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    hashes = hash_file(out_path)
    status = "ok" if hashes.sha1 == target.sha1 else "mismatch"
    return RebuildResult(target, status, out_path, hashes)


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
