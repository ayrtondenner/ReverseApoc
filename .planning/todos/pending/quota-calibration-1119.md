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
