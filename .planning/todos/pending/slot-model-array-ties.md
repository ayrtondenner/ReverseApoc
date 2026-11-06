---
title: Slot model and search fixes from Phase 7.1's phase review
created: 2026-11-06
source: 07.1-REVIEW.md, the phase-end review; plan 07.1-06 writes no Python, so these stayed open
---

# Slot model and search fixes from Phase 7.1's phase review

Plan 07.1-07 built and closed CR-01, WR-01, WR-03, WR-04 and IN-04. This is what the owner's ruling 3 left. Each finding is deferred in `07.1-REVIEW-DISPOSITION.md`, and none can land a wrong match, because `check` and the gate are untouched. The review holds the detail and suggested fixes.

**The findings left, by file:**
- `search.py`: WR-02 (three declaration forms leave `_readable` true on an incomplete frame).
- `lift.py`: IN-01, IN-02, IN-03.

**How the lifter declares slots.** `lift.py:649` sorts on M2 for array slots, and it declares address-taken slots as `char` arrays. A change there needs its own measurement.

**Frames past the measured boundary.** Two arrays beside three or more scalars and one array beside four or more are not measured, and the model calls them known.

**A skill's wording.** `.claude/skills/watcom-readability/SKILL.md:41` says the order of declarations decides the stack slots. Correct it later through `writing-skills`, RED first.

**How to measure it.** Use the Phase 7.1 curve gate, `.planning/phases/07.1-matching-tooling/measure_curve.py`, with the matched-row control over the exact rows.
