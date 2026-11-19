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

## Status (2026-11-18)

Status (batch 2026-11-18, U4 + U8): config/handoff.csv, the picker skip and the page listing are built. Left: the owner's retirement threshold N and the first rows.

## Resolution (2026-11-19)

- Owner rule (2026-11-19): retire a function at >= 24 attempts when its best percent did not rise
  over its last 9 attempts (3 passes); it returns when the owner writes a hint for it in
  config/hints/<exe>.toml or when tooling for its failure class lands (config/handoff-tooling.toml).
- `reverseapoc handoff --dry-run|--write [--json]` (quick 261119-bhn, merged 3800328e); docs/workflow.md.
- First write (ab5173a9), after the owner saw the dry run: 8 long-tail rows; the owner kept the two
  99%+ rows (ufo2p 0x000A5A50 at 99.89%, tacp 0x00087090 at 99.31%) in the queues, so each later
  dry run proposes them again until the owner says otherwise.
- The board also holds the suspected-bad-split rows (todo suspected-bad-splits).
