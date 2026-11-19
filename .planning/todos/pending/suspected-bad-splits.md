---
title: Flag functions whose code branches into another row
created: 2026-11-18
area: functions
files: tools/reverseapoc/splits.py
source: literature mining of 2026-11-18 (docs/research/notes-ideas-agentic-projects.md #4)
---

# Flag functions whose code branches into another row

**Why.** 23 agent notes suspect a bad function boundary (a jump into the next row); such a row cannot match as split.

**Do.** A deterministic check over functions.csv: branches whose targets fall in another row; list them as suspected splits for review.

**Done when.** A report lists suspects; one confirmed fix is landed or the list is shown to be noise.

**Effort / value.** S-M / med-high. Evidence and sources: docs/research/notes-ideas-agentic-projects.md #4.

## Status (2026-11-18)

Status (batch 2026-11-18, U15): `reverseapoc mechanics interior` reports 114 UFO2P / 88 TACP suspects, none on a matched row; the proposed functions.csv splits and merges are listed in the merge report. Left: the owner's rulings on those fixes.

## Status (2026-11-19)

Status (batch 261119-bhi, quick 261119-bhq): the supported fix input landed: `config/<exe>/boundary-fixes.csv` (`action,row,at,ruled_on,evidence`; split or merge), applied by `functions --write` right after reconcile, refusing matched rows (docs/toolchain.md, "Function boundaries"). Both files are header only. All 184 unmatched rows of the current `mechanics interior` fixes (110 UFO2P, 74 TACP; 14 of them call-split targets, 62 only on `review` fixes) sit on config/handoff.csv with return rule "boundary fixed". Left: the owner's rulings written into boundary-fixes.csv, functions.csv regenerated in the container, and the board rows of each landed fix deleted (a merged-away start is no row start any more, so the drive would refuse its board row).
