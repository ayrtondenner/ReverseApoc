---
title: Structure first for functions of 256 B and up
created: 2026-11-18
area: context-pack
files: tools/reverseapoc/contextpack.py, tools/reverseapoc/attempt.py
source: literature mining of 2026-11-18 (docs/research/notes-ideas-llm-decomp-research.md #1)
---

# Structure first for functions of 256 B and up

**Why.** Under 1% of attempts at 256 B and up match, nothing at 1 KB or more; length mismatches dominate. HELIOS, SK2Decompile and Decomperson recover control flow before details.

**Do.** A control-flow outline (blocks, branches, loops, switch tables) in the pack for large rows, and block/branch/length counts ours-vs-original in every check.

**Done when.** A held A/B at 256-1023 B against the current pack.

**Effort / value.** M / high. Evidence and sources: docs/research/notes-ideas-llm-decomp-research.md #1.

## Status (2026-11-18)

Status (batch 2026-11-18, U10): control-flow outline and the check's shape line are built; skill text 9443f1c7. Left: the held A/B at 256-1023 B (first used by the 256 B night).
