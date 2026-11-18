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
