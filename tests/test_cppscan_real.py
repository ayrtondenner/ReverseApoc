"""The C vs C++ scan on the real executables (counts, priorities and addresses only).

The runtime map is computed live (libmatch.load_libraries + scan_exe over SWEPT_VERSIONS), not
read from config/<stem>/runtime.csv. Skipped unless orig/UFO2P.EXE and orig/TACP.EXE exist and
every swept Watcom version is installed (REVERSEAPOC_ORIG / REVERSEAPOC_WATCOM_DIR point a git
worktree at the main checkout's copies, read-only). They never run in CI.
"""

from __future__ import annotations

import pytest

from conftest import ORIG_DIR, WATCOM_DIR, requires_version
from reverseapoc.cppscan import PRIO_DTOR, PRIO_PROGRAM, CppScanReport, scan
from reverseapoc.le import LE
from reverseapoc.libmatch import SWEPT_VERSIONS, LoadedLibrary, load_libraries, scan_exe

EXES = ("UFO2P.EXE", "TACP.EXE")

pytestmark = pytest.mark.skipif(
    not all((ORIG_DIR / name).is_file() for name in EXES),
    reason="orig/UFO2P.EXE and orig/TACP.EXE not present (run `uv run reverseapoc ingest`)",
)


@pytest.fixture(scope="module")
def libraries() -> list[LoadedLibrary]:
    for version in SWEPT_VERSIONS:
        requires_version(version)
    loaded, _skipped = load_libraries(WATCOM_DIR)
    return loaded


@pytest.fixture(scope="module", params=EXES)
def report(request, libraries) -> CppScanReport:
    le = LE(ORIG_DIR / request.param)
    rows = scan_exe(le, libraries, exe=request.param).ranges
    return scan(le, rows, WATCOM_DIR, exe=request.param)


def test_verdict_is_c(report):
    assert report.verdict.startswith("C (wcc386)"), report.verdict
    assert report.xi
    assert not [e for e in report.xi if e.priority == PRIO_PROGRAM]
    assert not [e for e in report.yi if e.priority == PRIO_DTOR]
