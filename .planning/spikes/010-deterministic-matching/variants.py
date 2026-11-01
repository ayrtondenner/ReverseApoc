# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 010 Q4: scripted variant search, no model. Every sample row the converter lifted and
compiled but did not match is lifted again under each combination of its choice points, and
every variant is judged by the real compiler:

- return type: as inferred, forced `void`, forced `int`;
- evaluation: compute-once (a reused value goes through its variable) or re-emit (Watcom CSE);
- narrow parameter and return types (char/short from byte/word reads) on or off;
- array indexing `((T *)D)[i]` or byte arithmetic `*(T *)(D + i*N)`;
- local declaration order: as found and reversed (stack slots; Theme Hospital MATCHING.md).

    uv run python .planning/spikes/010-deterministic-matching/variants.py --run <q3 run id>

Prints extra exact and filler-cut matches, compiles per match and seconds per variant.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time

import run as q3
from common import OUT, Job, compile_all, exe_inputs, judge, read_sample
from lift import Lifter, Unliftable


def variants():
    for ret, once, narrow, array, rev in itertools.product(
        (None, "void", "int"), (True, False), (True, False), (True, False), (False, True)
    ):
        yield dict(force_ret=ret, once=once, narrow=narrow, array=array), rev


def reverse_locals(text: str) -> str:
    lines = text.split("\n")
    idx = [
        i
        for i, line in enumerate(lines)
        if line.startswith("    ")
        and line.rstrip().endswith(";")
        and line.split()[0] in ("int", "short", "unsigned", "signed")
        and "=" not in line
        and "(" not in line
    ]
    head = [
        i for i in idx if i < next((k for k, ln in enumerate(lines) if ln == "{"), 0) + 1 + len(idx)
    ]
    block = [lines[i] for i in head]
    for i, line in zip(head, reversed(block), strict=True):
        lines[i] = line
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--infer-flags", metavar="CELL", help="as run.py --infer-flags")
    args = ap.parse_args()
    q3.INFER = args.infer_flags
    base = OUT / "q3" / args.run
    results = [json.loads(line) for line in (base / "results.jsonl").open(encoding="utf-8")]
    units = {(r["exe"], r["address"]): r["unit"] for r in read_sample()}
    todo = [r for r in results if r["set"] == "sample" and r["compiled"] and not r["exact"]]
    root = OUT / "q4" / args.run
    t0 = time.perf_counter()
    jobs, meta = [], []
    sigs: dict = {}  # callee signatures do not depend on the choice points: one cache
    for r in todo:
        exe = exe_inputs(r["exe"])
        start = int(r["address"], 16)
        row = next(x for x in exe.rows if x.start == start)
        seen = set()
        for n, (opts, rev) in enumerate(variants()):
            try:
                text = Lifter(exe, row, sigs, **opts).lift()
            except Unliftable:
                continue
            if rev:
                text = reverse_locals(text)
            if text in seen:
                continue
            seen.add(text)
            src = root / r["exe"] / f"f_{start:08x}_v{n:02d}.c"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text(text, encoding="ascii")
            rule = q3.effective_rule(exe, row, r["exe"], units[r["exe"], r["address"]])
            if q3.has_trailing_filler(exe, row) and any(f.startswith("-o") for f in rule.flags):
                text += q3.PAD
                src.write_text(text, encoding="ascii")
            jobs.append(Job(src, src.with_suffix(".obj"), rule))
            meta.append((r, n, opts, rev))
    gen_s = time.perf_counter() - t0
    done, timing = compile_all(jobs, args.workers)
    t1 = time.perf_counter()
    best: dict = {}
    hits: dict = {}
    for (r, n, opts, rev), c in zip(meta, done, strict=True):
        key = (r["exe"], r["address"])
        if not c.ok:
            continue
        v = judge(r["exe"], c.job.obj, int(r["address"], 16))
        best[key] = max(best.get(key, 0.0), v.score)
        if v.exact or v.exact_trim:
            hits.setdefault(key, []).append((n, "exact" if v.exact else "filler-cut", opts, rev))
    judge_s = time.perf_counter() - t1
    was_trim = {(r["exe"], r["address"]) for r in todo if r.get("exact_trim")}
    new = {k: v for k, v in hits.items() if k not in was_trim}
    print(
        f"rows {len(todo)} (compiled, not exact), distinct variants {len(jobs)}, "
        f"compiled {sum(c.ok for c in done)}; generate {gen_s:.1f}s, compile "
        f"{timing['compile_wall_s']:.1f}s, judge {judge_s:.1f}s -> "
        f"{(gen_s + timing['compile_wall_s'] + judge_s) / max(1, len(jobs)):.3f} s/variant"
    )
    print(
        f"rows with an exact or filler-cut variant: {len(hits)} (of which already filler-cut "
        f"before: {len(hits) - len(new)}; new: {len(new)}); strictly exact: "
        f"{sum(any(h[1] == 'exact' for h in v) for v in hits.values())}"
    )
    for k, v in sorted(new.items()):
        print(f"  NEW {k[0]} {k[1]}: {v[0][1]} via variant {v[0][0]} {v[0][2]} reversed={v[0][3]}")
    near = sorted(((s, k) for k, s in best.items() if k not in hits and s >= 90), reverse=True)
    print(f"best-variant near-misses (>=90, no match): {len(near)}")
    by_bucket: dict = {}
    for r in todo:
        k = (r["exe"], r["address"])
        b = by_bucket.setdefault(r["bucket"], [0, 0, 0.0])
        b[0] += 1
        b[1] += k in hits
        b[2] += best.get(k, 0.0)
    for name, (n, h, s) in sorted(by_bucket.items()):
        print(f"  {name:9} rows {n:3} matched by a variant {h:3} mean best score {s / n:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
