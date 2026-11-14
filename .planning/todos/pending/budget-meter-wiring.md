---
title: Wire the drive's meter seam to reverseapoc meters, once a meter reads live
created: 2026-11-13
source: batch of 2026-11-13 (units 5 and 6), coordinator's merge note
---

# Wire `Deps.meter` to `meters.read_all()`

`drive --arm-budget` caps an arm by session count, and between launches asks `Deps.meter`
(default: no reading) whether the budget is spent. `reverseapoc meters` exists, but on
2026-11-13 none of its sources moves during a night:
- Claude Code: `~/.claude.json` `cachedUsageUtilization` refreshes only when the usage panel is
  fetched (interactive CLI), not during `claude -p` sessions;
- Codex: drive sessions are `--ephemeral`, so the rollout's rate limits date from the last
  interactive session;
- Copilot: drive sessions run under their own COPILOT_HOME (build/), so `~/.copilot`'s
  `session-state` never sees them; sum the per-session `--usage-output-file` credits instead;
- OpenRouter: live (credits API), the one source that would work today.

Do (test first): map each plan in quota.toml to its meter reading (source, meter name, unit
`%week`/`%5h`/`$`/`credits`), wire `default_seams(...).meter`, and give Copilot a reading from
the night's own usage files. Skip a source that cannot move during a night.
