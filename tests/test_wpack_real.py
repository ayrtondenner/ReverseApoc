"""wpack against the real 10.5 CD: PCK00017 holds the 10.5 compiler `wcc386.exe`.

Skipped unless the media is present: run `uv run reverseapoc fetch-watcom`, or point
REVERSEAPOC_WATCOM_MEDIA at a directory holding the ISOs (needed from a git worktree). The parts
are read from the ISO into memory; nothing is extracted, written or printed. Only sizes and
hashes are compared.
"""

from __future__ import annotations

import io
import os
import struct
import zlib
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from reverseapoc.iso9660 import ISO9660
from reverseapoc.targets import hash_bytes
from reverseapoc.watcom import load_watcom_manifest
from reverseapoc.wpack import decode_member, join_parts, read_archive

MEDIA_DIR = Path(
    os.environ.get("REVERSEAPOC_WATCOM_MEDIA") or REPO_ROOT / "third_party" / "watcom-media"
)
MANIFEST = load_watcom_manifest()

pytestmark = pytest.mark.skipif(
    not MEDIA_DIR.is_dir(),
    reason=f"{MEDIA_DIR} not present (run `uv run reverseapoc fetch-watcom` or set "
    "REVERSEAPOC_WATCOM_MEDIA)",
)

PARTS = ["DISKIMGS/DISK02/PCK00017.1", "DISKIMGS/DISK03/PCK00017.2"]
MEMBER = "wcc386.exe"
MEMBER_LENGTH = 567558  # docs/research/wpack-format.md section 9
HEADER_LEN = 12  # the 10.5 disc's header (format doc section 2), own literal
INFO_OFFSET_FIELD = 8
MZ_LFANEW_FIELD = 0x3C  # u32 in the MZ header: offset of the new-style executable header


@pytest.fixture(scope="module")
def pck00017() -> bytes:
    iso = MEDIA_DIR / MANIFEST["10.5"].local_name
    if not iso.is_file():
        pytest.skip(f"{iso} not present")
    parts = []
    with ISO9660.open(iso) as image:
        for path in PARTS:
            buf = io.BytesIO()
            image.copy_to(image.find(path), buf)
            parts.append(buf.getvalue())
    return join_parts(parts)


def test_pck00017_header_and_crc(pck00017):
    (member,) = read_archive(pck00017)
    assert member.name == MEMBER
    assert member.length == MEMBER_LENGTH
    assert member.disk_addr == HEADER_LEN
    assert member.shannon  # format doc section 9
    (info_offset,) = struct.unpack_from("<I", pck00017, INFO_OFFSET_FIELD)
    assert zlib.crc32(pck00017[member.disk_addr : info_offset]) == member.crc


def test_pck00017_decodes_to_the_compiler(pck00017):
    data = decode_member(pck00017, MEMBER, expected_size=MEMBER_LENGTH)
    # Only derived values reach an assertion, so a failure never prints compiler bytes.
    size, head = len(data), bytes(data[:2])
    assert size == MEMBER_LENGTH
    assert head == b"MZ"
    # The 10.5 compiler is bound as an LX image (the other linear-executable variant DOS/4GW
    # loads), not LE: le.LE refuses it ("no LE header found"). So check the header level: the
    # MZ's e_lfanew points at the "LX" signature with little-endian byte and word order.
    (lfanew,) = struct.unpack_from("<I", data, MZ_LFANEW_FIELD)
    signature = bytes(data[lfanew : lfanew + 4])
    assert signature == b"LX\0\0"


def test_decoded_compiler_matches_manifest(pck00017):
    """The 10.5 pin in config/watcom.toml is what the ISO decodes to (D-01): re-derived from the
    owner's media on every real run, compared through the manifest loader, never a literal."""
    key = next(k for k in MANIFEST["10.5"].key_files if k.path == "BINW/WCC386.EXE")
    assert key.wpack == tuple(PARTS)
    assert key.wpack_member == MEMBER
    assert key.known_bad is False
    got = hash_bytes(decode_member(pck00017, MEMBER, expected_size=MEMBER_LENGTH))
    assert (got.size, got.md5, got.sha1, got.crc32) == (key.size, key.md5, key.sha1, key.crc32)
