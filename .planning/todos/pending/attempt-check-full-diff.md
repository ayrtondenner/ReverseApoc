---
title: Show the whole aligned diff and the failure class in attempt check
created: 2026-11-18
area: attempt-check
files: tools/reverseapoc/attempt.py, tools/reverseapoc/classify.py, tools/reverseapoc/hooks.py
source: literature mining of 2026-11-18 (docs/research/notes-ideas-agentic-projects.md #1, #8; docs/research/notes-ideas-llm-decomp-research.md #2)
---

# Show the whole aligned diff and the failure class in attempt check

**Why.** `attempt check` shows only a short window around the first differing instruction (attempt.py `_window_lines`), and the failure class `classify.py` computes never reaches the agent. Agents keep asking for more: 181 notes.md files request a fuller diff (agentic-projects #1). Echo and SymDec use the whole difference set as the repair signal.

**Do.** Add `attempt diff` (or a `--full` view of check): every differing run aligned ours/original, each with its mismatch class (length, register, order, relocation), plus the classify verdict in check's own output. Keep it bounded for context-pack size limits.

**Done when.** A test check on a two-run mismatch prints both runs and their classes; the skill names the command; a held A/B shows whether it raises the match rate at 64-255 B.

**Effort / value.** M / high. Evidence and sources: docs/research/notes-ideas-agentic-projects.md #1, #8; docs/research/notes-ideas-llm-decomp-research.md #2.

## Status (2026-11-18)

Status (batch 2026-11-18, U6, merge a326861d): `attempt diff`, the class line and the skill text (9443f1c7) are in. Left: the held A/B at 64-255 B.
