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
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from conftest import ORIG_DIR, WATCOM_DIR, requires_capstone, requires_ghidra, requires_version
from reverseapoc.asm import data_ranges
from reverseapoc.functions import (
    RUNTIME_VERSION,
    FunctionRow,
    Reconciled,
    boundaries_csv_path,
    check_unit_assignment,
    format_boundaries_csv,
    format_functions_csv,
    functions_csv_path,
    missing_verdicts,
    read_boundaries_csv,
    read_functions_csv,
    read_symbols_csv,
    read_units_csv,
    reconcile,
    runtime_aliases,
    runtime_entries,
    seed_runtime_rows,
    symbols_csv_path,
    units_csv_path,
)
from reverseapoc.ghidra import DEFAULT_EXPORT_DIR, EXPORT_NAME, export_functions, read_ghidra_export
from reverseapoc.le import LE
from reverseapoc.libmatch import (
    LoadedLibrary,
    MatchRange,
    load_libraries,
    read_runtime_csv,
    runtime_csv_path,
)
from reverseapoc.symbols import SYMBOL_KIND_FUNC, SymbolTable

EXES = ("UFO2P.EXE", "TACP.EXE")
EXPORT_ENV = "REVERSEAPOC_GHIDRA_EXPORT"
UNIT_NAME = re.compile(r"[a-z0-9_]+")
SPIKE_FUNCTIONS = ("main_",)  # spike 005: a linker name no functions.csv row carries


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


def _libraries(matches: list[MatchRange]) -> list[LoadedLibrary]:
    """The LIB386 of the version each runtime row is seeded from (the rule of the `functions`
    verb: 10.6 where the row lists it, else its first version)."""
    versions = {RUNTIME_VERSION if RUNTIME_VERSION in m.versions else m.versions[0]
                for m in matches if m.versions}  # fmt: skip
    for version in sorted(versions):
        requires_version(version)
    return load_libraries(WATCOM_DIR, sorted(versions))[0]


def _runtime_rows(matches: list[MatchRange]) -> list[FunctionRow]:
    return seed_runtime_rows(matches, _libraries(matches))


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


def _present(path: Path, how: str) -> Path:
    """A file committed for every EXE: missing is a failure, not a skip."""
    assert path.is_file(), f"{path} missing: {how}"
    return path


UNITS_HINT = "run `uv run reverseapoc units <exe> --write`"
SYMBOLS_HINT = "write it by hand from the spike 005 name table (D-19)"


@pytest.mark.parametrize("name", EXES)
def test_every_function_in_one_unit(name):
    """D-11: every functions.csv row lies in exactly one unit and its unit column says which."""
    functions = read_functions_csv(_committed(functions_csv_path(name), name))
    units = read_units_csv(_present(units_csv_path(name), UNITS_HINT))
    assert check_unit_assignment(functions, units) == []


@pytest.mark.parametrize("name", EXES)
def test_unit_names_are_safe(name):
    """Unit names become file names (src/<exe>/<unit>.c): [a-z0-9_]+ and unique."""
    names = [unit.unit for unit in read_units_csv(_present(units_csv_path(name), UNITS_HINT))]
    assert names
    assert [n for n in names if not UNIT_NAME.fullmatch(n)] == []
    assert len(set(names)) == len(names)


@pytest.mark.parametrize("name", EXES)
def test_symbols_resolve(name):
    """D-19: every symbols.csv name resolves through SymbolTable to its own address, a func name
    to a functions.csv start and a data name to the EXE's data object; the spike 005 names that
    no row carries are there."""
    path = ORIG_DIR / name
    if not path.is_file():
        pytest.skip(f"{path} not present (run `uv run reverseapoc ingest` or set REVERSEAPOC_ORIG)")
    functions = read_functions_csv(_committed(functions_csv_path(name), name))
    symbols = read_symbols_csv(_present(symbols_csv_path(name), SYMBOLS_HINT))
    matches = read_runtime_csv(runtime_csv_path(name))
    ranges = data_ranges(LE(path))
    aliases = runtime_aliases(runtime_entries(matches, _libraries(matches)))
    table = SymbolTable.build(functions, symbols, data_ranges=ranges, aliases=aliases)
    assert [s.name for s in symbols if table.address_of(s.name) != s.address] == []
    starts = {row.start for row in functions}
    funcs = [s for s in symbols if s.kind == SYMBOL_KIND_FUNC]
    assert [s.name for s in funcs if s.address not in starts] == []
    data = [s for s in symbols if s.kind != SYMBOL_KIND_FUNC]
    assert [s.name for s in data if not any(lo <= s.address < hi for lo, hi in ranges)] == []
    assert set(SPIKE_FUNCTIONS) <= {s.name for s in funcs}
