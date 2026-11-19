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
