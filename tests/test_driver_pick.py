"""The driver's picker (AGT-07, D-07, D-09, D-10): status-aware, variety-ruled picks over score's
P16 survivors. Synthetic candidates only: every address, name and unit below is made up."""

from __future__ import annotations

import random
from dataclasses import dataclass

import pytest

from reverseapoc.picker import Pick, PickerError, matched_starts, pilot, queue
from reverseapoc.score import Candidate

UFO2P = "ufo2p"
TACP = "tacp"
REGION = 0x10000
SPREAD_BASE = 0x00010000  # one candidate per 64 KiB region, so the variety rule never binds


def _candidate(start: int, score: int, *, size: int = 20) -> Candidate:
    return Candidate(start, f"func_{start:08X}", size, score, (f"size {size}",))


def _spread_pool(count: int, *, seed: int) -> tuple[list[Candidate], dict[int, str]]:
    """`count` candidates, each in its own unit and region, scores 100.. in a shuffled order."""
    pool = [_candidate(SPREAD_BASE + i * REGION, 100 + i) for i in range(count)]
    random.Random(seed).shuffle(pool)
    return pool, {c.address: f"u_{c.address:08x}" for c in pool}


def _two_pools(count: int = 20):
    ufo, ufo_units = _spread_pool(count, seed=1)
    tac, tac_units = _spread_pool(count, seed=2)
    return {UFO2P: ufo, TACP: tac}, {UFO2P: ufo_units, TACP: tac_units}


# ---- Task 1: interleave, exclusion, tie order ----


def test_pilot_interleaves_five_and_five():
    pools, units = _two_pools()
    picks = pilot(pools, units=units, excluded=frozenset(), difficult=frozenset())
    assert len(picks) == 10
    assert [p.exe for p in picks] == [UFO2P, TACP] * 5
    for exe in (UFO2P, TACP):
        mine = [p for p in picks if p.exe == exe]
        assert [p.score for p in mine] == [100, 101, 102, 103, 104]  # easiest first
        assert all(p.unit == units[exe][p.start] for p in mine)
    first = picks[0]
    assert first == Pick(UFO2P, SPREAD_BASE, f"func_{SPREAD_BASE:08X}", f"u_{SPREAD_BASE:08x}",
                         20, 100)  # fmt: skip


def test_queue_skips_excluded_and_difficult():
    pools, units = _two_pools(6)
    easiest = SPREAD_BASE  # score 100 in both pools
    second = SPREAD_BASE + REGION  # score 101
    excluded = {(UFO2P, easiest), (TACP, second)}
    difficult = {(UFO2P, second)}
    picks = list(queue(pools, units=units, excluded=excluded, difficult=difficult))
    keys = {(p.exe, p.start) for p in picks}
    assert keys.isdisjoint(excluded | difficult)
    assert len(picks) == 12 - 3
    assert [p.start for p in picks if p.exe == UFO2P][0] == SPREAD_BASE + 2 * REGION
    assert [p.start for p in picks if p.exe == TACP][0] == easiest


def test_equal_scores_order_by_start():
    high, low = SPREAD_BASE + 5 * REGION, SPREAD_BASE + REGION
    pools = {UFO2P: [_candidate(high, 50), _candidate(low, 50), _candidate(SPREAD_BASE, 60)]}
    units = {UFO2P: {high: "u_a", low: "u_b", SPREAD_BASE: "u_c"}}
    picks = list(queue(pools, units=units, excluded=(), difficult=()))
    assert [p.start for p in picks] == [low, high, SPREAD_BASE]
    again = list(queue({UFO2P: list(reversed(pools[UFO2P]))}, units=units, excluded=(),
                       difficult=()))  # fmt: skip
    assert again == picks  # stable across runs, whatever order the pool arrives in


def test_queue_continues_with_the_other_exe_when_one_runs_out():
    pools, units = _two_pools(3)
    pools[TACP] = pools[TACP][:1]
    picks = list(queue(pools, units=units, excluded=(), difficult=()))
    assert [p.exe for p in picks] == [UFO2P, TACP, UFO2P, UFO2P]


def test_pilot_caps_each_exe_at_five():
    pools, units = _two_pools()
    pools[TACP] = pools[TACP][:2]
    picks = pilot(pools, units=units, excluded=(), difficult=())
    assert [p.exe for p in picks] == [UFO2P, TACP, UFO2P, TACP, UFO2P, UFO2P, UFO2P]


@dataclass(frozen=True)
class _Row:
    start: int
    status: str


def test_matched_starts_reads_status_through_the_seam():
    tables = {UFO2P: [_Row(0x1000, "matched"), _Row(0x2000, "partial")],
              TACP: [_Row(0x3000, "matched")]}  # fmt: skip
    matched = matched_starts((UFO2P, TACP), read=tables.__getitem__)
    assert matched == {(UFO2P, 0x1000), (TACP, 0x3000)}


def test_missing_status_means_nothing_matched():
    def read(exe: str):
        raise FileNotFoundError(f"config/{exe}/status.csv")

    assert matched_starts((UFO2P, TACP), read=read) == frozenset()


def test_queue_refuses_a_candidate_without_a_unit():
    pools = {UFO2P: [_candidate(SPREAD_BASE, 10)]}
    with pytest.raises(PickerError, match="0x00010000"):
        list(queue(pools, units={UFO2P: {}}, excluded=(), difficult=()))
