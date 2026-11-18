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
