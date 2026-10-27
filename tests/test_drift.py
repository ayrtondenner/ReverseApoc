"""D-22 drift test, run in CI without game files: the gate-written status.csv and the matched C
agree.

For each EXE, the matched rows of config/<exe>/status.csv start exactly where the functions the
C under src/<exe>/ defines at file scope start (check.source_marks, the shared unitdefs finder,
with C names from symbols.csv, D-29), compared by start so a renamed function is no drift, and
each matched row's source_sha256 is the LF-normalised SHA-256 of its unit file today. So a row
added by hand, a match reverted to INCLUDE_ASM, a new definition nobody gated, or any edit of
matched C (a comment included) fails here until `reverseapoc gate` runs again in the container
(D-21). The planted cases run on tmp copies of the committed tables and C.

D-22 point 3: the committed decomphub.progress.json is byte for byte what tools/progress.py
derives from the committed CSVs, the same derivation gate writes it with (06-18).
"""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from reverseapoc.check import source_marks
from reverseapoc.functions import SymbolRow, read_functions_csv, read_symbols_csv, write_symbols_csv
from reverseapoc.status import (
    MATCHED,
    StatusRow,
    lf_sha256,
    read_status,
    status_path,
    write_status,
)
from reverseapoc.unitdefs import c_names
from test_progress import load_progress

EXES = ("ufo2p", "tacp")
CONFIG = REPO_ROOT / "config"
SRC = REPO_ROOT / "src"
FUNCTIONS_CSV = "functions.csv"
SYMBOLS_CSV = "symbols.csv"
UNIT_SUFFIX = ".c"
# The Phase 5 matches the table holds from 06-16 on; the planted cases work on the UFO2P one.
PLANT_EXE, PLANT_UNIT, PLANT_FUNC = "ufo2p", "u_000a34f0", "func_000A3980"
PLANT_STUB = "func_000A3970"  # an INCLUDE_ASM row of the same unit
PLANT_START = 0x000A3980  # PLANT_FUNC's start
PLANT_NAME = "SoundVolume"  # the planted rename's C name (symbols.csv SoundVolume_)
FEED = REPO_ROOT / "decomphub.progress.json"


def _read(path: Path) -> str:
    """A unit file as check reads it: strict UTF-8 bytes, never read_text (a lone CR stays)."""
    return path.read_bytes().decode("utf-8")


def matched_rows(config_root: Path, exe: str) -> list[StatusRow]:
    return [r for r in read_status(status_path(config_root, exe)) if r.status == MATCHED]


def _hex(start: int) -> str:
    return f"0x{start:08X}"


def exe_names(config_root: Path, exe: str) -> dict[str, int]:
    """C name -> start for every game and thunk row of `exe` (unitdefs.c_names over
    functions.csv and symbols.csv)."""
    exe_config = Path(config_root) / exe
    return c_names(read_functions_csv(exe_config / FUNCTIONS_CSV),
                   read_symbols_csv(exe_config / SYMBOLS_CSV))  # fmt: skip


def defined_starts(config_root: Path, src_root: Path, exe: str) -> dict[int, str]:
    """Start -> C name of every function the C under src/<exe>/*.c defines at file scope: the
    union of source_marks(...).defined_starts, each file read with its own unit's functions.csv
    rows and the EXE's C names."""
    rows = read_functions_csv(Path(config_root) / exe / FUNCTIONS_CSV)
    names = exe_names(config_root, exe)
    by_start = {start: name for name, start in names.items()}
    starts: set[int] = set()
    for path in sorted((Path(src_root) / exe).glob(f"*{UNIT_SUFFIX}")):
        unit_rows = [row for row in rows if row.unit == path.stem]
        starts |= source_marks(_read(path), unit_rows, all_names=names).defined_starts
    return {start: by_start[start] for start in starts}


def name_drift(config_root: Path, src_root: Path, exe: str) -> list[str]:
    """What the matched starts and the defined starts do not share, as readable problems."""
    matched = {r.start: r.name for r in matched_rows(config_root, exe)}
    defined = defined_starts(config_root, src_root, exe)
    return ([f"{exe}: {matched[start]} at {_hex(start)} is matched in status.csv but not "
             "defined in C" for start in sorted(matched.keys() - defined.keys())]
            + [f"{exe}: {defined[start]} at {_hex(start)} is defined in C but has no matched "
               "row (run gate)" for start in sorted(defined.keys() - matched.keys())])  # fmt: skip


def hash_drift(config_root: Path, src_root: Path, exe: str) -> list[str]:
    """Every matched row whose unit file is gone or hashes differently from its row."""
    problems = []
    for row in matched_rows(config_root, exe):
        path = Path(src_root) / exe / f"{row.unit}{UNIT_SUFFIX}"
        if not path.is_file():
            problems.append(f"{exe}: {row.name}: unit file {path.name} is gone")
        elif lf_sha256(_read(path)) != row.source_sha256:
            problems.append(f"{exe}: {row.name}: {path.name} changed since gate ran (re-gate it)")
    return problems


def drift(config_root: Path, src_root: Path, exe: str) -> list[str]:
    return name_drift(config_root, src_root, exe) + hash_drift(config_root, src_root, exe)


@pytest.mark.parametrize("exe", EXES)
def test_matched_rows_equal_defined_functions(exe):
    """D-22 point 1: status.csv's matched starts are exactly where the functions the C defines
    start."""
    assert matched_rows(CONFIG, exe), f"config/{exe}/status.csv has no matched row"
    assert name_drift(CONFIG, SRC, exe) == []


@pytest.mark.parametrize("exe", EXES)
def test_matched_units_hash(exe):
    """D-22 point 2: each matched row's source_sha256 is its unit file's lf_sha256 today."""
    rows = matched_rows(CONFIG, exe)
    assert rows, f"config/{exe}/status.csv has no matched row"
    assert hash_drift(CONFIG, SRC, exe) == []


@pytest.fixture
def planted(tmp_path) -> tuple[Path, Path]:
    """tmp copies of the committed config/<exe>/ tables and src/<exe>/ C, every EXE."""
    config_root, src_root = tmp_path / "config", tmp_path / "src"
    for exe in EXES:
        shutil.copytree(CONFIG / exe, config_root / exe)
        shutil.copytree(SRC / exe, src_root / exe)
    return config_root, src_root


def _unit_file(src_root: Path) -> Path:
    return src_root / PLANT_EXE / f"{PLANT_UNIT}{UNIT_SUFFIX}"


def test_drift_catches_planted_changes(planted):
    """A hand-added row, a removed definition and a one-character comment edit each fail."""
    config_root, src_root = planted
    for exe in EXES:  # the copies agree before anything is planted
        assert drift(config_root, src_root, exe) == []
    table = status_path(config_root, PLANT_EXE)
    committed = table.read_bytes()
    unit = _unit_file(src_root)
    original = unit.read_bytes()

    # 1. A matched row added by hand for a start the C still marks INCLUDE_ASM. Every other row
    # stays: the table holds other matches too (from the 06-26 pilot on), and dropping one would
    # read as a definition with no matched row.
    rows = read_status(table)
    (real,) = [r for r in rows if r.status == MATCHED and r.name == PLANT_FUNC]
    stub = next(row for row in read_functions_csv(config_root / PLANT_EXE / FUNCTIONS_CSV)
                if row.name == PLANT_STUB)  # fmt: skip
    write_status(table, [*(r for r in rows if r.start != stub.start),
                         StatusRow(stub.start, stub.name, PLANT_UNIT, MATCHED, 100.0, 0,
                                   real.source_sha256, real.date)])  # fmt: skip
    assert drift(config_root, src_root, PLANT_EXE) == [
        f"{PLANT_EXE}: {PLANT_STUB} at {_hex(stub.start)} is matched in status.csv but not "
        "defined in C"]
    table.write_bytes(committed)

    # 2. The matched definition removed (reverted to its INCLUDE_ASM marker).
    text = _read(unit)
    head = text.index(f"int {PLANT_FUNC}(void)\n{{")
    unit.write_bytes((text[:head] + f"INCLUDE_ASM({PLANT_FUNC});\n").encode("utf-8"))
    problems = drift(config_root, src_root, PLANT_EXE)
    assert (f"{PLANT_EXE}: {PLANT_FUNC} at {_hex(PLANT_START)} is matched in status.csv but not "
            "defined in C") in problems
    unit.write_bytes(original)

    # 3. One character of a comment edited: the C is the same code, but it was never gated.
    # Every matched row of the unit hashes the whole file, so each one reports it.
    edited = original.replace(b"Neither name", b"neither name", 1)
    assert edited != original
    unit.write_bytes(edited)
    stale = [r.name for r in matched_rows(config_root, PLANT_EXE) if r.unit == PLANT_UNIT]
    assert PLANT_FUNC in stale
    assert drift(config_root, src_root, PLANT_EXE) == [
        f"{PLANT_EXE}: {name}: {unit.name} changed since gate ran (re-gate it)" for name in stale]
    unit.write_bytes(original)
    assert drift(config_root, src_root, PLANT_EXE) == []


def _plant_rename(config_root: Path, src_root: Path) -> None:
    """symbols.csv names PLANT_FUNC's start SoundVolume_, and the unit's C is rewritten to the
    new C name (definition, comment and all)."""
    symbols = Path(config_root) / PLANT_EXE / SYMBOLS_CSV
    rows = [*read_symbols_csv(symbols), SymbolRow(PLANT_START, f"{PLANT_NAME}_", "func")]
    rows.sort(key=lambda row: row.address)
    write_symbols_csv(symbols, rows, f"{PLANT_EXE.upper()}.EXE")
    unit = _unit_file(src_root)
    unit.write_bytes(_read(unit).replace(PLANT_FUNC, PLANT_NAME).encode("utf-8"))


def _regate_hashes(config_root: Path, src_root: Path) -> None:
    """What gate would write for the planted unit's matched rows: today's source_sha256."""
    table = status_path(config_root, PLANT_EXE)
    digest = lf_sha256(_read(_unit_file(src_root)))
    write_status(table, [replace(r, source_sha256=digest) if r.unit == PLANT_UNIT else r
                         for r in read_status(table)])  # fmt: skip


def test_drift_by_start(planted):
    """D-29: the comparison is by start. A planted rename (a symbols.csv row and the unit's C
    rewritten to the new name) is no name drift; its hash drift is gate's to clear, and once the
    unit's rows carry today's hash nothing drifts. Deleting the renamed definition is drift
    naming the start."""
    config_root, src_root = planted
    for exe in EXES:
        assert name_drift(config_root, src_root, exe) == []
    _plant_rename(config_root, src_root)
    assert defined_starts(config_root, src_root, PLANT_EXE)[PLANT_START] == PLANT_NAME
    assert name_drift(config_root, src_root, PLANT_EXE) == []
    _regate_hashes(config_root, src_root)
    assert drift(config_root, src_root, PLANT_EXE) == []

    unit = _unit_file(src_root)
    text = _read(unit)
    head = text.index(f"int {PLANT_NAME}(void)\n{{")
    unit.write_bytes((text[:head] + f"INCLUDE_ASM({PLANT_NAME});\n").encode("utf-8"))
    assert name_drift(config_root, src_root, PLANT_EXE) == [
        f"{PLANT_EXE}: {PLANT_FUNC} at {_hex(PLANT_START)} is matched in status.csv but not "
        "defined in C"]


def derived_feed(config_root: Path) -> bytes:
    progress = load_progress()
    return progress.render(progress.build_decomphub(progress.derive(config_root)))


def test_committed_feed_is_derived():
    """D-22 point 3: decomphub.progress.json equals build_decomphub(derive(config/))."""
    assert FEED.is_file(), f"{FEED} is not committed; gate writes it (D-29)"
    assert FEED.read_bytes() == derived_feed(CONFIG), (
        "decomphub.progress.json drifted from the CSVs: re-run gate, or "
        "uv run python -I tools/progress.py --decomphub decomphub.progress.json")


def test_feed_drift_is_caught(planted):
    """A matched row removed from a tmp copy of status.csv changes the derived feed."""
    config_root, _ = planted
    before = derived_feed(config_root)
    table = status_path(config_root, PLANT_EXE)
    write_status(table, [r for r in read_status(table) if r.name != PLANT_FUNC])
    assert derived_feed(config_root) != before
