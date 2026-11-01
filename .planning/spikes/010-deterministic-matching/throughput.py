# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 010 Q2: batch compile and judge throughput with the real wcc386 10.6.

    uv run python .planning/spikes/010-deterministic-matching/throughput.py [--n 600]
    docker compose run --rm build uv run python \
        .planning/spikes/010-deterministic-matching/throughput.py

Writes N one-function stub files (`int <name>(void) { return 0; }`, one per Tier 1 member, the
unit's cflags rule) under build/spike-010/q2/<platform>/, compiles them at several worker counts
and judges each. The gate (check_gate: hash or stamp, banner) is timed once per batch. Prints
seconds per function and the projection for all Tier 1 members against the 10-minute target.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from common import CONFIG, OUT, Job, compile_all, exe_inputs, judge, rule_for

from reverseapoc import mechanics

TIER_SIZE = 943
TARGET_S = 600.0


def members(n: int) -> list[tuple[str, int, str]]:
    mech, rows = mechanics.read_committed(CONFIG)
    ids = mechanics._tier_ids(mech, 1)
    tier = sorted(
        (r for r in rows if r.role == mechanics.ROLE_MEMBER and ids.intersection(r.member_items)),
        key=mechanics.row_key,
    )
    out = []
    for m in tier[:n]:
        row = next(r for r in exe_inputs(m.exe).rows if r.start == m.address)
        out.append((m.exe, m.address, row.unit))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--workers", default=f"1,4,{os.cpu_count()}")
    args = ap.parse_args()
    t0 = time.perf_counter()
    picked = members(args.n)
    load_s = time.perf_counter() - t0
    root = OUT / "q2" / sys.platform
    jobs = []
    for exe, start, unit in picked:
        name = exe_inputs(exe).symbols.c_name(start)
        src = root / "src" / exe / f"f_{start:08x}.c"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(f"int {name}(void)\n{{\n    return 0;\n}}\n", encoding="ascii")
        jobs.append(Job(src, src.with_suffix(".obj"), rule_for(exe, unit)))
    print(
        f"platform {sys.platform}, cpu_count {os.cpu_count()}, {len(jobs)} stubs, "
        f"inputs loaded in {load_s:.2f}s"
    )
    for workers in (int(w) for w in args.workers.split(",")):
        done, timing = compile_all(jobs, workers)
        t1 = time.perf_counter()
        verdicts = [
            judge(exe, j.obj, start) for (exe, start, _), j in zip(picked, jobs, strict=True)
        ]
        judge_s = time.perf_counter() - t1
        ok = sum(c.ok for c in done)
        per_fn = (timing["compile_wall_s"] + judge_s) / len(jobs)
        mean_one = sum(c.seconds for c in done) / len(done)
        print(
            f"workers {workers:>2}: compiled {ok}/{len(jobs)} in {timing['compile_wall_s']:.2f}s "
            f"(one compile {mean_one:.3f}s mean), judged in {judge_s:.2f}s single-threaded, "
            f"gate {timing['gate_s']:.3f}s -> {per_fn:.4f} s/function; Tier 1 ({TIER_SIZE}) "
            f"projected {per_fn * TIER_SIZE:.1f}s vs target {TARGET_S:.0f}s; "
            f"exact stubs {sum(v.exact for v in verdicts)}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
