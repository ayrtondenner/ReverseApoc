"""Minimal stdlib ISO9660 (level 1) reader, enough to unpack the original Watcom CD images.

Joliet and Rock Ridge are not supported; only the little-endian half of every both-endian
field is read.
"""

from __future__ import annotations

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
        sector = 16
        while True:
            desc = self._read_at(sector * SECTOR, SECTOR)
            if desc[1:6] != b"CD001":
                raise ISOError("not an ISO9660 image (no CD001 volume descriptor)")
            if desc[0] == 1 and desc[6] == 1:
                break
            if desc[0] == 255:
                raise ISOError("no primary volume descriptor found")
            sector += 1
        self.volume_id = desc[40:72].decode("ascii", "replace").strip()
        (block,) = struct.unpack_from("<H", desc, 128)
        if block != SECTOR:
            raise ISOError(f"unsupported logical block size {block} (need {SECTOR})")
        rec = desc[156:190]
        extent, size = struct.unpack_from("<I", rec, 2)[0], struct.unpack_from("<I", rec, 10)[0]
        return IsoEntry("", True, extent, size, _decode_date(rec[18:25]))

    def _parse_record(self, parent: str, rec: bytes) -> IsoEntry:
        flags, name_len = rec[25], rec[32]
        if flags & 0x80:
            raise ISOError("multi-extent files are not supported")
        if 33 + name_len > len(rec):
            raise ISOError(f"directory record name runs past the record in {parent or '/'!r}")
        name = clean_name(rec[33 : 33 + name_len])
        extent, size = struct.unpack_from("<I", rec, 2)[0], struct.unpack_from("<I", rec, 10)[0]
        return IsoEntry(
            f"{parent}/{name}" if parent else name,
            bool(flags & 2),
            extent,
            size,
            _decode_date(rec[18:25]),
        )

    def walk(self, skip_dirs: Collection[str] = ()) -> Iterator[IsoEntry]:
        """Every directory and file, depth-first, parents before children. A directory whose
        path is in `skip_dirs` is neither yielded nor read."""
        yield from self._walk_dir(self._root, {self._root.extent}, frozenset(skip_dirs))

    def _walk_dir(
        self, directory: IsoEntry, visiting: set[int], skip: frozenset[str]
    ) -> Iterator[IsoEntry]:
        where = repr(directory.path or "/")
        data = self._read_at(directory.extent * SECTOR, directory.size)
        for start in range(0, len(data), SECTOR):
            sector = data[start : start + SECTOR]
            pos = 0
            while pos < len(sector):
                length = sector[pos]
                if length == 0:
                    break  # the rest of this sector is padding
                if length < 34 or pos + length > len(sector):
                    raise ISOError(f"corrupt directory record in {where}")
                rec = sector[pos : pos + length]
                pos += length
                if rec[32] == 1 and rec[33] in (0, 1):  # `.` and `..`
                    continue
                if rec[25] & 4:  # associated file
                    continue
                try:
                    entry = self._parse_record(directory.path, rec)
                    if entry.is_dir and entry.path in skip:
                        continue
                    self._check_bounds(entry)
                except ISOError as exc:
                    if where in str(exc):
                        raise
                    raise ISOError(f"{exc} (in {where})") from exc
                yield entry
                if entry.is_dir:
                    if entry.extent in visiting:
                        raise ISOError(f"directory loop at {entry.path!r}")
                    yield from self._walk_dir(entry, visiting | {entry.extent}, skip)

    def find(self, path: str) -> IsoEntry:
        """The entry at an exact-case POSIX path."""
        for entry in self.walk():
            if entry.path == path:
                return entry
        raise ISOError(f"{path!r} not found in image")

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
