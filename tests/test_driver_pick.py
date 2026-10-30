"""The driver's picker (AGT-07, D-07, D-09, D-10): status-aware, variety-ruled picks over score's
P16 survivors; and the tier queue (07-26; DEC-02, D-04, D-08, D-22, D-23): a signed tier's
must-match members callees first, unlimited passes, hubs after members. Synthetic candidates,
call graphs and mechanics data only: every address, name and unit below is made up."""

from __future__ import annotations

import datetime
import random
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from reverseapoc import driver, mechanics, picker
from reverseapoc.callgraph import DIRECT, MIDROW, CallGraph, Edge
from reverseapoc.mechanics import ROLE_ASM, ROLE_CLOSURE, ROLE_HUB, ROLE_MEMBER, MemberRow
from reverseapoc.picker import (
    END_BLOCKED,
    END_EXHAUSTED,
    Pick,
    PickerError,
    matched_starts,
    pilot,
    queue,
    requeue,
)
from reverseapoc.score import Candidate

UFO2P = "ufo2p"
TACP = "tacp"
REGION = 0x10000
SPREAD_BASE = 0x00010000  # one candidate per 64 KiB region, so the variety rule never binds


def _candidate(start: int, score: int, *, size: int = 20, chk: bool = False) -> Candidate:
    return Candidate(start, f"func_{start:08X}", size, score, (f"size {size}",), chk=chk)


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


def test_pilot_refuses_a_short_exe():
    """Fix round 1 (I2): a pool that cannot give 5 picks is an error naming the EXE, its count
    and why its queue ended, never a silently short pilot."""
    pools, units = _two_pools()
    pools[TACP] = pools[TACP][:2]
    with pytest.raises(PickerError, match=rf"{TACP} 2 of 5 \({END_EXHAUSTED}\)") as err:
        pilot(pools, units=units, excluded=(), difficult=())
    assert UFO2P not in str(err.value)


def test_pilot_names_a_variety_shortfall():
    pool = [_candidate(SPREAD_BASE + i * REGION, 10 + i) for i in range(6)]
    pools, units = _two_pools()
    pools[UFO2P] = pool
    units[UFO2P] = dict.fromkeys((c.address for c in pool), "u_one")
    with pytest.raises(PickerError, match=rf"{UFO2P} 2 of 5 \({END_BLOCKED}\)"):
        pilot(pools, units=units, excluded=(), difficult=())


def test_pilot_refuses_per_exe_below_one():
    pools, units = _two_pools()
    with pytest.raises(PickerError, match="per_exe"):
        pilot(pools, units=units, excluded=(), difficult=(), per_exe=0)


def test_queue_says_why_each_exe_ended():
    """I2: `ended` tells an exhausted pool from one the variety rule blocks, which is what
    requeue's pool_empty needs."""
    blocked = [_candidate(SPREAD_BASE + i * REGION, 10 + i) for i in range(3)]
    pools = {UFO2P: blocked, TACP: [_candidate(SPREAD_BASE, 10)]}
    units = {UFO2P: dict.fromkeys((c.address for c in blocked), "u_one"),
             TACP: {SPREAD_BASE: "u_t"}}  # fmt: skip
    q = queue(pools, units=units, excluded=(), difficult=())
    assert q.ended == {}
    assert len(list(q)) == 3
    assert q.ended == {UFO2P: END_BLOCKED, TACP: END_EXHAUSTED}
    assert not q.pool_empty(UFO2P)
    assert q.pool_empty(TACP)


def test_skipped_candidates_do_not_count_as_blocked():
    pool = [_candidate(SPREAD_BASE, 10), _candidate(SPREAD_BASE + REGION, 11)]
    q = queue({UFO2P: pool}, units={UFO2P: _own_units(pool)},
              excluded={(UFO2P, SPREAD_BASE + REGION)}, difficult=())  # fmt: skip
    assert len(list(q)) == 1
    assert q.ended[UFO2P] == END_EXHAUSTED
    assert q.pool_empty(TACP)  # an EXE in `order` with no pool is an exhausted one


def test_queue_refuses_pool_keys_outside_order():
    """M2: a pool keyed by the manifest name instead of the EXE stem is refused, not ignored."""
    pools, units = _two_pools(2)
    pools["UFO2P.EXE"] = pools.pop(UFO2P)
    with pytest.raises(PickerError, match="UFO2P.EXE"):
        queue(pools, units=units, excluded=(), difficult=())


def test_chk_candidates_come_last():
    """Fix round 1 (I1): score's own easiest-first rank, (__CHK, score, start). A __CHK function
    needs owner-only cflags (D-18), so it goes after every candidate without one."""
    chk_low = _candidate(SPREAD_BASE, 10, chk=True)
    plain_high = _candidate(SPREAD_BASE + REGION, 90)
    plain_tie = _candidate(SPREAD_BASE + 2 * REGION, 10)
    pool = [chk_low, plain_high, plain_tie]
    picks = list(queue({UFO2P: pool}, units={UFO2P: _own_units(pool)}, excluded=(),
                       difficult=()))  # fmt: skip
    assert [p.start for p in picks] == [plain_tie.address, plain_high.address, chk_low.address]


@dataclass(frozen=True)
class _Row:
    start: int
    status: str


def _status_path(root):
    return lambda exe: root / exe / "status.csv"


def test_matched_starts_reads_status_through_the_seam(tmp_path):
    tables = {UFO2P: [_Row(0x1000, "matched"), _Row(0x2000, "partial")],
              TACP: [_Row(0x3000, "matched")]}  # fmt: skip
    for exe in tables:
        (tmp_path / exe).mkdir()
        (tmp_path / exe / "status.csv").write_text("", encoding="utf-8")
    matched = matched_starts((UFO2P, TACP), path_of=_status_path(tmp_path),
                             read=lambda path: tables[path.parent.name])  # fmt: skip
    assert matched == {(UFO2P, 0x1000), (TACP, 0x3000)}


def test_missing_status_means_nothing_matched(tmp_path):
    (tmp_path / UFO2P).mkdir()
    (tmp_path / TACP).mkdir()

    def read(path):
        raise AssertionError(f"{path} does not exist and must not be read")

    assert matched_starts((UFO2P, TACP), path_of=_status_path(tmp_path), read=read) == frozenset()


def test_matched_starts_refuses_an_exe_without_a_config_dir(tmp_path):
    """M1: a wrong EXE key (no config/<exe>/) is not "nothing matched"."""
    (tmp_path / UFO2P).mkdir()
    with pytest.raises(PickerError, match="UFO2P.EXE"):
        matched_starts((UFO2P, "UFO2P.EXE"), path_of=_status_path(tmp_path), read=lambda p: [])


@pytest.mark.parametrize("error", [ValueError("line 3: unknown status"),
                                   FileNotFoundError("some/other/file")])  # fmt: skip
def test_matched_starts_lets_reader_errors_through(tmp_path, error):
    """M1: a malformed table, or a missing file other than status.csv itself, propagates."""
    (tmp_path / UFO2P).mkdir()
    (tmp_path / UFO2P / "status.csv").write_text("", encoding="utf-8")

    def read(path):
        raise error

    with pytest.raises(type(error)):
        matched_starts((UFO2P,), path_of=_status_path(tmp_path), read=read)


def test_queue_refuses_a_candidate_without_a_unit():
    """M3: refused when the queue is built, before any pick is handed out."""
    pools = {UFO2P: [_candidate(SPREAD_BASE, 10)], TACP: [_candidate(SPREAD_BASE, 5)]}
    with pytest.raises(PickerError, match="0x00010000"):
        queue(pools, units={UFO2P: {}, TACP: {SPREAD_BASE: "u_t"}}, excluded=(), difficult=())


def test_a_skipped_candidate_needs_no_unit():
    pool = [_candidate(SPREAD_BASE, 10), _candidate(SPREAD_BASE + REGION, 11)]
    units = {UFO2P: {SPREAD_BASE + REGION: "u_b"}}
    picks = list(queue({UFO2P: pool}, units=units, excluded={(UFO2P, SPREAD_BASE)}, difficult=()))
    assert [p.start for p in picks] == [SPREAD_BASE + REGION]


# ---- Task 2: the variety rule (D-10) and the difficult-list re-queue (D-07) ----

LOOKALIKE_FIRST = 0x0008A0E0  # UFO2P's eight look-alike 27-byte functions, 0x0008A0E0..0x0008A1C0
LOOKALIKE_STEP = 0x20


def _own_units(pool: list[Candidate]) -> dict[int, str]:
    return {c.address: f"u_{c.address:08x}" for c in pool}


def test_at_most_two_per_unit():
    same = [_candidate(SPREAD_BASE + i * REGION, 10 + i) for i in range(6)]
    others = [_candidate(SPREAD_BASE + (6 + i) * REGION, 50 + i) for i in range(3)]
    units = {UFO2P: dict.fromkeys((c.address for c in same), "u_same") | _own_units(others)}
    picks = list(queue({UFO2P: same + others}, units=units, excluded=(), difficult=()))
    assert [p.score for p in picks] == [10, 11, 50, 51, 52]
    assert sum(p.unit == "u_same" for p in picks) == 2


def test_at_most_three_per_region():
    lookalikes = [_candidate(LOOKALIKE_FIRST + i * LOOKALIKE_STEP, 27, size=27) for i in range(8)]
    assert lookalikes[-1].address == 0x0008A1C0
    elsewhere = _candidate(0x00120000, 90)
    pool = lookalikes + [elsewhere]
    picks = list(queue({UFO2P: pool}, units={UFO2P: _own_units(pool)}, excluded=(),
                       difficult=()))  # fmt: skip
    assert [p.start for p in picks] == [0x0008A0E0, 0x0008A100, 0x0008A120, 0x00120000]
    in_lookalike_region = [p for p in picks if p.start // REGION == LOOKALIKE_FIRST // REGION]
    assert len(in_lookalike_region) == 3


def test_region_boundary_is_start_floor_64k():
    """M5: 0x0008FFFF is still region 8, 0x00090000 opens region 9."""
    region8 = [_candidate(start, 10) for start in (0x0008FFC0, 0x0008FFD0, 0x0008FFE0, 0x0008FFFF)]
    region9 = _candidate(0x00090000, 11)
    pool = region8 + [region9]
    picks = list(queue({UFO2P: pool}, units={UFO2P: _own_units(pool)}, excluded=(),
                       difficult=()))  # fmt: skip
    assert [p.start for p in picks] == [0x0008FFC0, 0x0008FFD0, 0x0008FFE0, 0x00090000]


def test_variety_counts_per_exe():
    pools = {exe: [_candidate(LOOKALIKE_FIRST + i * LOOKALIKE_STEP, 27) for i in range(4)]
             for exe in (UFO2P, TACP)}  # fmt: skip
    units = {exe: _own_units(pool) for exe, pool in pools.items()}
    picks = list(queue(pools, units=units, excluded=(), difficult=()))
    assert [p.exe for p in picks] == [UFO2P, TACP] * 3  # TACP's region is not UFO2P's


def test_variety_exhaustion_ends_the_queue():
    pool = [_candidate(SPREAD_BASE + i * REGION, 10 + i) for i in range(5)]
    units = {UFO2P: dict.fromkeys((c.address for c in pool), "u_one")}
    picks = list(queue({UFO2P: pool}, units=units, excluded=(), difficult=()))
    assert [p.score for p in picks] == [10, 11]  # the rest is blocked: the queue ends


def test_variety_limits_are_parameters():
    pool = [_candidate(LOOKALIKE_FIRST + i * LOOKALIKE_STEP, 27) for i in range(8)]
    units = {UFO2P: dict.fromkeys((c.address for c in pool), "u_one")}
    picks = list(queue({UFO2P: pool}, units=units, excluded=(), difficult=(), max_per_unit=8,
                       max_per_region=5))  # fmt: skip
    assert len(picks) == 5
    wide = list(queue({UFO2P: pool}, units=units, excluded=(), difficult=(), max_per_unit=8,
                      region_size=LOOKALIKE_STEP))  # fmt: skip
    assert len(wide) == 8  # every look-alike in its own 32-byte region


@pytest.mark.parametrize("limit", ["max_per_unit", "max_per_region", "region_size"])
def test_variety_limits_below_one_are_refused(limit):
    pool = [_candidate(SPREAD_BASE, 10)]
    with pytest.raises(PickerError, match=limit):
        list(queue({UFO2P: pool}, units={UFO2P: _own_units(pool)}, excluded=(), difficult=(),
                   **{limit: 0}))  # fmt: skip


def test_requeue_on_exhausted_pool():
    difficult = {(UFO2P, 0x1000): frozenset(), (TACP, 0x2000): frozenset()}
    everything = requeue(difficult, matched=frozenset(), callees={}, pool_empty=True)
    assert everything == ((UFO2P, 0x1000), (TACP, 0x2000))
    assert requeue(difficult, matched=frozenset(), callees={}, pool_empty=False) == ()


def test_requeue_on_matched_callee():
    newly, known, never = (UFO2P, 0x1000), (UFO2P, 0x2000), (TACP, 0x3000)
    callee_new, callee_old, callee_open = (UFO2P, 0x9000), (UFO2P, 0x9100), (TACP, 0x9200)
    difficult = {
        newly: frozenset(),  # its callee was matched after it was capped
        known: frozenset({callee_old}),  # its only matched callee was matched before the cap
        never: frozenset(),
    }
    callees = {newly: (callee_new,), known: (callee_old,), never: (callee_open,)}
    matched = frozenset({callee_new, callee_old})
    assert requeue(difficult, matched=matched, callees=callees, pool_empty=False) == (newly,)


# ---- 07-26: the tier queue (DEC-02, D-04, D-08, D-22, D-23) ----

T1_ITEM, T2_ITEM = "997", "263-2"  # item ids of tiers 1 and 2
URLS = {T1_ITEM: "https://github.com/OpenApoc/OpenApoc/issues/997",
        T2_ITEM: "https://github.com/OpenApoc/OpenApoc/issues/263"}  # fmt: skip
SIGNED_ON = datetime.date(2026, 11, 2)
TA, TB, TC, TD, TE, TH, TS = (0x00020000 + 0x100 * i for i in range(7))
EXES = (UFO2P, TACP)


def _member(address: int, *, role: str = ROLE_MEMBER, items: tuple[str, ...] = (T1_ITEM,),
            exe: str = UFO2P) -> MemberRow:  # fmt: skip
    """A members-file row reached by `items`; a member row has them as its member items."""
    tiers = tuple(sorted({1 if i == T1_ITEM else 2 for i in items}))
    return MemberRow(exe, address, items, tiers, items if role == ROLE_MEMBER else (), "direct",
                     role)  # fmt: skip


def _mech(rows, *, tiers=(1,), signed=(1,)) -> mechanics.Mechanics:
    """Tiers `tiers` (item 997 is tier 1, item 263-2 tier 2); each tier in `signed` carries a
    sign-off with the digest of `rows`, as the owner's `mechanics digest` gives it."""
    items = tuple(mechanics.Item(i, int(i.split("-")[0]), f"Item {i}", URLS[i], t, "in",
                                 exes=(UFO2P,))
                  for i, t in ((T1_ITEM, 1), (T2_ITEM, 2)) if t in tiers)  # fmt: skip
    base = mechanics.Mechanics(tiers=tuple(mechanics.Tier(t, f"Tier {t}") for t in tiers),
                               items=items)  # fmt: skip
    signed_tiers = tuple(
        replace(t, signed_off_by="owner", signed_off_date=SIGNED_ON,
                members_sha256=mechanics.tier_digest(base, rows, t.id))
        if t.id in signed else t for t in base.tiers)  # fmt: skip
    return replace(base, tiers=signed_tiers)


def _graph(*edges) -> CallGraph:
    """Edges (src, dst) are direct calls; (src, dst, kind) names the kind."""
    found: dict[int, set[Edge]] = {}
    for edge in edges:
        src, dst, kind = (*edge, DIRECT) if len(edge) == 2 else edge
        found.setdefault(src, set()).add(Edge(src, dst, kind))
        found.setdefault(dst, set())
    return CallGraph(edges={start: tuple(sorted(e)) for start, e in sorted(found.items())})


def _ranked(starts, *, scores=None, chk=()) -> dict[int, Candidate]:
    scores = scores or {}
    return {s: Candidate(s, f"func_{s:08X}", 20, scores.get(s, 50), (), chk=s in chk)
            for s in starts}  # fmt: skip


def _tq(rows, edges=(), *, mech=None, matched=(), passes=None, scores=None, units=None,
        chk=()):  # fmt: skip
    """The tier queue of UFO2P `rows` over the graph of `edges`, each row in its own unit."""
    starts = [r.address for r in rows]
    units = units or {s: f"u_{s:08x}" for s in starts}
    return picker.tier_queue(mech or _mech(rows), rows, {UFO2P: _graph(*edges)},
                             {UFO2P: _ranked(starts, scores=scores, chk=chk)}, {UFO2P: units},
                             matched=frozenset((UFO2P, m) for m in matched),
                             passes={} if passes is None else passes)  # fmt: skip


def _serve(q, passes: dict, *, match=(), limit=50) -> list[int]:
    """One worker's night: take the next item, then finish it: matched when its start is in
    `match` (True: every one), else capped (its finished passes + 1, as the night counts
    them). The starts, in the order they were taken."""
    order: list[int] = []
    for _ in range(limit):
        item = q.next_item()
        if item is None:
            break
        key = (item.pick.exe, item.pick.start)
        q.take(key)
        order.append(item.pick.start)
        if match is True or item.pick.start in match:
            q.finish(key, matched=True)
        else:
            passes[key] = passes.get(key, 0) + 1
            q.finish(key, matched=False)
    return order


def test_tier_queue_leaves_first():
    """DEC-02: members A -> B -> C come out C, B, A, each once its callee is done."""
    rows = [_member(a) for a in (TA, TB, TC)]
    q = _tq(rows, [(TA, TB), (TB, TC)])
    assert _serve(q, {}, match=True) == [TC, TB, TA]
    assert q.next_eligible() is None


def test_tier_queue_waits_for_an_in_flight_callee():
    """A caller is not eligible while its callee is in flight and has never been capped."""
    rows = [_member(a) for a in (TA, TB)]
    q = _tq(rows, [(TA, TB)])
    first = q.next_item()
    assert (first.pick.start, first.level, first.tier) == (TB, 0, 1)
    q.take((UFO2P, TB))
    assert q.next_eligible() is None
    q.finish((UFO2P, TB), matched=True)
    second = q.next_item()
    assert (second.pick.start, second.level) == (TA, 1)


def test_scc_members_do_not_block_each_other():
    """A <-> B recursion plus B -> C: C first; the SCC {A, B} waits for C as one node, then A
    and B are both eligible (one in flight does not block the other)."""
    rows = [_member(a) for a in (TA, TB, TC)]
    q = _tq(rows, [(TA, TB), (TB, TA), (TB, TC)])
    assert q.next_eligible().start == TC
    q.take((UFO2P, TC))
    assert q.next_eligible() is None
    q.finish((UFO2P, TC), matched=True)
    a = q.next_item()
    assert (a.pick.start, a.level) == (TA, 1)
    q.take((UFO2P, TA))
    b = q.next_item()
    assert (b.pick.start, b.level) == (TB, 1)


def test_hub_and_asm_never_block():
    """D-22, D-23: member A calls hub H and asm S, both unmatched: A is eligible at once; the asm
    row is never queued, and a closure row neither."""
    rows = [_member(TA), _member(TH, role=ROLE_HUB), _member(TS, role=ROLE_ASM),
            _member(TC, role=ROLE_CLOSURE)]  # fmt: skip
    q = _tq(rows, [(TA, TH), (TA, TS), (TA, TC)])
    assert q.next_eligible().start == TA
    order = _serve(q, {}, match=True)
    assert order == [TA, TH]


def test_midrow_edges_do_not_order_members():
    """Owner ruling Q1 (07-22): a switch-table midrow edge is no call; it neither orders nor
    blocks members."""
    rows = [_member(a) for a in (TA, TB)]
    q = _tq(rows, [(TA, TB, MIDROW)], scores={TA: 10, TB: 90})
    item = q.next_item()
    assert (item.pick.start, item.level) == (TA, 0)


def test_tier_queue_picks_carry_unit_name_size_and_score():
    q = _tq([_member(TA)], scores={TA: 77}, units={TA: "u_made_up"})
    assert q.next_eligible() == Pick(UFO2P, TA, f"func_{TA:08X}", "u_made_up", 20, 77)


def test_tier_queue_refuses_a_member_without_a_unit():
    with pytest.raises(PickerError, match=f"0x{TA:08X}"):
        _tq([_member(TA)], units={TB: "u_other"})


# ---- the driver with a signed tier (07-26 Task 1) ----


def _signed_files(rows, scratch: Path, *, sign: bool = True) -> dict[str, str]:
    """config/mechanics.toml (tier 1, item 997, one entry; signed when `sign`) and the members
    file of `rows`, as text for a commit. `scratch` holds the unsigned draft the digest reads."""
    from test_mechanics import entry, item, tier, toml_text  # 07-10's TOML writer

    tables = {"item": [item()], "entry": [entry(address=rows[0].address)]}
    text = toml_text(None, tier=[tier(1)], **tables)
    if sign:
        draft = scratch / "draft-mechanics.toml"
        draft.write_text(text, encoding="utf-8")
        mech = mechanics.load(draft)
        signed = tier(1, signed_off_by="owner", signed_off_date=SIGNED_ON,
                      members_sha256=mechanics.tier_digest(mech, rows, 1))  # fmt: skip
        text = toml_text(None, tier=[signed], **tables)
    return {"config/mechanics.toml": text,
            "config/mechanics-members.csv": mechanics.format_members_csv(rows)}  # fmt: skip


def _never(*args, **kwargs):
    raise AssertionError("a real_deps effect ran where the night's fake should have")


def _world(starts, edges=(), *, pool=(), unit=None) -> dict[str, driver.ExeWorld]:
    """Both EXEs' worlds for real_deps: `pool` (UFO2P's Phase 6 survivors), and for each UFO2P
    start of `starts` its unit (`unit`, else its own), its rank and the call graph of `edges`."""
    out = {}
    for exe in EXES:
        mine = tuple(starts) if exe == UFO2P else ()
        units = {s: unit or f"u_{s:08x}" for s in (*mine, *(c.address for c in pool))}
        graph = _graph(*edges) if exe == UFO2P else _graph()
        out[exe] = driver.ExeWorld(pool=list(pool) if exe == UFO2P else [], units=units,
                                   callees={}, pack=_never, scaffold=_never,
                                   ranks=_ranked(mine), graph=lambda g=graph: g)  # fmt: skip
    return out


def _seams(night, worlds) -> driver.Seams:
    return driver.Seams(run=_never, git=night._recorded_git, world=lambda: worlds,
                        session=_never, argv=_never)  # fmt: skip


def test_driver_uses_tier_queue_when_signed(tmp_path):
    """DEC-02: with Tier 1 signed in config/mechanics.toml the night's first launch is the
    tier's leaf; without a signed tier the Phase 6 pool is used."""
    from test_driver import RUN, START, UNIT, Night
    from test_driver_records import _commit

    leaf, mid, top = START, START + 0x10, START + 0x20
    rows = [_member(a) for a in (leaf, mid, top)]
    pool = [Candidate(top, f"func_{top:08X}", 20, 10, ())]
    for case, sign, first in (("signed", True, leaf), ("unsigned", False, top)):
        night = Night(tmp_path / case)
        _commit(night, _signed_files(rows, tmp_path, sign=sign))
        worlds = _world((leaf, mid, top), [(top, mid), (mid, leaf)], pool=pool, unit=UNIT)
        options = driver.DriveOptions(repo=night.repo, run_id=RUN)
        deps = driver.real_deps(options, _seams(night, worlds), worlds)
        night.run(config={"max_sessions": 1}, queue=deps.queue, requeue=deps.requeue)
        assert [p.start for p, _, _ in night.packed][:1] == [first], case
