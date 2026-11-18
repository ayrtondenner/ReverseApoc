---
title: Infer struct shapes once and share them across functions
created: 2026-11-18
area: context-pack
files: tools/reverseapoc/contextpack.py
source: literature mining of 2026-11-18 (docs/research/notes-ideas-llm-decomp-research.md #7)
---

# Infer struct shapes once and share them across functions

**Why.** Each session re-guesses struct layouts; the fidelity taxonomy and Idioms/ReCopilot recover types across functions.

**Do.** Collect field offsets and widths per base pointer across matched functions into shared struct headers, used by packs and readability sessions.

**Done when.** A generated header set; a held A/B on functions that touch those structs.

**Effort / value.** L / high. Evidence and sources: docs/research/notes-ideas-llm-decomp-research.md #7.
