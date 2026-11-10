---
title: Slot model and search fixes from Phase 7.1's phase review
created: 2026-11-06
source: 07.1-REVIEW.md, the phase-end review; plan 07.1-06 writes no Python, so these stayed open
updated: 2026-11-10 by plan 07.2-14
---

# Slot model and search fixes from Phase 7.1's phase review

Plan 07.1-07 built and closed CR-01, WR-01, WR-03, WR-04 and IN-04. This is what the owner's ruling 3 left. The review holds the detail and suggested fixes, and none of these could land a wrong match, because `check` and the gate are untouched.

**The findings, closed.** Quick task 261107-qke closed `search.py` WR-02 and `lift.py` IN-01, IN-02 and IN-03, test first, with the commits in its SUMMARY. `07.1-REVIEW-DISPOSITION.md` still reads deferred, because Phase 7.1's files stay closed.

**How the lifter declares slots: closed by 07.2-14.** The lifter declares a 4-byte address-taken slot `int s_X[1]` (`f2239f28`, tests `f1d7fed2`), which keeps M2 in both cells where three `char[4]` do not (probe `pr_arr_int1_x3`), and the `pr_lift_taken_*` round trips compile back to the probe bytes. Wider taken slots stay `char s_X[N]`; two or more of one size have no known order, and the draft's nearest-the-entry-first order is a guess there.

**Frames past the sweep: narrowed, still open.** 07.2-14 measured three more in both cells (`78bd8cb8`): a `char[4]` beside a `short[2]` keeps M2 (known, placed right), two `char[4]` beside a `short[2]` leave it (refused, right), and a `char[4]` and an `int` beside a `char[2]` hold while the model refuses them. Nothing moved `order_is_known`. What is left: the refusal stays wider than the compiler's line on the safe side (`REFUSED_HOLDING` in `tests/test_slots_real.py`), and frames past the sweep and these three are still unmeasured. Narrowing it needs a line that a measurement draws, not one more frame.

**A skill's wording: closed by 07.2-14.** `.claude/skills/watcom-readability/SKILL.md:41` no longer says the order of declarations decides the stack slots, through `writing-skills`, RED first (`3d0a8bf1`). `.claude/skills/watcom-decomp/SKILL.md:68` already states the measured rule and needs no change (07.2-14's SUMMARY hands 07.2-09 "none").

**How to measure it.** Use the converter-curve copy, `.planning/converter-curve/measure_curve.py`, with the matched-row control over the exact rows; 07.2-14 measured point 16 there.
