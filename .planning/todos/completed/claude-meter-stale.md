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

## Resolution (2026-11-23)

Owner ruling (2026-11-23). Question: how should meters report a cache whose reading predates the
last reset? Options: withhold the figure, or keep the figure and flag it. Chosen: withhold.

- meters: `_claude_limit` compares each bar's `resets_at` with the read time. A bar whose reset
  is already past was cached before that reset, so its `used` and `remaining` are None and the
  new `Reading.stale` is true; `limit`, `resets_at` and `as_of` stay. The text report prints
  `stale (read <as_of>, reset <resets_at>)` and no figure; `--json` gives `"used": null,
  "remaining": null, "stale": true`. A bar whose reset is ahead is unchanged. The only consumer
  of these readings is the `meters` verb (cli.py), which prints both forms.
- Budget sizing never read these bars, so the "make budget sizing refuse a stale reading" half
  needs no change: `refuse_budgets` sizes from quota.toml's `week_percent`, and the mid-night
  `budget_meter` sums the arm's recorded `cost_usd` over `usd_per_week_point`.
- docs/model-routing.md "Reading the meters" says so.
- Tests: tests/test_meters.py (`test_claude_code_withholds_a_bar_that_reset_since_the_cache`,
  `test_claude_code_keeps_a_bar_whose_reset_is_ahead`,
  `test_the_verb_prints_a_withheld_bar_as_json_null`; `test_reading_json_holds_every_field`
  now lists `stale`).
