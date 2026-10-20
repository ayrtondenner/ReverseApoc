"""Minimal stdlib ISO9660 (level 1) reader, enough to unpack the original Watcom CD images.

Joliet and Rock Ridge are not supported; only the little-endian half of every both-endian
field is read.
"""

from __future__ import annotations

import itertools
import os
import struct
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO

SECTOR = 2048
_FORBIDDEN = frozenset("/\\:\x00")
_RESERVED = frozenset(["CON", "PRN", "AUX", "NUL"]) | frozenset(
    f"{dev}{n}" for dev in ("COM", "LPT") for n in range(1, 10)
)

# Directory record layout (ECMA-119 9.1). Both-endian fields: only the little-endian half is read.
_REC_EXTENT = 2  # u32: first sector of the file or directory
_REC_SIZE = 10  # u32: data length in bytes
_REC_DATE = slice(18, 25)  # 7-byte recording date
_REC_FLAGS = 25
_REC_NAME_LEN = 32
_REC_NAME = 33  # the fixed part of a record ends here; the name follows
_MIN_RECORD = _REC_NAME + 1  # shortest record: a one-byte name (`.`, `..` or the root)

_FLAG_DIR = 0x02
_FLAG_ASSOCIATED = 0x04
_FLAG_MULTI_EXTENT = 0x80

# Volume descriptors (ECMA-119 8.1): one per sector from sector 16 up to the terminator.
_VD_FIRST_SECTOR = 16
_VD_TYPE = 0
_VD_ID = slice(1, 6)
_VD_MAGIC = b"CD001"
_VD_VERSION = 6
_VD_PRIMARY = 1
_VD_TERMINATOR = 255

# Primary volume descriptor layout (ECMA-119 8.4).
_PVD_VOLUME_ID = slice(40, 72)
_PVD_BLOCK_SIZE = 128  # u16
_PVD_ROOT = 156  # the root directory's record, _MIN_RECORD bytes long


class ISOError(ValueError):
    """The image is malformed, truncated, unsupported, or holds an unsafe name."""


@dataclass(frozen=True)
class IsoEntry:
    path: str  # POSIX-style, relative to the root, on-disc case
    is_dir: bool
    extent: int  # first sector
    size: int
    mtime: datetime | None


def clean_name(raw: bytes) -> str:
    """Decode an on-disc name: drop the `;version` and one trailing dot, reject unsafe names."""
    try:
        name = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ISOError(f"non-ASCII file name {raw!r}") from exc
    name = name.split(";", 1)[0]
    if name.endswith("."):
        name = name[:-1]
    if not name or name in (".", ".."):
        raise ISOError(f"unusable file name {raw!r}")
    if _FORBIDDEN & set(name):
        raise ISOError(f"file name {raw!r} contains a path separator or control character")
    if name.split(".", 1)[0].upper() in _RESERVED:
        raise ISOError(f"file name {raw!r} is a reserved Windows device name")
    return name


def _is_dot_record(rec: bytes) -> bool:
    """`.` or `..`: a one-byte name of 0x00 or 0x01."""
    return rec[_REC_NAME_LEN] == 1 and rec[_REC_NAME] in (0, 1)


def _extent_and_size(rec: bytes) -> tuple[int, int]:
    """A directory record's first sector and data length."""
    (extent,) = struct.unpack_from("<I", rec, _REC_EXTENT)
    (size,) = struct.unpack_from("<I", rec, _REC_SIZE)
    return extent, size


def _decode_date(raw: bytes) -> datetime | None:
    if not any(raw):
        return None
    year, month, day, hour, minute, second, gmt = struct.unpack("<6Bb", raw)
    try:
        return datetime(
            1900 + year, month, day, hour, minute, second,
            tzinfo=timezone(timedelta(minutes=15 * gmt)),
        )  # fmt: skip
    except ValueError:
        return None


class ISO9660:
    """Read-only view of an ISO9660 image held in a seekable binary file object."""

    def __init__(self, fh: BinaryIO) -> None:
        self._fh = fh
        fh.seek(0, os.SEEK_END)
        self._image_size = fh.tell()
        self.volume_id = ""
        self._root = self._read_pvd()

    @classmethod
    @contextmanager
    def open(cls, path: Path | str) -> Iterator[ISO9660]:
        with Path(path).open("rb") as fh:
            yield cls(fh)

    def _check_bounds(self, entry: IsoEntry) -> None:
        if (entry.extent * SECTOR) + entry.size > self._image_size:
            raise ISOError(f"image is truncated ({entry.path or 'root'!r} lies beyond the end)")

    def _read_at(self, offset: int, length: int) -> bytes:
        if offset < 0 or offset + length > self._image_size:
            raise ISOError("image is truncated (data lies beyond the end of the file)")
        self._fh.seek(offset)
        return self._fh.read(length)

    def _read_pvd(self) -> IsoEntry:
        for sector in itertools.count(_VD_FIRST_SECTOR):
            desc = self._read_at(sector * SECTOR, SECTOR)
            if desc[_VD_ID] != _VD_MAGIC:
                raise ISOError("not an ISO9660 image (no CD001 volume descriptor)")
            if desc[_VD_TYPE] == _VD_PRIMARY and desc[_VD_VERSION] == 1:
                break
            if desc[_VD_TYPE] == _VD_TERMINATOR:
                raise ISOError("no primary volume descriptor found")
        self.volume_id = desc[_PVD_VOLUME_ID].decode("ascii", "replace").strip()
        (block,) = struct.unpack_from("<H", desc, _PVD_BLOCK_SIZE)
        if block != SECTOR:
            raise ISOError(f"unsupported logical block size {block} (need {SECTOR})")
        rec = desc[_PVD_ROOT : _PVD_ROOT + _MIN_RECORD]
        return IsoEntry("", True, *_extent_and_size(rec), _decode_date(rec[_REC_DATE]))

    def _parse_record(self, parent: str, rec: bytes) -> IsoEntry:
        flags, name_len = rec[_REC_FLAGS], rec[_REC_NAME_LEN]
        if flags & _FLAG_MULTI_EXTENT:
            raise ISOError("multi-extent files are not supported")
        if _REC_NAME + name_len > len(rec):
            raise ISOError("directory record name runs past the record")
        name = clean_name(rec[_REC_NAME : _REC_NAME + name_len])
        return IsoEntry(
            f"{parent}/{name}" if parent else name,
            bool(flags & _FLAG_DIR),
            *_extent_and_size(rec),
            _decode_date(rec[_REC_DATE]),
        )

    def walk(self, skip_dirs: Collection[str] = ()) -> Iterator[IsoEntry]:
        """Every directory and file, depth-first, parents before children. A directory whose
        path is in `skip_dirs` is neither yielded nor read."""
        yield from self._walk_dir(self._root, {self._root.extent}, frozenset(skip_dirs))

    def _walk_dir(
        self, directory: IsoEntry, visiting: set[int], skip: frozenset[str]
    ) -> Iterator[IsoEntry]:
        for entry in self._entries(directory, skip):
            yield entry
            if not entry.is_dir:
                continue
            if entry.extent in visiting:
                raise ISOError(f"directory loop at {entry.path!r}")
            yield from self._walk_dir(entry, visiting | {entry.extent}, skip)

    def _entries(self, directory: IsoEntry, skip: frozenset[str]) -> Iterator[IsoEntry]:
        """Each bounds-checked entry of a directory, lazily, without `.`, `..`, associated files
        or skipped directories. Any error in this directory's records names the directory."""
        try:
            for rec in self._records(directory):
                if _is_dot_record(rec) or rec[_REC_FLAGS] & _FLAG_ASSOCIATED:
                    continue
                entry = self._parse_record(directory.path, rec)
                if entry.is_dir and entry.path in skip:
                    continue
                self._check_bounds(entry)
                yield entry
        except ISOError as exc:
            raise ISOError(f"{exc} (in {directory.path or '/'!r})") from exc

    def _records(self, directory: IsoEntry) -> Iterator[bytes]:
        """Each raw record in a directory's extent. Records never cross a sector; a zero length
        byte pads out the rest of the sector."""
        data = self._read_at(directory.extent * SECTOR, directory.size)
        for start in range(0, len(data), SECTOR):
            sector = data[start : start + SECTOR]
            pos = 0
            while pos < len(sector) and (length := sector[pos]):
                if length < _MIN_RECORD or pos + length > len(sector):
                    raise ISOError("corrupt directory record")
                yield sector[pos : pos + length]
                pos += length

    def find(self, path: str) -> IsoEntry:
        """The entry at an exact-case POSIX path; the walk stops at the first match."""
        entry = next((e for e in self.walk() if e.path == path), None)
        if entry is None:
            raise ISOError(f"{path!r} not found in image")
        return entry

    def copy_to(self, entry: IsoEntry, out: BinaryIO, chunk: int = 1 << 20) -> None:
        """Stream a file's bytes to `out`."""
        if entry.is_dir:
            raise ISOError(f"{entry.path!r} is a directory")
        self._check_bounds(entry)
        self._fh.seek(entry.extent * SECTOR)
        left = entry.size
        while left:
            data = self._fh.read(min(chunk, left))
            if not data:
                raise ISOError("image is truncated while reading a file")
            out.write(data)
            left -= len(data)


def extract_all(
    iso_path: Path | str,
    dest: Path | str,
    *,
    timestamps: bool = True,
    skip_dirs: Collection[str] = (),
) -> list[IsoEntry]:
    """Unpack the whole image under `dest`; refuse any target that would land outside it.
    Directories listed in `skip_dirs` (damaged ones) are left out together with their children."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    extracted: list[tuple[IsoEntry, Path]] = []
    with ISO9660.open(iso_path) as iso:
        for entry in iso.walk(skip_dirs):
            target =(root / entry.path).resolve()
            if not target.is_relative_to(root) or target == root:
                raise ISOError(f"{entry.path!r} would be written outside {root}")
            if entry.is_dir:
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("wb") as out:
                    iso.copy_to(entry, out)
            extracted.append((entry, target))
    if timestamps:
        # files first, then directories deepest-first, so writing a child never bumps a parent
        files = [(e, t) for e, t in extracted if not e.is_dir]
        dirs = [(e, t) for e, t in reversed(extracted) if e.is_dir]
        for entry, target in files + dirs:
            if entry.mtime is not None:
                stamp = entry.mtime.timestamp()
                os.utime(target, (stamp, stamp))
    return [entry for entry, _ in extracted]
