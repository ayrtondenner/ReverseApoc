---
title: Slot model and search fixes from Phase 7.1's phase review
created: 2026-11-06
source: 07.1-REVIEW.md, the phase-end review; plan 07.1-06 writes no Python, so these stayed open
---

# Slot model and search fixes from Phase 7.1's phase review

Plan 07.1-07 built and closed CR-01, WR-01, WR-03, WR-04 and IN-04. This is what the owner's ruling 3 left. The review holds the detail and suggested fixes, and none of these could land a wrong match, because `check` and the gate are untouched.

**The findings, closed.** Quick task 261107-qke closed `search.py` WR-02 and `lift.py` IN-01, IN-02 and IN-03, test first, with the commits in its SUMMARY. `07.1-REVIEW-DISPOSITION.md` still reads deferred, because Phase 7.1's files stay closed.

**How the lifter declares slots.** `lift.py:649` sorts on M2 for array slots, and it declares address-taken slots as `char` arrays. A change there needs its own measurement.

**Frames past the sweep.** `build/gate/07.1-evidence/07-verify-review.py` swept 260 frames in both cells, and none it calls known is placed wrongly. It covers `char[4]` and `short[2]` beside up to nine and five ints, and one array across up to four blocks. Past that the model still calls some frames known unmeasured, such as a `char[4]` beside other multi-element shapes. The refusal is wider than the compiler's line on the safe side, and narrowing it needs its own measurement.

**A skill's wording.** `.claude/skills/watcom-readability/SKILL.md:41` says the order of declarations decides the stack slots. Correct it later through `writing-skills`, RED first.

**How to measure it.** Use the Phase 7.1 curve gate, `.planning/phases/07.1-matching-tooling/measure_curve.py`, with the matched-row control over the exact rows.
