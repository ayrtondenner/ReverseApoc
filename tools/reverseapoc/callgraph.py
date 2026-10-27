# SPDX-License-Identifier: GPL-3.0-or-later
"""The typed call graph of one EXE (DEC-01, D-02, research 07-R1 §Q1, R4, R5): the call trees the
mechanics list, the locator, the hub report and the tier picker read.

Edges come from the LE image, its fixups and the functions.csv rows only (no Ghidra), decoded
through `reverseapoc.x86` (the pinned capstone). Every edge runs from one game or thunk row to
another, and has one of these kinds, strongest first (EDGE_KINDS):

- `direct`: a call or jump onto another row's start (a jump there is a tail call), exactly
  contextpack.CallIndex's callees;
- `pointer`: an off32 or ptr16:32 fixup in a game or thunk row whose target is another such row's
  start (`push offset func`: callbacks, comparators, button handlers);
- `table`: data pointer slots (off32 or ptr16:32 fixups in the data object onto any row's start,
  research Q1's count) grouped into runs whose consecutive slots lie at most TABLE_SLOT_GAP bytes
  apart; every code row with a fixup into a run's [first slot, end of the last slot) gets one edge
  per distinct game/thunk slot target (a slot onto a runtime row keeps its run together only);
- `midrow`: an address fixup from code row A into the middle of another row B. It is either a
  missed function start or a table base inside B, so the closure keeps B (conservative) and the
  reference is reported for classification before Tier 1 freezes;
- `hand`: an edge a reader proved for an indirect call, added from config/mechanics.toml.

Runtime rows are leaves: they are never walked and an edge into one is dropped (D-02). Data-in-code
rows get no edges either way: a jump table's slots lie in one and point at its own function's case
labels. A data fixup into the middle of a row is reported only. An indirect call (`call eax`,
`call [ebx+4]`) with no fixup on its operand is counted per row and never guessed into an edge.
Pointer runs that no game/thunk row references and that hold a game/thunk slot target are listed
as orphan roots (by first slot address).

Every mapping and tuple is sorted by address, so two builds of the same inputs are equal.
"""

from __future__ import annotations

import heapq
from bisect import bisect_right
from collections import defaultdict, deque
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING

from . import asm
from .contextpack import CallIndex
from .functions import KIND_GAME, KIND_THUNK, FunctionRow
from .le import SRC_OFF32, SRC_PTR1632, Fixup
from .x86 import Insn

if TYPE_CHECKING:
    from .check import ExeInputs

DIRECT, POINTER, TABLE, MIDROW, HAND = "direct", "pointer", "table", "midrow", "hand"
EDGE_KINDS = (DIRECT, POINTER, TABLE, MIDROW, HAND)  # strongest first, weakest last
WALKED_KINDS = (KIND_GAME, KIND_THUNK)  # the rows that have edges (D-02)
POINTER_FIXUPS = (SRC_OFF32, SRC_PTR1632)  # the fixup kinds that hold a linear address
TABLE_SLOT_GAP = 16  # research Q1: the largest address step between slots of one pointer run
ORIGIN_CODE = "code"  # a mid-row reference from a game/thunk row
ORIGIN_DATA = "data"  # a mid-row reference from the data object

type Range = tuple[int, int]  # [start, end)


@dataclass(frozen=True, slots=True, order=True)
class Edge:
    src: int
    dst: int
    kind: str


@dataclass(frozen=True, slots=True)
class MidRowRef:
    """An address fixup into the middle of a game/thunk row (research R4). `src_row` is the
    referencing row's start (None for a data reference); `boundary` is True when the target is
    an instruction start of `target_row` as asm.walk decodes it."""

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
    """Typed edges of every game/thunk row (`edges[start]`, possibly empty), the mid-row
    references, the unresolvable indirect calls per row and the orphan pointer runs."""

    edges: Mapping[int, tuple[Edge, ...]]
    midrow: tuple[MidRowRef, ...] = ()
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
        image = _Image(rows, flat, fixups, code, data)
        found: defaultdict[int, set[Edge]] = defaultdict(set)
        for edge in image.edges():
            found[edge.src].add(edge)
        edges = {start: tuple(sorted(found.get(start, ()), key=_edge_key))
                 for start in image.walked}  # fmt: skip
        orphans = (run[0].src_va for run in image.table_runs()
                   if image.run_targets(run) and not image.run_referrers(run))  # fmt: skip
        return cls(
            edges=edges,
            midrow=tuple(sorted(image.midrow_refs(), key=lambda ref: ref.src_va)),
            indirect={start: n for start in image.walked if (n := image.scan(start).indirect)},
            orphan_tables=tuple(orphans),
        )

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


@dataclass(frozen=True, slots=True)
class _Scan:
    starts: frozenset[int]  # instruction starts of the row
    indirect: int  # unresolvable indirect calls in the row


def _inside(va: int, span: Range) -> bool:
    return span[0] <= va < span[1]


class _Image:
    """One EXE's rows, bytes and fixups with the lookups the edge rules share."""

    def __init__(
        self,
        rows: Sequence[FunctionRow],
        flat: bytes | bytearray,
        fixups: Sequence[Fixup],
        code: Range,
        data: Range,
    ) -> None:
        self.rows = sorted(rows, key=lambda row: row.start)
        self.starts = [row.start for row in self.rows]
        self.walked = {row.start: row for row in self.rows if row.kind in WALKED_KINDS}
        self.flat, self.fixups, self.code, self.data = flat, fixups, code, data
        self.index = asm.FixupIndex(fixups)
        self._scans: dict[int, _Scan] = {}
        pointers = [fx for fx in self.index.fixups if fx.kind in POINTER_FIXUPS]
        self.from_code = [(row, fx) for fx in pointers if (row := self._code_source(fx))]
        self.from_data = [fx for fx in pointers if _inside(fx.src_va, data)]

    def containing(self, va: int) -> FunctionRow | None:
        """The row containing `va` (rows are sorted and do not overlap)."""
        i = bisect_right(self.starts, va) - 1
        if i < 0:
            return None
        row = self.rows[i]
        return row if va < row.end else None

    def _code_source(self, fx: Fixup) -> FunctionRow | None:
        """The game/thunk row holding the fixup's field, if it is one."""
        if not _inside(fx.src_va, self.code):
            return None
        row = self.containing(fx.src_va)
        return row if row is not None and row.start in self.walked else None

    def _mid_target(self, va: int) -> FunctionRow | None:
        """The game/thunk row `va` lies strictly inside of."""
        row = self.containing(va)
        if row is None or row.start not in self.walked or va == row.start:
            return None
        return row

    def scan(self, start: int) -> _Scan:
        """Instruction starts and unresolvable indirect calls of one game/thunk row."""
        if start not in self._scans:
            self._scans[start] = self._scan_row(self.walked[start])
        return self._scans[start]

    def _scan_row(self, row: FunctionRow) -> _Scan:
        near = self.index.overlapping(row.start, row.end)
        code = bytes(self.flat[row.start : row.end])
        insns = [item for item in asm.walk(code, row.start, asm.row_sites(row, near))
                 if isinstance(item, Insn)]  # fmt: skip
        indirect = sum(1 for insn in insns if _unresolvable_call(insn, near))
        return _Scan(frozenset(insn.va for insn in insns), indirect)

    # ---- edges ----

    def edges(self) -> Iterator[Edge]:
        yield from self._direct_edges()
        yield from self._pointer_edges()
        yield from self._midrow_edges()
        yield from self._table_edges()

    def _direct_edges(self) -> Iterator[Edge]:
        index = CallIndex.build(self.rows, self.flat, self.fixups)
        for src, targets in index.callees.items():
            yield from (Edge(src, dst, DIRECT) for dst in targets if dst in self.walked)

    def _pointer_edges(self) -> Iterator[Edge]:
        for row, fx in self.from_code:
            if fx.target_va in self.walked and fx.target_va != row.start:
                yield Edge(row.start, fx.target_va, POINTER)

    def _code_midrow(self) -> Iterator[tuple[FunctionRow, Fixup, FunctionRow]]:
        """(source row, fixup, target row) of each code fixup into the middle of another row."""
        for row, fx in self.from_code:
            target = self._mid_target(fx.target_va)
            if target is not None and target.start != row.start:
                yield row, fx, target

    def _midrow_edges(self) -> Iterator[Edge]:
        for row, _fx, target in self._code_midrow():
            yield Edge(row.start, target.start, MIDROW)

    def midrow_refs(self) -> Iterator[MidRowRef]:
        for row, fx, target in self._code_midrow():
            yield self._ref(fx, row.start, target, ORIGIN_CODE)
        for fx in self.from_data:
            target = self._mid_target(fx.target_va)
            if target is not None:
                yield self._ref(fx, None, target, ORIGIN_DATA)

    def _ref(self, fx: Fixup, src_row: int | None, target: FunctionRow, origin: str) -> MidRowRef:
        boundary = fx.target_va in self.scan(target.start).starts
        return MidRowRef(fx.src_va, src_row, fx.target_va, target.start, origin, boundary)

    # ---- pointer tables ----

    @cached_property
    def _slots(self) -> list[Fixup]:
        """Data-object off32/ptr16:32 fixups onto any row's start, by slot address. Slots onto
        runtime or data-in-code rows shape the runs (research Q1 counts them) but add no edge."""
        starts = frozenset(self.starts)
        return [fx for fx in self.from_data if fx.target_va in starts]

    def table_runs(self) -> list[tuple[Fixup, ...]]:
        """The slots split into runs where consecutive slots are more than TABLE_SLOT_GAP bytes
        apart."""
        runs: list[list[Fixup]] = []
        for fx in self._slots:
            if runs and fx.src_va - runs[-1][-1].src_va <= TABLE_SLOT_GAP:
                runs[-1].append(fx)
            else:
                runs.append([fx])
        return [tuple(run) for run in runs]

    def run_referrers(self, run: tuple[Fixup, ...]) -> list[int]:
        """The game/thunk rows with a code fixup into [first slot, end of the last slot)."""
        span = (run[0].src_va, run[-1].src_va + run[-1].size)
        return sorted({row.start for row, fx in self.from_code if _inside(fx.target_va, span)})

    def run_targets(self, run: tuple[Fixup, ...]) -> list[int]:
        """The distinct game/thunk rows the run's slots point at."""
        return sorted({fx.target_va for fx in run if fx.target_va in self.walked})

    def _table_edges(self) -> Iterator[Edge]:
        for run in self.table_runs():
            targets = self.run_targets(run)
            for src in self.run_referrers(run):
                yield from (Edge(src, dst, TABLE) for dst in targets if dst != src)


def _unresolvable_call(insn: Insn, near: Sequence[Fixup]) -> bool:
    """A call with a register or memory operand and no fixup on any of its bytes (research R5)."""
    if not insn.is_call or insn.branch_target is not None:
        return False
    end = insn.va + insn.size
    return not any(fx.src_va < end and fx.src_va + fx.size > insn.va for fx in near)


def build_for(exe: ExeInputs) -> CallGraph:
    """The graph of one loaded EXE, the code and data ranges taken from its LE objects."""
    objects = exe.le.objects
    code = next(obj for obj in objects if obj.flags & asm.OBJ_EXECUTABLE)
    data = next(obj for obj in objects if not obj.flags & asm.OBJ_EXECUTABLE)
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


# ---- strongly connected components (iterative Tarjan) ----


class _Tarjan:
    """Tarjan's algorithm with an explicit work stack, so a long chain cannot hit Python's
    recursion limit. `succ` holds each node's successors inside the node set, sorted."""

    def __init__(self, succ: Mapping[int, Sequence[int]]) -> None:
        self.succ = succ
        self.index: dict[int, int] = {}
        self.low: dict[int, int] = {}
        self.stack: list[int] = []
        self.on_stack: set[int] = set()
        self.found: list[frozenset[int]] = []

    def run(self) -> list[frozenset[int]]:
        for node in sorted(self.succ):
            if node not in self.index:
                self._component_walk(node)
        return self.found

    def _enter(self, node: int) -> None:
        self.index[node] = self.low[node] = len(self.index)
        self.stack.append(node)
        self.on_stack.add(node)

    def _component_walk(self, root: int) -> None:
        self._enter(root)
        work = [(root, 0)]
        while work:
            node, i = work[-1]
            if i < len(self.succ[node]):
                work[-1] = (node, i + 1)
                self._step(node, self.succ[node][i], work)
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                self.low[parent] = min(self.low[parent], self.low[node])
            if self.low[node] == self.index[node]:
                self._pop_component(node)

    def _step(self, node: int, nxt: int, work: list[tuple[int, int]]) -> None:
        if nxt not in self.index:
            self._enter(nxt)
            work.append((nxt, 0))
        elif nxt in self.on_stack:
            self.low[node] = min(self.low[node], self.index[nxt])

    def _pop_component(self, head: int) -> None:
        members = set()
        while True:
            node = self.stack.pop()
            self.on_stack.discard(node)
            members.add(node)
            if node == head:
                break
        self.found.append(frozenset(members))


def _leaves_first(
    components: Sequence[frozenset[int]], succ: Mapping[int, Sequence[int]]
) -> tuple[frozenset[int], ...]:
    """The components in a canonical leaves-first order: a component comes out once every
    component it has an edge into is out, and among those ready the smallest address goes first."""
    owner = {node: i for i, comp in enumerate(components) for node in comp}
    outgoing = [{owner[d] for n in comp for d in succ[n]} - {i}
                for i, comp in enumerate(components)]  # fmt: skip
    incoming: defaultdict[int, list[int]] = defaultdict(list)
    for i, targets in enumerate(outgoing):
        for target in targets:
            incoming[target].append(i)
    pending = [len(targets) for targets in outgoing]
    ready = [(min(comp), i) for i, comp in enumerate(components) if not pending[i]]
    heapq.heapify(ready)
    ordered = []
    while ready:
        _, i = heapq.heappop(ready)
        ordered.append(components[i])
        for caller in incoming[i]:
            pending[caller] -= 1
            if not pending[caller]:
                heapq.heappush(ready, (min(components[caller]), caller))
    return tuple(ordered)


def sccs(graph: CallGraph, nodes: Iterable[int]) -> tuple[frozenset[int], ...]:
    """The strongly connected components of the graph restricted to `nodes` (edges leaving the
    set are ignored), leaves first, ties by smallest address. Pure and deterministic."""
    members = frozenset(nodes)
    succ = {node: sorted({e.dst for e in graph.callees(node) if e.dst in members})
            for node in sorted(members)}  # fmt: skip
    return _leaves_first(_Tarjan(succ).run(), succ)


# ---- reach: hops and the weakest edge kind on the chosen shortest path ----

ENTRY = "entry"  # the `via` of a root
_ROOT_RANK = -1  # stronger than every edge kind


def _next_level(
    graph: CallGraph,
    frontier: Iterable[int],
    best: Mapping[int, tuple[int, int]],
    stop: frozenset[int],
) -> dict[int, int]:
    """The nodes one hop past `frontier` not reached yet, each with the strongest weakest-edge
    rank over the edges that reach it."""
    level: dict[int, int] = {}
    for node in frontier:
        if node in stop:
            continue
        weakest = best[node][1]
        for edge in graph.callees(node):
            if edge.dst in best:
                continue
            rank = max(weakest, EDGE_KINDS.index(edge.kind))
            level[edge.dst] = min(rank, level.get(edge.dst, rank))
    return level


def reach(
    graph: CallGraph, roots: Iterable[int], *, stop: frozenset[int] = frozenset()
) -> dict[int, tuple[int, str]]:
    """Every node reachable from `roots`, mapped to (hops, via): `via` is the weakest edge kind on
    a shortest path, choosing among shortest paths the one whose weakest edge is strongest (rank
    = position in EDGE_KINDS). Roots map to (0, "entry"); a node in `stop` is reached but not
    expanded. Sorted by address."""
    best = {root: (0, _ROOT_RANK) for root in roots}
    frontier = sorted(best)
    hops = 0
    while frontier:
        hops += 1
        level = _next_level(graph, frontier, best, stop)
        best.update((node, (hops, rank)) for node, rank in level.items())
        frontier = sorted(level)
    return {node: (h, ENTRY if rank == _ROOT_RANK else EDGE_KINDS[rank])
            for node, (h, rank) in sorted(best.items())}  # fmt: skip


def with_edges(graph: CallGraph, extra: Iterable[Edge]) -> CallGraph:
    """A copy of `graph` with `extra` edges merged in (the `hand` edges of config/mechanics.toml):
    each row's callees stay sorted by (target, kind rank), an edge already present is not added
    twice, and the reports are kept. The input graph is not changed."""
    found: defaultdict[int, set[Edge]] = defaultdict(set)
    for start, edges in graph.edges.items():
        found[start].update(edges)
    for edge in extra:
        found[edge.src].add(edge)
        found.setdefault(edge.dst, set())
    edges = {start: tuple(sorted(found[start], key=_edge_key)) for start in sorted(found)}
    return CallGraph(edges=edges, midrow=graph.midrow, indirect=graph.indirect,
                     orphan_tables=graph.orphan_tables)  # fmt: skip
