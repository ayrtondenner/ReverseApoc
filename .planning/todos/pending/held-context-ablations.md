---
title: Measure what the context pack's parts are worth on held picks
created: 2026-11-18
area: evaluation
files: tools/reverseapoc/contextpack.py, docs/model-comparison.md
source: literature mining of 2026-11-18 (docs/research/notes-ideas-llm-decomp-research.md #4; docs/research/notes-ideas-agentic-projects.md #10, #11)
---

# Measure what the context pack's parts are worth on held picks

**Why.** Three context choices were never measured: look-alike retrieval, carrying the earlier best C and give-ups (help or anchoring?), and reasoning effort (drives always pass null). FidelityGPT and Idioms report retrieval gains on other tasks.

**Do.** One held run per factor on frozen picks (`--hold --picks`), the factor on and off, same arm; label carried claims by the model that made them.

**Done when.** A dated section in docs/model-comparison.md per factor, with the paired result and a keep/drop decision in the pack.

**Effort / value.** M / high. Evidence and sources: docs/research/notes-ideas-llm-decomp-research.md #4; docs/research/notes-ideas-agentic-projects.md #10, #11.

## Owner rulings and status (2026-11-24, unit K)

Rulings: the ablations are the held benchmark's pre-registered comparisons, on Haiku 5.5
(`claude-haiku-5-5`), k = 2 repeats, Wilson intervals and exact McNemar per factor, about 6.6%
of the weekly Claude bar for this design. Factors, each on and off: look-alike retrieval,
carrying the earlier best C, give-ups and notes, and reasoning effort.

Built (TDD): `drive --pack-variant NAME`, repeatable. `no-lookalikes` makes the pack's
look-alikes none and loads no other EXE. `no-carry` leaves out the earlier notes, records,
give-ups and best C. `effort-LEVEL` (low, medium, high, xhigh, max) adds `claude --effort LEVEL`
and puts the level in the attempt record's `effort`. It is refused on an arm that is not a
claude-harness arm on the Claude login. The variants reach the launch pack and, through the
session's `REVERSEAPOC_PACK_VARIANTS`, the wrapper's `attempt context` (in its cache key too).
They are recorded, sorted, in the STARTED record's `environment.variants`, so the environment
digest tells the runs apart, and `stats --run` names them on each run's environment line.
The cli refuses a variant named twice, two efforts, and a variant with --canary, --land-held
or --session readability. With no variant, the argv, session env,
pack and digest are unchanged (pinned). Effort finding: Claude Code 2.1.311 has `--effort
<low|medium|high|xhigh|max>`, and Haiku 5.5 takes every level (API default medium), so the
effort factor runs on Haiku: high against the CLI default. Not built: `--pack-variant
no-full-diff` (todo attempt-check-full-diff, no ruling for it yet). The dry run's pack sizes
still show the full pack.

Pre-registration: `docs/benchmarks/held-v1b-ablations.md`, on config/benchmarks/held-v1b.txt.
It has 4 conditions (base, lookalike-off, carry-off, effort-on) x 2 repeats = 8 hold runs of 56
picks, 448 sessions, about 4.5% of the week, with budgets capped at 5.6%. Left: the runs, then
one dated section per factor in docs/model-comparison.md with the keep or drop decision.
