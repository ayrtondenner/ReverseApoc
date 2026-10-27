# SPDX-License-Identifier: GPL-3.0-or-later
"""The typed call graph of one EXE (DEC-01, D-02, research 07-R1 §Q1): the call trees the mechanics
list, the locator, the hub report and the tier picker read.

Edges come from the LE image, its fixups and the functions.csv rows only (no Ghidra), decoded
through `reverseapoc.x86` (the pinned capstone). Every edge runs from one game or thunk row to the
start of another, and has one of these kinds, strongest first:

- `direct`: a call or jump onto another row's start (a jump there is a tail call), exactly
  contextpack.CallIndex's callees;
- `pointer`: an off32 or ptr16:32 fixup in a game or thunk row whose target is another such row's
  start (`push offset func`: callbacks, comparators, button handlers);
- `table`, `midrow`: data pointer tables and references into the middle of a row (added beside
  these, see below);
- `hand`: an edge a reader proved for an indirect call, added from config/mechanics.toml.

Runtime rows are leaves: they are never walked and an edge into one is dropped (D-02). Data-in-code
rows get no edges either way. An indirect call is never guessed into an edge.

Every mapping and tuple is sorted by address, so two builds of the same inputs are equal.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING

from .asm import OBJ_EXECUTABLE
from .contextpack import CallIndex
from .functions import KIND_GAME, KIND_THUNK, FunctionRow
from .le import SRC_OFF32, SRC_PTR1632, Fixup

if TYPE_CHECKING:
    from .check import ExeInputs

DIRECT, POINTER, TABLE, MIDROW, HAND = "direct", "pointer", "table", "midrow", "hand"
EDGE_KINDS = (DIRECT, POINTER, TABLE, MIDROW, HAND)  # strongest first, weakest last
WALKED_KINDS = (KIND_GAME, KIND_THUNK)  # the rows that have edges (D-02)
POINTER_FIXUPS = (SRC_OFF32, SRC_PTR1632)  # the fixup kinds that hold a linear address

type Range = tuple[int, int]  # [start, end)


@dataclass(frozen=True, slots=True, order=True)
class Edge:
    src: int
    dst: int
    kind: str


@dataclass(frozen=True, slots=True)
class MidRowRef:
    """An address fixup into the middle of a game/thunk row (research R4)."""

    src_va: int
    src_row: int | None
    target_va: int
    target_row: int
    origin: str
    boundary: bool


def _edge_key(edge: Edge) -> tuple[int, int]:
    return edge.dst, EDGE_KINDS.index(edge.kind)


@dataclass(frozen=True)
class CallGraph:
    """Typed edges of every game/thunk row (`edges[start]`, possibly empty), plus the reports the
    closure needs before Tier 1 freezes."""

    edges: Mapping[int, tuple[Edge, ...]]
    midrow: tuple[object, ...] = ()
    indirect: Mapping[int, int] = field(default_factory=dict)
    orphan_tables: tuple[int, ...] = ()

    @classmethod
    def build(
        cls,
        rows: Sequence[FunctionRow],
        flat: bytes | bytearray,
        fixups: Sequence[Fixup],
        *,
        code: Range,
        data: Range,
    ) -> CallGraph:
        """The graph of one EXE. `flat` is load_flat(relocate=False); `code` and `data` are the
        [start, end) of the code and data objects."""
        rows = sorted(rows, key=lambda row: row.start)
        walked = {row.start: row for row in rows if row.kind in WALKED_KINDS}
        found: defaultdict[int, set[Edge]] = defaultdict(set)
        index = CallIndex.build(rows, flat, fixups)
        for src, targets in index.callees.items():
            found[src].update(Edge(src, dst, DIRECT) for dst in targets if dst in walked)
        locate = _RowLocator(rows)
        for edge in _pointer_edges(fixups, locate, walked, code):
            found[edge.src].add(edge)
        edges = {start: tuple(sorted(found.get(start, ()), key=_edge_key)) for start in walked}
        return cls(edges)

    def callees(self, start: int) -> tuple[Edge, ...]:
        """The edges out of `start`, by target address then kind (strongest first)."""
        return self.edges.get(start, ())

    def callers(self, start: int) -> tuple[int, ...]:
        """The rows with at least one edge into `start`, by address."""
        return self._callers.get(start, ())

    @cached_property
    def _callers(self) -> dict[int, tuple[int, ...]]:
        found: defaultdict[int, set[int]] = defaultdict(set)
        for edge in (e for edges in self.edges.values() for e in edges):
            found[edge.dst].add(edge.src)
        return {dst: tuple(sorted(srcs)) for dst, srcs in sorted(found.items())}


class _RowLocator:
    """The row containing an address, by bisection over the sorted, non-overlapping rows."""

    def __init__(self, rows: Sequence[FunctionRow]) -> None:
        self.rows = rows
        self.starts = [row.start for row in rows]

    def containing(self, va: int) -> FunctionRow | None:
        i = bisect_right(self.starts, va) - 1
        if i < 0:
            return None
        row = self.rows[i]
        return row if va < row.end else None


def _inside(va: int, span: Range) -> bool:
    return span[0] <= va < span[1]


def _pointer_edges(
    fixups: Iterable[Fixup], locate: _RowLocator, walked: Mapping[int, FunctionRow], code: Range
) -> Iterable[Edge]:
    """`pointer` edges: an address fixup in a game/thunk row onto another such row's start."""
    for fx in fixups:
        if fx.kind not in POINTER_FIXUPS or not _inside(fx.src_va, code):
            continue
        src = locate.containing(fx.src_va)
        if src is None or src.start not in walked:
            continue
        if fx.target_va in walked and fx.target_va != src.start:
            yield Edge(src.start, fx.target_va, POINTER)


def build_for(exe: ExeInputs) -> CallGraph:
    """The graph of one loaded EXE, the code and data ranges taken from its LE objects."""
    objects = exe.le.objects
    code = next(obj for obj in objects if obj.flags & OBJ_EXECUTABLE)
    data = next(obj for obj in objects if not obj.flags & OBJ_EXECUTABLE)
    return CallGraph.build(exe.rows, exe.flat, exe.fixups, code=(code.base, code.end),
                           data=(data.base, data.end))  # fmt: skip


def closure(
    graph: CallGraph, roots: Iterable[int], *, stop: frozenset[int] = frozenset()
) -> frozenset[int]:
    """Every node reachable from `roots` (roots included). A node in `stop` is reached but not
    expanded, so its callees come in only through another path."""
    seen = set(roots)
    queue = deque(sorted(seen))
    while queue:
        node = queue.popleft()
        if node in stop:
            continue
        for edge in graph.callees(node):
            if edge.dst not in seen:
                seen.add(edge.dst)
                queue.append(edge.dst)
    return frozenset(seen)
