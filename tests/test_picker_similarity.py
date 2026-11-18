"""Todo similarity-first-picking: `--order similarity` ranks the tier queue's eligible work by
each function's best look-alike ratio (contextpack.lookalikes over mnemonic sequences) against
the matched functions of both EXEs. Made-up mnemonic sequences and addresses only."""

from __future__ import annotations

import difflib
import json
import random
from dataclasses import replace

import pytest

from reverseapoc import contextpack, driver, picker, status
from reverseapoc.score import Candidate
from test_driver_pick import TA, TACP, TB, TC, UFO2P, _member, _rig_world, _signed_rig, _tq

LEAF = ("push", "mov", "mov", "add", "pop", "ret")
TWIN = ("push", "mov", "mov", "add", "pop", "ret")  # TC's twin, matched in the other EXE
NEAR = ("push", "mov", "sub", "add", "pop", "ret")  # 5 of 6 alike: ratio 0.83
FAR = ("cmp", "jne", "xor", "jmp")
TM = 0x00120000  # a matched TACP row (made up)


def _naive(target, matched, *, floor, top):
    """contextpack.lookalikes as it was before the bounds: every ratio computed."""
    ranked = []
    for key, sequence in matched.items():
        ratio = difflib.SequenceMatcher(None, list(target), list(sequence),
                                        autojunk=False).ratio()  # fmt: skip
        if ratio >= floor:
            ranked.append((-ratio, key))
    return [(key, -negative) for negative, key in sorted(ranked)[:top]]


@pytest.mark.parametrize("seed", range(20))
def test_lookalikes_bounds_change_no_result(seed):
    """The quick upper bounds only skip rows that cannot rank: the result is the full ranking's,
    ties by key included."""
    rng = random.Random(seed)
    words = ("mov", "push", "pop", "call", "ret", "add", "jmp")
    target = [rng.choice(words) for _ in range(rng.randrange(1, 30))]
    matched = {0x10000 + i: [rng.choice(words) for _ in range(rng.randrange(1, 30))]
               for i in range(40)}  # fmt: skip
    matched[0x20000] = list(target)  # an exact twin and a tie
    matched[0x0F000] = list(target)
    for floor, top in ((0.6, 3), (0.0, 1), (0.3, 5), (0.9, 0)):
        assert contextpack.lookalikes(target, matched, floor=floor, top=top) == _naive(
            target, matched, floor=floor, top=top)


def test_lookalikes_ranks_keys_of_both_exes():
    """Keys may be (EXE, start): look-alikes across UFO2P and TACP, ties ordered by key."""
    matched = {(TACP, TM): TWIN, (UFO2P, TA): LEAF, (UFO2P, TB): FAR}
    assert contextpack.lookalikes(LEAF, matched) == [((TACP, TM), 1.0), ((UFO2P, TA), 1.0)]


def _sequences(table):
    return lambda key: table.get(key)


def test_similarity_is_the_best_ratio_against_matched_rows_of_both_exes():
    """A key's best look-alike ratio among the matched keys with a sequence (0.0 below the
    pack's floor or with no sequence); a new match raises the computed ratios."""
    table = {(UFO2P, TA): FAR, (UFO2P, TB): NEAR, (UFO2P, TC): LEAF, (TACP, TM): TWIN}
    sim = picker.Similarity(_sequences(table), matched=[(TACP, TM), (UFO2P, 0x999)])
    assert sim.ratio((UFO2P, TC)) == 1.0
    assert sim.ratio((UFO2P, TB)) == pytest.approx(5 / 6)
    assert sim.ratio((UFO2P, TA)) == 0.0
    assert sim.ratio((UFO2P, 0x777)) == 0.0  # no sequence: no game/thunk row
    landed = (UFO2P, 0x555)
    table[landed] = FAR
    sim.matched(landed)
    assert sim.ratio((UFO2P, TA)) == 1.0


def test_tier_queue_orders_eligible_work_by_similarity():
    """Three leaves of one tier, equal rank: by score TA, TB, TC; by similarity TC (a matched
    TACP twin), TB (0.83), then TA (below the floor) by rank. Pass N still runs before N+1,
    and a match raises its look-alikes' ratios at once."""
    rows = [_member(a) for a in (TA, TB, TC)]
    assert [i.pick.start for i in _tq(rows).preview(10)] == [TA, TB, TC]
    table = {(UFO2P, TA): FAR, (UFO2P, TB): NEAR, (UFO2P, TC): LEAF, (TACP, TM): TWIN}
    q = _tq(rows, similarity=picker.Similarity(_sequences(table), matched=[(TACP, TM)]))
    shown = [(i.pick.start, i.similarity) for i in q.preview(10)]
    assert shown == [(TC, 1.0), (TB, pytest.approx(5 / 6)), (TA, 0.0)]
    passes = {(UFO2P, TC): 1}
    q.use_passes(passes)
    assert q.next_item().pick.start == TB  # TC's pass 2 waits behind the others' pass 1
    table[(UFO2P, TB)] = FAR
    q.take((UFO2P, TB))
    q.finish((UFO2P, TB), matched=True)
    assert (q.next_item().pick.start, q.next_item().similarity) == (TA, 1.0)


def test_only_keeps_the_similarity_order():
    rows = [_member(a) for a in (TA, TB, TC)]
    table = {(UFO2P, TA): FAR, (UFO2P, TB): NEAR, (UFO2P, TC): LEAF, (TACP, TM): TWIN}
    q = _tq(rows, similarity=picker.Similarity(_sequences(table), matched=[(TACP, TM)]))
    assert [i.pick.start for i in q.only({(UFO2P, TA), (UFO2P, TC)}).preview(10)] == [TC, TA]


def _similar_rig(tmp_path):
    """A signed rig: leaves TA, TB, TC; TACP's TM is matched and is TC's twin."""
    from test_drive import _git

    rig = _signed_rig(tmp_path, [_member(a) for a in (TA, TB, TC)])
    row = status.StatusRow(TM, f"func_{TM:08X}", "u_tm", status.MATCHED, 100.0, 1, "0" * 64,
                           "2026-11-01")  # fmt: skip
    status.write_status(rig.repo / "config/tacp/status.csv", [row])
    _git(rig.repo, rig.env, "add", "--", "config/tacp/status.csv")
    _git(rig.repo, rig.env, "commit", "-q", "-m", "a matched TACP twin (made up)")
    worlds = _rig_world(rig.packs, (TA, TB, TC), ())
    table = {(UFO2P, TA): FAR, (UFO2P, TB): NEAR, (UFO2P, TC): LEAF, (TACP, TM): TWIN}
    tm = Candidate(TM, f"func_{TM:08X}", 20, 50, ())
    worlds = {exe: replace(world, mnemonics=lambda start, exe=exe: table[(exe, start)],
                           ranks={**world.ranks, **({TM: tm} if exe == TACP else {})})
              for exe, world in worlds.items()}  # fmt: skip
    return rig, worlds


def test_a_dry_run_shows_the_similarity_order(tmp_path, capsys):
    rig, worlds = _similar_rig(tmp_path)
    code, out, _ = rig.drive(capsys, dry_run=True, json=True, order=picker.ORDER_SIMILARITY,
                             seams={"world": lambda: worlds})  # fmt: skip
    assert code == 0, out
    picks = json.loads(out)["picks"]
    assert [(int(p["start"], 16), p["similarity"]) for p in picks] == [
        (TC, 1.0), (TB, 0.8333), (TA, 0.0)]  # fmt: skip
    code, out, _ = rig.drive(capsys, dry_run=True, order=picker.ORDER_SIMILARITY,
                             seams={"world": lambda: worlds})  # fmt: skip
    line = next(line for line in out.splitlines() if line.startswith(UFO2P))
    assert line.endswith("tier 1 level 0 pass 1 similarity 1.00"), line
    code, out, _ = rig.drive(capsys, dry_run=True, json=True, seams={"world": lambda: worlds})
    picks = json.loads(out)["picks"]
    assert [int(p["start"], 16) for p in picks] == [TA, TB, TC]
    assert "similarity" not in picks[0]


def test_the_night_queue_takes_the_similarity_order(tmp_path):
    rig, worlds = _similar_rig(tmp_path)
    options = rig.options(order=picker.ORDER_SIMILARITY)
    deps = driver.real_deps(options, rig.seams(world=lambda: worlds), worlds)
    assert [i.pick.start for i in deps.queue(frozenset()).preview(10)] == [TC, TB, TA]


def test_similarity_needs_a_signed_tier(tmp_path, capsys):
    from test_drive import Rig

    rig = Rig(tmp_path / "rig")
    code, out, _ = rig.drive(capsys, dry_run=True, json=True, order=picker.ORDER_SIMILARITY)
    assert code == 2
    doc = json.loads(out)
    assert (doc["event"], doc["reason"]) == ("REFUSED", "order")


def test_every_lane_shares_one_similarity(tmp_path):
    """The queues one tier source builds (one per lane) share one Similarity: each ratio is
    computed once a night, and a match one lane lands raises the ratios every lane sees."""
    rig, worlds = _similar_rig(tmp_path)
    worlds[UFO2P] = replace(worlds[UFO2P], mnemonics=lambda start: {
        TA: FAR, TB: LEAF, TC: FAR}[start])  # fmt: skip
    source = driver.tier_source(rig.repo / "config", worlds, similar=True)
    one, other = source(None), source(None)
    assert other.next_item().similarity == 1.0  # TB, TACP's TM twin
    one.take((UFO2P, TC))
    one.finish((UFO2P, TC), matched=True)
    # TA (FAR) now has TC's twin; TC itself is left to `other`'s own matched set
    assert [(i.pick.start, i.similarity) for i in other.preview(10)] == [
        (TA, 1.0), (TB, 1.0), (TC, 0.0)]  # fmt: skip
