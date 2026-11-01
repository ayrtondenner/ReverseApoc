# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 010 fixed sample: every matched Tier 1 must-match member (the control) plus PER_BUCKET
not-matched members per size bucket, drawn with a fixed seed. Held rows (07-44) are left out.

    uv run python .planning/spikes/010-deterministic-matching/sample.py

Writes build/spike-010/sample.csv (exe, address, unit, size, bucket, status, set); prints counts.
"""

from __future__ import annotations

import csv
import random
from collections import Counter

from common import BUCKETS, CONFIG, OUT, bucket_of, exe_inputs

from reverseapoc import mechanics

SEED = 20261101
PER_BUCKET = 50
TIER = 1


def main() -> None:
    mech, members = mechanics.read_committed(CONFIG)
    statuses = mechanics.read_statuses(CONFIG, ("ufo2p", "tacp"))
    held = mechanics.signed_held(CONFIG, mech)
    status = mechanics.tier_status(mech, members, statuses, TIER, held=held)
    waiting = set(status.unmatched_starts)
    ids = mechanics._tier_ids(mech, TIER)
    tier = sorted(
        (
            r
            for r in members
            if r.role == mechanics.ROLE_MEMBER and ids.intersection(r.member_items)
        ),
        key=mechanics.row_key,
    )
    rows = []
    for m in tier:
        exe = exe_inputs(m.exe)
        row = next(r for r in exe.rows if r.start == m.address)
        size = row.end - row.start
        st = statuses.get((m.exe, m.address), "unmatched")
        rows.append(
            dict(
                exe=m.exe,
                address=f"0x{m.address:08X}",
                unit=row.unit,
                size=size,
                bucket=bucket_of(size),
                status=st,
                held=(m.exe, m.address) in held,
                waiting=(m.exe, m.address) in waiting,
            )
        )
    control = [r for r in rows if r["status"] == "matched"]
    rng = random.Random(SEED)
    picked = []
    for _, _, name in BUCKETS:
        pool = [
            r for r in rows if r["bucket"] == name and r["status"] != "matched" and not r["held"]
        ]
        picked += rng.sample(pool, min(PER_BUCKET, len(pool)))
    out = [dict(r, set="control") for r in control] + [dict(r, set="sample") for r in picked]
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "sample.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh, fieldnames=["exe", "address", "unit", "size", "bucket", "status", "set"]
        )
        w.writeheader()
        for r in out:
            w.writerow({k: r[k] for k in w.fieldnames})
    print(
        f"tier {TIER}: {len(rows)} members; not matched {len(waiting)}; "
        f"held {len(status.held_starts)}"
    )
    print("all members by bucket:", dict(Counter(r["bucket"] for r in rows)))
    print(
        "not matched by bucket:",
        dict(Counter(r["bucket"] for r in rows if r["status"] != "matched")),
    )
    print(f"control {len(control)}:", dict(Counter(r["bucket"] for r in control)))
    print(f"sample {len(picked)}:", dict(Counter(r["bucket"] for r in picked)))


if __name__ == "__main__":
    main()
