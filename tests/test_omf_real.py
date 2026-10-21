"""Facts of the real Watcom LIB386 libraries (survey of 2026-10-21; counts and names only).

Each test skips unless WATCOM_DIR/<version> is installed (`uv run reverseapoc install-watcom
<version>`, or REVERSEAPOC_WATCOM_DIR pointing at the installed trees, which is how a git worktree
reads them). They never run in CI: the compilers are proprietary and never committed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import WATCOM_DIR, requires_version
from reverseapoc.omf import Library, read_library


def load(path: Path) -> Library:
    return read_library(path.read_bytes(), path=path.relative_to(WATCOM_DIR).as_posix())


@pytest.mark.parametrize(("version", "count"), [("10.5", 544), ("10.6", 549), ("11.0", 970)])
def test_clib3r_module_counts(version: str, count: int):
    root = requires_version(version)
    lib = load(root / "LIB386" / "DOS" / "CLIB3R.LIB")
    assert len(lib.modules) == count
    assert lib.failures == ()
