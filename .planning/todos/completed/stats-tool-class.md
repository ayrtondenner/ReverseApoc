---
title: Class twin and lift landings as tool-written in stats and on the progress page
created: 2026-11-19
area: stats
files: tools/reverseapoc/stats.py, tools/progress.py, tools/reverseapoc/twins.py, tests/test_stats.py
source: coordinator, after the 2026-11-18/19 drives (59 twin landings)
---

# A "tool" class for matches no person and no session wrote

`stats.classify` (tools/reverseapoc/stats.py) has three classes: `unattended` and `human-hints`
need the driver's `Matched-By: reverseapoc drive`, and everything else is `human-written`. The
progress page (tools/progress.py, `MATCHED_BY_TOOL` and the class rule beside it) does the same.
So the 59 twin landings of 2026-11-18 (`Matched-By: reverseapoc twins`, twins.py `MATCHED_BY`)
count as human-written: `stats` reports 106 human-written of 295 matched, though no person wrote
their C. Landings by `reverseapoc lift` (the converter; flags.py `AUTHORS`) are classed the same
way.

Do, test first:
- add a `tool` class to `stats.CLASSES`, keyed on `Matched-By: reverseapoc twins` or
  `Matched-By: reverseapoc lift` (without the driver's trailer);
- give the progress page the same class, with its legend text;
- keep `--min-unattended` (AGT-11) counting only `unattended`;
- check how a `Flags-Approved-By:` trailer combines with the new class.

## Resolution (2026-11-19)

Quick 261119-bhj (batch 261119-bhi). RED `36a18463`, GREEN `155b4874`.

- `stats.CLASSES` and `progress.PROVENANCE_CLASSES` are `unattended, human-hints, tool,
  human-written`. `tool`: no driver `Matched-By` but a `Matched-By` of exactly
  `reverseapoc twins` (twins.MATCHED_BY) or `reverseapoc lift`. The driver's trailer wins
  (unattended or human-hints); `claude subagent (spike 011)` and `reverseapoc search` alone stay
  human-written (the ruling names twins and lift only).
- `Flags-Approved-By:` stays orthogonal: the event keeps its `flags_approved`; stats' top-level
  `flags_approved` stays the unattended subset (R4); the page shows `tool, under approved flags`.
- `--min-unattended` counts unattended only (tests/test_stats.py
  test_min_unattended_does_not_count_tool_matches).
- Measured (stats text and --json at fccbab48, and an independent per-commit `git diff` walk
  classed by stats.classify at fccbab48, 8349c97b and ea7d2a60^): at fccbab48 and at 8349c97b,
  295 matched (141 UFO2P + 154 TACP, status.csv agrees) = 189 unattended (32 flag-approved) +
  0 human-hints + 99 tool + 7 human-written, none unclassed. The 187/99/7 split of the
  expectation holds at ea7d2a60^ (293): the two Sol matches ea7d2a60 and 4c4de2db are ancestors
  of 8349c97b, and HEAD adds none after it. The 99 tool: 59 twins, 40 lift (11 under approved
  flags; 23 in b21bf435, which names both `reverseapoc lift` and `claude subagent (spike 011)`
  and is tool because it names lift). The 7 human-written: the 5 spike-011 flag landings of
  2026-11-03 and the 2 Phase 5 seeds of 58eba4d.
