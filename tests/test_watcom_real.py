"""Facts of the real Watcom CD images (survey of 2026-10-19).

Skipped unless the media is present: run `uv run reverseapoc fetch-watcom`, or point the
environment variable REVERSEAPOC_WATCOM_MEDIA at a directory holding the ISOs (useful when
testing from a git worktree, which has no third_party/). They never run in CI because the media
is proprietary and never committed. Nothing is extracted and the images are not hashed here.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from reverseapoc.iso9660 import ISO9660, ISOError
from reverseapoc.watcom import load_watcom_manifest

MEDIA_DIR = Path(
    os.environ.get("REVERSEAPOC_WATCOM_MEDIA") or REPO_ROOT / "third_party" / "watcom-media"
)
MANIFEST = load_watcom_manifest()

pytestmark = pytest.mark.skipif(
    not MEDIA_DIR.is_dir(),
    reason=f"{MEDIA_DIR} not present (run `uv run reverseapoc fetch-watcom` or set "
    "REVERSEAPOC_WATCOM_MEDIA)",
)

COMMON = {"LIB386/DOS/CLIB3R.LIB": None, "LIB386/MATH3R.LIB": None}  # None: must exist

# version -> (volume id, {path: size or None})
EXPECTED = {
    "10.5": ("WATCOM_C105", {"BINNT/WCC386.EXE": 9216, "BINW/WCC386.EXE": 65536, **COMMON}),
    "10.6": ("WATCOM_C106", {"BINNT/WCC386.EXE": 9216, "BINW/WCC386.EXE": 567698, **COMMON}),
    "11.0": (
        "WATCOMC_110",
        {
            "BINNT/WCC386.EXE": 24064,
            "BINNT/WCCD386.DLL": 659968,
            "BINW/WCC386.EXE": 653342,
            **COMMON,
        },
    ),
    "11.0a": (
        "WATCOMC110A",
        {
            "BINNT/WCC386.EXE": 24576,
            "BINNT/WCCD386.DLL": 666624,
            "BINW/WCC386.EXE": 659300,
            "LIB386/DOS/CLIB3R.LIB": 480256,
            "LIB386/MATH3R.LIB": 66560,
        },
    ),
    "11.0b": (
        "WATCOM_C11B",
        {
            "BINNT/WCC386.EXE": 25088,
            "BINNT/WCCD386.DLL": 668160,
            "BINW/WCC386.EXE": 660850,
            "LIB386/DOS/CLIB3R.LIB": 481280,
            "LIB386/MATH3R.LIB": 67584,
        },
    ),
}


def _iso(version: str) -> Path:
    path = MEDIA_DIR / MANIFEST[version].local_name
    if not path.is_file():
        pytest.skip(f"{path} not present")
    return path


@pytest.mark.parametrize("version", list(EXPECTED))
def test_image_layout(version):
    volume_id, expected = EXPECTED[version]
    media = MANIFEST[version]
    iso = _iso(version)
    assert iso.stat().st_size == media.size
    with ISO9660.open(iso) as image:
        index = {e.path: e for e in image.walk(skip_dirs=media.skip_dirs)}
        assert image.volume_id == volume_id
    for path, size in expected.items():
        assert path in index, path
        if size is not None:
            assert index[path].size == size, path


def test_11_0b_damaged_directory_is_documented():
    iso = _iso("11.0b")
    assert MANIFEST["11.0b"].skip_dirs == ("SAMPLES/WIN/DATACTL/WIN16",)
    with ISO9660.open(iso) as image, pytest.raises(ISOError, match="SAMPLES/WIN/DATACTL/WIN16"):
        list(image.walk())
