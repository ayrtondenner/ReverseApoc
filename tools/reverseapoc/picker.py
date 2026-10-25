# SPDX-License-Identifier: GPL-3.0-or-later
"""The driver's picker (AGT-07, D-09, D-10): which function an agent attempts next.

The pools are score's P16 survivors (`ScoreReport.candidates`, from `score.assess` as it is,
D-09), one list per EXE. The picker adds status awareness on top: a start in `excluded`
(matched, capped or partial in this pass) or in `difficult` is never picked.

Within an EXE the picks go easiest first, by (score, start), so equal scores come out by
ascending start and the queue is the same on every run whatever order a pool arrives in. The
EXEs are interleaved in `order`; when one runs out the others go on.

The variety rule (D-10) counts the picks yielded so far, per EXE: at most 2 per unit and at most
3 per 64 KiB region (`start // 0x10000`), so look-alike neighbours such as UFO2P's eight 27-byte
functions at 0x0008A0E0..0x0008A1C0 cannot crowd the pilot. When the rule blocks every remaining
candidate the queue ends; it never breaks the rule. `requeue` says when capped functions (the
difficult list) come back (D-07).

Everything here is pure: the caller reads status.csv, functions.csv and the LE. `matched_starts`
is the one seam to the status table, and takes the reader as an argument so tests can fake it.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Container, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from .score import Candidate

EXE_ORDER = ("ufo2p", "tacp")
PILOT_PER_EXE = 5  # D-10: 5 UFO2P + 5 TACP
MAX_PER_UNIT = 2  # D-10 variety rule
MAX_PER_REGION = 3
REGION_SIZE = 0x10000  # 64 KiB of linear address; D-10 fixes no alignment, so start // 0x10000
STATUS_MATCHED = "matched"

Key = tuple[str, int]  # (EXE, row start): one functions.csv row, as in status.csv


class PickerError(ValueError):
    """The picker was given a pool it cannot pick from (e.g. a candidate with no unit)."""


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
    exes: Iterable[str], *, read: Callable[[str], Iterable[StatusRow]]
) -> frozenset[Key]:
    """The (EXE, start) of every matched row in each EXE's status table. `read(exe)` returns
    the table's rows; a table that does not exist yet (FileNotFoundError) means nothing is
    matched in that EXE."""
    out: set[Key] = set()
    for exe in exes:
        try:
            rows = list(read(exe))
        except FileNotFoundError:
            continue
        out.update((exe, row.start) for row in rows if row.status == STATUS_MATCHED)
    return frozenset(out)


def _unit(exe: str, start: int, units: Mapping[str, Mapping[int, str]]) -> str:
    unit = units.get(exe, {}).get(start)
    if not unit:
        raise PickerError(f"{exe} candidate 0x{start:08X} has no unit")
    return unit


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


def _exe_picks(
    exe: str, pool: Sequence[Candidate], *, units: Mapping[str, Mapping[int, str]],
    skip: Callable[[Key], bool], rule: _Rule,
) -> Iterator[Pick]:  # fmt: skip
    """One EXE's picks, easiest first by (score, start), under the variety rule. The counts only
    grow, so a candidate the rule blocks stays blocked: one pass in order is enough, and the
    stream ends when the rule blocks every candidate left."""
    count = _Variety(rule)
    for c in sorted(pool, key=lambda c: (c.score, c.address)):
        if skip((exe, c.address)):
            continue
        pick = Pick(exe, c.address, c.name, _unit(exe, c.address, units), c.size, c.score)
        if not count.allows(pick):
            continue
        count.take(pick)
        yield pick


def _interleave(streams: Sequence[Iterator[Pick]]) -> Iterator[Pick]:
    """One pick from each stream in turn; an exhausted stream drops out."""
    live = list(streams)
    while live:
        for stream in list(live):
            pick = next(stream, None)
            if pick is None:
                live.remove(stream)
                continue
            yield pick


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
) -> Iterator[Pick]:
    """Every pick, the EXEs in `order` interleaved, each easiest first under the variety rule
    (D-10, counted per EXE). `units` maps each EXE's row starts to their unit; `excluded` and
    `difficult` hold (EXE, start) keys."""
    rule = _Rule(max_per_unit, max_per_region, region_size)

    def skip(key: Key) -> bool:
        return key in excluded or key in difficult

    streams = [_exe_picks(exe, pools.get(exe, ()), units=units, skip=skip, rule=rule)
               for exe in order]  # fmt: skip
    return _interleave(streams)


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
    """The pilot's picks (D-10): the first `per_exe` of each EXE, interleaved."""
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
            break
    return picks


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
    it calls. When the easy pool is exhausted (`pool_empty`) every difficult function comes
    back; otherwise only those with a callee matched since the cap."""
    if pool_empty:
        return tuple(difficult)

    def newly_matched(key: Key) -> bool:
        before = difficult[key]
        return any(c in matched and c not in before for c in callees.get(key, ()))

    return tuple(key for key in difficult if newly_matched(key))
