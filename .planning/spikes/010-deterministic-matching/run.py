# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 010 Q3: lift every sample row, compile it with the real wcc386, judge it like `check`,
group the failures and append one point to the curve.

    uv run python .planning/spikes/010-deterministic-matching/run.py --label "iter 0: v0"

Writes build/spike-010/q3/<run>/ (src, obj, results.jsonl) and appends to
build/spike-010/curve.jsonl: per set and bucket, rows, lifted, compiled, exact, and the mean
score of the compiled rows. Prints the top failure groups. C sources stay under build/.
"""

from __future__ import annotations

import argparse
import dataclasses
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime

from common import (
    BUCKETS,
    OUT,
    Job,
    append_jsonl,
    compile_all,
    exe_inputs,
    judge,
    read_sample,
    rule_for,
    write_jsonl,
)
from lift import Lifter, Unliftable

# A next function under -o rules, so Watcom aligns ours as in the original. Not empty: an empty
# function's ret is tail-merged into ours (measured on tacp 0x000A68B0).
PAD = "\nint spike_pad(void)\n{\n    return 0x5a5a5a5a;\n}\n"


INFER = None  # --infer-flags CELL: the flag cell a default-rule row that ends in filler takes


def effective_rule(exe, row, stem, unit):
    """The unit's committed rule, or (with --infer-flags) a spike-local cell for a default-rule
    row whose original ends in filler: Watcom 10.6 aligns the next function to 16 only under a
    `t` optimisation (-ot, -oneatx; measured on tacp 0x000A68B0), so the filler is evidence of
    that option. A temporary rule, as `check --sweep` uses; config/cflags.txt is never edited."""
    rule = rule_for(stem, unit)
    if INFER and not any(f.startswith("-o") for f in rule.flags) and has_trailing_filler(exe, row):
        return dataclasses.replace(rule, flags=tuple(INFER.split()))
    return rule


def has_trailing_filler(exe, row) -> bool:
    from reverseapoc.x86 import decode, is_filler

    insns = list(decode(exe.flat[row.start : row.end], row.start))
    if not insns:
        return False
    last = insns[-1]
    ops = last.op_str.replace("dword ptr ", "").split(", ")
    return (
        is_filler(last)
        or last.mnemonic == "nop"
        or (last.mnemonic in ("mov", "lea") and len(ops) == 2 and ops[1].strip("[]") == ops[0])
    )


def lift_all(rows, root):
    sigs: dict = {}
    lifted = {}
    for r in rows:
        exe = exe_inputs(r["exe"])
        start = int(r["address"], 16)
        row = next(x for x in exe.rows if x.start == start)
        try:
            text = Lifter(exe, row, sigs).lift()
        except Unliftable as exc:
            lifted[r["exe"], start] = ("unliftable", str(exc))
            continue
        except Exception as exc:  # noqa: BLE001 - a converter crash is its own group in a spike
            lifted[r["exe"], start] = ("crash", f"{type(exc).__name__}")
            continue
        rule = effective_rule(exe, row, r["exe"], r["unit"])
        if has_trailing_filler(exe, row) and any(f.startswith("-o") for f in rule.flags):
            text += PAD
        src = root / "src" / r["exe"] / f"f_{start:08x}.c"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(text, encoding="ascii")
        lifted[r["exe"], start] = ("ok", src, rule)
    return lifted


_ERR = re.compile(r"Error! (E\d+):")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--set", default="sample,control")
    ap.add_argument("--infer-flags", metavar="CELL", help='e.g. "-4r -oneatx -s -fpi"')
    args = ap.parse_args()
    global INFER
    INFER = args.infer_flags
    sets = set(args.set.split(","))
    rows = [r for r in read_sample() if r["set"] in sets]
    run = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    root = OUT / "q3" / run
    t0 = time.perf_counter()
    lifted = lift_all(rows, root)
    lift_s = time.perf_counter() - t0
    jobs = {
        key: Job(v[1], v[1].with_suffix(".obj"), v[2]) for key, v in lifted.items() if v[0] == "ok"
    }
    done, timing = compile_all(list(jobs.values()), args.workers)
    by_src = {c.job.src: c for c in done}
    results = []
    t1 = time.perf_counter()
    for r in rows:
        key = (r["exe"], int(r["address"], 16))
        status, info = lifted[key][:2]
        rec = dict(
            exe=r["exe"],
            address=r["address"],
            set=r["set"],
            bucket=r["bucket"],
            size=int(r["size"]),
            lifted=status == "ok",
        )
        if status != "ok":
            rec.update(
                group=f"{status}: {info}", exact=False, exact_trim=False, compiled=False, score=0.0
            )
        else:
            c = by_src[info]
            rec["compiled"] = c.ok
            if not c.ok:
                m = _ERR.search(c.output)
                rec.update(
                    group=f"compile: {m.group(1) if m else 'error'}",
                    exact=False,
                    exact_trim=False,
                    score=0.0,
                )
            else:
                v = judge(r["exe"], c.job.obj, key[1])
                rec.update(
                    exact=v.exact,
                    exact_trim=v.exact or v.exact_trim,
                    score=v.score,
                    reloc_ok=v.reloc_ok,
                    bytes_ok=v.bytes_ok,
                    len_ours=v.len_ours,
                    len_row=v.len_row,
                    group="" if v.exact else _group(v),
                )
        results.append(rec)
    judge_s = time.perf_counter() - t1
    write_jsonl(root / "results.jsonl", results)
    point = dict(
        time=datetime.now(UTC).isoformat(timespec="seconds"),
        run=run,
        label=args.label,
        lift_s=round(lift_s, 2),
        compile_s=round(timing["compile_wall_s"], 2),
        judge_s=round(judge_s, 2),
        cells={},
    )
    cells = defaultdict(list)
    for rec in results:
        cells[f"{rec['set']}:{rec['bucket']}"].append(rec)
        cells[f"{rec['set']}:all"].append(rec)
    for cell, recs in cells.items():
        comp = [x for x in recs if x["compiled"]]
        point["cells"][cell] = dict(
            rows=len(recs),
            lifted=sum(x["lifted"] for x in recs),
            compiled=len(comp),
            exact=sum(x["exact"] for x in recs),
            exact_trim=sum(x["exact_trim"] for x in recs),
            mean_score=round(sum(x["score"] for x in comp) / len(comp), 1) if comp else 0.0,
            near=sum(1 for x in comp if not x["exact"] and x["score"] >= 90),
        )
    append_jsonl(OUT / "curve.jsonl", point)
    print(
        f"run {run} ({args.label}): lift {lift_s:.1f}s, compile {timing['compile_wall_s']:.1f}s, "
        f"judge {judge_s:.1f}s"
    )
    order = [
        f"{s}:{b}" for s in ("control", "sample") for b in [*(n for _, _, n in BUCKETS), "all"]
    ]
    for cell in order:
        if cell in point["cells"]:
            c = point["cells"][cell]
            print(
                f"  {cell:18} rows {c['rows']:3}  lifted {c['lifted']:3}"
                f"  compiled {c['compiled']:3}"
                f"  exact {c['exact']:3} ({100 * c['exact'] / c['rows']:5.1f}%)"
                f"  +filler-cut {c['exact_trim']:3}  near>=90 {c['near']:3}"
                f"  mean score {c['mean_score']}"
            )
    groups = Counter(
        "unit-boundary filler (exact when cut)" if rec["exact_trim"] else rec["group"]
        for rec in results
        if not rec["exact"]
    )
    print("top failure groups:")
    for g, n in groups.most_common(25):
        print(f"  {n:4}  {g}")
    return 0


def _group(v) -> str:
    if v.len_ours != v.len_row and v.score >= 99.9:
        return "length only"
    return f"diff: {v.key}"


if __name__ == "__main__":
    sys.exit(main())
