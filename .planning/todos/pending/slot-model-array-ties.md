---
title: Slot model and search fixes from Phase 7.1's phase review
created: 2026-11-06
source: 07.1-REVIEW.md, the phase-end review; plan 07.1-06 writes no Python, so these stayed open
updated: 2026-11-12 by quick 261112-fdx
---

# Slot model and search fixes from Phase 7.1's phase review

Plan 07.1-07 built and closed CR-01, WR-01, WR-03, WR-04 and IN-04. This is what the owner's ruling 3 left. The review holds the detail and suggested fixes, and none of these could land a wrong match, because `check` and the gate are untouched.

**The findings, closed.** Quick task 261107-qke closed `search.py` WR-02 and `lift.py` IN-01, IN-02 and IN-03, test first, with the commits in its SUMMARY. `07.1-REVIEW-DISPOSITION.md` still reads deferred, because Phase 7.1's files stay closed.

**How the lifter declares slots: closed by 07.2-14.** The lifter declares a 4-byte address-taken slot `int s_X[1]` (`f2239f28`, tests `f1d7fed2`), which keeps M2 in both cells where three `char[4]` do not (probe `pr_arr_int1_x3`), and the `pr_lift_taken_*` round trips compile back to the probe bytes. Wider taken slots stay `char s_X[N]`; two or more of one size have no known order, and the draft's nearest-the-entry-first order is a guess there.

**Frames past the sweep: narrowed by quick 261112-fdx, still open.** 07.2-14 measured three frames in both cells (`78bd8cb8`). Quick 261112-fdx fixed four lines before measuring 27 `pr_line_*` frames in both cells, and drew three, each with its own RED and GREEN commits:
- Line A (`3fe150ff`, `51b194c9`): one 2-byte array declared first keeps M2 beside plain 2-byte locals in one block. Measured from 1 to 11 shorts after it, as `char[2]` and `unsigned char[2]` beside `short`, `unsigned short` and `short[1]`.
- Line B (`eebf0e76`, `cdefe67e`): two 4-byte arrays declared first in the top block, a plain local after them there, and plain locals in later blocks keep M2 and M4. Measured with 1 to 3 ints in the top block, 1 to 5 in a later block and up to two later blocks, as two `char[4]`, two `short[2]` (sweep frames only) or one of each (one frame).
- Line C (`b0b9de22`, `b52e9019`): three or more 4-byte arrays declared first in one block, with a plain local after them, keep M2. Measured with 3 or 4 arrays then 1 or 2 ints, as `char[4]`, one frame with a `short[2]` third.
- Line D, a 4-byte array and an int beside one 2-byte local, broke: `char a[4]; int b; char c[2];` and `int a; char b[4]; short c;` leave declaration order (`pr_line_d_c4_i_c2`, `pr_line_d_i_c4_h`, in TIES). It was not refit; a narrower line there needs frames of its own.
- The four `pr_line_k_` frames the model already called known, past the sweep's counts, sit where it puts them.

What is left: `REFUSED_HOLDING` still holds `pr_arr_two_two_small` (c2 c2 h h) and `pr_arr_two_two_block` (c4 c4 | i i), each a single held frame between leavers that no measured line reaches, `pr_arr_c4_c2_int` with its `_rev` twin and `pr_line_d_c4_i_h`, `_h_i_c4`, `_c4_c2_i_late` and the control `pr_line_d_i2_h`, all held but on the broken line D. The refusal stays wider than the compiler's line there, on the safe side. This todo stays in pending/ as a documented partial for that remainder.

Curve: point 17 (`.planning/converter-curve/CURVE.md`): no record of the 1834 moved and none of point 16's 175 exact records was lost, so the drawn lines cost nothing on this curve.

**A skill's wording: closed by 07.2-14.** `.claude/skills/watcom-readability/SKILL.md:41` no longer says the order of declarations decides the stack slots, through `writing-skills`, RED first (`3d0a8bf1`). `.claude/skills/watcom-decomp/SKILL.md:68` already states the measured rule and needs no change (07.2-14's SUMMARY hands 07.2-09 "none").

**How to measure it.** Use the converter-curve copy, `.planning/converter-curve/measure_curve.py`, with the matched-row control over the exact rows; 07.2-14 measured point 16 there.
