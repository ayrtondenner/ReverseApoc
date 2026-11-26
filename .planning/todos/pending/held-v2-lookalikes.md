---
title: held-v2, a held set with power, and the look-alike test on it
created: 2026-11-25
area: evaluation
files: config/benchmarks/held-v2.txt, config/benchmarks/reserved.txt, docs/benchmarks/held-v2-lookalikes.md, tests/test_stats.py
source: held-v1c ablations (docs/model-comparison.md, 2026-11-25): 0 exact in all four conditions, 0 discordant, p = 1.0
---

# held-v2, a held set with power, and the look-alike test on it

**Why.** held-v1c answered nothing. Its picks had already resisted earlier sessions, so no
condition matched anything, and a factor needs about 6 discordant picks to reach p < 0.05.
held-v2 draws from never-attempted small rows, where Haiku matches often.

**Do.** Freeze held-v2 with tests, reserve it from normal nights, pre-register the look-alike
pair (docs/benchmarks/held-v2-lookalikes.md), run it after the owner approves, land, release.

**Done when.** A dated section in docs/model-comparison.md gives the paired result and the
look-alike decision, the exact picks are landed, and held-v2 is out of reserved.txt.

## Owner rulings (2026-11-25)

| Choice | Ruling |
|---|---|
| Pool | Every never-attempted row under 256 B that the tier queue serves (a member with a member item, or a hub; no held asm row, not on the board; no status.csv row, no attempt record): a census of 274. The first ruling, never-attempted rows under 128 B including closure rows, was refused by the dry run (no night queues closure rows) |
| Count | 274 (34 under 64 B, 118 at 64-127 B, 122 at 128-255 B); the first ruling of 200 (120 + 80) is superseded |
| Seed | 20261125 was ruled for the draw; the census needs none |
| Rows matched after the freeze | Tooling: a reserved list (config/benchmarks/reserved.txt) keeps every night off the set |
| Who may queue reserved picks | Only a `--hold` night whose `--picks` file is the reserved file; a non-hold night over it is refused |
| Factor | Look-alikes only (carry can't be tested on never-attempted rows) |
| Analysed picks | Only the picks with a look-alike at the run commit (147 of 274 at 6e55ae16), listed before the base run; all 274 as description |
| k | 1 |
| Arm | `claude-haiku-5-5`, 8 workers, `--hold` |
| Budget | 2.8%week per run, 5.6% cap for the pair, `--max-sessions 274`; after the reset of Fri 2026-11-27 16:00, on the owner's go and a fresh bar reading |
| After the pair | `--land-held` the exact picks, then release held-v2; effort gets its own pair |

Design: docs/superpowers/specs/2026-11-25-held-v2-design.md.

## Status

- 2026-11-25: designed, rulings taken; reservation tooling, freeze and pre-registration in this
  batch. Runs not launched (waiting for the reset and the owner's go).
