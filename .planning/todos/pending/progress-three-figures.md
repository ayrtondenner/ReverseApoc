---
title: Progress shows three figures - strict bytes, functions and fuzzy - in badges, README and progress.json
created: 2026-11-13
source: owner Q&A on the low byte percent (main session, 2026-11-13)
---

# Show more than one progress number

The badges and the README headline show only the strict byte percent (0.81% combined on
2026-11-13). That figure gives no credit to partial rows and is weighted towards the large
functions not yet attempted, so it reads as "nothing is happening" while 180 functions are
matched. Other decomp projects show several figures next to each other.

What exists today:
- strict bytes: progress.json `percent`, the three shields, the page, report.json
  `matched_code_percent`;
- function ratio: progress.json `functions`, the page's per-EXE line ("93 of 1,412 functions
  matched"), DecompHub's `*-functions` tracks; no badge;
- fuzzy: only report.json `fuzzy_match_percent` (5.4445% combined), computed in
  `tools/progress.py`'s report section from status.csv best_percent; not in progress.json, the
  page or any badge.

Do (test first, in `tools/progress.py`, stdlib-only, same determinism rules as today):
- add `functions_percent` (matched over total game and thunk functions) and `fuzzy_percent`
  (size-weighted best_percent, the same number report.json carries) to progress.json per EXE and
  combined, derived once and reused by report.json so the two cannot disagree;
- the page's headline per EXE shows all three, each with a one-line definition (strict:
  byte-identical functions only; functions: count, not size; fuzzy: objdiff's closeness, partial
  credit);
- shields: keep the existing endpoints and their message unchanged (consumers depend on them);
  add `progress-shield-functions*.json` and `progress-shield-fuzzy*.json`, or ask the owner
  whether to put "0.81% · 6.4% fn" in one badge instead;
- README: the badge row and the paragraph that defines the percent name all three; the strict
  percent stays the headline (it is the only one proven by byte comparison);
- leave `decomphub.progress.json` and `.recomp.json` as they are unless the owner asks.

Done when tests and ruff pass in the container, two runs over the same CSVs give the same bytes,
and the page shows the three figures for both EXEs.
