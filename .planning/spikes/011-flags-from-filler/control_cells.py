# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 011 falsification check: the committed units of every matched function, compiled under
the committed rule and under each candidate t-cell. If the units were really built with a
t-optimisation, the matched functions should stay exact under that cell (or tell which cell).

    uv run python .planning/spikes/011-flags-from-filler/control_cells.py

Prints, per cell, how many of the matched functions stay exact, split by their unit's census
verdict (unit_census.py must have run).
"""

from __future__ import annotations

import csv
import dataclasses
from collections import Counter

import s011
from common import REPO_ROOT, Job, compile_all, exe_inputs, judge, rule_for

CELLS = (None, "-4r -oneatx -s -fpi", "-4r -ot -s -fpi", "-4r -ox -s -fpi")


def matched() -> list[tuple[str, int, str]]:
    out = []
    for stem in ("ufo2p", "tacp"):
        path = REPO_ROOT / "config" / stem / "status.csv"
        rows = csv.reader(line for line in path.open(encoding="utf-8") if not line.startswith("#"))
        next(rows)
        for start, _name, unit, status, *_ in rows:
            if status == "matched":
                out.append((stem, int(start, 16), unit))
    return out


def main() -> None:
    census = {
        (r["exe"], r["unit"]): r["verdict"]
        for r in csv.DictReader((s011.OUT / "unit-census.csv").open(encoding="utf-8"))
    }
    funcs = matched()
    units = sorted({(s, u) for s, _, u in funcs})
    for cell in CELLS:
        jobs = []
        for stem, unit in units:
            base = rule_for(stem, unit)
            rule_ = base if cell is None else dataclasses.replace(base, flags=tuple(cell.split()))
            tag = "committed" if cell is None else cell.split()[1].lstrip("-")
            src = REPO_ROOT / "src" / stem / f"{unit}.c"
            obj = s011.OUT / "control" / tag / stem / f"{unit}.obj"
            jobs.append(Job(src, obj, rule_))
        done, _ = compile_all(jobs, 12)
        objs = {(j.src.parent.name, j.src.stem): j.obj for j in jobs}
        res: Counter = Counter()
        for stem, start, unit in funcs:
            ok = judge(stem, objs[stem, unit], start).exact
            verdict = census.get((stem, unit), "?")
            committed_t = any(f in ("-ot", "-oneatx") for f in rule_for(stem, unit).flags)
            group = "t-rule unit" if committed_t else f"default/o unit, census {verdict}"
            res[group, ok] += 1
        label = cell or "committed rule"
        print(f"{label}: compiled {sum(c.ok for c in done)}/{len(done)} units")
        for group in sorted({g for g, _ in res}):
            total = res[group, True] + res[group, False]
            print(f"  {group:38} exact {res[group, True]:3} / {total:3}")
    assert exe_inputs  # imported for its EXE cache only


if __name__ == "__main__":
    main()
