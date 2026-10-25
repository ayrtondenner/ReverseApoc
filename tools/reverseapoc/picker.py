# SPDX-License-Identifier: GPL-3.0-or-later
"""The driver's picker (AGT-07, D-09, D-10): which function an agent attempts next.

The pools are score's P16 survivors (`ScoreReport.candidates`, from `score.assess` as it is,
D-09), one list per EXE. The picker adds status awareness on top: a start in `excluded`
(matched, capped or partial in this pass) or in `difficult` is never picked.

Within an EXE the picks go easiest first, by (score, start), so equal scores come out by
ascending start and the queue is the same on every run whatever order a pool arrives in. The
EXEs are interleaved in `order`; when one runs out the others go on.

Everything here is pure: the caller reads status.csv, functions.csv and the LE. `matched_starts`
is the one seam to the status table, and takes the reader as an argument so tests can fake it.
"""

from __future__ import annotations

from collections.abc import Callable, Container, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from .score import Candidate

EXE_ORDER = ("ufo2p", "tacp")
PILOT_PER_EXE = 5  # D-10: 5 UFO2P + 5 TACP
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


def _exe_picks(
    exe: str, pool: Sequence[Candidate], *, units: Mapping[str, Mapping[int, str]],
    skip: Callable[[Key], bool],
) -> Iterator[Pick]:  # fmt: skip
    """One EXE's picks, easiest first by (score, start)."""
    for c in sorted(pool, key=lambda c: (c.score, c.address)):
        if skip((exe, c.address)):
            continue
        yield Pick(exe, c.address, c.name, _unit(exe, c.address, units), c.size, c.score)


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
    order: Sequence[str] = EXE_ORDER,
) -> Iterator[Pick]:
    """Every pick, the EXEs in `order` interleaved, each easiest first. `units` maps each EXE's
    row starts to their unit; `excluded` and `difficult` hold (EXE, start) keys."""

    def skip(key: Key) -> bool:
        return key in excluded or key in difficult

    streams = [_exe_picks(exe, pools.get(exe, ()), units=units, skip=skip) for exe in order]
    return _interleave(streams)


def pilot(
    pools: Mapping[str, Sequence[Candidate]],
    *,
    units: Mapping[str, Mapping[int, str]],
    excluded: Container[Key],
    difficult: Container[Key],
    per_exe: int = PILOT_PER_EXE,
    order: Sequence[str] = EXE_ORDER,
) -> list[Pick]:
    """The pilot's picks (D-10): the first `per_exe` of each EXE, interleaved."""
    taken: dict[str, int] = dict.fromkeys(order, 0)
    picks: list[Pick] = []
    for pick in queue(pools, units=units, excluded=excluded, difficult=difficult, order=order):
        if taken[pick.exe] < per_exe:
            taken[pick.exe] += 1
            picks.append(pick)
        if all(n >= per_exe for n in taken.values()):
            break
    return picks
