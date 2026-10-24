"""The committed split (SPL-01, SPL-02) against the real executables, LIB386 and Ghidra export.

config/<stem>/functions.csv and boundaries.csv are only written by `uv run reverseapoc functions
<EXE> --ghidra-export PATH --write`; a person writes only the verdict and reason of the
boundaries rows the D-07 rule leaves open (D-08). These tests re-derive both files from
orig/<EXE>, the capstone pass, config/<stem>/runtime.csv with the installed LIB386, the cached
Ghidra export and the committed hand verdicts, and fail on any text difference, so a hand edit of
a tool-owned column or a rule change that moves a row cannot pass unnoticed (the runtime.csv
precedent, tests/test_libmatch_real.py).

The Ghidra export is read from REVERSEAPOC_GHIDRA_EXPORT (a directory holding
<stem>/functions.raw.csv; point it at the main checkout's build/ghidra to run from a worktree),
else from build/ghidra. When the cached file is missing and Ghidra is installed
(GHIDRA_INSTALL_DIR, or the container) it is exported into build/ghidra first.

Skipped, naming the missing input, unless orig/<EXE>, the Watcom trees the runtime rows are
seeded from, capstone and the export (or Ghidra) are present; they never run in CI because
neither the game nor Ghidra's output is ever committed. Assertions compare text and addresses
only, never game bytes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from conftest import ORIG_DIR, WATCOM_DIR, requires_capstone, requires_ghidra, requires_version
from reverseapoc.functions import (
    RUNTIME_VERSION,
    FunctionRow,
    Reconciled,
    boundaries_csv_path,
    format_boundaries_csv,
    format_functions_csv,
    functions_csv_path,
    missing_verdicts,
    read_boundaries_csv,
    read_units_csv,
    reconcile,
    seed_runtime_rows,
    units_csv_path,
)
from reverseapoc.ghidra import DEFAULT_EXPORT_DIR, EXPORT_NAME, export_functions, read_ghidra_export
from reverseapoc.le import LE
from reverseapoc.libmatch import MatchRange, load_libraries, read_runtime_csv, runtime_csv_path

EXES = ("UFO2P.EXE", "TACP.EXE")
EXPORT_ENV = "REVERSEAPOC_GHIDRA_EXPORT"


@dataclass(frozen=True)
class Regenerated:
    name: str
    functions: str  # functions.csv text as the `functions --write` verb would write it
    boundaries: str  # boundaries.csv text likewise
    result: Reconciled


def _stem(name: str) -> str:
    return Path(name).stem.lower()


def _committed(path: Path, name: str) -> Path:
    """A committed config file; skips (per EXE) until the plan step that writes it has run."""
    if not path.is_file():
        pytest.skip(f"{path} not committed yet (run `uv run reverseapoc functions {name} --write`)")
    return path


def _export_csv(name: str) -> Path:
    """The cached Ghidra export of `name`; exported into build/ghidra first when it is missing
    and Ghidra is installed (skips naming GHIDRA_INSTALL_DIR otherwise)."""
    root = Path(os.environ[EXPORT_ENV]) if EXPORT_ENV in os.environ else DEFAULT_EXPORT_DIR
    cached = root / _stem(name) / EXPORT_NAME
    if cached.is_file():
        return cached
    requires_ghidra()
    return export_functions(name, ORIG_DIR, DEFAULT_EXPORT_DIR).path


def _runtime_rows(matches: list[MatchRange]) -> list[FunctionRow]:
    """The seeded runtime rows, from the LIB386 of the version each row is seeded from (the
    rule of the `functions` verb: 10.6 where the row lists it, else its first version)."""
    versions = {RUNTIME_VERSION if RUNTIME_VERSION in m.versions else m.versions[0]
                for m in matches if m.versions}  # fmt: skip
    for version in sorted(versions):
        requires_version(version)
    libraries, _ = load_libraries(WATCOM_DIR, sorted(versions))
    return seed_runtime_rows(matches, libraries)


@pytest.fixture(scope="module", params=EXES)
def regenerated(request) -> Regenerated:
    """Both CSVs re-derived exactly as `functions <EXE> --write` derives them: the committed
    boundaries.csv supplies the hand verdicts, the committed units.csv (when present) the unit
    column."""
    from reverseapoc.discover import discover  # capstone: import only once it is known present
    from reverseapoc.units import assign_units

    name = request.param
    requires_capstone()
    path = ORIG_DIR / name
    if not path.is_file():
        pytest.skip(f"{path} not present (run `uv run reverseapoc ingest` or set REVERSEAPOC_ORIG)")
    boundaries = _committed(boundaries_csv_path(name), name)
    _committed(functions_csv_path(name), name)
    export = _export_csv(name)
    le = LE(path)
    matches = read_runtime_csv(runtime_csv_path(name))
    runtime_rows = _runtime_rows(matches)
    found = discover(le, runtime_starts=[row.start for row in runtime_rows])
    result = reconcile(le, read_ghidra_export(export), found, runtime_rows,
                       existing=read_boundaries_csv(boundaries), modules=matches)  # fmt: skip
    units = units_csv_path(name)
    rows = assign_units(result.functions, read_units_csv(units)) if units.is_file() else (
        result.functions)  # fmt: skip
    return Regenerated(name, format_functions_csv(rows, name),
                       format_boundaries_csv(result.boundaries, name), result)  # fmt: skip


def test_functions_csv_has_no_drift(regenerated):
    committed = functions_csv_path(regenerated.name).read_text(encoding="utf-8")
    assert regenerated.functions == committed


def test_boundaries_csv_has_no_drift(regenerated):
    committed = boundaries_csv_path(regenerated.name).read_text(encoding="utf-8")
    assert regenerated.boundaries == committed


def test_no_hand_verdict_lost(regenerated):
    """A regeneration keeps every committed hand verdict: none replaced by the rule, none
    dropped as no longer a disagreement (05-13 review round 1)."""
    assert regenerated.result.replaced == ()
    assert regenerated.result.dropped_hand == ()


@pytest.mark.parametrize("name", EXES)
def test_every_disagreement_has_a_verdict(name):
    """D-08: every Ghidra/capstone disagreement carries a verdict and a reason."""
    rows = read_boundaries_csv(_committed(boundaries_csv_path(name), name))
    assert rows, f"{name}: boundaries.csv lists no disagreement"
    assert [f"0x{a:08X}" for a in missing_verdicts(rows)] == []
    assert [f"0x{r.address:08X}" for r in rows if not r.reason] == []
