---
spike: 008
idea: night-economics
name: fable-trial-matching
type: comparison
validates: "Given functions Opus left PARTIAL, when a `drive --fable-trial` night runs them on claude-fable-5-1, then its match rate, cost per match and minutes per session beat Opus retries on the same kind of function"
verdict: INVALIDATED
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
- Run 20261101-123417 STOPPED after 11 s, 0 sessions: a thread race in unitdefs.load_configure
  (6 workers loading configure.py at once). Fixed with TDD (8bd0e61 RED, 253dedc GREEN).
- Run 20261101-132005 was killed by a power outage after 9 finished sessions (records committed by
  hand, f26808f). Its 6 in-flight sessions have no record.
- Run 20261101-153646 (`--max-sessions 15`) ENDED: 15 sessions, 0 matched (37c1594). The first
  24-pick queue had spent 3 attempts per function on the 7 larger never-passed partials; after
  they got their pass, the tiny 16-32 byte Opus partials came next.
- Every Fable session ended on the 41-turn cap or the 30-minute clock, at $2-7 each.
- Side finding (cost accounting): a session killed by the 30-minute clock is recorded with cost 0,
  turns 0 and tokens 0, because only the CLI's final `result` event is read. 6 records overall
  (4 Opus, 2+2 Fable). Sessions killed by a stop or a crash get no record at all. A stream
  lower bound (deduplicated per-message usage) is exact for input/cache tokens and never above
  the real cost in 307 checked sessions.
- Side finding (the real blocker): 58 functions have C that reaches 100% under another flag cell
  (`sweep_cells_100`); 55 are PARTIAL (of 102), 52 of them Tier 1 must-match. 49 hit under
  `wcc386@10.6 -4r -oneatx -s -fpi`; the `*` default in config/cflags.txt has no `-o` option.
  Every Fable "partial" probed here that has a hit (func_00090940 98.67%, func_00061F50,
  func_000213A0) is a flags problem, which no model can fix by writing different C.

## Results
**INVALIDATED.** Fable does not beat Opus on functions Opus left PARTIAL.

```
group                            sess    match     rate   $/sess  $/match min/sess
fable on partial                   17        0     0.0%     2.59      n/a     18.4
fable, no prior partial             7        0     0.0%     3.12      n/a     25.7
opus first try                    129       43    33.3%     0.62     1.85      7.6
opus retry after partial          134        0     0.0%     0.89      n/a     13.1
```

Recorded Fable spend is about $66 for 24 sessions; with the 4 zero-cost timeouts (~$8 each) and
the 6 unrecorded sessions of the killed run (lower bound $22.6), the real cost is about $120.
Fable costs about 3-4x an Opus retry per session and matched nothing either.

Signal for the build: keep D-09 as is (Opus first, Fable only at pass 3); do not spend the Fable
bar on the partial backlog. The lever for the PARTIAL backlog is the D-12 flag queue (`flags
propose --from-attempts`, container `flags regate`, owner `flags approve`) and possibly the D-33
default-rule bar, not the model. Fix the timeout cost record before the next cost comparison.
