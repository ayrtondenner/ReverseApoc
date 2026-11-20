---
title: Set the per-attempt check budget and session caps from our own records
created: 2026-11-18
area: stats
files: tools/reverseapoc/stats.py, tools/reverseapoc/attempt.py, docs/model-routing.md
source: literature mining of 2026-11-18 (docs/research/notes-ideas-agentic-projects.md #7; docs/research/notes-ideas-tooling-reproducibility.md #8; docs/research/notes-ideas-llm-decomp-research.md #3)
---

# Set the per-attempt check budget and session caps from our own records

**Why.** Measured from attempts.jsonl (2026-11-18): 64% of matched attempts matched on the first check, p95 at check 6, none after check 10; sessions with 11-25 checks used 8% of tokens for 2 matches. Re-measure before acting.

**Do.** Add attempt-to-match curves per size bucket to `stats`, then set CHECK_BUDGET and per-bucket caps from them; record stages reached and exit reasons per attempt (Reveree-style diagnostics).

**Done when.** `stats` prints the curves; the new budget is justified in docs/model-routing.md with the numbers.

**Effort / value.** S / med. Evidence and sources: docs/research/notes-ideas-agentic-projects.md #7; docs/research/notes-ideas-tooling-reproducibility.md #8; docs/research/notes-ideas-llm-decomp-research.md #3.

## Status (2026-11-18)

Status (batch 2026-11-18, U7): `stats` prints check curves; docs/model-routing.md 'The check budget' argues for 15. Left: the owner's ruling (D-07) to change CHECK_BUDGET and MAX_CHECK_RUNS from 25 to 15 (change set in that paragraph).

## Status (2026-11-20)

- Done: the owner ruled 15 on 2026-11-18, and `attempt.CHECK_BUDGET` and
  `session.MAX_CHECK_RUNS` are 15. Per-bucket caps: none. The buckets' latest exact checks
  (10, 11, 13) are too close, as docs/model-routing.md says.
- Re-measured 2026-11-20 over the committed log (4,335 matching sessions, 192 exact). The
  latest exact is still check 13, so 15 holds. The figures are in docs/model-routing.md "The
  check budget".
- New: `stats` prints "exit reasons and stages reached per size bucket" (JSON key `funnel`).
  The stages are checked, compiled, 80+, 95+ and exact. The exits are exact, abort (reason),
  gave up (category) and partial under or at CHECK_BUDGET checks. It reads only fields the
  attempt record already has. Tests: tests/test_stats.py
  `test_funnel_stages_and_exits_per_bucket` and `test_funnel_text`. Result: the budget ends
  3.2% of sessions. 75.7% end on their own under it, 11.0% give up and 5.8% abort.
- Open: the rest of "record stages reached ... per attempt". The record cannot give the plan
  accepted, the sweep ran (only `sweep_hit`), the index of the best check, regressions (a
  check below the best so far) or repeated C per attempt. Those live only in the gitignored
  per-attempt files under build/driver/ (checks.jsonl, checks/NNNN.json, plan.json).

### Owner question (2026-11-20): record the missing funnel stages, or stop here?

- **A. Stop here and close the todo.** The ledger funnel answers what this todo was for: the
  budget, and where sessions fall away per bucket. The missing stages can come back as a new
  todo when a question needs them.
- **B. Put them in the attempt record (schema 4).** The driver writes `plan_accepted`,
  `sweep_ran`, `best_check`, `regressions` and `repeats` into each record. This is a schema
  change, like D-16 and D-26: driver writing, validation, the v3 and v4 readers, and tests.
  Effort M. The figures exist only for sessions after the change.
- **C. `stats --run` reads them from build/driver/** the way `per_try` already reads
  checks.jsonl. No schema change, but it works only on the machine that ran the drive and
  only while build/driver is kept. Effort S to M.

Recommendation: **A**. "Done when" is met. Reveree's main question was budget exhaustion
against giving up, and our records answer it. B costs a schema version for figures no
decision is waiting on now.
