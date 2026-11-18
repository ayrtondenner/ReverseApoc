---
title: Retire long-tail functions from agent queues onto a hand-off board
created: 2026-11-18
area: picking
files: tools/reverseapoc/picker.py, config/handoff.csv, tools/progress.py
source: literature mining of 2026-11-18 (docs/research/notes-ideas-agentic-projects.md #3)
---

# Retire long-tail functions from agent queues onto a hand-off board

**Why.** 180 functions tried by 3 or more models took 1,963 of 4,070 sessions (48%, measured 2026-11-18); 65 of them sit at 90% or more. Agent sessions keep returning to them.

**Do.** A committed board (e.g. config/handoff.csv) of functions retired from agent queues after N models fail, with their best percent and notes, for the owner or a human contributor.

**Done when.** The picker skips board rows; the progress page lists the board; a rule says when a row returns.

**Effort / value.** S-M / high. Evidence and sources: docs/research/notes-ideas-agentic-projects.md #3.
