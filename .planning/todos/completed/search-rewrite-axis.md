---
title: Echo-style branch, loop and expression rewrites as a search axis
created: 2026-11-18
area: search
files: tools/reverseapoc/search.py
source: literature mining of 2026-11-18 (docs/research/notes-ideas-llm-decomp-research.md #8)
---

# Echo-style branch, loop and expression rewrites as a search axis

**Why.** The slot class held none of the 841 unmatched rows examined; Echo rewrites control flow and expressions while keeping semantics.

**Do.** Add rewrite operators (loop form, branch inversion, expression reassociation) to `search` for near misses, under the same gate.

**Done when.** search reports matches found by rewrites on the near-miss set, or a documented null result.

**Effort / value.** M / medium. Evidence and sources: docs/research/notes-ideas-llm-decomp-research.md #8.

## Resolution (2026-11-18)

Done in batch 2026-11-18 (U12, merge 54e59508): the rewrite axis is built; documented null result on 5 near-miss rows (docs/learnings.md 2026-11-18). The full near-miss measurement remains open in the curve gate.
