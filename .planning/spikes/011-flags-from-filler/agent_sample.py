# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 011 part 2 sample: default-rule Tier 1 rows that end in filler and that no converter arm
of all_tier1.py matched, drawn with a fixed seed per size bucket.

    uv run python .planning/spikes/011-flags-from-filler/agent_sample.py

Writes build/spike-011/agent-sample.csv and prints one line per agent group.
"""

from __future__ import annotations

import csv
import json
import random

import s011
from common import rule_for

SEED = 20261102
PER_BUCKET = {"64-255": 6, "256-1023": 5, ">=1024": 3}


def main() -> None:
    results = [
        json.loads(line) for line in (s011.OUT / "all" / "results.jsonl").open(encoding="utf-8")
    ]
    rng = random.Random(SEED)
    picked = []
    for bucket, n in PER_BUCKET.items():
        pool = [
            r
            for r in results
            if r["bucket"] == bucket
            and r["filler"]
            and not any(r[a] for a in ("committed", "committed+void", "inferred", "inferred+void"))
            and not any(f.startswith("-o") for f in rule_for(r["exe"], r["unit"]).flags)
        ]
        picked += [dict(r, group=bucket) for r in rng.sample(pool, n)]
        print(
            f"{bucket}: pool {len(pool)}, picked {n}: "
            + ", ".join(f"{r['exe']} {r['address']} ({r['size']} B)" for r in picked[-n:])
        )
    with (s011.OUT / "agent-sample.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["group", "exe", "address", "unit", "size", "status"])
        w.writeheader()
        for r in picked:
            w.writerow({k: r[k] for k in w.fieldnames})


if __name__ == "__main__":
    main()
