"""Shared fixtures. The LE images here are synthetic and tiny: no game bytes are ever committed.

`ORIG_DIR` is the orig/ the real-file tests read. The environment variable REVERSEAPOC_ORIG
overrides it, so those tests can run from a git worktree that has no orig/ of its own (point it
at the main checkout's orig/; the tests only read it). Docker and CI leave it unset.

`WATCOM_DIR` holds the installed Watcom trees (`third_party/watcom/<version>/`); the environment
variable REVERSEAPOC_WATCOM_DIR overrides it the same way, read-only. Real-file tests call
`requires_version(version)` first, which skips naming the missing version, and compile tests call
`requires_runner()`, which skips unless a compiler runner exists (the Windows host or wibo).

Tests that need another tool skip the same way, naming it: `requires_capstone()`,
`requires_objdiff()` (objdiff-cli on PATH), `requires_clang()` (clang-18 or clang on PATH) and
`requires_ghidra()`, which returns the Ghidra install (GHIDRA_INSTALL_DIR, read at call time, else
GHIDRA_DIR) and skips unless it holds support/analyzeHeadless.

`build_le_image(ghidra_loadable=True)` builds an image Ghidra's LeLoader accepts: the first MZ
gets e_lfarlc 0x40 and an e_lfanew pointing at the LE header.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import struct
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ORIG_DIR = (
    Path(os.environ["REVERSEAPOC_ORIG"]) if "REVERSEAPOC_ORIG" in os.environ else REPO_ROOT / "orig"
)
WATCOM_DIR = Path(os.environ.get("REVERSEAPOC_WATCOM_DIR") or REPO_ROOT / "third_party" / "watcom")


def requires_version(version: str) -> Path:
    """The installed tree of one Watcom version; skips the test when it is not installed."""
    path = WATCOM_DIR / version
    if not path.is_dir():
        pytest.skip(
            f"Watcom {version}: {path} not installed (run `uv run reverseapoc install-watcom "
            f"{version}` or set REVERSEAPOC_WATCOM_DIR)"
        )
    return path


def requires_runner() -> None:
    """Skips the test unless the Watcom compilers can run: natively on Windows, else via wibo."""
    if sys.platform != "win32" and shutil.which("wibo") is None:
        pytest.skip("no compiler runner: needs the Windows host or wibo in the container")


def requires_capstone() -> None:
    """Skips the test unless the capstone package is importable."""
    if importlib.util.find_spec("capstone") is None:
        pytest.skip("capstone is not installed (`uv sync --locked`, or run in the container)")


def requires_objdiff() -> None:
    """Skips the test unless objdiff-cli is on PATH."""
    if shutil.which("objdiff-cli") is None:
        pytest.skip("objdiff-cli is not on PATH (run in the container)")


def requires_clang() -> None:
    """Skips the test unless clang-18 or clang is on PATH."""
    if shutil.which("clang-18") is None and shutil.which("clang") is None:
        pytest.skip("clang-18 / clang is not on PATH (run in the container)")


GHIDRA_DIR = Path("/opt/ghidra")  # where the Docker image installs Ghidra


def ghidra_dir() -> Path:
    """The Ghidra install: GHIDRA_INSTALL_DIR when set, read at call time, else GHIDRA_DIR."""
    return Path(os.environ.get("GHIDRA_INSTALL_DIR") or GHIDRA_DIR)


def requires_ghidra() -> Path:
    """The Ghidra install dir; skips the test unless it holds support/analyzeHeadless."""
    path = ghidra_dir()
    if not (path / "support" / "analyzeHeadless").is_file():
        pytest.skip(
            f"Ghidra: {path}/support/analyzeHeadless not found (set GHIDRA_INSTALL_DIR, "
            "or run in the container)"
        )
    return path


PAGE_SIZE = 0x1000
LAST_PAGE_SIZE = 0x200
OUTER_STUB_SIZE = 0x180  # fake "bound extender" MZ in front of the MZ that owns the LE header
INNER_LFANEW = 0x80  # e_lfanew of the owning MZ (relative to that MZ)
LE_HEADER_SIZE = 0xC4  # object table follows the header, as wlink lays it out
MZ_E_LFARLC = 0x18  # MZ header field: file offset of the relocation table (u16)
MZ_E_LFANEW = 0x3C  # MZ header field: file offset of the new-format (LE) header (u32)
LE_DATA_PAGES = 0x80  # LE header field: data pages offset, relative to the MZ owning the header
# e_lfarlc value of a new-format executable: Ghidra's LeLoader trusts e_lfanew only with it.
NEW_FORMAT_LFARLC = 0x40

# (vsize, base, flags, first logical page, page count)
OBJECTS = [
    (0x1800, 0x10000, 0x2045, 1, 2),  # code: readable, executable, big
    (0x3000, 0x20000, 0x2043, 3, 1),  # data: readable, writable, big; tail is bss
]
ENTRY = (1, 0x123)
STACK = (2, 0x3000)
SYNTHETIC_TRAILER = b"SYNTHETIC-TRAILER-27-BYTES!"  # 27 synthetic bytes after the last page


def fixup_record(
    src: int,
    offsets: int | list[int],
    obj: int,
    off: int | None = None,
    *,
    flags: int = 0,
    obj16: bool = False,
    off32: bool | None = None,
) -> bytes:
    """Encode one internal-reference LE fixup record (a list of offsets makes a source list)."""
    source_list = isinstance(offsets, list)
    if off32 is None:
        off32 = off is not None and off > 0xFFFF
    flg = flags | (0x40 if obj16 else 0) | (0x10 if off32 else 0)
    out = bytes([src | (0x20 if source_list else 0), flg])
    out += bytes([len(offsets)]) if source_list else struct.pack("<h", offsets)
    out += struct.pack("<H", obj) if obj16 else bytes([obj])
    if off is not None:
        out += struct.pack("<I" if off32 else "<H", off)
    if source_list:
        out += b"".join(struct.pack("<h", o) for o in offsets)
    return out


# Fixup records per logical page, and the decoded fixups the parser must produce from them:
# (src_va, kind, target_va, target_obj, target_off, size), deduplicated and sorted.
DEFAULT_FIXUPS: list[bytes] = [
    # page 1 = object 1 + 0x0000
    fixup_record(7, 0x010, 2, 0x100)  # off32 -> obj2:0x100 (16-bit target offset)
    + fixup_record(7, 0x020, 2, 0x2FF0, off32=True)  # off32, 32-bit target offset
    + fixup_record(8, 0x030, 1, 0x800)  # rel32 -> obj1:0x800
    + fixup_record(7, 0xFFE, 2, 0x40),  # off32 straddling into page 2 ...
    # page 2 = object 1 + 0x1000
    fixup_record(7, -2, 2, 0x40)  # ... and listed again here with a negative offset
    + fixup_record(2, 0x010, 2)  # sel16 -> obj2 (no target offset)
    + fixup_record(6, 0x020, 1, 0, off32=True)  # ptr16:32 -> obj1:0
    + fixup_record(7, [0x040, 0x044], 2, 0x200),  # source list, two off32 fields
    # page 3 = object 2 + 0x0000
    fixup_record(5, 0x008, 2, 0x10)  # off16 -> obj2:0x10
    + fixup_record(0, 0x000, 1, 0x1)  # byte -> obj1:1
    + fixup_record(7, 0x00C, 1, 0x50, obj16=True),  # off32 with a 16-bit object number
]
DEFAULT_DECODED = [
    (0x10010, 7, 0x20100, 2, 0x100, 4),
    (0x10020, 7, 0x22FF0, 2, 0x2FF0, 4),
    (0x10030, 8, 0x10800, 1, 0x800, 4),
    (0x10FFE, 7, 0x20040, 2, 0x40, 4),
    (0x11010, 2, 0x20000, 2, 0, 2),
    (0x11020, 6, 0x10000, 1, 0, 6),
    (0x11040, 7, 0x20200, 2, 0x200, 4),
    (0x11044, 7, 0x20200, 2, 0x200, 4),
    (0x20000, 0, 0x10001, 1, 1, 1),
    (0x20008, 5, 0x20010, 2, 0x10, 2),
    (0x2000C, 7, 0x10050, 1, 0x50, 4),
]


def page_fill(page_number: int) -> int:
    """Byte value every physical page is filled with (page 1 -> 0x11, 2 -> 0x22, ...)."""
    return 0x11 * page_number


@dataclass
class SyntheticLE:
    data: bytes
    stub_offset: int
    le_offset: int
    data_pages_offset: int
    page_offsets: list[int] = field(default_factory=list)
    trailer_offset: int = 0  # file offset just past the last page
    fixup_start: int = 0  # file offset of the fixup page table (start of the fixup section)
    fixup_end: int = 0  # file offset just past the fixup section


def _patch_offset(
    objects: list[tuple[int, int, int, int, int]],
    page_numbers: tuple[int, ...],
    page_offsets: list[int],
    va: int,
    size: int,
) -> int:
    """File offset of linear address `va` for a patch of `size` bytes (see build_le_image)."""
    for _vsize, base, _flags, first_page, page_count in objects:
        if not base <= va < base + page_count * PAGE_SIZE:
            continue
        logical = first_page + (va - base) // PAGE_SIZE
        physical = page_numbers[logical - 1]
        in_page = (va - base) % PAGE_SIZE
        page_size = LAST_PAGE_SIZE if physical == len(page_numbers) else PAGE_SIZE
        assert in_page + size <= page_size, f"patch at {va:#x} crosses the end of its page"
        return page_offsets[physical - 1] + in_page
    raise AssertionError(f"patch at {va:#x} lies in no object's pages")


def build_le_image(
    *,
    bound: bool = True,
    fixups: list[bytes] | None = None,
    page_flags: tuple[int, ...] = (0, 0, 0),
    entry: tuple[int, int] = ENTRY,
    page_numbers: tuple[int, ...] | None = None,
    trailer: bytes = b"",
    extra_header_fields: dict[int, int] | None = None,
    objects: list[tuple[int, int, int, int, int]] | None = None,
    patches: dict[int, bytes] | None = None,
    ghidra_loadable: bool = False,
) -> SyntheticLE:
    """Build a minimal LE executable: [fake extender MZ] + MZ stub + LE header + tables + pages
    [+ trailer].

    With `bound=True` the first MZ's e_lfanew does not point at the LE header (like a bound
    DOS/4GW executable), so the parser has to find the owning MZ by scanning. A decoy "LE\0\0"
    in the extender checks that the scan does not stop at the first signature it sees.

    `page_numbers` gives the physical page number of each logical page (identity by default);
    pages are always written in physical order, each filled with `page_fill(physical number)`,
    the short page last. `trailer` is appended after the last page. `extra_header_fields`
    (LE header offset -> u32) is merged over the header fields before packing. `objects`
    replaces OBJECTS for this image. `patches` ({linear address: bytes}) overwrites page bytes
    after the fill: each address is mapped through the object table to its logical page, then
    through `page_numbers` to the physical page in the file. A patch must stay inside one page
    and inside that page's data (the short last page included); otherwise AssertionError.

    With `ghidra_loadable=True` the first MZ (the fake extender when bound, else the stub) gets
    e_lfarlc = NEW_FORMAT_LFARLC and an e_lfanew holding the LE header's file offset, which is
    what Ghidra's LeLoader needs to accept the file (05-RESEARCH Pitfall 5). That MZ then owns
    the LE header, so the data-pages field is written relative to it (the start of the file)
    and the pages stay where they are: `LE(data).stub_offset` is 0, every other parsed value
    matches the default image.
    """
    fixups = DEFAULT_FIXUPS if fixups is None else fixups
    num_pages = len(page_flags)
    assert len(fixups) == num_pages
    if page_numbers is None:
        page_numbers = tuple(range(1, num_pages + 1))
    assert len(page_numbers) == num_pages
    objects = OBJECTS if objects is None else objects

    prefix = b""
    if bound:
        outer = bytearray(b"\xcc" * OUTER_STUB_SIZE)
        outer[0:2] = b"MZ"
        # e_lfanew points past EOF, like the real loader
        struct.pack_into("<I", outer, MZ_E_LFANEW, 0x0FFFFFF0)
        outer[0x100:0x104] = b"LE\x00\x00"  # decoy: no MZ owns it
        prefix = bytes(outer)

    stub_offset = len(prefix)
    inner = bytearray(b"\x90" * INNER_LFANEW)
    inner[0:2] = b"MZ"
    struct.pack_into("<I", inner, MZ_E_LFANEW, INNER_LFANEW)

    obj_table = b"".join(struct.pack("<6I", *obj, 0) for obj in objects)
    page_map = b"".join(
        bytes([(n >> 16) & 0xFF, (n >> 8) & 0xFF, n & 0xFF, flags])
        for n, flags in zip(page_numbers, page_flags, strict=True)
    )
    fixup_page_table = b""
    pos = 0
    for records in fixups:
        fixup_page_table += struct.pack("<I", pos)
        pos += len(records)
    fixup_page_table += struct.pack("<I", pos)
    fixup_records = b"".join(fixups)

    rel_obj = LE_HEADER_SIZE
    rel_map = rel_obj + len(obj_table)
    rel_fpt = rel_map + len(page_map)
    rel_frt = rel_fpt + len(fixup_page_table)
    loader_end = rel_frt + len(fixup_records)

    header = bytearray(LE_HEADER_SIZE)
    header[0:4] = b"LE\x00\x00"
    struct.pack_into("<HH", header, 0x08, 2, 1)  # cpu 386, os OS/2
    fields = {
        0x10: 0x200,
        0x14: num_pages,
        0x18: entry[0],
        0x1C: entry[1],
        0x20: STACK[0],
        0x24: STACK[1],
        0x28: PAGE_SIZE,
        0x2C: LAST_PAGE_SIZE,
        0x30: len(fixup_page_table) + len(fixup_records),
        0x38: loader_end - rel_obj,
        0x40: rel_obj,
        0x44: len(objects),
        0x48: rel_map,
        0x68: rel_fpt,
        0x6C: rel_frt,
        0x70: loader_end,
        0x78: loader_end,
        0x94: 2,
    }
    fields.update(extra_header_fields or {})
    for off, value in fields.items():
        struct.pack_into("<I", header, off, value)

    le_rel = INNER_LFANEW  # LE header offset relative to the owning MZ
    tables = bytes(header) + obj_table + page_map + fixup_page_table + fixup_records
    body_end = le_rel + len(tables)
    data_pages_rel = (body_end + 0x1FF) & ~0x1FF
    owner_offset = 0 if ghidra_loadable else stub_offset  # file offset of the MZ owning LE
    struct.pack_into("<I", header, LE_DATA_PAGES, stub_offset - owner_offset + data_pages_rel)
    tables = bytes(header) + obj_table + page_map + fixup_page_table + fixup_records

    image = bytearray(prefix + bytes(inner) + tables)
    if ghidra_loadable:
        struct.pack_into("<H", image, MZ_E_LFARLC, NEW_FORMAT_LFARLC)
        struct.pack_into("<I", image, MZ_E_LFANEW, stub_offset + le_rel)
    image += b"\x00" * (stub_offset + data_pages_rel - len(image))
    page_offsets = []
    for n in range(1, num_pages + 1):
        page_offsets.append(len(image))
        size = LAST_PAGE_SIZE if n == num_pages else PAGE_SIZE
        image += bytes([page_fill(n)]) * size
    for va, blob in (patches or {}).items():
        at = _patch_offset(objects, page_numbers, page_offsets, va, len(blob))
        image[at : at + len(blob)] = blob
    trailer_offset = len(image)
    image += trailer
    return SyntheticLE(
        data=bytes(image),
        stub_offset=stub_offset,
        le_offset=stub_offset + le_rel,
        data_pages_offset=stub_offset + data_pages_rel,
        page_offsets=page_offsets,
        trailer_offset=trailer_offset,
        fixup_start=stub_offset + le_rel + rel_fpt,
        fixup_end=stub_offset + le_rel + loader_end,
    )


@pytest.fixture
def le_builder():
    return build_le_image


@pytest.fixture
def synthetic_le() -> SyntheticLE:
    return build_le_image()


@pytest.fixture
def synthetic_le_path(tmp_path: Path, synthetic_le: SyntheticLE) -> Path:
    path = tmp_path / "SYNTH.EXE"
    path.write_bytes(synthetic_le.data)
    return path


def write_manifest(path: Path, files: dict[str, bytes], subdir: str = "SUB") -> Path:
    """Write a targets manifest describing `files` (name -> content) with correct hashes."""
    parts = []
    for name, content in files.items():
        parts.append(
            "[[targets]]\n"
            f'name = "{name}"\n'
            f'path = "{subdir}/{name}"\n'
            f"size = {len(content)}\n"
            f"crc32 = {zlib.crc32(content):#x}\n"
            f'md5 = "{hashlib.md5(content).hexdigest()}"\n'
            f'sha1 = "{hashlib.sha1(content).hexdigest()}"\n'
        )
    path.write_text("\n".join(parts), encoding="utf-8")
    return path
