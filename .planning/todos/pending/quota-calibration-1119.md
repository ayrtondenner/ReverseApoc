---
title: Re-measure quota per session for Fable 5.1 and for Terra at 256 B and up
created: 2026-11-20
area: driver
files: config/driver/quota.toml, docs/model-routing.md
source: drives of 2026-11-19 (20261119-claude, 20261119-fable, the 3s A/B, 20261119-quota*)
---

# The budgets under-count two arms

**Why.**
- Fable 5.1: the owner's bar went 37% to 45% while run 20261119-fable spent about $60 API-equivalent
  (about 3.4 points at quota.toml's $17.73 a point); the run's 31 sessions spent $118.06 in all. So the
  bar moved about 2.3 times the cost meter's figure, and a `--arm-budget claude-fable-5-1=N%week`
  overshoots.
- GPT-6.1 Terra: quota.toml says 0.25% of the week a session; at 256 B and up it was 0.41%
  (docs/model-comparison.md 2026-11-18/19), and a 5-hour window held only about 40 minutes of the
  2026-11-20 sessions.
- Opus/Sonnet: run 20261119-claude (62 sessions, $34.55) moved the bar about 3 points with the
  orchestrator's own use included.

**Do.** Re-measure from owner meter readings taken before and after a single-arm run (no other Claude
use in between), update quota.toml's entries with source and date, and say in docs/model-routing.md
"Quota per session" which bars the cost meter tracks.

**Done when.** quota.toml's Fable, Terra (by size) and Opus/Sonnet figures match a measured run.

## Attempt of 2026-11-20 (run 20261120-quota): no clean reading

- Bars (S): weekly 53%, Fable 27% at 15:13 (the prompt's 15% Fable was a stale panel figure). The
  week reset at 16:00 before a closing reading, and the owner read 0% / 0% at about 16:10.
- Fable 5.1: 10 sessions, $41.49 recorded (T), $4.15 a session (2.9-7.5); the 2026-11-19 run's
  31 sessions were $3.81 each.
- Orchestrator and up to 11 Claude Code agents ran in the same window, so even with a closing
  reading this run would not isolate an arm.
- Next try: read both bars right before and right after a single-arm Claude run with no agents
  working, and well before the Friday 16:00 reset.

## Readings of 2026-11-21 to 2026-11-23

- Claude, run 20261121-mix (one drive, Fable 5.1 near-miss 8 + Opus 5.5 near-miss 4 + Codex arms;
  11:02-15:27 on 2026-11-21): weekly bar 6% (10:56), 8% (11:30), 13% (~12:16), 18% (13:10), 35%
  at the stop; Fable bar 0%, 0%, 12%, 22%, 53% (S). 59 Fable and 46 Opus sessions, $277.46
  recorded (T): about $9.6 recorded cost per weekly point and 0.9 Fable-bar points per Fable
  session (derived; this session's own use falls in the same window, so both are upper bounds).
- Codex (S, owner screenshots; sessions from the records, T):
  - run 20261120-codex2: weekly 84% -> 37% left over 68 sessions, about 0.7 points a session;
  - run 20261121-mix, Codex arms: 37% -> 21% left over 21 sessions, about 0.8 a session;
  - run 20261123-codex, first window (12:36-13:33): 84% -> 69% left over 28 sessions, about 0.5 a
    session; a 5-hour window held about 50 minutes of 8 workers.
- These supersede the guesses above for sizing; update config/driver/quota.toml from them when
  the todo is worked.
