"""The drive verb's real world (plan 06-25): both EXEs loaded through check's loader, score's
P16 survivors as the pools, and the pilot's 10 picks over the committed config/ (D-09, D-10).

Reads orig/ only (REVERSEAPOC_ORIG points a git worktree at the main checkout's orig/). No pack
is built, no docker, no claude: this is the part of `drive --dry-run` that needs the real files.
Prints only addresses and names, never game bytes.
"""

from __future__ import annotations

import pytest

from conftest import ORIG_DIR, REPO_ROOT
from reverseapoc import attempt, driver
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


def test_real_pilot_is_5_plus_5_and_skips_the_matched_rows(worlds):
    options = driver.DriveOptions(repo=REPO_ROOT, run_id="real-test", dry_run=True)
    picks = driver.pilot_picks(options, worlds, today="2026-10-25")
    assert [p.exe for p in picks] == list(EXE_ORDER) * PILOT_PER_EXE
    matched = driver.matched_keys(options.config_root)
    assert matched  # both Phase 5 matches are in the committed status tables
    assert not {(p.exe, p.start) for p in picks} & matched
    for exe in EXE_ORDER:
        units = [p.unit for p in picks if p.exe == exe]
        assert max(units.count(u) for u in units) <= 2  # D-10 variety rule
