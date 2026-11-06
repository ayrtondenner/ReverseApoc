---
title: Slot model and search fixes from Phase 7.1's phase review
created: 2026-11-06
source: 07.1-REVIEW.md, the phase-end review; plan 07.1-06 writes no Python, so these stayed open
---

# Slot model and search fixes from Phase 7.1's phase review

The phase review found these after plans 01 to 05 closed. Each is deferred in `07.1-REVIEW-DISPOSITION.md`, and none can land a wrong match, because `check` and the gate are untouched. The review holds the detail and suggested fixes.

**CR-01, the one to do first.** `slots.order_is_known` calls a tie of three or more multi-element arrays known, and wcc386 10.6 does not place them that way. In both cells, three `char[4]` or `short[2]` sit at 4, 8, 0 and three `char[2]` at 0, 8, 4, where the model says 8, 4, 0. Where the model says known, `search` turns off its plain declaration moves, so the wrong answer removes the fallback too. Reach today: 2 of 919 converter drafts.

The skill and `docs/matching.md` are already corrected. Still to do:
- carry the shape into `slots.Local` and refuse it in `order_is_known`;
- add the shapes to `probe/cg_slots.c` and `TIES` in `tests/test_slots_real.py`, and correct `probe/README.md`;
- measure two arrays beside two or more scalars;
- decide whether `lift.py` should declare a 4-byte taken slot as `int` or `int s[1]`, which follows the rule, and re-measure the curve if so.

**The others, by file:**
- `search.py`: WR-01 (a tie at shifted offsets empties the axis with no fallback), WR-02 (three declaration forms leave `_readable` true on an incomplete frame).
- `classify.py`: WR-03 (a slot-only difference on a filler-tailed row is class `size`). This one bears on the owner's open item about class `size`.
- `batch.py`: WR-04 (a slot pair can hold None and crash the search's output).
- `lift.py`: IN-01, IN-02, IN-03.
- `docs/toolchain.md`: IN-04 (`lift` is documented as writing nothing, and it writes the census).

**How to measure it.** Use the Phase 7.1 curve gate, `.planning/phases/07.1-matching-tooling/measure_curve.py`, with the matched-row control over the exact rows.
