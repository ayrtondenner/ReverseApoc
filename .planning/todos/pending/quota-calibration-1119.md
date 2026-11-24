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

## Applied 2026-11-23

- config/driver/quota.toml, Codex (plan chatgpt-plus, still `no_meter`): gpt-6.1-terra,
  gpt-6.1-sol, gpt-6-luna and gpt-6-astra each take five_hour_percent 3.6 and week_percent
  0.67, read 2026-11-23, source marked mixed-arm, not isolated (78 week points over 117
  sessions of the readings above; about 28 sessions to one 5-hour window). Sol, Luna and Astra
  are new entries, with no measured match rate. Terra was 1.35 / 0.25; its isolated figures of
  2026-11-16 stay in a comment, and it alone keeps `credits = 2.3` (the only measured credits)
  and its match rate (18 of 978).
- Claude: `[plans."claude-ultra"] usd_per_week_point` 17.73 to 9.6, from run 20261121-mix
  ($277.46 recorded for 29 points). The orchestrator's own use fell in the same window, so 9.6
  is a lower bound and the cost meter errs early. The per-arm Claude week_percent figures are
  unchanged, with a comment saying why.
- docs/model-routing.md "Quota per session" and the drive-budget skill's example
  (`--max-sessions` 674 to 627: Terra's 100%5h now buys 27 sessions, not 74) follow; the tests
  that pinned the old figures carry the new ones.

Still open: the Claude per-arm figures (Fable, Opus, Sonnet, Haiku) need a single-arm Claude run
with no agents working, both bars read right before and right after, well away from the Friday
reset. Terra by size (0.41% of the week at 256 B and up) is not split out either: the Codex
figure is one mixed-arm average.

## Reading of 2026-11-24

- Codex (S, owner paste at 11:16): 5-hour window 96% used (resets in 4 h 20 min), week 94% used,
  so 6% left (resets in 4 d 12 h). Against 69% left at ~13:45 on 2026-11-23 that is 63 points.
  Sessions since then, from the records (T): 24 of run 20261123-codex after 13:33, 21 of
  20261124-codex, and 41 of 20261124-codex2 by 11:15. That is 86, or about 0.73 points a session
  (derived, mixed arms, interactive use inside). It agrees with the 0.67 set on 2026-11-23, so
  quota.toml stays as it is.
