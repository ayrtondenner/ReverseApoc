"""Spike 008: Opus vs Fable on functions Opus already left PARTIAL.

Reads progress/attempts.jsonl (committed, schema 2 matching records) and prints one row per
group: Opus first tries, Opus retries after a PARTIAL, and Fable sessions (the --fable-trial
night). A session counts as "after partial" when an earlier record of the same function ended
PARTIAL. Prints counts, rates, dollars and minutes only.

Usage: uv run python .planning/spikes/008-fable-trial-matching/compare.py [RUN ...]
With RUN ids, the Fable group is limited to those runs.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

LOG = Path(__file__).resolve().parents[3] / "progress" / "attempts.jsonl"
FABLE = "claude-fable-5-1"


def main(runs: set[str]) -> int:
    seen: dict[tuple[str, str], list[str]] = defaultdict(list)
    groups: dict[str, list[dict]] = defaultdict(list)
    for line in LOG.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec.get("kind") != "attempt" or rec.get("schema") != 2:
            continue
        if rec.get("session") != "matching":
            continue
        key = (rec["exe"], rec["start"])
        after = "PARTIAL" in seen[key]
        if rec.get("model_requested") == FABLE:
            if not runs or rec["run"] in runs:
                name = "fable on partial" if after else "fable, no prior partial"
                groups[name].append(rec)
        else:
            groups["opus retry after partial" if after else "opus first try"].append(rec)
        seen[key].append(rec["outcome"])
    head = ("group", "sess", "match", "rate", "$/sess", "$/match", "min/sess")
    print(f"{head[0]:28} " + " ".join(f"{h:>8}" for h in head[1:]))
    for name in sorted(groups):
        recs = groups[name]
        n = len(recs)
        m = sum(r["outcome"] == "MATCHED" for r in recs)
        cost = sum(r.get("cost_usd") or 0.0 for r in recs)
        secs = sum(r.get("seconds") or 0.0 for r in recs)
        per_match = f"{cost / m:8.2f}" if m else f"{'n/a':>8}"
        cells = (f"{n:8d}", f"{m:8d}", f"{m / n:8.1%}", f"{cost / n:8.2f}", per_match,
                 f"{secs / n / 60:8.1f}")
        print(f"{name:28} " + " ".join(cells))
    return 0


if __name__ == "__main__":
    sys.exit(main(set(sys.argv[1:])))
