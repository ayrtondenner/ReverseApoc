"""Test-only builder of tiny synthetic ISO9660 level 1 images.

Layout: 16 zero sectors, PVD at 16, terminator at 17, directory extents from 18, then file data.
The big-endian halves of every both-endian field are filled with 0xA5 so a reader that looks at
them gets caught.
"""

from __future__ import annotations

import struct
from datetime import UTC, datetime, timedelta

SECTOR = 2048
GARBAGE = 0xA5


def _both32(value: int) -> bytes:
    return struct.pack("<I", value) + bytes([GARBAGE] * 4)


def _both16(value: int) -> bytes:
    return struct.pack("<H", value) + bytes([GARBAGE] * 2)


def _date(mtime: datetime) -> bytes:
    offset = (mtime.utcoffset() or timedelta(0)).total_seconds() // 900
    return struct.pack(
        "<6Bb", mtime.year - 1900, mtime.month, mtime.day, mtime.hour, mtime.minute,
        mtime.second, int(offset),
    )  # fmt: skip


def record(name: bytes, extent: int, size: int, mtime: datetime, *, is_dir: bool) -> bytes:
    """One directory record, padded to an even length."""
    body = (
        _both32(extent) + _both32(size) + _date(mtime)
        + bytes([2 if is_dir else 0, 0, 0]) + _both16(1) + bytes([len(name)]) + name
    )  # fmt: skip
    body = b"\x00\x00" + body  # [0] length, [1] extended attribute length
    body += b"\x00" * (len(body) % 2)
    return bytes([len(body)]) + body[1:]


def _pack(records: list[bytes]) -> bytes:
    """Pack records into sectors; a record never crosses a sector boundary."""
    out, used = bytearray(), 0
    for rec in records:
        if used + len(rec) > SECTOR:
            out += b"\x00" * (SECTOR - used)
            used = 0
        out += rec
        used += len(rec)
    return bytes(out) + b"\x00" * (-len(out) % SECTOR)


def _sectors(n: int) -> int:
    return max(1, -(-n // SECTOR))


def build_iso(
    tree: dict[str, bytes],
    *,
    volume_id: str = "TESTVOL",
    mtime: datetime = datetime(1996, 2, 29, 7, 6, tzinfo=UTC),
    raw_names: dict[str, bytes] | None = None,
) -> bytes:
    """Build an image from {"DIR/FILE.EXT": bytes}; directories are implied.

    `raw_names` maps an entry's path to the exact on-disc name bytes to write instead of the
    default (`NAME;1` for files, `NAME` for directories).
    """
    raw_names = raw_names or {}
    dirs: dict[str, list[str]] = {"": []}  # directory path -> child paths
    for path in sorted(tree):
        parts = path.split("/")
        for i in range(1, len(parts)):
            parent, child = "/".join(parts[: i - 1]), "/".join(parts[:i])
            if child not in dirs:
                dirs[child] = []
                dirs[parent].append(child)
        dirs["/".join(parts[:-1])].append(path)

    def disc_name(path: str) -> bytes:
        default = path.rsplit("/", 1)[-1].encode() + (b";1" if path in tree else b"")
        return raw_names.get(path, default)

    def dir_records(path: str, extents: dict[str, int], sizes: dict[str, int]) -> list[bytes]:
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        own, up = extents.get(path, 0), extents.get(parent, 0)
        out = [
            record(b"\x00", own, sizes.get(path, SECTOR), mtime, is_dir=True),
            record(b"\x01", up, sizes.get(parent, SECTOR), mtime, is_dir=True),
        ]
        for child in dirs[path]:
            data = tree.get(child)
            size = len(data) if data is not None else sizes.get(child, SECTOR)
            out.append(
                record(disc_name(child), extents.get(child, 0), size, mtime, is_dir=data is None)
            )
        return out

    # record lengths do not depend on extent values, so size the directories with dummies
    sizes = {d: len(_pack(dir_records(d, {}, {}))) for d in dirs}
    extents, nxt = {}, 18
    for d in dirs:
        extents[d] = nxt
        nxt += sizes[d] // SECTOR
    for path in sorted(tree):
        extents[path] = nxt
        nxt += _sectors(len(tree[path]))

    pvd = bytearray(SECTOR)
    pvd[0:7] = b"\x01CD001\x01"
    pvd[40:72] = volume_id.encode().ljust(32)
    pvd[80:88] = _both32(nxt)
    pvd[128:132] = _both16(SECTOR)
    pvd[156:190] = record(b"\x00", extents[""], sizes[""], mtime, is_dir=True)[:34]
    terminator = b"\xffCD001\x01".ljust(SECTOR, b"\x00")

    image = bytearray(b"\x00" * (16 * SECTOR) + bytes(pvd) + terminator)
    for d in dirs:
        image += _pack(dir_records(d, extents, sizes))
    for path in sorted(tree):
        data = tree[path]
        image += data + b"\x00" * (_sectors(len(data)) * SECTOR - len(data))
    return bytes(image)


def record_offset(image: bytes, name: bytes) -> int:
    """Offset of the (unique) directory record whose on-disc name is `name`, for patching."""
    return image.index(bytes([len(name)]) + name, 18 * SECTOR) - 32
