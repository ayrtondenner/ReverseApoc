---
spike: 008
idea: night-economics
name: fable-trial-matching
type: comparison
validates: "Given functions Opus left PARTIAL, when a `drive --fable-trial` night runs them on claude-fable-5-1, then its match rate, cost per match and minutes per session beat Opus retries on the same kind of function"
verdict: PENDING
related: [009]
tags: [fable, opus, d-09, cost, drive, fable-trial]
---

# Spike 008: Fable trial on Opus-PARTIAL functions

## What This Validates
Given functions Opus left PARTIAL, when a `drive --fable-trial` night runs them on Fable, then
Fable's match rate, cost per match and minutes per session beat Opus retries on the same kind of
function. Owner-authorized (2026-11-01): the orchestrator runs the real night.

## How to Run
```
uv run reverseapoc drive --fable-trial --dry-run --max-sessions 24
uv run reverseapoc drive --fable-trial --workers 6 --max-sessions 24 --fable-budget-usd 12.50
uv run python .planning/spikes/008-fable-trial-matching/compare.py <run id>
```

## What to Expect
One row per group (Opus first try, Opus retry after partial, Fable on partial): sessions,
matches, rate, $/session, $/match, minutes/session. The owner adds the weekly and Fable usage
bars before and after.

## Investigation Trail
- Baseline before the trial (nights 2-4, schema 2 matching records): Opus first tries 129
  sessions, 43 matched (33.3%), $0.62/session, $1.85/match, 7.6 min. Opus retries after a PARTIAL:
  134 sessions, 0 matched, $0.89/session, 13.1 min. Opus has never matched a function after its
  first PARTIAL.

## Results
PENDING
