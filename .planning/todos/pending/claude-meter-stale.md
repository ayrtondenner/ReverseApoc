---
title: The Claude bar reading from ~/.claude.json goes stale across the weekly reset
created: 2026-11-23
area: meters
files: tools/reverseapoc/meters.py, docs/model-routing.md
source: 2026-11-21 quota run (owner's panel 6% while the cache read 53%)
---

# Last week's number

**Why.** `reverseapoc meters` reads the Claude bars from `~/.claude.json`
`cachedUsageUtilization`, which refreshes only when the usage panel fetches. On 2026-11-21 at 11:02
the cache still read 53% (last week's figure) while the owner's panel read 6% after the Friday
reset; a scratchpad watcher on the cache stopped at once on the stale value. Budget-sized drives
(`--arm-budget ...%week`) read the same meter.

**Do.** Test first: when the cached figure's `as_of` is before the bar's last reset (the reset time
is in the cache or derivable from the plan's weekly reset), report the reading as stale (no
figure, or flagged), and make budget sizing refuse a stale reading instead of using it.

**Done when.** A cache older than the last reset is reported stale by `meters`, a budgeted drive
does not size from it, and a test pins both.
