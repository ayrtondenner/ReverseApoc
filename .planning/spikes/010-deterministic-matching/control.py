# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 010 harness control: the committed units of the matched Tier 1 sample rows, compiled by
the batch path and judged by the harness, must all be exact; a planted mutant must not be.

    uv run python .planning/spikes/010-deterministic-matching/control.py [--workers N]

The mutant copies one control unit to build/spike-010/control/mutant/ and turns its first
`extern signed char` into `extern unsigned char` (or `extern int` into `extern short`).
Exit 1 unless every control function is exact and the mutant fails.
"""

from __future__ import annotations

import argparse
import re
import sys

from common import OUT, REPO_ROOT, Job, compile_all, judge, read_sample, rule_for

_MUTATIONS = (
    (re.compile(r"\bextern signed char\b"), "extern unsigned char"),
    (re.compile(r"\bextern int\b"), "extern short"),
    (re.compile(r"\bextern short\b"), "extern int"),
    (re.compile(r"\bextern char\b"), "extern signed char"),
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    control = [r for r in read_sample() if r["set"] == "control"]
    units = sorted({(r["exe"], r["unit"]) for r in control})
    base = OUT / "control"
    jobs = [
        Job(
            REPO_ROOT / "src" / exe / f"{unit}.c",
            base / "obj" / exe / f"{unit}.obj",
            rule_for(exe, unit),
        )
        for exe, unit in units
    ]
    done, timing = compile_all(jobs, args.workers)
    failed_compiles = [c.job.src.name for c in done if not c.ok]
    exact = 0
    for r in control:
        obj = base / "obj" / r["exe"] / f"{r['unit']}.obj"
        v = judge(r["exe"], obj, int(r["address"], 16))
        exact += v.exact
        if not v.exact:
            print(f"FAIL control {r['exe']} {r['address']} {v.key} score={v.score}")
    print(
        f"control: {exact}/{len(control)} exact from {len(units)} units; compile failures "
        f"{len(failed_compiles)}; gate {timing['gate_s']:.2f}s; compile wall "
        f"{timing['compile_wall_s']:.2f}s"
    )
    ok = exact == len(control) and not failed_compiles
    return 0 if mutant(control, base) and ok else 1


def mutant(control: list[dict], base) -> bool:
    for r in control:
        text = (REPO_ROOT / "src" / r["exe"] / f"{r['unit']}.c").read_text(encoding="utf-8")
        for pattern, repl in _MUTATIONS:
            if not pattern.search(text):
                continue
            src = base / "mutant" / r["exe"] / f"{r['unit']}.c"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text(pattern.sub(repl, text, count=1), encoding="utf-8")
            obj = src.with_suffix(".obj")
            done, _ = compile_all([Job(src, obj, rule_for(r["exe"], r["unit"]))], 1)
            members = [c for c in control if (c["exe"], c["unit"]) == (r["exe"], r["unit"])]
            verdicts = [judge(c["exe"], obj, int(c["address"], 16)) for c in members]
            if not done[0].ok or all(v.exact for v in verdicts):
                continue  # the mutation did not reach a control function; try the next one
            print(
                f"mutant {r['exe']}/{r['unit']} ({pattern.pattern} -> {repl}): "
                f"{sum(not v.exact for v in verdicts)} of {len(verdicts)} control functions fail "
                "(PASS: the judge can fail)"
            )
            return True
    print("FAIL no mutant reached a control function")
    return False


if __name__ == "__main__":
    sys.exit(main())
