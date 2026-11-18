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
