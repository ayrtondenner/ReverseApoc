"""The one "functions a unit defines" finder and the one C-naming rule (D-29, refines D-19).

configure.py's D-12 check, check.source_marks, the D-22 drift test, and later readlint and the
rename step all ask which game and thunk rows a unit file defines in C and which it marks
INCLUDE_ASM. They ask here, so a function renamed in symbols.csv is found by its start
everywhere at once.

The file is read through configure.py's translation phases (normalize_source, code_text:
comments and literals blanked, dead `#if 0` branches removed, any other conditional refused).
Definitions and markers are matched by any C identifier and mapped to row starts through C
names:

- a definition must use the row's current C name: a definition under the old placeholder of a
  renamed row is a problem (it would export bytes under a name no row has);
- an INCLUDE_ASM marker may use the current C name or the row's old placeholder (a marker
  emits no bytes, so a scaffold written before a rename still accounts for its row);
- a marker, a placeholder-shaped definition, or a definition of another row's known C name
  that names no game or thunk row of the unit is a problem; a definition of any other
  identifier is a helper and is ignored;
- every game or thunk row of the unit is defined or marked exactly once, never both.

C names (c_name_of): a func symbols.csv name links with Watcom's register-convention trailing
`_` (`Foo_` is C `Foo`), a data name with a leading `_` (`_g_vol` is C `g_vol`); a row without
a symbols.csv name keeps its functions.csv placeholder.
"""

from __future__ import annotations

import functools
import importlib.util
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from .functions import (
    ADDRESS_DIGITS,
    GAME_PREFIX,
    KIND_GAME,
    KIND_THUNK,
    SYMBOL_KINDS,
    FunctionRow,
    SymbolRow,
    game_name,
)
from .targets import REPO_ROOT

CONFIGURE = "configure.py"  # owns the translation phases; loaded by path, never copied
_LOADED_AS = "_reverseapoc_configure"  # the module name a by-path load registers under
_SCRIPT_NAMES = ("configure", "__main__", _LOADED_AS)  # where configure.py may already be loaded
FUNC_KIND, DATA_KIND = SYMBOL_KINDS  # symbols.csv kinds: (func, data)
FUNC_LINK_SUFFIX = "_"  # Watcom register convention: C Foo links as Foo_
DATA_LINK_PREFIX = "_"  # and C g_vol as _g_vol
_REQUIRED_KINDS = (KIND_GAME, KIND_THUNK)  # runtime and data-in-code rows are exempt (F5)

_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
PLACEHOLDER = re.compile(rf"{re.escape(GAME_PREFIX)}[0-9A-F]{{{ADDRESS_DIGITS}}}")
MARKER_ANY = re.compile(rf"\bINCLUDE_ASM\s*\(\s*({_IDENT})\s*\)\s*;")
# A declarator whose parameter list (one level of nested parentheses, for function pointers) is
# followed by `{`: a definition. A prototype ends in `;` and a call never meets a `{` directly;
# `if (x) {` and its kin match too, so C_KEYWORDS are never names.
DEFINITION_ANY = re.compile(rf"\b({_IDENT})\s*\((?:[^()]|\([^()]*\))*\)\s*\{{")
C_KEYWORDS = frozenset({
    # C89
    "auto", "break", "case", "char", "const", "continue", "default", "do", "double", "else",
    "enum", "extern", "float", "for", "goto", "if", "int", "long", "register", "return",
    "short", "signed", "sizeof", "static", "struct", "switch", "typedef", "union", "unsigned",
    "void", "volatile", "while",
    # Watcom calling conventions, modifiers and pointer kinds (include/watcom_compat.h)
    "__cdecl", "_cdecl", "__pascal", "_pascal", "__watcall", "__syscall", "_syscall",
    "__stdcall", "_stdcall", "__fastcall", "_fastcall", "__fortran", "_fortran", "__far",
    "_far", "__near", "_near", "__huge", "_huge", "__interrupt", "_interrupt", "__loadds",
    "_loadds", "__saveregs", "_saveregs", "__export", "_export", "__declspec", "__based",
    "_based", "__segment", "_segment", "__segname", "__self", "__inline", "_inline", "__asm",
    "_asm", "_Packed",
})  # fmt: skip


class UnitDefsError(ValueError):
    """A C name cannot be derived (a func linker name without its `_`), or configure.py is
    missing."""


@dataclass(frozen=True)
class UnitDefs:
    """What one unit file defines and marks, keyed by row start. `defined` and `marked` hold
    only game and thunk rows of the unit, each with the name the file wrote (the first one, when
    a row appears more than once). `problems` are the D-12 problems in configure.py's order:
    each row's completeness first, then `source_problems`, the problems of the file itself (a
    refused conditional, a stale placeholder definition, a marker or definition naming no row of
    the unit), which check reports as source problems of the unit."""

    defined: dict[int, str]
    marked: dict[int, str]
    problems: tuple[str, ...]
    source_problems: tuple[str, ...]


def c_name_of(linker: str, kind: str) -> str:
    """The C name of a symbols.csv linker name: a func name minus its trailing `_`, a data
    name minus its leading `_`. UnitDefsError (a ValueError) for a name without that `_`, an
    empty C name or an unknown kind."""
    if kind == FUNC_KIND:
        name = linker.removesuffix(FUNC_LINK_SUFFIX)
        changed = linker.endswith(FUNC_LINK_SUFFIX)
    elif kind == DATA_KIND:
        name = linker.removeprefix(DATA_LINK_PREFIX)
        changed = linker.startswith(DATA_LINK_PREFIX)
    else:
        raise UnitDefsError(f"{linker}: unknown symbol kind {kind!r}")
    if not changed or not name:
        where = "end" if kind == FUNC_KIND else "start"
        raise UnitDefsError(
            f"{kind} linker name {linker!r} does not {where} with Watcom's '_' around a C name"
        )
    return name


def _is_required(row: FunctionRow) -> bool:
    return row.kind in _REQUIRED_KINDS


def placeholders(rows: Iterable[FunctionRow]) -> dict[str, int]:
    """func_XXXXXXXX -> start for every game and thunk row of `rows`."""
    return {game_name(row.start): row.start for row in rows if _is_required(row)}


def c_names(rows: Iterable[FunctionRow], symbol_rows: Iterable[SymbolRow]) -> dict[str, int]:
    """C name -> start for every game and thunk row of `rows`: c_name_of its symbols.csv func
    name, else its placeholder."""
    renamed = {s.address: c_name_of(s.name, FUNC_KIND) for s in symbol_rows if s.kind == FUNC_KIND}
    names: dict[str, int] = {}
    for row in rows:
        if not _is_required(row):
            continue
        name = renamed.get(row.start, game_name(row.start))
        if names.setdefault(name, row.start) != row.start:
            first = names[name]
            raise UnitDefsError(f"C name {name} names both 0x{first:08X} and 0x{row.start:08X}")
    return names


def load_configure(path: Path) -> ModuleType:
    """configure.py at `path`: the module already imported from that file (as `configure`, as
    the running script, or by an earlier by-path load), else loaded by path (it is a script, not
    part of the package). UnitDefsError when the file is missing."""
    resolved = Path(path).resolve()
    for name in _SCRIPT_NAMES:
        loaded = sys.modules.get(name)
        if loaded is not None and Path(getattr(loaded, "__file__", "") or "").resolve() == resolved:
            return loaded
    spec = importlib.util.spec_from_file_location(_LOADED_AS, path)
    if not Path(path).is_file() or spec is None or spec.loader is None:
        raise UnitDefsError(f"{path} not found: unit files are read with its D-12 parser")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # its dataclasses look their module up while it executes
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[spec.name]
        raise
    return module


@functools.cache
def _configure() -> ModuleType:
    return load_configure(REPO_ROOT / CONFIGURE)


def _file_scope(code: str, pattern: re.Pattern[str]) -> list[str]:
    """The names `pattern` matches at brace depth 0 of `code` (comments already blanked)."""
    depth = 0
    position = 0
    found = []
    for match in pattern.finditer(code):
        between = code[position : match.start()]
        depth += between.count("{") - between.count("}")
        position = match.start()
        if depth == 0 and match.group(1) not in C_KEYWORDS:
            found.append(match.group(1))
    return found


def file_scope_definitions(code: str) -> list[str]:
    """The names of the function definitions at brace depth 0 of `code` (configure's code_text:
    comments and literals blanked, directives and dead branches removed), in file order, by any
    identifier but a C keyword. readlint (07-27) places each one on its token; it asks here so
    the two never disagree about what a definition is."""
    return _file_scope(code, DEFINITION_ANY)


@dataclass(frozen=True)
class _Names:
    """The names one find reads by: the unit's game and thunk rows by current C name and by old
    placeholder, and every known name of a row outside the unit."""

    current: dict[str, int]  # C name -> start
    old: dict[str, int]  # old placeholder -> start, for the unit's renamed rows
    cname: dict[int, str]  # start -> C name
    other: frozenset[str]  # C names and placeholders of rows outside the unit

    @classmethod
    def of(cls, required: Sequence[int], names: Mapping[str, int] | None,
           all_names: Mapping[str, int] | None, holders: Mapping[str, int]) -> _Names:  # fmt: skip
        """A row of the unit takes its C name from `names` when given, else from `all_names`
        (the EXE's current C names are authoritative), else its placeholder: a placeholder never
        overrides a C name passed in either map (fix round 1). Only `all_names` and
        `placeholders` name rows outside the unit."""
        own = set(required)
        given = [_own_names(m, own) for m in (names, all_names) if m is not None]
        cname = {start: next((g[start] for g in given if start in g), game_name(start))
                 for start in required}  # fmt: skip
        current = {name: start for start, name in cname.items()}
        own_holders = {**holders, **{game_name(start): start for start in required}}
        old = {p: s for p, s in own_holders.items() if s in own and p not in current}
        other = frozenset(n for n, s in {**holders, **(all_names or {})}.items() if s not in own)
        return cls(current, old, cname, other)


def _own_names(names: Mapping[str, int], own: set[int]) -> dict[int, str]:
    """start -> C name for the starts of `own` that `names` names; UnitDefsError when it gives
    one start two names (which would make the row's current name a guess)."""
    by_start: dict[int, str] = {}
    for name, start in names.items():
        if start not in own:
            continue
        if by_start.setdefault(start, name) != name:
            raise UnitDefsError(f"0x{start:08X} has two C names: {by_start[start]} and {name}")
    return by_start


@dataclass
class _Found:
    """What one pass over the live code found: names by start, stale placeholder definitions,
    and names that belong to no game or thunk row of the unit."""

    by_start: dict[int, list[str]] = field(default_factory=dict)
    stale: list[str] = field(default_factory=list)
    outside: list[str] = field(default_factory=list)

    def add(self, start: int, name: str) -> None:
        self.by_start.setdefault(start, []).append(name)

    def count(self, start: int) -> int:
        return len(self.by_start.get(start, ()))

    def first(self) -> dict[int, str]:
        return {start: found[0] for start, found in self.by_start.items()}


def _read_markers(code: str, names: _Names) -> _Found:
    """INCLUDE_ASM markers: under the current C name or the old placeholder, or outside."""
    found = _Found()
    for name in MARKER_ANY.findall(code):
        start = names.current.get(name, names.old.get(name))
        if start is None:
            found.outside.append(name)
        else:
            found.add(start, name)
    return found


def _read_definitions(code: str, names: _Names) -> _Found:
    """File-scope definitions: under the current C name, stale under the old placeholder, or
    outside when they name another row or are placeholder-shaped. Any other identifier is a
    helper and is left out."""
    found = _Found()
    for name in _file_scope(code, DEFINITION_ANY):
        if name in names.current:
            found.add(names.current[name], name)
        elif name in names.old:
            found.stale.append(name)
        elif name in names.other or PLACEHOLDER.fullmatch(name):
            found.outside.append(name)
    return found


def _row_problem(name: str, defined: int, marked: int) -> str | None:
    """configure.py's D-12 messages for one row, named by its C name."""
    if defined and marked:
        return f"{name} is both defined in C and marked INCLUDE_ASM"
    if marked > 1:
        return f"{name} is marked INCLUDE_ASM {marked} times"
    if defined > 1:
        return f"{name} is defined {defined} times"
    if not defined and not marked:
        return f"{name} is neither defined in C nor marked INCLUDE_ASM (D-12)"
    return None


def _source_problems(marks: _Found, defs: _Found, names: _Names) -> list[str]:
    """The problems of the file itself, outside names sorted as configure.py sorts them."""
    problems = [f"{n} is marked INCLUDE_ASM but is not a function of the unit"
                for n in sorted(set(marks.outside))]  # fmt: skip
    problems += [f"{n} is defined in C but is not a function of the unit"
                 for n in sorted(set(defs.outside))]  # fmt: skip
    for old in dict.fromkeys(defs.stale):
        new = names.cname[names.old[old]]
        problems.append(f"{old} is defined in C under its old placeholder: symbols.csv names it "
                        f"{new}, so the definition must be {new}")  # fmt: skip
    return problems


def find(
    text: str,
    unit_rows: Sequence[FunctionRow],
    *,
    placeholders: Mapping[str, int],
    names: Mapping[str, int] | None = None,
    all_names: Mapping[str, int] | None = None,
) -> UnitDefs:
    """What `text` (a unit file) defines and marks, by start, and its D-12 problems.

    A game or thunk row of the unit is read under its current C name: from `names` when given
    (C name -> start), else from `all_names` (the EXE's c_names, authoritative), else its
    placeholder; with neither map given, the pre-D-29 placeholder reading applies. `all_names`
    alone decides which known names belong to rows outside the unit, so a definition of another
    unit's renamed function is refused instead of read as a helper; entries of `names` for other
    starts are ignored. `placeholders` maps placeholders to starts, so a renamed row's old
    placeholder is recognised. #include problems are not read here
    (configure.include_problems)."""
    cfg = _configure()
    try:
        code = cfg.code_text(text)
    except cfg._ConditionalError as exc:
        return UnitDefs({}, {}, (str(exc),), (str(exc),))
    required = [row.start for row in unit_rows if _is_required(row)]
    table = _Names.of(required, names, all_names, placeholders)
    marks, defs = _read_markers(code, table), _read_definitions(code, table)
    stale = {table.old[old] for old in defs.stale}
    rows = [_row_problem(table.cname[start], defs.count(start), marks.count(start))
            for start in required
            if start not in stale or defs.count(start) or marks.count(start)]  # fmt: skip
    source = tuple(_source_problems(marks, defs, table))
    problems = tuple(p for p in rows if p is not None) + source
    return UnitDefs(defs.first(), marks.first(), problems, source)
