"""symbols.py: the one address <-> linker-name mapping (P8). Made-up addresses throughout, except
the documented runtime public `exit_`."""

from __future__ import annotations

import inspect

import pytest

from libtree import body, code_module, write_lib
from reverseapoc import symbols as symbols_module
from reverseapoc.functions import (
    SYMBOL_KINDS,
    FunctionRow,
    SymbolRow,
    runtime_aliases,
    runtime_entries,
    seed_runtime_rows,
)
from reverseapoc.libmatch import MatchRange, load_libraries
from reverseapoc.symbols import SYMBOL_KIND_FUNC, SymbolError, SymbolTable

GAME = FunctionRow(0x12345, 0x12350, "func_00012345", "game", "a", "call")
THUNK = FunctionRow(0x12350, 0x12358, "func_00012350", "thunk", "a", "call")
RUNTIME = FunctionRow(0x12360, 0x12380, "exit_", "runtime", "", "runtime")
DATA_IN_CODE = FunctionRow(0x12380, 0x12390, "D_00012380", "data-in-code", "a", "capstone")
OVERRIDDEN = FunctionRow(0x10010, 0x10020, "func_00010010", "game", "a", "entry")
FUNCTIONS = [OVERRIDDEN, GAME, THUNK, RUNTIME, DATA_IN_CODE]
SYMBOLS = [SymbolRow(0x10010, "main_", "func"), SymbolRow(0xD3000, "_errno", "data")]
DATA_RANGES = [(0xD0000, 0xE0000)]


@pytest.fixture
def table() -> SymbolTable:
    return SymbolTable.build(FUNCTIONS, SYMBOLS, data_ranges=DATA_RANGES)


def test_game_function_names(table):
    assert table.linker_name(0x12345) == "func_00012345_"
    assert table.c_name(0x12345) == "func_00012345"
    assert table.linker_name(0x12350) == "func_00012350_"  # thunks are func_ rows too


def test_data_names(table):
    assert table.linker_name(0xD2000, data=True) == "_D_000D2000"
    assert table.c_name(0xD2000, data=True) == "D_000D2000"


def test_runtime_names_are_the_public_verbatim(table):
    assert table.linker_name(0x12360) == "exit_"
    assert table.c_name(0x12360) == "exit_"


def test_data_in_code_rows_use_the_data_convention(table):
    assert table.linker_name(0x12380) == "_D_00012380"
    assert table.c_name(0x12380) == "D_00012380"


def test_symbols_csv_overrides_the_placeholder(table):
    assert table.linker_name(0x10010) == "main_"
    assert table.address_of("main_") == 0x10010
    assert table.linker_name(0xD3000, data=True) == "_errno"


def test_linker_name_refuses_an_address_that_starts_no_row(table):
    with pytest.raises(SymbolError, match="0x00012346"):
        table.linker_name(0x12346)


def test_address_of(table):
    assert table.address_of("func_00012345_") == 0x12345
    assert table.address_of("_D_000D2000") == 0xD2000
    assert table.address_of("exit_") == 0x12360
    assert table.address_of("_D_00012380") == 0x12380
    assert table.address_of("_errno") == 0xD3000


def test_address_of_refuses_an_unknown_symbol(table):
    with pytest.raises(SymbolError, match="helper_"):
        table.address_of("helper_")


def test_address_of_refuses_a_placeholder_that_is_not_a_row_start(table):
    with pytest.raises(SymbolError, match="func_00012346_"):
        table.address_of("func_00012346_")


def test_address_of_refuses_data_outside_every_data_range(table):
    with pytest.raises(SymbolError, match="_D_000F0000"):
        table.address_of("_D_000F0000")


def test_address_of_refuses_a_lowercase_placeholder(table):
    with pytest.raises(SymbolError):
        table.address_of("func_000d2000_")


def test_round_trip_through_names(table):
    for row in FUNCTIONS:
        assert table.address_of(table.linker_name(row.start)) == row.start


def test_function_at_and_containing(table):
    assert table.function_at(0x12345) == GAME
    assert table.function_at(0x12346) is None
    assert table.containing(0x12346) == GAME
    assert table.containing(0x12350) == THUNK  # touching rows: the end belongs to the next row
    assert table.containing(0x12358) is None  # the gap before the runtime row
    assert table.containing(0x10000) is None


def test_two_symbols_for_one_address_are_refused():
    symbols = [SymbolRow(0x10010, "main_", "func"), SymbolRow(0x10010, "start_", "func")]
    with pytest.raises(SymbolError, match="0x00010010"):
        SymbolTable.build(FUNCTIONS, symbols)


def test_a_func_symbol_must_name_a_row_start():
    with pytest.raises(SymbolError, match="0x00012346"):
        SymbolTable.build(FUNCTIONS, [SymbolRow(0x12346, "helper_", "func")])


def test_runtime_aliases_resolve_to_their_row(tmp_path):
    # Orchestrator ruling F12: one row per offset, every alias still resolves through address_of.
    watcom = tmp_path / "w"
    publics = [("_nquux_", 0), ("quux_", 0), ("quux2_", 4)]
    write_lib(watcom, "10.6", "DOS/CLIB3R.LIB", [code_module("quux", body(8), publics=publics)])
    libraries, _ = load_libraries(watcom, ("10.6",))
    runtime = [
        MatchRange(
            0x12360,
            0x12368,
            "_TEXT",
            "quux",
            ("DOS/CLIB3R.LIB",),
            ("10.6",),
            ("_nquux_", "quux2_", "quux_"),
            "unique",
        ),  # fmt: skip
    ]
    entries = runtime_entries(runtime, libraries)
    table = SymbolTable.build(
        seed_runtime_rows(runtime, libraries), aliases=runtime_aliases(entries)
    )
    assert table.linker_name(0x12360) == "quux_"
    assert table.address_of("quux_") == table.address_of("_nquux_") == 0x12360
    assert table.address_of("quux2_") == 0x12364


def test_an_alias_must_name_a_runtime_row_start():
    with pytest.raises(SymbolError, match="_nexit_"):
        SymbolTable.build(FUNCTIONS, aliases={"_nexit_": 0x12361})


def test_one_name_for_two_addresses_is_refused():
    with pytest.raises(SymbolError, match="exit_"):
        SymbolTable.build(FUNCTIONS, aliases={"exit_": 0x12360, "_exit_": 0x12360},
                          symbols=[SymbolRow(0xD3000, "exit_", "data")])  # fmt: skip


def test_a_runtime_name_at_two_addresses_is_ambiguous():
    # A module-local table public (like _Alphabet in both itoa and ltoa) seeds two runtime rows
    # of one name: each row keeps its name, but the name resolves to no single address.
    rows = [
        FunctionRow(0x12360, 0x12364, "_tbl", "runtime", "", "runtime"),
        FunctionRow(0x12364, 0x12370, "one_", "runtime", "", "runtime"),
        FunctionRow(0x12380, 0x12384, "_tbl", "runtime", "", "runtime"),
    ]
    table = SymbolTable.build(rows)
    assert table.linker_name(0x12380) == "_tbl"
    assert table.ambiguous == {"_tbl": (0x12360, 0x12380)}
    assert table.address_of("one_") == 0x12364
    with pytest.raises(SymbolError, match="_tbl.*ambiguous"):
        table.address_of("_tbl")


# ---- 05-REVIEW deferred minors (DI-19 rows 3, 7a, 7b, 7c) ----


@pytest.mark.parametrize(
    "address",
    [0xF0000, 0xE0000, 0xCFFFF],  # past the range, its exclusive end, just before its start
    ids=["past", "at-end", "before"],
)
def test_data_symbol_outside_every_data_range_is_refused(address):
    symbols = [SymbolRow(address, "_far", "data")]
    with pytest.raises(SymbolError, match=f"0x{address:08X}"):
        SymbolTable.build(FUNCTIONS, symbols, data_ranges=DATA_RANGES)


def test_data_symbol_inside_a_data_range_loads():
    for address in (0xD0000, 0xDFFFF):  # the range's first and last byte
        table = SymbolTable.build(FUNCTIONS, [SymbolRow(address, "_x", "data")],
                                  data_ranges=DATA_RANGES)  # fmt: skip
        assert table.address_of("_x") == address


def test_data_symbol_is_not_range_checked_without_data_ranges():
    # Orchestrator ruling F6: a CSV-only caller has no LE, so it passes no data ranges.
    table = SymbolTable.build(FUNCTIONS, [SymbolRow(0xF0000, "_far", "data")])
    assert table.address_of("_far") == 0xF0000


def test_address_of_refuses_the_placeholder_of_a_renamed_address(table):
    with pytest.raises(SymbolError, match="main_"):
        table.address_of("func_00010010_")


def test_address_of_refuses_the_data_placeholder_of_a_renamed_address(table):
    with pytest.raises(SymbolError, match="_errno"):
        table.address_of("_D_000D3000")


def test_symbol_kind_func_is_one_of_symbol_kinds():
    assert SYMBOL_KIND_FUNC == "func"
    assert SYMBOL_KIND_FUNC in SYMBOL_KINDS
    source = inspect.getsource(symbols_module)
    assert '"func"' not in source and "'func'" not in source  # no second literal for the kind
