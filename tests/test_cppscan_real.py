"""The C vs C++ scan on the real executables (counts, priorities and addresses only).

The runtime map is computed live (libmatch.load_libraries + scan_exe over SWEPT_VERSIONS), not
read from config/<stem>/runtime.csv. Skipped unless orig/UFO2P.EXE and orig/TACP.EXE exist and
every swept Watcom version is installed (REVERSEAPOC_ORIG / REVERSEAPOC_WATCOM_DIR point a git
worktree at the main checkout's copies, read-only). They never run in CI.
"""

from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from conftest import ORIG_DIR, WATCOM_DIR, requires_version
from reverseapoc.cppscan import PRIO_DTOR, PRIO_PROGRAM, CppScanReport, scan
from reverseapoc.le import LE
from reverseapoc.libmatch import (
    CPP_LIBRARY_PREFIXES,
    SWEPT_VERSIONS,
    LoadedLibrary,
    Skipped,
    load_libraries,
    scan_exe,
)

EXES = ("UFO2P.EXE", "TACP.EXE")

pytestmark = pytest.mark.skipif(
    not all((ORIG_DIR / name).is_file() for name in EXES),
    reason="orig/UFO2P.EXE and orig/TACP.EXE not present (run `uv run reverseapoc ingest`)",
)


def is_cpp(relpath: str) -> bool:
    """An independent oracle for "a C++ runtime library" (PLIB*, PLBX*, CPLX*)."""
    return PurePosixPath(relpath).name.upper().startswith(CPP_LIBRARY_PREFIXES)


@pytest.fixture(scope="module")
def sweep() -> tuple[list[LoadedLibrary], list[Skipped]]:
    for version in SWEPT_VERSIONS:
        requires_version(version)
    return load_libraries(WATCOM_DIR)


@pytest.fixture(scope="module")
def libraries(sweep) -> list[LoadedLibrary]:
    return sweep[0]


@pytest.fixture(scope="module", params=EXES)
def report(request, libraries) -> CppScanReport:
    le = LE(ORIG_DIR / request.param)
    rows = scan_exe(le, libraries, exe=request.param).ranges
    return scan(le, rows, WATCOM_DIR, exe=request.param)


def test_cpp_libraries_were_swept_and_none_was_skipped(sweep):
    """"No C++-only runtime module" means nothing unless C++ libraries were in the sweep."""
    loaded, skipped = sweep
    for version in SWEPT_VERSIONS:
        cpp = [lib for lib in loaded if lib.version == version and is_cpp(lib.relpath)]
        assert cpp, f"no C++ library was loaded from Watcom {version}"
    assert [s for s in skipped if is_cpp(s.library)] == []


def test_verdict_is_c(report):
    assert report.verdict.startswith("C (wcc386): "), report.verdict
    assert report.cpp_only_gap == ""  # the C++-only module signal was computed, not skipped
    assert report.xi
    assert not [e for e in report.xi if e.priority == PRIO_PROGRAM]
    assert not [e for e in report.yi if e.priority == PRIO_DTOR]


def test_no_cpp_signals(report):
    assert report.cpp_only_modules == ()
    assert (report.wcpp_strings, report.mangled_strings) == (0, 0)
