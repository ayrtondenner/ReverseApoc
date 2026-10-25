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

Skipped, naming the missing input, unless orig/<EXE>, capstone and the export (or Ghidra) are
present; they never run in CI because neither the game nor Ghidra's output is ever committed.
Once the game file is there, a Watcom version a runtime.csv row lists without its LIB386 tree
installed is a failure, not a skip. Assertions compare text and addresses
only, never game bytes.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from conftest import ORIG_DIR, WATCOM_DIR, requires_capstone, requires_ghidra
from reverseapoc import cli
from reverseapoc.asm import OBJ_EXECUTABLE, data_ranges
from reverseapoc.functions import (
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
    symbols_csv_path,
    units_csv_path,
)
from reverseapoc.ghidra import DEFAULT_EXPORT_DIR, EXPORT_NAME, export_functions, read_ghidra_export
from reverseapoc.le import LE
from reverseapoc.libmatch import (
    LIB_DIR,
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
# Code-object bytes past the last functions.csv row, which no row and so no unit covers: UFO2P's
# 3 bytes at 0x000CFADA are the target of the jump that is all of func_000CFAB6; neither Ghidra
# nor capstone starts a function there, so it is no disagreement either (see the 05-16 SUMMARY).
UNCOVERED_TAIL = {"UFO2P.EXE": 3, "TACP.EXE": 0}
FUNCTIONS_HINT = "run `uv run reverseapoc functions <exe> --ghidra-export PATH --write`"
UNITS_HINT = "run `uv run reverseapoc units <exe> --write`"
SYMBOLS_HINT = "write it by hand from the spike 005 name table (D-19)"


@dataclass(frozen=True)
class Regenerated:
    name: str
    functions: str  # functions.csv text as the `functions --write` verb would write it
    boundaries: str  # boundaries.csv text likewise
    result: Reconciled


def _stem(name: str) -> str:
    return Path(name).stem.lower()


def _present(path: Path, how: str) -> Path:
    """A committed config file: missing is a failure, never a skip (only the game and Ghidra
    inputs, which are never committed, may skip)."""
    assert path.is_file(), f"{path} missing: {how}"
    return path


def _orig(name: str) -> Path:
    path = ORIG_DIR / name
    if not path.is_file():
        pytest.skip(f"{path} not present (run `uv run reverseapoc ingest` or set REVERSEAPOC_ORIG)")
    return path


def _export_root() -> Path:
    """REVERSEAPOC_GHIDRA_EXPORT when set, else build/ghidra."""
    return Path(os.environ[EXPORT_ENV]) if EXPORT_ENV in os.environ else DEFAULT_EXPORT_DIR


def _export_csv(name: str) -> Path:
    """The cached Ghidra export of `name` under _export_root(); exported there first when it is
    missing and Ghidra is installed (skips naming GHIDRA_INSTALL_DIR otherwise)."""
    root = _export_root()
    cached = root / _stem(name) / EXPORT_NAME
    if cached.is_file():
        return cached
    requires_ghidra()
    return export_functions(name, ORIG_DIR, root).path


def _listed_versions(matches: list[MatchRange]) -> list[str]:
    """Every Watcom version some runtime.csv row lists, after asserting that its LIB386 tree is
    installed under WATCOM_DIR. Strict: a listed version without its tree fails loudly, it is
    never skipped (the game file is present by now, so the comparison must run)."""
    versions = sorted({version for match in matches for version in match.versions})
    missing = [v for v in versions if not (WATCOM_DIR / v / LIB_DIR).is_dir()]
    assert missing == [], (
        f"runtime.csv rows list Watcom {missing}, whose {LIB_DIR} trees are not under "
        f"{WATCOM_DIR} (run `uv run reverseapoc install-watcom` or set REVERSEAPOC_WATCOM_DIR)"
    )
    return versions


def _runtime_rows(matches: list[MatchRange]) -> list[FunctionRow]:
    """The runtime rows exactly as the `functions` verb seeds them, through cli's own helper,
    which picks each row's version itself (05-REVIEW row 16a: no copy of its rule here)."""
    _listed_versions(matches)
    return cli._seeded_runtime_rows(matches, WATCOM_DIR)


def _libraries(matches: list[MatchRange]) -> list[LoadedLibrary]:
    """The LIB386 of every version a runtime row lists; functions.runtime_entries picks each
    row's version from them by the verb's own rule."""
    return load_libraries(WATCOM_DIR, _listed_versions(matches))[0]


@pytest.fixture(scope="module", params=EXES)
def regenerated(request) -> Regenerated:
    """Both CSVs re-derived exactly as `functions <EXE> --write` derives them: the committed
    boundaries.csv supplies the hand verdicts, the committed units.csv (when present) the unit
    column."""
    from reverseapoc.discover import discover  # capstone: import only once it is known present
    from reverseapoc.units import assign_units

    name = request.param
    boundaries = _present(boundaries_csv_path(name), FUNCTIONS_HINT)
    _present(functions_csv_path(name), FUNCTIONS_HINT)
    requires_capstone()
    path = _orig(name)
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
    rows = read_boundaries_csv(_present(boundaries_csv_path(name), FUNCTIONS_HINT))
    assert rows, f"{name}: boundaries.csv lists no disagreement"
    assert [f"0x{a:08X}" for a in missing_verdicts(rows)] == []
    assert [f"0x{r.address:08X}" for r in rows if not r.reason] == []


@pytest.mark.parametrize("name", EXES)
def test_every_function_in_one_unit(name):
    """D-11: every functions.csv row lies in exactly one unit and its unit column says which."""
    functions = read_functions_csv(_present(functions_csv_path(name), FUNCTIONS_HINT))
    units = read_units_csv(_present(units_csv_path(name), UNITS_HINT))
    assert check_unit_assignment(functions, units) == []


@pytest.mark.parametrize("name", EXES)
def test_units_tile_the_code(name):
    """D-11 coverage rule, the part that needs the LE: the units start at the code object's base,
    and past the last functions.csv row only the UNCOVERED_TAIL bytes remain, in no row and no
    unit. The gap-free tiling up to that row is CSV-only and runs without orig/
    (tests/test_units.py::test_committed_units_tile_their_rows)."""
    functions = read_functions_csv(_present(functions_csv_path(name), FUNCTIONS_HINT))
    units = sorted(read_units_csv(_present(units_csv_path(name), UNITS_HINT)),
                   key=lambda unit: unit.start)  # fmt: skip
    (code,) = [obj for obj in LE(_orig(name)).objects if obj.flags & OBJ_EXECUTABLE]
    assert units[0].start == code.base
    last_end = max(row.end for row in functions)
    assert code.end - last_end == UNCOVERED_TAIL[name]


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
    functions = read_functions_csv(_present(functions_csv_path(name), FUNCTIONS_HINT))
    symbols = read_symbols_csv(_present(symbols_csv_path(name), SYMBOLS_HINT))
    path = _orig(name)
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
