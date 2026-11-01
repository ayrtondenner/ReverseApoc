# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 011: classify every unit by function-start alignment.

Under -ot / -oneatx wcc386 10.6 aligns each function to 16 (spike 010, iteration 7), so in a
unit built that way every game/thunk row after the unit's first starts on a 16-byte boundary.
One interior start off a 16 boundary rules a t-optimisation out for that unit (the default and
-ox do not align). A unit whose interior starts are all aligned is a t-optimisation candidate;
the evidence is weak when it has few interior starts (a start is aligned by chance 1 time in 16
under no alignment, roughly).

    uv run python .planning/spikes/011-flags-from-filler/unit_census.py

Prints per EXE and rule: units, candidates by number of aligned interior starts, units ruled
out; and the Tier 1 not-matched rows that sit in candidate units. Writes
build/spike-011/unit-census.csv (exe, unit, rule, interior starts, aligned, verdict).
"""

from __future__ import annotations

import csv
import json
from collections import Counter

import s011
from common import exe_inputs, rule_for

ALIGN = 16
KINDS = ("game", "thunk")


def main() -> None:
    tier1 = {
        (r["exe"], r["unit"])
        for r in (
            json.loads(line) for line in (s011.OUT / "all" / "results.jsonl").open(encoding="utf-8")
        )
    }
    rows_out = []
    counts: Counter = Counter()
    for stem in ("ufo2p", "tacp"):
        exe = exe_inputs(stem)
        by_unit: dict = {}
        for row in sorted(exe.rows, key=lambda r: r.start):
            if row.kind in KINDS:
                by_unit.setdefault(row.unit, []).append(row)
        for unit, rows in by_unit.items():
            rule_ = rule_for(stem, unit)
            t_opt = any(f in ("-ot", "-oneatx") for f in rule_.flags)
            kind = (
                "t-rule"
                if t_opt
                else ("o-rule" if any(f.startswith("-o") for f in rule_.flags) else "default")
            )
            interior = rows[1:]
            aligned = sum(1 for r in interior if r.start % ALIGN == 0)
            if not interior:
                verdict = "no evidence"
            elif aligned < len(interior):
                verdict = "not t"
            elif len(interior) >= 3:
                verdict = "t (strong)"
            else:
                verdict = "t (weak)"
            counts[stem, kind, verdict] += 1
            rows_out.append(
                dict(
                    exe=stem,
                    unit=unit,
                    rule=" ".join(rule_.flags),
                    kind=kind,
                    interior=len(interior),
                    aligned=aligned,
                    verdict=verdict,
                    tier1=(stem, unit) in tier1,
                )
            )
    for stem in ("ufo2p", "tacp"):
        for kind in ("default", "o-rule", "t-rule"):
            line = ", ".join(
                f"{v} {counts[stem, kind, v]}"
                for v in ("t (strong)", "t (weak)", "not t", "no evidence")
            )
            print(f"{stem:5} {kind:7}: {line}")
    with (s011.OUT / "unit-census.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_out[0]))
        w.writeheader()
        w.writerows(rows_out)
    verdict_of = {(r["exe"], r["unit"]): r["verdict"] for r in rows_out}
    results = [
        json.loads(line) for line in (s011.OUT / "all" / "results.jsonl").open(encoding="utf-8")
    ]
    per: Counter = Counter()
    for r in results:
        per[verdict_of.get((r["exe"], r["unit"]), "no unit"), r["filler"]] += 1
    print("not-matched Tier 1 rows by their unit's verdict (row ends in filler / not):")
    for v in ("t (strong)", "t (weak)", "not t", "no evidence"):
        print(f"  {v:12} filler {per[v, True]:4}  no filler {per[v, False]:4}")


if __name__ == "__main__":
    main()
