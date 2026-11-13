---
title: Progress-over-days chart with a daily log on the progress page
created: 2026-11-13
source: owner, during run 20261113-cascade3
---

# Which actions moved progress, day by day

On https://ayrtondenner.github.io/ReverseApoc/ (built by `tools/reverseapoc/progress.py`,
published by pages.yml), add a chart of matched-code percentage against days since the
project's first day, one line per EXE (UFO2P.EXE, TACP.EXE; a later EXE such as XCOMAPOC.EXE
gets its own line starting on the day work on it began), plus a per-day summary of what was done.

**Why (owner):** proof of which actions raised progress the most and which had no effect at all
(a tooling phase, a flags landing, a model or routing change, a night of a given arm).

**Data, all from the repo (deterministic, no hand entry):**
- Per EXE per day: the matched bytes and percentage at the end of that day, recomputed from the
  git history of `config/<exe>/status.csv` (the same figure the page shows today), so past days
  are back-filled from history.
- Per day: what happened, from the commits of that day (matches with their `Matched-By` and
  `Co-Authored-By` trailers, flags approvals, tooling/plan commits), the drive runs of that day
  (`progress/attempts.jsonl` run records: arms, sessions, matched) and the dated
  docs/learnings.md entries. A short generated summary per day, plus the delta it caused.
- Mark each point with its biggest driver (for example "flags F-0069..F-0071", "cascade night,
  Haiku 4", "Phase 7.1 converter") so a flat stretch and a jump are both explained.

**Build (test-first, Python tooling rules):** the history walk and per-day aggregation as a
pure function over git log + the CSVs, tested on a synthetic repo; the chart as inline SVG in the
generated page (no third-party JS unless recorded in docs/tools.md), phone-legible (backlog
999.4's lessons), with a text table of the same data for accessibility.
