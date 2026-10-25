"""The one address <-> name mapping of the split (P8, research Pattern 5 rule 8).

This is the only naming function: the target ELF writer, the relocation check, the asm writer and
the scorer all call it, so the names objdiff pairs on cannot drift between them (Pitfall 3).

Linker names follow Watcom's register calling convention, as the probe externs show
(`func_00012345_`, `_D_000D2000`):

- a game or thunk row func_XXXXXXXX links as func_XXXXXXXX_ (a trailing underscore);
- data D_XXXXXXXX, and a data-in-code row named so, links as _D_XXXXXXXX (a leading one);
- a runtime row links under its Watcom public verbatim (`exit_`), and so does each alias placed
  at the same offset (`_nmalloc_` next to `malloc_`, orchestrator ruling F12);
- a symbols.csv row (D-19) names its address verbatim and wins over the placeholder.

XXXXXXXX is the linear address at the preferred base as 8 uppercase hex digits.
"""

from __future__ import annotations

import bisect
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from .functions import (
    ADDRESS_DIGITS,
    DATA_PREFIX,
    GAME_PREFIX,
    KIND_DATA_IN_CODE,
    KIND_GAME,
    KIND_RUNTIME,
    KIND_THUNK,
    SYMBOL_KINDS,
    FunctionRow,
    SymbolRow,
    data_name,
    game_name,
)

FUNCTION_LINK_SUFFIX = "_"  # Watcom register convention: func_X -> func_X_
DATA_LINK_PREFIX = "_"  # and D_X -> _D_X
SYMBOL_KIND_FUNC = SYMBOL_KINDS[0]  # functions.SYMBOL_KINDS is (func, data)
SYMBOL_KIND_DATA = SYMBOL_KINDS[1]
_HEX_ADDRESS = f"([0-9A-F]{{{ADDRESS_DIGITS}}})"
_GAME_LINK = re.compile(re.escape(GAME_PREFIX) + _HEX_ADDRESS + re.escape(FUNCTION_LINK_SUFFIX))
_DATA_LINK = re.compile(re.escape(DATA_LINK_PREFIX + DATA_PREFIX) + _HEX_ADDRESS)
_HEX_BASE = 16
_PLACEHOLDER_KINDS = (KIND_GAME, KIND_THUNK)


class SymbolError(ValueError):
    """A name or address has no mapping, or the inputs of a SymbolTable disagree."""


def _hex(va: int) -> str:
    return f"0x{va:0{ADDRESS_DIGITS}X}"


def _add_name(names: dict[str, int], name: str, va: int) -> None:
    known = names.setdefault(name, va)
    if known != va:
        raise SymbolError(f"{name} names both {_hex(known)} and {_hex(va)}")


def _runtime_names(
    pairs: Iterable[tuple[str, int]],
) -> tuple[dict[str, int], dict[str, tuple[int, ...]]]:
    """(unique, ambiguous): each runtime row name or alias with its one address, and each name
    placed at more than one address (a module-local public such as _Alphabet, which omf.py
    reads like any other public) with all of them, sorted."""
    addresses: dict[str, set[int]] = defaultdict(set)
    for name, va in pairs:
        addresses[name].add(va)
    unique = {name: next(iter(vas)) for name, vas in addresses.items() if len(vas) == 1}
    ambiguous = {name: tuple(sorted(vas)) for name, vas in addresses.items() if len(vas) > 1}
    return unique, ambiguous


@dataclass(frozen=True)
class SymbolTable:
    """Names for one EXE, built from its functions.csv rows, symbols.csv rows, runtime aliases
    and the [start, end) of its LE data objects."""

    rows: tuple[FunctionRow, ...]  # sorted by start
    starts: tuple[int, ...]
    by_start: Mapping[int, FunctionRow]
    symbols: Mapping[int, SymbolRow]  # symbols.csv, by address
    names: Mapping[str, int]  # runtime names, aliases and symbols.csv names -> address
    data_ranges: tuple[tuple[int, int], ...]
    ambiguous: Mapping[str, tuple[int, ...]] = field(default_factory=dict)  # runtime names only

    @classmethod
    def build(
        cls,
        functions: Sequence[FunctionRow],
        symbols: Sequence[SymbolRow] = (),
        *,
        data_ranges: Sequence[tuple[int, int]] = (),
        aliases: Mapping[str, int] | None = None,
    ) -> SymbolTable:
        """`data_ranges` are the LE data objects, given by the caller from le.objects; `aliases`
        are functions.runtime_aliases, each naming a runtime row start.

        A symbols.csv data row must lie in one of `data_ranges`, but only when they are given:
        production callers always pass data_ranges(le) (check.load_exe, cli._split_inputs),
        while a CSV-only caller has no LE and passes none (orchestrator ruling F6)."""
        rows = tuple(sorted(functions, key=lambda row: row.start))
        by_start = {row.start: row for row in rows}
        by_address = _symbols_by_address(symbols, by_start, data_ranges)
        aliases = aliases or {}
        for alias, va in aliases.items():
            _check_alias(alias, va, by_start)
        runtime = [(row.name, row.start) for row in rows if row.kind == KIND_RUNTIME]
        names, ambiguous = _runtime_names([*runtime, *aliases.items()])
        for symbol in by_address.values():
            if symbol.name in ambiguous:
                raise SymbolError(f"symbols.csv name {symbol.name} is also a runtime public")
            _add_name(names, symbol.name, symbol.address)
        return cls(rows, tuple(row.start for row in rows), by_start, by_address, names,
                   tuple(data_ranges), ambiguous)  # fmt: skip

    # ---- address -> row ----

    def function_at(self, va: int) -> FunctionRow | None:
        """The row starting at `va`, or None."""
        return self.by_start.get(va)

    def containing(self, va: int) -> FunctionRow | None:
        """The row with start <= va < end, or None."""
        index = bisect.bisect_right(self.starts, va) - 1
        if index < 0 or va >= self.rows[index].end:
            return None
        return self.rows[index]

    # ---- address -> name ----

    def linker_name(self, va: int, *, data: bool = False) -> str:
        """The name the linker and objdiff see for `va`: a symbols.csv name, else `_D_<va>` for
        data, else the name of the row starting at `va` in its kind's convention."""
        symbol = self.symbols.get(va)
        if symbol is not None:
            return symbol.name
        if data:
            return DATA_LINK_PREFIX + data_name(va)
        row = self._row_at(va)
        if row.kind in _PLACEHOLDER_KINDS:
            return game_name(va) + FUNCTION_LINK_SUFFIX
        if row.kind == KIND_DATA_IN_CODE:
            return DATA_LINK_PREFIX + data_name(va)
        return row.name

    def c_name(self, va: int, *, data: bool = False) -> str:
        """The name C source writes for `va`: func_<va> or D_<va> for placeholders, runtime
        publics and symbols.csv names verbatim."""
        symbol = self.symbols.get(va)
        if symbol is not None:
            return symbol.name
        if data:
            return data_name(va)
        row = self._row_at(va)
        if row.kind in _PLACEHOLDER_KINDS:
            return game_name(va)
        if row.kind == KIND_DATA_IN_CODE:
            return data_name(va)
        return row.name

    def _row_at(self, va: int) -> FunctionRow:
        row = self.by_start.get(va)
        if row is None:
            raise SymbolError(f"no functions.csv row starts at {_hex(va)}")
        return row

    # ---- name -> address ----

    def address_of(self, name: str) -> int:
        """The address a linker name stands for; SymbolError for anything this table does not
        know (a placeholder whose address starts no row or lies in no data range, the
        placeholder of an address symbols.csv renames, or an unknown name)."""
        game = _GAME_LINK.fullmatch(name)
        if game is not None:
            va = int(game.group(1), _HEX_BASE)
            self._refuse_renamed(name, va)
            return self._placeholder_function(name, va)
        data = _DATA_LINK.fullmatch(name)
        if data is not None:
            va = int(data.group(1), _HEX_BASE)
            self._refuse_renamed(name, va)
            return self._placeholder_data(name, va)
        if name in self.ambiguous:
            places = ", ".join(_hex(va) for va in self.ambiguous[name])
            raise SymbolError(f"{name} is ambiguous: a runtime public at {places}")
        va = self.names.get(name)
        if va is None:
            raise SymbolError(f"unknown symbol {name}")
        return va

    def _refuse_renamed(self, name: str, va: int) -> None:
        """A placeholder of an address symbols.csv names is not that address's linker name."""
        symbol = self.symbols.get(va)
        if symbol is not None:
            raise SymbolError(f"{name}: symbols.csv names {_hex(va)} {symbol.name}")

    def _placeholder_function(self, name: str, va: int) -> int:
        row = self.by_start.get(va)
        if row is None or row.kind not in _PLACEHOLDER_KINDS:
            raise SymbolError(f"{name}: no game or thunk row starts at {_hex(va)}")
        return va

    def _placeholder_data(self, name: str, va: int) -> int:
        row = self.by_start.get(va)
        if row is not None and row.kind == KIND_DATA_IN_CODE:
            return va
        if _in_data_range(va, self.data_ranges):
            return va
        raise SymbolError(f"{name}: {_hex(va)} is in no data object and starts no data-in-code row")


def _in_data_range(va: int, data_ranges: Sequence[tuple[int, int]]) -> bool:
    return any(start <= va < end for start, end in data_ranges)


def _symbols_by_address(
    symbols: Sequence[SymbolRow],
    by_start: Mapping[int, FunctionRow],
    data_ranges: Sequence[tuple[int, int]],
) -> dict[int, SymbolRow]:
    """symbols.csv by address: one name per address, a func symbol names a row start, and a
    data symbol lies in a data range when any are given (rows 3, 7b of 05-REVIEW)."""
    by_address: dict[int, SymbolRow] = {}
    for symbol in symbols:
        if symbol.address in by_address:
            raise SymbolError(f"symbols.csv names {_hex(symbol.address)} twice")
        _check_symbol(symbol, by_start, data_ranges)
        by_address[symbol.address] = symbol
    return by_address


def _check_symbol(
    symbol: SymbolRow, by_start: Mapping[int, FunctionRow], data_ranges: Sequence[tuple[int, int]]
) -> None:
    where = f"{symbol.name} at {_hex(symbol.address)}"
    if symbol.kind == SYMBOL_KIND_FUNC and symbol.address not in by_start:
        raise SymbolError(f"symbols.csv func {where} starts no functions.csv row")
    if symbol.kind != SYMBOL_KIND_DATA or not data_ranges:
        return
    if not _in_data_range(symbol.address, data_ranges):
        raise SymbolError(f"symbols.csv data {where} lies in no data object")


def _check_alias(alias: str, va: int, by_start: Mapping[int, FunctionRow]) -> None:
    row = by_start.get(va)
    if row is None or row.kind != KIND_RUNTIME:
        raise SymbolError(f"runtime alias {alias} at {_hex(va)} starts no runtime row")
