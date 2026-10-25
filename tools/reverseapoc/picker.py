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
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Container, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .score import Candidate

EXE_ORDER = ("ufo2p", "tacp")
PILOT_PER_EXE = 5  # D-10: 5 UFO2P + 5 TACP
MAX_PER_UNIT = 2  # D-10 variety rule
MAX_PER_REGION = 3
REGION_SIZE = 0x10000  # 64 KiB of linear address; D-10 fixes no alignment, so start // 0x10000
# TODO(06-25): use 06-11's status.py vocabulary once both are merged (06-14 review M6).
STATUS_MATCHED = "matched"

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
