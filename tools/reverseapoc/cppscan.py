"""C vs C++ scan (CID-06): does an EXE carry evidence that it was compiled with wpp386?

Signals, strongest first:

1. The static-init (XI) and destructor (YI) tables. Watcom's init walker, module `inirt386` of
   the C runtime, addresses the bounds XIB/XIE and YIB/YIE through segment-relative fixups; the
   LE fixups at the same sites in the EXE give the table addresses. Each entry is 6 bytes:
   routine type (u8), priority (u8), near routine pointer (u32, read relocated). C++ static
   constructors run at priority 64 (program) and module destructors at 40; the C runtime's own
   entries use 1, 2, 10 and 32. An XI entry at 64 or a YI entry at 40 is C++ evidence.

Output (reports and JSON) holds counts, addresses, priorities and module names only, never
bytes or strings from the EXE.
"""

from __future__ import annotations

import struct
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from .le import LE, Fixup
from .libmatch import LIB_DIR, MatchRange, check_versions
from .omf import Module, Segment, read_library


class CppScanError(ValueError):
    """The scan cannot locate or read the init tables, or its inputs are inconsistent."""


# One XI/YI entry (struct rt_init in Watcom's runtime): routine type, priority, routine.
_XI_RTN_TYPE = 0  # u8: 0 near, 1 far
_XI_PRIORITY = 1  # u8
_XI_ROUTINE = 2  # u32: near pointer to the routine
_NEAR_POINTER = 4  # bytes of a 32-bit near pointer
XI_ENTRY_SIZE = _XI_ROUTINE + _NEAR_POINTER

# Init priorities, from Open Watcom's bld/watcom/h/rtprior.h (research assumption A4: unchanged
# since 10.6; the C runtime's entries observed at 32 support it). Other values are reported as
# numbers, never mapped.
PRIO_THREAD = 1
PRIO_FPU = 2
PRIO_RUNTIME = 10
PRIO_LIBRARY = 32
PRIO_DTOR = 40  # YI: module destructors (C++)
PRIO_PROGRAM = 64  # XI: static constructors (C++)
PRIORITY_NAMES = {
    PRIO_THREAD: "thread",
    PRIO_FPU: "fpu",
    PRIO_RUNTIME: "runtime",
    PRIO_LIBRARY: "library",
    PRIO_DTOR: "destructor",
    PRIO_PROGRAM: "program",
}

INIT_MODULE = "inirt386"  # the C runtime module that walks the XI and YI tables
TABLE_BOUNDS = {"XI": ("XIB", "XIE"), "YI": ("YIB", "YIE")}
_OBJ_EXECUTABLE = 0x0004  # LE object flag: executable
_SEGMENT_TARGET = "segment"


@dataclass(frozen=True)
class InitEntry:
    table: str  # "XI" or "YI"
    va: int  # linear address of the entry
    rtn_type: int
    priority: int
    routine_va: int
    in_library: bool  # the routine lies inside a runtime-map range

    def to_json(self) -> dict[str, Any]:
        return {"va": self.va, "rtn_type": self.rtn_type, "priority": self.priority,
                "routine_va": self.routine_va, "in_library": self.in_library}  # fmt: skip


def _priority_text(priority: int) -> str:
    name = PRIORITY_NAMES.get(priority)
    return f"{priority} ({name})" if name else str(priority)


def _profile(entries: Sequence[InitEntry]) -> str:
    """Counts per priority, e.g. "1 (thread) x1, 32 (library) x7"."""
    tally = Counter(e.priority for e in entries)
    return ", ".join(f"{_priority_text(p)} x{n}" for p, n in sorted(tally.items())) or "none"


@dataclass(frozen=True)
class CppScanReport:
    exe: str
    xi: tuple[InitEntry, ...]
    yi: tuple[InitEntry, ...]
    cpp_only_modules: tuple[str, ...] = ()
    wcpp_strings: int = 0
    mangled_strings: int = 0
    vtable_candidates: int = 0
    verdict: str = ""
    bounds: Mapping[str, tuple[int, int]] | None = None  # table -> (start, end)

    def _tables(self) -> dict[str, tuple[InitEntry, ...]]:
        return {"XI": self.xi, "YI": self.yi}

    def _range(self, table: str) -> tuple[int, int] | None:
        return (self.bounds or {}).get(table)

    def format(self) -> str:
        lines = [f"{self.exe}: {self.verdict}"]
        for table, entries in self._tables().items():
            where = self._range(table)
            span = f" 0x{where[0]:08X}..0x{where[1]:08X}" if where else ""
            in_lib = sum(e.in_library for e in entries)
            lines.append(f"{table}{span}: {len(entries)} entries; priority {_profile(entries)}; "
                         f"routine in runtime map {in_lib}")  # fmt: skip
        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        tables = {}
        for table, entries in self._tables().items():
            where = self._range(table)
            tables[table] = {
                "start": where[0] if where else None,
                "end": where[1] if where else None,
                "entries": [e.to_json() for e in entries],
            }
        return {
            "exe": self.exe,
            "verdict": self.verdict,
            "tables": tables,
            "cpp_only_modules": list(self.cpp_only_modules),
            "wcpp_strings": self.wcpp_strings,
            "mangled_strings": self.mangled_strings,
            "vtable_candidates": self.vtable_candidates,
        }


# ---- locating the tables through inirt386 ----


def _init_row(rows: Sequence[MatchRange]) -> MatchRange:
    for row in rows:
        if row.module.casefold() == INIT_MODULE:
            return row
    raise CppScanError(f"the runtime map has no {INIT_MODULE} row: the init tables cannot be found")


def _library_path(watcom_dir: Path, version: str, library: str) -> Path:
    """watcom_dir/<version>/LIB386/<library>, refused when it would leave that tree."""
    try:
        check_versions([version])
    except ValueError as exc:
        raise CppScanError(str(exc)) from exc
    root = (Path(watcom_dir) / version / LIB_DIR).resolve()
    path = (root / PurePosixPath(library)).resolve()
    if not path.is_relative_to(root):
        raise CppScanError(f"library {library!r} lies outside {root}")
    return path


def _init_segment(row: MatchRange, watcom_dir: Path) -> Segment:
    """The CODE segment of the library module the inirt386 row was matched from."""
    if not row.libraries or not row.versions:
        raise CppScanError(f"{row.describe()}: the row names no library or version")
    path = _library_path(watcom_dir, row.versions[0], row.libraries[0])
    if not path.is_file():
        raise CppScanError(f"{path} not found (install Watcom {row.versions[0]})")
    library = read_library(path.read_bytes(), path=row.libraries[0])
    modules = [m for m in library.modules if _stem(m) == row.module]
    for seg in (s for m in modules for s in m.segments):
        if seg.is_code and seg.name == row.segment and seg.length == row.end - row.start:
            return seg
    raise CppScanError(
        f"{row.libraries[0]} ({row.versions[0]}) has no {row.module} CODE segment "
        f"{row.segment} of {row.end - row.start} bytes"
    )


def _stem(module: Module) -> str:
    return PureWindowsPath(module.name).stem


def _bound_addresses(row: MatchRange, seg: Segment, fixups: Mapping[int, Fixup]) -> dict[str, int]:
    """Bound segment name -> the linear address the LE fixup at each of its sites points to."""
    wanted = {name for pair in TABLE_BOUNDS.values() for name in pair}
    found: dict[str, set[int]] = {}
    for f in seg.fixups:
        to_bound = f.segment_relative and f.target_kind == _SEGMENT_TARGET
        if not to_bound or f.target_name not in wanted:
            continue
        le_fixup = fixups.get(row.start + f.offset)
        if le_fixup is None:
            raise CppScanError(f"no LE fixup at {row.start + f.offset:#010x} ({f.target_name} "
                               f"site of {row.describe()})")  # fmt: skip
        found.setdefault(f.target_name, set()).add(le_fixup.target_va)
    missing = sorted(wanted - found.keys())
    if missing:
        raise CppScanError(f"{row.describe()} has no fixup to {', '.join(missing)}")
    split = {name: sorted(vas) for name, vas in found.items() if len(vas) > 1}
    if split:
        raise CppScanError(f"{row.describe()}: bound sites disagree: {split}")
    return {name: next(iter(vas)) for name, vas in found.items()}


def _check_table(le: LE, table: str, start: int, end: int) -> None:
    """[start, end) is a whole number of entries inside one non-executable object."""
    if end < start or (end - start) % XI_ENTRY_SIZE:
        raise CppScanError(f"{table} table 0x{start:08X}..0x{end:08X} is not a multiple of "
                           f"{XI_ENTRY_SIZE} bytes")  # fmt: skip
    obj = le.obj_of_va(start)
    if obj is None or obj.flags & _OBJ_EXECUTABLE or end > obj.end:
        raise CppScanError(f"{table} table 0x{start:08X}..0x{end:08X} is not inside the data "
                           "object")  # fmt: skip


def table_bounds(
    le: LE, rows: Sequence[MatchRange], watcom_dir: Path
) -> dict[str, tuple[int, int]]:
    """Table name ("XI", "YI") -> (start, end), located through the inirt386 row's fixups."""
    row = _init_row(rows)
    seg = _init_segment(row, Path(watcom_dir))
    addresses = _bound_addresses(row, seg, {fx.src_va: fx for fx in le.fixups()})
    bounds = {table: (addresses[b], addresses[e]) for table, (b, e) in TABLE_BOUNDS.items()}
    for table, (start, end) in bounds.items():
        _check_table(le, table, start, end)
    return bounds


def _in_rows(va: int, rows: Sequence[MatchRange]) -> bool:
    return any(r.start <= va < r.end for r in rows)


def _read_entries(
    image: bytes, table: str, start: int, end: int, rows: Sequence[MatchRange]
) -> tuple[InitEntry, ...]:
    entries = []
    for va in range(start, end, XI_ENTRY_SIZE):
        (routine,) = struct.unpack_from("<I", image, va + _XI_ROUTINE)
        entries.append(InitEntry(table, va, image[va + _XI_RTN_TYPE], image[va + _XI_PRIORITY],
                                 routine, _in_rows(routine, rows)))  # fmt: skip
    return tuple(entries)


def _tables_from(
    le: LE, rows: Sequence[MatchRange], bounds: Mapping[str, tuple[int, int]]
) -> dict[str, tuple[InitEntry, ...]]:
    image = bytes(le.load_flat(relocate=True))  # routine pointers hold their target only here
    return {table: _read_entries(image, table, *bounds[table], rows) for table in TABLE_BOUNDS}


def init_tables(
    le: LE, rows: Sequence[MatchRange], watcom_dir: Path
) -> tuple[tuple[InitEntry, ...], tuple[InitEntry, ...]]:
    """The XI and YI entries of `le`, located through the inirt386 row of its runtime map."""
    tables = _tables_from(le, rows, table_bounds(le, rows, watcom_dir))
    return tables["XI"], tables["YI"]


# ---- the verdict ----


def _with_priority(entries: Sequence[InitEntry], priority: int) -> int:
    return sum(e.priority == priority for e in entries)


def verdict(xi: Sequence[InitEntry], yi: Sequence[InitEntry]) -> str:
    """"C (wcc386): ..." when no C++ signal fired, else "C++ evidence: ..." naming them."""
    signals = []
    if n := _with_priority(xi, PRIO_PROGRAM):
        signals.append(f"XI priority {PRIO_PROGRAM} x{n}")
    if n := _with_priority(yi, PRIO_DTOR):
        signals.append(f"YI priority {PRIO_DTOR} x{n}")
    if not signals:
        return f"C (wcc386): no XI priority {PRIO_PROGRAM}, no YI priority {PRIO_DTOR}"
    return f"C++ evidence: {', '.join(signals)}"


def scan(le: LE, rows: Sequence[MatchRange], watcom_dir: Path, *, exe: str) -> CppScanReport:
    """Every C++ signal of `le`, given its runtime map `rows`, and the verdict."""
    bounds = table_bounds(le, rows, watcom_dir)
    tables = _tables_from(le, rows, bounds)
    xi, yi = tables["XI"], tables["YI"]
    return CppScanReport(exe, xi, yi, verdict=verdict(xi, yi), bounds=bounds)
