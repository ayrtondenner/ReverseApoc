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

## Owner rulings and status (2026-11-24, unit K)

Rulings: (1) picks matched after the freeze: **copy without them**. (2) The first
pre-registered comparison is the context-pack ablations of todo `held-context-ablations`, on
Haiku 5.5 (arm `claude-haiku-5-5`), k = 2 repeats, Wilson intervals and exact McNemar per
factor, within about 6.6% of the weekly Claude bar.

Built: `config/benchmarks/held-v1b.txt`, held-v1 without the 4 picks matched by 9b98ecc7
(ufo2p 0x0008A0C0, tacp 0x000A3790, ufo2p 0x00060BD0, tacp 0x00097370; 56 picks: 18, 19, 19
by size group). Its header names the date, source set, base commit and dropped picks, and
tests/test_stats.py checks both lists. The pre-registration, with hypotheses, the run matrix,
the exact commands and the decision rules, is `docs/benchmarks/held-v1b-ablations.md`. Repeats
combine as "exact in any repeat" per pick, which `stats --compare 'RUN-r*'` already computes.
Left: the 8 hold runs and their dated result sections in docs/model-comparison.md.

## Result (2026-11-25)

Run as amended before any comparison was read (k = 1, held-v1c with 55 picks, one session per
pick, Haiku 5.5 on 8 workers, `--hold`, 1.1%week each): `20261125b-abl-base-r1`,
`-lookalike-off-r1b`, `-carry-off-r1b`, `-effort-on-r1c`, 54 sessions each (1 pick over the pack
cap in every run). 0 exact in every condition, 0 discordant pairs, exact McNemar p = 1.0000 for
each factor. Decision under the pre-registered rule: **no difference shown** for look-alikes,
carry and effort. The pack stays as it is, and nights keep the CLI's default effort.
Descriptively, best percent moved by under a point and high effort cost about 2x ($10.36 against
$5.30). Full tables, digests, controls and the runs that don't count:
docs/model-comparison.md "Held context ablations on held-v1c (2026-11-25, Haiku 5.5)"; stats
output in build/gate/20261125-abl/. A second repeat (r2) was not run and is not pre-registered as
it stands; held-v2 with easier, unattempted picks would give the tests more power.
