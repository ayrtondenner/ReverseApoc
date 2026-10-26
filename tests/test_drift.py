"""D-22 drift test, run in CI without game files: the gate-written status.csv and the matched C
agree.

For each EXE, the matched rows of config/<exe>/status.csv name exactly the func_ functions the
C under src/<exe>/ defines at file scope (check.source_marks, configure.py's D-12 parser), and
each matched row's source_sha256 is the LF-normalised SHA-256 of its unit file today. So a row
added by hand, a match reverted to INCLUDE_ASM, a new definition nobody gated, or any edit of
matched C (a comment included) fails here until `reverseapoc gate` runs again in the container
(D-21). The planted cases run on tmp copies of the committed tables and C.

D-22 point 3: the committed decomphub.progress.json is byte for byte what tools/progress.py
derives from the committed CSVs, the same derivation gate writes it with (06-18).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from reverseapoc.check import source_marks
from reverseapoc.functions import read_functions_csv
from reverseapoc.status import (
    MATCHED,
    StatusRow,
    lf_sha256,
    read_status,
    status_path,
    write_status,
)
from test_progress import load_progress

EXES = ("ufo2p", "tacp")
CONFIG = REPO_ROOT / "config"
SRC = REPO_ROOT / "src"
FUNCTIONS_CSV = "functions.csv"
UNIT_SUFFIX = ".c"
# The Phase 5 matches the table holds from 06-16 on; the planted cases work on the UFO2P one.
PLANT_EXE, PLANT_UNIT, PLANT_FUNC = "ufo2p", "u_000a34f0", "func_000A3980"
PLANT_STUB = "func_000A3970"  # an INCLUDE_ASM row of the same unit
FEED = REPO_ROOT / "decomphub.progress.json"


def _read(path: Path) -> str:
    """A unit file as check reads it: strict UTF-8 bytes, never read_text (a lone CR stays)."""
    return path.read_bytes().decode("utf-8")


def matched_rows(config_root: Path, exe: str) -> list[StatusRow]:
    return [r for r in read_status(status_path(config_root, exe)) if r.status == MATCHED]


def defined_functions(config_root: Path, src_root: Path, exe: str) -> set[str]:
    """The union of source_marks(...).defined over src/<exe>/*.c, each file read with its own
    unit's functions.csv rows."""
    rows = read_functions_csv(Path(config_root) / exe / FUNCTIONS_CSV)
    defined: set[str] = set()
    for path in sorted((Path(src_root) / exe).glob(f"*{UNIT_SUFFIX}")):
        unit_rows = [row for row in rows if row.unit == path.stem]
        defined |= source_marks(_read(path), unit_rows).defined
    return defined


def name_drift(config_root: Path, src_root: Path, exe: str) -> list[str]:
    """What the matched names and the defined names do not share, as readable problems."""
    matched = {r.name for r in matched_rows(config_root, exe)}
    defined = defined_functions(config_root, src_root, exe)
    return ([f"{exe}: {name} is matched in status.csv but not defined in C"
             for name in sorted(matched - defined)]
            + [f"{exe}: {name} is defined in C but has no matched row (run gate)"
               for name in sorted(defined - matched)])  # fmt: skip


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
    """D-22 point 1: status.csv's matched names are exactly the functions the C defines."""
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
        f"{PLANT_EXE}: {PLANT_STUB} is matched in status.csv but not defined in C"]
    table.write_bytes(committed)

    # 2. The matched definition removed (reverted to its INCLUDE_ASM marker).
    text = _read(unit)
    head = text.index(f"int {PLANT_FUNC}(void)\n{{")
    unit.write_bytes((text[:head] + f"INCLUDE_ASM({PLANT_FUNC});\n").encode("utf-8"))
    problems = drift(config_root, src_root, PLANT_EXE)
    assert f"{PLANT_EXE}: {PLANT_FUNC} is matched in status.csv but not defined in C" in problems
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
