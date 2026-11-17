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

## Token-based stop for Claude arms (added 2026-11-17)

On 2026-11-16 the owner's weekly bar was shared with another project, so the bar could not say
what a run spent. The coordinator measured the run instead: the records' `cost_usd`
(API-equivalent) at a calibrated $17.73 a point of the week (runs `20261114-opus-sonnet` to
`20261115-claude-push2`: $354.59 moved the bar 20 points), with scratchpad scripts and a manual
Ctrl-C at the target. That belongs here as a meter source: a Claude arm's `%week` budget read
from the run's own `cost_usd` and a dollars-per-point figure kept in quota.toml beside the plan,
re-calibrated whenever the owner sends a before and after reading of a run that had the bar to
itself. The sessions' own `seven_day.utilization` (rate_limit_event) is the whole account's bar:
use it only when nothing else draws on the plan, and read it as about one point of jitter
(the newest transcript can lag another session's reading).
