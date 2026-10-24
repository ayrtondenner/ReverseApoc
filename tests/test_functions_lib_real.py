"""Runtime functions.csv rows from the committed runtime.csv and the owner's 10.6 LIB386.

config/<stem>/runtime.csv gives each runtime module's range; the public offsets inside it come
from the installed Watcom 10.6 libraries. Skipped unless 10.6 is installed (`requires_version`);
never in CI, because the libraries are never committed. Point REVERSEAPOC_WATCOM_DIR at the main
checkout's third_party/watcom to run these from a worktree.
"""

from __future__ import annotations

import pytest

from conftest import WATCOM_DIR, requires_version
from reverseapoc.functions import (
    FunctionRow,
    format_functions_csv,
    read_functions_csv,
    runtime_aliases,
    runtime_entries,
    seed_runtime_rows,
)
from reverseapoc.libmatch import LoadedLibrary, load_libraries, read_runtime_csv, runtime_csv_path
from reverseapoc.symbols import SymbolTable

EXES = ("UFO2P.EXE", "TACP.EXE")


@pytest.fixture(scope="module")
def libraries() -> list[LoadedLibrary]:
    requires_version("10.6")
    loaded, _ = load_libraries(WATCOM_DIR, ("10.6",))
    return loaded


def _by_name(rows: list[FunctionRow]) -> dict[str, FunctionRow]:
    return {row.name: row for row in rows}


def test_runtime_publics_from_lib386(libraries):
    runtime = read_runtime_csv(runtime_csv_path("UFO2P.EXE"))
    rows = seed_runtime_rows(runtime, libraries)
    named = _by_name(rows)
    assert named["__CMain"].start == 0x000C5C9C
    assert named["exit_"].start == 0x000C01E1  # Pitfall 8: exit_ is the module start + 1
    assert all(row.kind == "runtime" and row.evidence == "runtime" for row in rows)


@pytest.mark.parametrize("exe", EXES)
def test_every_seeded_row_lies_inside_its_runtime_row(exe, libraries, tmp_path):
    runtime = read_runtime_csv(runtime_csv_path(exe))
    rows = seed_runtime_rows(runtime, libraries)
    assert rows
    for row in rows:
        assert row.start < row.end
        assert any(r.start <= row.start and row.end <= r.end for r in runtime), row
    path = tmp_path / "functions.csv"
    path.write_text(format_functions_csv(rows, name=exe), encoding="utf-8")
    assert read_functions_csv(path) == rows


@pytest.mark.parametrize("exe", EXES)
def test_every_alias_shares_its_rows_start(exe, libraries):
    entries = runtime_entries(read_runtime_csv(runtime_csv_path(exe)), libraries)
    assert any(len(e.aliases) > 1 for e in entries)  # malloc_/_nmalloc_ and the like (F12)
    for entry in entries:
        assert entry.name in entry.aliases


@pytest.mark.parametrize("exe", EXES)
def test_runtime_names_and_aliases_build_one_symbol_table(exe, libraries):
    runtime = read_runtime_csv(runtime_csv_path(exe))
    entries = runtime_entries(runtime, libraries)
    table = SymbolTable.build(
        seed_runtime_rows(runtime, libraries), aliases=runtime_aliases(entries)
    )
    # _Alphabet heads both itoa and ltoa: a module-local table, so it names no single address.
    assert set(table.ambiguous) == {"_Alphabet"}
    for entry in entries:
        assert table.linker_name(entry.start) == entry.name
        unique = [alias for alias in entry.aliases if alias not in table.ambiguous]
        assert all(table.address_of(alias) == entry.start for alias in unique)
