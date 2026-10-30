"""The drive verb's real world (plan 06-25): both EXEs loaded through check's loader, score's
P16 survivors as the pools, and the pilot's 10 picks over the committed config/ (D-09, D-10).

Reads orig/ only (REVERSEAPOC_ORIG points a git worktree at the main checkout's orig/). No pack
is built, no docker, no claude: this is the part of `drive --dry-run` that needs the real files.
Prints only addresses and names, never game bytes.
"""

from __future__ import annotations

import pytest

from conftest import ORIG_DIR, REPO_ROOT
from reverseapoc import attempt, driver, mechanics
from reverseapoc.picker import EXE_ORDER, PILOT_PER_EXE

NAMES = {"ufo2p": "UFO2P.EXE", "tacp": "TACP.EXE"}


@pytest.fixture(scope="module")
def worlds():
    for name in NAMES.values():
        if not (ORIG_DIR / name).is_file():
            pytest.skip(f"orig/{name} not present (run uv run reverseapoc ingest)")
    roots = attempt.Roots(orig=ORIG_DIR)
    return {exe: driver.load_world(exe, roots=roots) for exe in EXE_ORDER}


def test_real_pools_have_units_and_callees(worlds):
    for exe in EXE_ORDER:
        world = worlds[exe]
        assert len(world.pool) > PILOT_PER_EXE, exe
        assert all(world.units.get(c.address) for c in world.pool), exe
        assert any(world.callees.values()), exe


def test_real_pilot_is_5_plus_5_and_skips_the_matched_rows(worlds, monkeypatch):
    """The Phase 6 pilot over the real pools (a signed tier would replace it: switched off)."""
    monkeypatch.setattr(driver, "tier_source", lambda *args, **kwargs: None)
    options = driver.DriveOptions(repo=REPO_ROOT, run_id="real-test", dry_run=True)
    picks = driver.pilot_picks(options, worlds, today="2026-10-25")
    assert [p.exe for p in picks] == list(EXE_ORDER) * PILOT_PER_EXE
    matched = driver.matched_keys(options.config_root)
    assert matched  # both Phase 5 matches are in the committed status tables
    assert not {(p.exe, p.start) for p in picks} & matched
    for exe in EXE_ORDER:
        units = [p.unit for p in picks if p.exe == exe]
        assert max(units.count(u) for u in units) <= 2  # D-10 variety rule


def _member_keys(mech, rows, tier_id: int) -> set[tuple[str, int]]:
    """A tier's must-match set through the mechanics API (every member, matched or not)."""
    status = mechanics.tier_status(mech, rows, {}, tier_id)
    assert status.total == len(status.unmatched_starts)
    return set(status.unmatched_starts)


def test_real_tier_queue_holds_the_signed_tiers_members(worlds):
    """07-26 over the committed config/: the tier queue's members are exactly the signed tiers'
    must-match sets (a row of two tiers in the first), never an asm row; its first dry-run
    picks are unmatched Tier 1 members, each once, a leaf first."""
    config_root = REPO_ROOT / "config"
    mech, rows = mechanics.read_committed(config_root)
    signed = mechanics.signed_tiers(mech, rows)
    assert signed and signed[0] == 1
    queue = driver.tier_source(config_root, worlds)({})
    queued = {i.key for i in queue.items if not i.hub}
    expected: set[tuple[str, int]] = set()
    for tier_id in signed:
        expected |= _member_keys(mech, rows, tier_id)
    assert queued == expected
    tier1 = {i.key for i in queue.items if i.tier == 1 and not i.hub}
    assert tier1 == _member_keys(mech, rows, 1)
    asm = {(r.exe, r.address) for r in rows if r.role == mechanics.ROLE_ASM}
    assert not {i.key for i in queue.items} & asm
    options = driver.DriveOptions(repo=REPO_ROOT, run_id="real-test", dry_run=True)
    picks = driver.pilot_picks(options, worlds, today="2026-10-25")
    assert len(picks) == driver.DRY_RUN_TIER_PICKS
    assert len({p.key for p in picks}) == len(picks)
    assert picks[0].level == 0
    matched = driver.matched_keys(config_root)
    for pick in picks:
        assert (pick.tier, pick.hub) == (1, False) and pick.key in tier1 - matched
        assert pick.pass_n >= 1
