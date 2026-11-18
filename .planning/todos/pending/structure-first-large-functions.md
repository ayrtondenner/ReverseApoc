---
title: Structure first for functions of 256 B and up
created: 2026-11-18
source: literature mining of 2026-11-18 (docs/research/notes-ideas-llm-decomp-research.md #1)
---

# Structure first for functions of 256 B and up

**Why.** Under 1% of attempts at 256 B and up match, nothing at 1 KB or more; length mismatches dominate. HELIOS, SK2Decompile and Decomperson recover control flow before details.

**Do.** A control-flow outline (blocks, branches, loops, switch tables) in the pack for large rows, and block/branch/length counts ours-vs-original in every check.

**Done when.** A held A/B at 256-1023 B against the current pack.

**Effort / value.** M / high. Evidence and sources: docs/research/notes-ideas-llm-decomp-research.md #1.
