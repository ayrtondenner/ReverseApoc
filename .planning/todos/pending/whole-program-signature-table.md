---
title: A whole-program signature table before matching
created: 2026-11-18
area: context-pack
files: tools/reverseapoc/contextpack.py, tools/reverseapoc/callgraph.py
source: literature mining of 2026-11-18 (docs/research/notes-ideas-llm-decomp-research.md #9)
---

# A whole-program signature table before matching

**Why.** Decomperson's participants stub every function's signature first; ours are inferred per session.

**Do.** A table of each function's arguments, returns and calling convention from callers and callees, used in packs and headers.

**Done when.** Generated table; packs include the callee signatures.

**Effort / value.** M / medium. Evidence and sources: docs/research/notes-ideas-llm-decomp-research.md #9.
