# SPDX-License-Identifier: GPL-3.0-or-later
"""The driver's picker (AGT-07, D-09, D-10): which function an agent attempts next.

The pools are score's P16 survivors (`ScoreReport.candidates`, from `score.assess` as it is,
D-09), one list per EXE, keyed by the EXE stem in `order` ("ufo2p", "tacp"). The picker adds
status awareness on top: a start in `excluded` (matched, capped or partial in this pass) or in
`difficult` is never picked.

Within an EXE the picks go easiest first by score's own rank, (__CHK, score, start): a function
without a __CHK prologue comes first, because the default `-s` applies to it and cflags are
owner-only (D-18), then the lower score, then the lower start. The queue is therefore the same
on every run whatever order a pool arrives in. The EXEs are interleaved in `order`; when one
ends the others go on.

The variety rule (D-10) counts the picks yielded so far, per EXE: at most 2 per unit and at most
3 per 64 KiB region (`start // 0x10000`), so look-alike neighbours such as UFO2P's eight 27-byte
functions at 0x0008A0E0..0x0008A1C0 cannot crowd the pilot. When the rule blocks every remaining
candidate the EXE's stream ends; it never breaks the rule. `PickQueue.ended` says why each EXE
ended (pool exhausted, or the rule blocks the rest), which is what `requeue`'s `pool_empty`
needs (D-07). `pilot` refuses to return fewer picks than asked.

The picking is pure: the caller reads functions.csv and the LE. `matched_starts` is the one seam
to the status table, and takes the path and the reader as arguments so tests can fake them.

The tier queue (07-26; DEC-02, D-04, D-08, D-22, D-23) replaces the pools once a tier of
config/mechanics.toml is signed with a digest that still matches (`mechanics.signed_tiers`).
It queues each signed tier's must-match members (role member with a member item of the tier;
never an asm or closure row), then the tier's hubs, every one whatever score's P16 filter says
of it, ranked by score's own (__CHK, score, start). Within a group the order is callees first:
the group's call graph (every edge kind but midrow, owner ruling Q1, plus the hand edges) is
condensed to SCCs, leaves at level 0. An item is eligible when it is not matched, not in flight,
its unit is not claimed, and every group callee of its SCC outside the SCC is matched or has
finished a pass (capped at least once); hubs, asm and closure rows never block a member. The
next pick is the eligible item with the least (finished passes, tier, member before hub, level,
rank): every eligible function runs pass N before any runs pass N+1 (D-08). No variety rule.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Container, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from .callgraph import HAND, CallGraph, Edge, sccs, with_edges
from .mechanics import HUB_KINDS, ROLE_HUB, ROLE_MEMBER, Mechanics, MemberRow, signed_tiers
from .score import Candidate
from .status import MATCHED

EXE_ORDER = ("ufo2p", "tacp")
PILOT_PER_EXE = 5  # D-10: 5 UFO2P + 5 TACP
MAX_PER_UNIT = 2  # D-10 variety rule
MAX_PER_REGION = 3
REGION_SIZE = 0x10000  # 64 KiB of linear address; D-10 fixes no alignment, so start // 0x10000
STATUS_MATCHED = MATCHED  # status.py's vocabulary (06-14 review M6, closed in 06-25)

END_EXHAUSTED = "pool exhausted"  # no eligible candidate left in the EXE's pool
END_BLOCKED = "variety rule blocks the rest"  # candidates are left, the rule blocks them all

Key = tuple[str, int]  # (EXE, row start): one functions.csv row, as in status.csv


class PickerError(ValueError):
    """The picker was given something it cannot pick from (a candidate with no unit, an
    unknown EXE key, a limit below 1), or a pilot that cannot be filled."""


@dataclass(frozen=True, slots=True)
class Pick:
    exe: str
    start: int
    name: str
    unit: str
    size: int
    score: int


class StatusRow(Protocol):
    start: int
    status: str


def matched_starts(
    exes: Iterable[str],
    *,
    path_of: Callable[[str], Path],
    read: Callable[[Path], Iterable[StatusRow]],
) -> frozenset[Key]:
    """The (EXE, start) of every matched row in each EXE's status table at `path_of(exe)`.

    A table that does not exist yet in an existing config directory means nothing is matched in
    that EXE (D-20). A missing config directory is a wrong EXE key and is refused. Everything
    `read(path)` raises (a malformed table, any other missing file) propagates."""
    out: set[Key] = set()
    for exe in exes:
        path = path_of(exe)
        if not path.parent.is_dir():
            raise PickerError(f"{exe}: no config directory {path.parent} (wrong EXE key?)")
        if not path.exists():
            continue
        out.update((exe, row.start) for row in read(path) if row.status == STATUS_MATCHED)
    return frozenset(out)


@dataclass(frozen=True, slots=True)
class _Rule:
    max_per_unit: int
    max_per_region: int
    region_size: int

    def __post_init__(self) -> None:
        for field in ("max_per_unit", "max_per_region", "region_size"):
            if getattr(self, field) < 1:
                raise PickerError(f"{field} must be at least 1, not {getattr(self, field)}")


class _Variety:
    """D-10's variety rule over one EXE's picks so far: at most `max_per_unit` per unit and
    `max_per_region` per region of `region_size` bytes (`start // region_size` of the linear
    address)."""

    def __init__(self, rule: _Rule) -> None:
        self._rule = rule
        self._units: Counter[str] = Counter()
        self._regions: Counter[int] = Counter()

    def allows(self, pick: Pick) -> bool:
        rule = self._rule
        region = pick.start // rule.region_size
        return self._units[pick.unit] < rule.max_per_unit and (
            self._regions[region] < rule.max_per_region
        )

    def take(self, pick: Pick) -> None:
        self._units[pick.unit] += 1
        self._regions[pick.start // self._rule.region_size] += 1


def _easiest_first(c: Candidate) -> tuple[bool, int, int]:
    """score.candidates' own rank: no __CHK prologue first, then score, then start."""
    return (c.chk, c.score, c.address)


class _ExeStream:
    """One EXE's picks, easiest first, under the variety rule. The counts only grow, so a
    candidate the rule blocks stays blocked: one pass in order is enough. `end` is None until
    the stream is used up, then END_EXHAUSTED or END_BLOCKED."""

    def __init__(self, picks: Sequence[Pick], rule: _Rule) -> None:
        self._picks = iter(picks)
        self._count = _Variety(rule)
        self._blocked = False
        self.end: str | None = None

    def next(self) -> Pick | None:
        for pick in self._picks:
            if not self._count.allows(pick):
                self._blocked = True
                continue
            self._count.take(pick)
            return pick
        self.end = END_BLOCKED if self._blocked else END_EXHAUSTED
        return None


class PickQueue(Iterator[Pick]):
    """The picks, one EXE after another in `order`; an EXE whose stream ends drops out.
    `ended` maps each EXE that has ended to why (END_EXHAUSTED or END_BLOCKED): a queue that
    stopped does not by itself mean the pool is empty."""

    def __init__(self, streams: Mapping[str, _ExeStream]) -> None:
        self._streams = dict(streams)
        self._live = list(self._streams.values())
        self._turn = 0

    def __next__(self) -> Pick:
        while self._live:
            turn = self._turn % len(self._live)
            pick = self._live[turn].next()
            if pick is None:
                del self._live[turn]  # the next stream moves into this turn
                continue
            self._turn = turn + 1
            return pick
        raise StopIteration

    @property
    def ended(self) -> dict[str, str]:
        return {exe: s.end for exe, s in self._streams.items() if s.end is not None}

    def pool_empty(self, exe: str) -> bool:
        """The EXE's stream ended because no eligible candidate is left (requeue's pool_empty)."""
        return self.ended.get(exe) == END_EXHAUSTED


def _exe_picks(
    exe: str, pool: Sequence[Candidate], *, units: Mapping[int, str],
    skip: Callable[[Key], bool],
) -> list[Pick]:  # fmt: skip
    """The EXE's eligible candidates as picks, easiest first. Every one needs a unit; that is
    checked here, before any pick is handed out."""
    picks = []
    for c in sorted(pool, key=_easiest_first):
        if skip((exe, c.address)):
            continue
        unit = units.get(c.address)
        if not unit:
            raise PickerError(f"{exe} candidate 0x{c.address:08X} has no unit")
        picks.append(Pick(exe, c.address, c.name, unit, c.size, c.score))
    return picks


def queue(
    pools: Mapping[str, Sequence[Candidate]],
    *,
    units: Mapping[str, Mapping[int, str]],
    excluded: Container[Key],
    difficult: Container[Key],
    max_per_unit: int = MAX_PER_UNIT,
    max_per_region: int = MAX_PER_REGION,
    region_size: int = REGION_SIZE,
    order: Sequence[str] = EXE_ORDER,
) -> PickQueue:
    """Every pick, the EXEs in `order` interleaved, each easiest first under the variety rule
    (D-10, counted per EXE). `units` maps each EXE's row starts to their unit; `excluded` and
    `difficult` hold (EXE, start) keys. A pool key outside `order` is refused."""
    rule = _Rule(max_per_unit, max_per_region, region_size)
    unknown = sorted(set(pools) - set(order))
    if unknown:
        raise PickerError(f"pool keys {unknown} are not in order {list(order)}")

    def skip(key: Key) -> bool:
        return key in excluded or key in difficult

    picks = {exe: _exe_picks(exe, pools.get(exe, ()), units=units.get(exe, {}), skip=skip)
             for exe in order}  # fmt: skip
    return PickQueue({exe: _ExeStream(p, rule) for exe, p in picks.items()})


def pilot(
    pools: Mapping[str, Sequence[Candidate]],
    *,
    units: Mapping[str, Mapping[int, str]],
    excluded: Container[Key],
    difficult: Container[Key],
    per_exe: int = PILOT_PER_EXE,
    max_per_unit: int = MAX_PER_UNIT,
    max_per_region: int = MAX_PER_REGION,
    region_size: int = REGION_SIZE,
    order: Sequence[str] = EXE_ORDER,
) -> list[Pick]:
    """The pilot's picks (D-10): the first `per_exe` of each EXE, interleaved. An EXE that
    cannot give `per_exe` picks is a PickerError naming it, its count and why it ended."""
    if per_exe < 1:
        raise PickerError(f"per_exe must be at least 1, not {per_exe}")
    taken: dict[str, int] = dict.fromkeys(order, 0)
    picks: list[Pick] = []
    stream = queue(pools, units=units, excluded=excluded, difficult=difficult,
                   max_per_unit=max_per_unit, max_per_region=max_per_region,
                   region_size=region_size, order=order)  # fmt: skip
    for pick in stream:
        if taken[pick.exe] < per_exe:
            taken[pick.exe] += 1
            picks.append(pick)
        if all(n >= per_exe for n in taken.values()):
            return picks
    short = [f"{exe} {taken[exe]} of {per_exe} ({stream.ended[exe]})"
             for exe in order if taken[exe] < per_exe]  # fmt: skip
    raise PickerError("pilot short: " + "; ".join(short))


def requeue(
    difficult: Mapping[Key, Container[Key]],
    *,
    matched: Container[Key],
    callees: Mapping[Key, Iterable[Key]],
    pool_empty: bool,
) -> tuple[Key, ...]:
    """The difficult functions that become eligible again (D-07), in `difficult`'s order.

    `difficult` maps each capped function to its callees that were already matched when it was
    capped; `matched` is every function matched now; `callees` maps a function to the functions
    it calls. When the easy pool is exhausted (`pool_empty`, e.g. `PickQueue.pool_empty`) every
    difficult function comes back; otherwise only those with a callee matched since the cap."""
    if pool_empty:
        return tuple(difficult)

    def newly_matched(key: Key) -> bool:
        before = difficult[key]
        return any(c in matched and c not in before for c in callees.get(key, ()))

    return tuple(key for key in difficult if newly_matched(key))


# ---- the tier queue (07-26) ----

Rank = tuple[bool, int, int]  # score's own: (__CHK prologue, score, start)
Passes = Mapping[Key, int]  # each function's finished passes (driver.pass_index)
Ranks = Mapping[str, Mapping[int, Candidate]]  # EXE -> row start -> the row as score ranks it
Units = Mapping[str, Mapping[int, str]]  # EXE -> row start -> unit


@dataclass(frozen=True, slots=True)
class TierItem:
    """One queued function: its signed tier, its callees-first level in its group (0: a leaf),
    its rank, the pick, whether it is one of the tier's hubs, and (set by `next_item`) the pass
    it would run, one more than its finished passes."""

    tier: int
    level: int
    rank: Rank
    pick: Pick
    hub: bool = False
    pass_n: int = 0

    @property
    def key(self) -> Key:
        return self.pick.exe, self.pick.start


class TierQueue:
    """The signed tiers' items and, for each, the group callees its SCC waits for (`callees`).

    `matched` is every matched key; `passes` maps a key to its finished passes and is read live,
    never written (the night counts the passes, `use_passes` binds the night's own index).
    `take` marks an item in flight, `finish` ends that (`matched` adds it to the matched set)."""

    def __init__(self, items: Iterable[TierItem], callees: Mapping[Key, Iterable[Key]], *,
                 matched: Iterable[Key] = (), passes: Passes | None = None) -> None:  # fmt: skip
        self._items = tuple(items)
        self._callees = {key: tuple(keys) for key, keys in callees.items()}
        self._matched = set(matched)
        self._passes: Passes = {} if passes is None else passes
        self._flight: set[Key] = set()

    @property
    def items(self) -> tuple[TierItem, ...]:
        return self._items

    def use_passes(self, passes: Passes) -> None:
        """Read finished passes from `passes` from now on (the night's pass index)."""
        self._passes = passes

    def _done_once(self, key: Key) -> bool:
        return key in self._matched or self._passes.get(key, 0) > 0

    def _eligible(self, item: TierItem, claimed: Container[tuple[str, str]]) -> bool:
        key = item.key
        if key in self._matched or key in self._flight:
            return False
        if (item.pick.exe, item.pick.unit) in claimed:
            return False
        return all(self._done_once(callee) for callee in self._callees.get(key, ()))

    def _order(self, item: TierItem) -> tuple:
        return (self._passes.get(item.key, 0), item.tier, item.hub, item.level, item.rank,
                EXE_ORDER.index(item.pick.exe))  # fmt: skip

    def next_item(self, claimed_units: Container[tuple[str, str]] = frozenset()) -> TierItem | None:
        """The eligible item with the least (finished passes, tier, member before hub, level,
        rank), its `pass_n` set; None when no item is eligible now. `claimed_units` holds the
        (EXE, unit) pairs other passes hold: their items are skipped, not dropped."""
        eligible = (item for item in self._items if self._eligible(item, claimed_units))
        best = min(eligible, key=self._order, default=None)
        if best is None:
            return None
        return replace(best, pass_n=self._passes.get(best.key, 0) + 1)

    def next_eligible(self, claimed_units: Container[tuple[str, str]] = frozenset()) -> Pick | None:
        item = self.next_item(claimed_units)
        return None if item is None else item.pick

    def preview(self, count: int) -> list[TierItem]:
        """The first `count` distinct picks one worker would take if every pass ended capped,
        each at its next pass (the dry run's and the drafts' list). Nothing is counted or taken
        in this queue."""
        passes = dict(self._passes)
        trial = TierQueue(self._items, self._callees, matched=self._matched, passes=passes)
        trial._flight = set(self._flight)
        out: list[TierItem] = []
        while len(out) < count and (item := trial.next_item()) is not None:
            out.append(item)
            trial.take(item.key)  # once each
            passes[item.key] = passes.get(item.key, 0) + 1  # capped: its callers may follow
        return out

    def take(self, key: Key) -> None:
        self._flight.add(key)

    def finish(self, key: Key, *, matched: bool) -> None:
        self._flight.discard(key)
        if matched:
            self._matched.add(key)


def _call_graph(mech: Mechanics, exe: str, graph: CallGraph) -> CallGraph:
    """The calls the tier order follows: every edge kind but midrow (owner ruling Q1: a switch
    table is no call), plus the hand edges of mechanics.toml."""
    hand = (Edge(e.src, e.dst, HAND) for e in mech.edges if e.exe == exe)
    full = with_edges(graph, hand)
    return CallGraph(edges={start: tuple(e for e in edges if e.kind in HUB_KINDS)
                            for start, edges in full.edges.items()})  # fmt: skip


def _levels(graph: CallGraph, nodes: frozenset[int]) -> tuple[dict[int, int], dict[int, list[int]]]:
    """Each node's level (its SCC's: 0 for a leaf, else one more than its deepest callee SCC)
    and the group callees its SCC waits for (the edges from the SCC to other group SCCs)."""
    components = sccs(graph, nodes)  # leaves first: every callee SCC comes before its callers
    owner = {node: i for i, comp in enumerate(components) for node in comp}
    level: dict[int, int] = {}
    waits: dict[int, list[int]] = {}
    for i, comp in enumerate(components):
        out = sorted({e.dst for n in comp for e in graph.callees(n)
                      if e.dst in nodes and owner[e.dst] != i})  # fmt: skip
        comp_level = 1 + max((level[d] for d in out), default=-1)
        for node in comp:
            level[node], waits[node] = comp_level, out
    return level, waits


def _group_rows(rows: Sequence[MemberRow], ids: frozenset[str], tier_id: int,
                hub: bool) -> list[MemberRow]:  # fmt: skip
    """A tier's members (role member with a member item of the tier) or its hubs (role hub,
    reached by a tier item). asm and closure rows are never in a group."""
    if hub:
        return [row for row in rows if row.role == ROLE_HUB and tier_id in row.tiers]
    return [row for row in rows if row.role == ROLE_MEMBER and ids.intersection(row.member_items)]


def _tier_pick(row: MemberRow, ranks: Ranks, units: Units) -> tuple[Rank, Pick]:
    where = f"{row.exe} member 0x{row.address:08X}"
    ranked = ranks.get(row.exe, {}).get(row.address)
    if ranked is None:
        raise PickerError(f"{where} has no rank")
    unit = units.get(row.exe, {}).get(row.address)
    if not unit:
        raise PickerError(f"{where} has no unit")
    pick = Pick(row.exe, row.address, ranked.name, unit, ranked.size, ranked.score)
    return (ranked.chk, ranked.score, ranked.address), pick


def tier_queue(
    mech: Mechanics,
    members: Sequence[MemberRow],
    graphs: Mapping[str, CallGraph],
    ranks: Ranks,
    units: Units,
    *,
    matched: Iterable[Key] = (),
    passes: Passes | None = None,
) -> TierQueue:
    """The tier queue of every signed tier (`mechanics.signed_tiers`: signed, digest matching),
    in tier order: each tier's members, then its hubs, a row queued once (by its first tier).
    `graphs` are the EXEs' call graphs, `ranks` every row as score ranks it (no P16 filter),
    `units` each row's unit. A queued row without a rank, a unit or a call graph is refused."""
    items: list[TierItem] = []
    callees: dict[Key, tuple[Key, ...]] = {}
    for group in _groups(mech, members):
        if group.exe not in graphs:
            raise PickerError(f"{group.exe}: no call graph for tier {group.tier}")
        for item, waits in _group_items(mech, group, graphs[group.exe], ranks, units):
            items.append(item)
            callees[item.key] = waits
    return TierQueue(items, callees, matched=matched, passes=passes)


@dataclass(frozen=True)
class _Group:
    """One EXE's rows of one tier's members (hub False) or hubs (hub True)."""

    tier: int
    hub: bool
    exe: str
    rows: tuple[MemberRow, ...]


def _groups(mech: Mechanics, members: Sequence[MemberRow]) -> Iterator[_Group]:
    """The groups in queue order: signed tiers ascending, members before hubs, EXEs in order. A
    row is in the first group that has it."""
    queued: set[Key] = set()
    for tier_id in signed_tiers(mech, members):
        ids = frozenset(item.id for item in mech.items if item.tier == tier_id)
        for hub in (False, True):
            group = [row for row in _group_rows(members, ids, tier_id, hub)
                     if (row.exe, row.address) not in queued]  # fmt: skip
            queued.update((row.exe, row.address) for row in group)
            for exe in sorted({row.exe for row in group}, key=EXE_ORDER.index):
                yield _Group(tier_id, hub, exe, tuple(row for row in group if row.exe == exe))


def _group_items(mech: Mechanics, group: _Group, graph: CallGraph, ranks: Ranks,
                 units: Units) -> Iterator[tuple[TierItem, tuple[Key, ...]]]:  # fmt: skip
    """Each row's item and the group keys its SCC waits for."""
    level, waits = _levels(_call_graph(mech, group.exe, graph),
                           frozenset(row.address for row in group.rows))  # fmt: skip
    for row in group.rows:
        rank, pick = _tier_pick(row, ranks, units)
        item = TierItem(group.tier, level[row.address], rank, pick, group.hub)
        yield item, tuple((group.exe, d) for d in waits[row.address])
