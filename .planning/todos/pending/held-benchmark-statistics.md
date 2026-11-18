---
title: A frozen held benchmark with repeats, intervals and paired tests
created: 2026-11-18
area: evaluation
files: tools/reverseapoc/stats.py, tools/reverseapoc/cli.py
source: literature mining of 2026-11-18 (docs/research/notes-ideas-tooling-reproducibility.md #3; docs/research/notes-ideas-agentic-projects.md #6)
---

# A frozen held benchmark with repeats, intervals and paired tests

**Why.** Model comparisons use single runs and raw rates, with no spread (trAIns' single baseline is the pattern to avoid). Mizuchi repeats runs; VideoGameBench keeps hidden games; McNemar and Wilson intervals fit paired match/no-match data.

**Do.** A versioned pick set with a dev/held-out split, k repeats per arm, Wilson intervals and McNemar tests in stats, and decision rules written before each held comparison.

**Done when.** stats --compare prints intervals and the paired test; a pre-registered comparison is run once.

**Effort / value.** M / high. Evidence and sources: docs/research/notes-ideas-tooling-reproducibility.md #3; docs/research/notes-ideas-agentic-projects.md #6.

## Status (2026-11-18)

Status (batch 2026-11-18, U7): config/benchmarks/held-v1.txt (60 picks, seed 20261118) and `stats --compare` with Wilson intervals and exact McNemar are built. Left: one pre-registered comparison run; and a ruling on picks matched after the freeze (copy without them, or a driver skip option).
