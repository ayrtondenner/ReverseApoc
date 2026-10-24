# Derived from KKND-Decomp tools/gen_units.py (CC0 1.0), https://github.com/Wyrelade/KKND-Decomp
"""The units draft (SPL-03, D-11) and the INCLUDE_ASM scaffold of a unit's source (SPL-04, D-12).

A unit is an address range of the code object: Watcom emits a module's functions out of source
order and lets one fall through into the next, so units are ranges, never source orders
(05-RESEARCH Pattern 4). `draft_units` walks functions.csv in address order and cuts a new unit
where the LE gives a reason, recorded in units.csv:

- `runtime`: a runtime.csv module starts or ends; every row of one module is unit rt_<module>;
- `source-string`: a function references a string naming a source file (a `__FILE__` or assert
  string such as `source\\grafix.c`): the file stem names the unit;
- `chk-cluster`: the __CHK prologue (`push imm32; call __CHK`) starts or stops (the modules
  built with stack checks sit together);
- `data-order`: a function references a string below every string its unit referenced so far
  (string literals are module-private and laid out module by module);
- `alignment-gap`: only filler or zero bytes lie before a 16-aligned function start.

Other units are named u_<start> in lowercase hex; a repeated name gets _2, _3. A jump table that
touches the function after it (a leading table) always goes with that function. The draft is a
draft: a unit that is wrong is re-cut by hand (reason `hand`) and `units --write` never replaces
units.csv unless asked to.

`scaffold_unit` writes src/<exe>/<unit>.c: `#include "common.h"` and one
`INCLUDE_ASM(func_XXXXXXXX);` marker per game and thunk function of the unit, which emits no
bytes, so the in-place splice keeps the original bytes. `write_unit_source` never overwrites a
file: matched C lives there.
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from . import x86
from .discover import code_objects
from .functions import KIND_DATA_IN_CODE, KIND_GAME, KIND_THUNK, FunctionRow, UnitRow
from .le import LE, SRC_OFF32, Fixup
from .libmatch import MatchRange
from .targets import config_dir


class UnitsError(ValueError):
    """Units cannot be drafted, or a unit source cannot be scaffolded."""


REASON_FIRST = "first"
REASON_RUNTIME = "runtime"
REASON_CHK = "chk-cluster"
REASON_SOURCE = "source-string"
REASON_DATA_ORDER = "data-order"
REASON_GAP = "alignment-gap"
RUNTIME_PREFIX = "rt_"
UNIT_PREFIX = "u_"
UNIT_ALIGNMENT = 16  # a unit's _TEXT starts paragraph-aligned after the previous one's filler
_SCAFFOLDED = (KIND_GAME, KIND_THUNK)  # rows that get a marker (orchestrator ruling F5)
_MAX_INSN = 15  # longest x86 instruction
_MAX_STRING = 256  # bytes read when looking for a C string's terminating NUL
_MIN_STRING = 2  # shorter runs of printable bytes are not taken for a string
_PRINTABLE = frozenset(range(0x20, 0x7F)) | {0x09, 0x0A, 0x0D}
_SOURCE_FILE = re.compile(r"(?:^|[\\/:\s])([A-Za-z0-9_]+)\.(?:c|cc|cpp)(?![A-Za-z0-9_])", re.I)
_NOT_UNIT_CHAR = re.compile(r"[^a-z0-9_]")

# The __CHK prologue at a function start: push imm32 (the frame size), then call rel32.
_PUSH_IMM32 = 0x68
_PUSH_SIZE = 5
_CALL_REL32 = 0xE8
_CALL_OPCODE = _PUSH_SIZE  # offset of the call's opcode from the function start
_CALL_FIELD = _CALL_OPCODE + 1  # offset of its rel32 field
_REL32_SIZE = 4
_PROLOGUE_SIZE = _CALL_FIELD + _REL32_SIZE


def unit_name(text: str) -> str:
    """`text` as a unit name: lowercase, every character outside [a-z0-9_] replaced by _."""
    return _NOT_UNIT_CHAR.sub("_", text.lower()) or "u"


# ---- facts about each function ----


def _c_string(flat: bytes | bytearray, va: int) -> str | None:
    """The NUL-terminated printable ASCII string at `va`, else None."""
    raw = bytes(flat[va : va + _MAX_STRING])
    end = raw.find(b"\x00")
    if end < _MIN_STRING or any(byte not in _PRINTABLE for byte in raw[:end]):
        return None
    return raw[:end].decode("ascii")


def _source_stem(text: str) -> str | None:
    match = _SOURCE_FILE.search(text)
    return unit_name(match.group(1)) if match else None


def _only_filler(flat: bytes | bytearray, start: int, end: int) -> bool:
    """True when [start, end) holds only zero bytes and Watcom filler instructions."""
    va = start
    while va < end:
        if flat[va] == 0:
            va += 1
            continue
        insn = x86.decode_one(bytes(flat[va : min(va + _MAX_INSN, end)]), va)
        if insn is None or not x86.is_filler(insn):
            return False
        va += insn.size
    return True


@dataclass(frozen=True)
class _Facts:
    """What the cut rules read about one function (or the leading table run before it)."""

    start: int
    module: int | None  # index of the runtime.csv row holding the function, if any
    module_name: str
    code: bool  # a game or thunk row
    chk: bool
    stem: str | None  # the source file a referenced string names
    strings: tuple[int, ...]  # addresses of the strings it references, sorted
    aligned_gap: bool  # only filler before a 16-aligned start


class _Scanner:
    """The LE facts behind the cut rules."""

    def __init__(self, le: LE, flat: bytes | bytearray, fixups: Iterable[Fixup],
                 runtime: Sequence[MatchRange], chk: Iterable[int]) -> None:  # fmt: skip
        code = code_objects(le)
        self.flat = flat
        self.data = [obj for obj in le.objects if obj not in code]
        self.fixups = sorted((f for f in fixups if f.kind == SRC_OFF32), key=lambda f: f.src_va)
        self.sites = [f.src_va for f in self.fixups]
        self.modules = sorted(runtime, key=lambda m: m.start)
        self.module_starts = [m.start for m in self.modules]
        self.chk = frozenset(chk)

    def module(self, va: int) -> int | None:
        index = bisect.bisect_right(self.module_starts, va) - 1
        if index < 0 or va >= self.modules[index].end:
            return None
        return index

    def strings(self, row: FunctionRow) -> list[tuple[int, str]]:
        """(address, text) of every string the row references through an off32 fixup into a
        data object, in the order of the references."""
        lo = bisect.bisect_left(self.sites, row.start)
        hi = bisect.bisect_left(self.sites, row.end)
        found = []
        for fixup in self.fixups[lo:hi]:
            target = fixup.target_va
            if not any(obj.contains(target) for obj in self.data):
                continue
            text = _c_string(self.flat, target)
            if text is not None:
                found.append((target, text))
        return found

    def facts(self, first: FunctionRow, row: FunctionRow, previous_end: int | None) -> _Facts:
        """Facts of `row`, whose item starts at `first` (a leading table, or `row` itself)."""
        module = self.module(row.start)
        strings = self.strings(row)
        stems = (_source_stem(text) for _, text in strings)
        gap = (previous_end is not None and previous_end < first.start
               and first.start % UNIT_ALIGNMENT == 0
               and _only_filler(self.flat, previous_end, first.start))  # fmt: skip
        return _Facts(
            start=first.start,
            module=module,
            module_name=self.modules[module].module if module is not None else "",
            code=row.kind in _SCAFFOLDED,
            chk=row.start in self.chk,
            stem=next((stem for stem in stems if stem is not None), None),
            strings=tuple(sorted(address for address, _ in strings)),
            aligned_gap=gap,
        )


def _items(rows: Sequence[FunctionRow]) -> list[tuple[FunctionRow, FunctionRow]]:
    """(first row, deciding row) per item: a run of data-in-code rows touching the row after it
    (a leading jump table) is one item with that row; any other row is an item on its own."""
    items = []
    first = None
    for row, after in zip(rows, [*rows[1:], None], strict=True):
        leads = row.kind == KIND_DATA_IN_CODE and after is not None and row.end == after.start
        if first is None:
            first = row
        if not leads:
            items.append((first, row))
            first = None
    return items


# ---- the cut rules ----


@dataclass
class _Open:
    """The unit being drafted."""

    start: int
    name: str
    reason: str
    module: int | None
    stem: str | None
    chk: bool | None  # the __CHK status of its game rows, once it has one
    floor: int | None  # the lowest string address its functions referenced


def _cut(unit: _Open, facts: _Facts) -> str | None:
    """Why a new unit starts at `facts`, else None."""
    if facts.module != unit.module:
        return REASON_RUNTIME
    if facts.module is not None or not facts.code:
        return None
    if facts.stem is not None and facts.stem != unit.stem:
        return REASON_SOURCE
    if unit.chk is not None and facts.chk != unit.chk:
        return REASON_CHK
    if unit.floor is not None and facts.strings and facts.strings[0] < unit.floor:
        return REASON_DATA_ORDER
    if facts.aligned_gap:
        return REASON_GAP
    return None


def _open(facts: _Facts, reason: str) -> _Open:
    """A new unit at `facts`: a runtime module or a source file names it, else its start."""
    if facts.module is not None:
        name, reason = RUNTIME_PREFIX + unit_name(facts.module_name), REASON_RUNTIME
    elif facts.stem is not None:
        name, reason = facts.stem, REASON_SOURCE
    else:
        name = f"{UNIT_PREFIX}{facts.start:08x}"
    unit = _Open(facts.start, name, reason, facts.module, facts.stem, None, None)
    _extend(unit, facts)
    return unit


def _extend(unit: _Open, facts: _Facts) -> None:
    if facts.code and unit.chk is None:
        unit.chk = facts.chk
    if facts.strings:
        lowest = facts.strings[0]
        unit.floor = lowest if unit.floor is None else min(unit.floor, lowest)


def _unique(names: Iterable[str]) -> list[str]:
    """`names` with every repeat suffixed _2, _3, ... (never colliding with another name)."""
    used: set[str] = set()
    result = []
    for name in names:
        candidate, n = name, 1
        while candidate in used:
            n += 1
            candidate = f"{name}_{n}"
        used.add(candidate)
        result.append(candidate)
    return result


def draft_units(
    le: LE,
    functions: Sequence[FunctionRow],
    *,
    runtime: Sequence[MatchRange],
    chk_callers: Iterable[int],
    flat: bytes | bytearray,
    fixups: Iterable[Fixup],
) -> list[UnitRow]:
    """The D-11 draft over `functions` (any order): units tile the code from the first row's
    start to the last row's end, each starting at a cut with its reason. `runtime` are the
    runtime.csv rows, `chk_callers` the starts of the functions with a __CHK prologue, `flat`
    and `fixups` the unrelocated image and the LE fixups."""
    rows = sorted(functions, key=lambda row: row.start)
    if not rows:
        raise UnitsError("no function to group into units")
    scanner = _Scanner(le, flat, fixups, runtime, chk_callers)
    opened: list[_Open] = []
    previous_end = None
    for first, row in _items(rows):
        facts = scanner.facts(first, row, previous_end)
        reason = _cut(opened[-1], facts) if opened else REASON_FIRST
        if reason is None:
            _extend(opened[-1], facts)
        else:
            opened.append(_open(facts, reason))
        previous_end = row.end
    ends = [unit.start for unit in opened[1:]] + [rows[-1].end]
    names = _unique(unit.name for unit in opened)
    return [UnitRow(name, unit.start, end, unit.reason)
            for name, unit, end in zip(names, opened, ends, strict=True)]  # fmt: skip


def chk_callers(
    functions: Iterable[FunctionRow], flat: bytes | bytearray, chk: Sequence[tuple[int, int]]
) -> set[int]:
    """The starts of the game and thunk rows that open with `push imm32; call rel32` into one of
    the `chk` ranges (the runtime.csv rows publishing __CHK)."""
    found = set()
    for row in functions:
        start = row.start
        if row.kind not in _SCAFFOLDED or row.end - start < _PROLOGUE_SIZE:
            continue
        if flat[start] != _PUSH_IMM32 or flat[start + _CALL_OPCODE] != _CALL_REL32:
            continue
        field = bytes(flat[start + _CALL_FIELD : start + _PROLOGUE_SIZE])
        target = start + _PROLOGUE_SIZE + int.from_bytes(field, "little", signed=True)
        if any(lo <= target < hi for lo, hi in chk):
            found.add(start)
    return found


def assign_units(functions: Iterable[FunctionRow], units: Sequence[UnitRow]) -> list[FunctionRow]:
    """`functions` with the unit column set to the unit holding each row's start (empty when
    none does; check_unit_assignment reports such rows)."""
    ordered = sorted(units, key=lambda unit: unit.start)
    starts = [unit.start for unit in ordered]
    result = []
    for row in functions:
        index = bisect.bisect_right(starts, row.start) - 1
        inside = index >= 0 and row.start < ordered[index].end
        result.append(replace(row, unit=ordered[index].unit if inside else ""))
    return result


# ---- the INCLUDE_ASM scaffold (D-12) ----

_SCAFFOLD_HEADER = """\
/*
 * src/{exe_dir}/{unit}.c: translation unit {unit} of {exe}, 0x{start:08X}..0x{end:08X} (D-11).
 *
 * Scaffolded by `uv run reverseapoc units {exe} --write-src {unit}`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

"""


def scaffold_unit(exe: str, unit: UnitRow, functions: Iterable[FunctionRow]) -> str:
    """The source text of a new src/<exe>/<unit>.c: the header comment, `#include "common.h"`
    and one INCLUDE_ASM marker per game and thunk row inside the unit, in address order.
    Runtime and data-in-code rows get none (orchestrator ruling F5)."""
    rows = sorted((row for row in functions
                   if unit.start <= row.start < unit.end and row.kind in _SCAFFOLDED),
                  key=lambda row: row.start)  # fmt: skip
    if not rows:
        raise UnitsError(f"unit {unit.unit} holds no game or thunk function to scaffold")
    header = _SCAFFOLD_HEADER.format(exe_dir=config_dir(exe).name, unit=unit.unit, exe=exe,
                                     start=unit.start, end=unit.end)  # fmt: skip
    return header + "".join(f"INCLUDE_ASM({row.name});\n" for row in rows)


def write_unit_source(path: Path, text: str) -> None:
    """Create `path` holding `text` (ASCII, LF); an existing file is refused, never replaced."""
    path = Path(path)
    data = text.encode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
    except FileExistsError as exc:
        raise UnitsError(
            f"{path} exists; a unit source is never overwritten (matched C lives there)"
        ) from exc
