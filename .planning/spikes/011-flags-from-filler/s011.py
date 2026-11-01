# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 011 shared setup: spike 010's harness and converter, plus the inferred flag cell.

Spike 010 (`.planning/spikes/010-deterministic-matching/`) owns the batch compile, the judge
(check's relocation check and byte compare) and the converter; this spike imports them.
"""

from __future__ import annotations

import sys
from pathlib import Path

S010 = Path(__file__).resolve().parents[1] / "010-deterministic-matching"
sys.path.insert(0, str(S010))

import common  # noqa: E402  (spike 010)
import run as s010_run  # noqa: E402  (spike 010: effective_rule, has_trailing_filler, PAD)

from reverseapoc import mechanics  # noqa: E402

OUT = common.REPO_ROOT / "build" / "spike-011"
CELL = "-4r -oneatx -s -fpi"  # spike 010 iteration 7: beats -ot (20 vs 15 of 200)


def not_matched_tier1() -> list[dict]:
    """Every Tier 1 must-match member that status.csv does not mark matched."""
    mech, members = mechanics.read_committed(common.CONFIG)
    statuses = mechanics.read_statuses(common.CONFIG, ("ufo2p", "tacp"))
    ids = mechanics._tier_ids(mech, 1)
    out = []
    for m in sorted(members, key=mechanics.row_key):
        if m.role != mechanics.ROLE_MEMBER or not ids.intersection(m.member_items):
            continue
        status = statuses.get((m.exe, m.address), "unmatched")
        if status == "matched":
            continue
        exe = common.exe_inputs(m.exe)
        row = next(r for r in exe.rows if r.start == m.address)
        size = row.end - row.start
        out.append(
            dict(
                exe=m.exe,
                address=f"0x{m.address:08X}",
                unit=row.unit,
                size=size,
                bucket=common.bucket_of(size),
                status=status,
                filler=s010_run.has_trailing_filler(exe, row),
            )
        )
    return out


def rule(exe_stem: str, row, inferred: bool):
    """The committed rule, or (inferred) the spike's cell for a default-rule row that ends in
    filler."""
    s010_run.INFER = CELL if inferred else None
    return s010_run.effective_rule(common.exe_inputs(exe_stem), row, exe_stem, row.unit)


def needs_pad(exe_stem: str, row, rule_) -> bool:
    return s010_run.has_trailing_filler(common.exe_inputs(exe_stem), row) and any(
        f.startswith("-o") for f in rule_.flags
    )
