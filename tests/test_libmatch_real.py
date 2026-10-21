"""The committed runtime maps (D-06) against the real executables and LIB386 trees.

config/<stem>/runtime.csv is only written by `uv run reverseapoc libmatch <EXE> --write`. These
tests re-derive both files from orig/ and the swept Watcom trees and fail on any text difference,
so a hand edit or a matcher change that moves a row cannot pass unnoticed.

Skipped unless orig/<EXE> exists (`uv run reverseapoc ingest`) and every swept version is
installed (`requires_version`); they never run in CI because neither is ever committed. Point
REVERSEAPOC_ORIG and REVERSEAPOC_WATCOM_DIR at the main checkout to run them from a worktree.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from conftest import ORIG_DIR, WATCOM_DIR, requires_version
from reverseapoc.le import LE
from reverseapoc.libmatch import (
    SWEPT_VERSIONS,
    LibMatchReport,
    LoadedLibrary,
    MatchRange,
    Skipped,
    format_runtime_csv,
    load_libraries,
    read_runtime_csv,
    runtime_csv_path,
    scan_exe,
)

EXES = ("UFO2P.EXE", "TACP.EXE")


@dataclass(frozen=True)
class Scanned:
    name: str
    le: LE
    report: LibMatchReport


@pytest.fixture(scope="module")
def libraries() -> tuple[list[LoadedLibrary], list[Skipped]]:
    """Every swept version's LIB386 tree, loaded once for both EXEs."""
    for version in SWEPT_VERSIONS:
        requires_version(version)
    return load_libraries(WATCOM_DIR, SWEPT_VERSIONS)


@pytest.fixture(scope="module", params=EXES)
def scanned(request, libraries) -> Scanned:
    name = request.param
    path = ORIG_DIR / name
    if not path.is_file():
        pytest.skip(f"{path} not present (run `uv run reverseapoc ingest` or set REVERSEAPOC_ORIG)")
    loaded, skipped = libraries
    le = LE(path)
    return Scanned(name, le, scan_exe(le, loaded, exe=name, skipped=skipped))


def _committed_csv(name: str) -> Path:
    path = runtime_csv_path(name)
    assert path.is_file(), f"{path} missing: run `uv run reverseapoc libmatch {name} --write`"
    return path


def _committed_rows(name: str) -> list[MatchRange]:
    return read_runtime_csv(_committed_csv(name))


def test_runtime_csv_has_no_drift(scanned):
    fresh = format_runtime_csv(scanned.report, scanned.name)
    assert fresh == _committed_csv(scanned.name).read_text(encoding="utf-8")


def test_cstart_at_entry_point(scanned):
    """`_cstart_` sits on the LE entry point, which corroborates the whole map."""
    rows = [r for r in _committed_rows(scanned.name) if "_cstart_" in r.publics]
    assert [r.start for r in rows] == [scanned.le.entry_va]


def test_some_module_discriminates_versions(scanned):
    """D-07: at least one module matches only some of the swept versions."""
    swept = set(SWEPT_VERSIONS)
    assert any(set(r.versions) < swept for r in _committed_rows(scanned.name))


def test_rows_do_not_overlap(scanned):
    rows = sorted(_committed_rows(scanned.name), key=lambda r: r.start)
    assert rows
    for row, following in zip(rows, rows[1:], strict=False):
        assert row.end <= following.start, f"{row.describe()} overlaps {following.describe()}"


def test_summary_names_discriminating_modules(scanned):
    """D-07 evidence for the docs: a version set smaller than all swept versions, with names."""
    every = f"versions {'+'.join(SWEPT_VERSIONS)}"
    sets = [line.split(": ") for line in scanned.report.summary() if line.startswith("versions ")]
    assert any(len(parts) == 3 and parts[0] != every and parts[2] for parts in sets)
