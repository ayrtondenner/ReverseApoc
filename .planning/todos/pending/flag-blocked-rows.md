---
title: Repair the flag-blocked rows that reach 100% only under another rule
created: 2026-11-14
source: near-miss lane review (main session, 2026-11-14)
---

# Seven partial rows at best 100.00% that no proposal can land

Each reaches objdiff 100% only under a non-default rule (`needs flags ...`), and the near-miss lane
leaves them out (picker: best_percent in [minimum, 100)). No proposal for them passed its re-gate,
so `flags approve` cannot land them:

| Row(s) | Proposal | Re-gate failure | Repair |
|---|---|---|---|
| ufo2p func_000520A0, func_000520C0 | F-0028 | candidate C does not compile in the unit (undeclared D_000E12F0, ...) | a candidate with the unit's declarations, then `flags regate` |
| ufo2p func_0005DB80 | F-0029 | compile errors (unk_016A field, undeclared D_00128616) | the same |
| ufo2p func_0008A0C0 | F-0037 | the rule breaks 5 sibling functions in u_00089980 (75%, reloc) | decide how one unit holds functions built under different rules (split the unit?) |
| ufo2p func_000B4B80 | F-0072 | `-5r` breaks matched func_000B4470 in u_000b4470 (92%) | the same |
| tacp func_00088450, func_000AB650 | none | never proposed | `flags propose` from their sweep hits, then regate |

The owner approves landings (`flags approve`); this todo is the work that makes them approvable.
