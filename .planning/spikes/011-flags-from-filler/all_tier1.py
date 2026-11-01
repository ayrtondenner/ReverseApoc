# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 011 part 1: spike 010's converter over every not-matched Tier 1 row (886), under the
committed rule and under the inferred cell, each with the converter's default choice points and
with `void` forced (spike 010 Q4's only winning variant).

    uv run python .planning/spikes/011-flags-from-filler/all_tier1.py

Writes build/spike-011/all/results.jsonl (address, bucket, filler, exact per arm) and prints
exact counts per bucket and arm. Generated C stays under build/spike-011/all/.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter

import s011
from common import Job, compile_all, exe_inputs, judge
from lift import Lifter, Unliftable

ARMS = (
    ("committed", False, {}),
    ("committed+void", False, {"force_ret": "void", "once": True}),
    ("inferred", True, {}),
    ("inferred+void", True, {"force_ret": "void", "once": True}),
)


def main() -> int:
    rows = s011.not_matched_tier1()
    root = s011.OUT / "all"
    t0 = time.perf_counter()
    sigs: dict = {}
    jobs, meta = [], []
    lift_fail: Counter = Counter()
    for r in rows:
        exe = exe_inputs(r["exe"])
        start = int(r["address"], 16)
        row = next(x for x in exe.rows if x.start == start)
        texts = {}
        for name, _, opts in ARMS:
            key = json.dumps(opts, sort_keys=True)
            if key in texts:
                continue
            try:
                texts[key] = Lifter(exe, row, sigs, **opts).lift()
            except Unliftable as exc:
                texts[key] = None
                lift_fail[str(exc)] += name == "committed"
            except Exception as exc:  # noqa: BLE001 - a converter crash is a refusal here
                texts[key] = None
                lift_fail[f"crash: {type(exc).__name__}"] += name == "committed"
        for name, inferred, opts in ARMS:
            text = texts[json.dumps(opts, sort_keys=True)]
            if text is None:
                continue
            rule_ = s011.rule(r["exe"], row, inferred)
            if s011.needs_pad(r["exe"], row, rule_):
                text += s011.s010_run.PAD
            src = root / name.replace("+", "-") / r["exe"] / f"f_{start:08x}.c"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text(text, encoding="ascii")
            jobs.append(Job(src, src.with_suffix(".obj"), rule_))
            meta.append((r, name))
    gen_s = time.perf_counter() - t0
    done, timing = compile_all(jobs, 12)
    t1 = time.perf_counter()
    exact: dict = {}
    for (r, name), c in zip(meta, done, strict=True):
        ok = c.ok and judge(r["exe"], c.job.obj, int(r["address"], 16)).exact
        exact.setdefault((r["exe"], r["address"]), {})[name] = ok
    judge_s = time.perf_counter() - t1
    out = root / "results.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            arms = exact.get((r["exe"], r["address"]), {})
            fh.write(json.dumps(dict(r, **{n: arms.get(n, False) for n, _, _ in ARMS})) + "\n")
    print(
        f"rows {len(rows)}, variants compiled {sum(c.ok for c in done)}/{len(jobs)}; "
        f"lift {gen_s:.1f}s, compile {timing['compile_wall_s']:.1f}s, judge {judge_s:.1f}s"
    )
    print(f"refused by the converter (committed arm): {sum(lift_fail.values())}")
    buckets = ("<64", "64-255", "256-1023", ">=1024")
    header = "arm".ljust(16) + "".join(b.rjust(10) for b in buckets) + "     all"
    print(header)
    for name, _, _ in ARMS:
        counts = [
            sum(
                1
                for r in rows
                if r["bucket"] == b and exact.get((r["exe"], r["address"]), {}).get(name)
            )
            for b in buckets
        ]
        print(
            name.ljust(16) + "".join(str(n).rjust(10) for n in counts) + str(sum(counts)).rjust(8)
        )
    best = [
        sum(
            1
            for r in rows
            if r["bucket"] == b and any(exact.get((r["exe"], r["address"]), {}).values())
        )
        for b in buckets
    ]
    totals = [sum(1 for r in rows if r["bucket"] == b) for b in buckets]
    print("any arm".ljust(16) + "".join(str(n).rjust(10) for n in best) + str(sum(best)).rjust(8))
    print("rows".ljust(16) + "".join(str(n).rjust(10) for n in totals) + str(sum(totals)).rjust(8))
    return 0


if __name__ == "__main__":
    sys.exit(main())
