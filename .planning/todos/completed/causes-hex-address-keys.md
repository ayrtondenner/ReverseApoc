---
created: 2026-11-10
source: 07.2-10 SUMMARY (concern 1)
---

# `reverseapoc causes`: hex addresses split one mismatch cause into many keys

`causes` normalises a mismatch key by turning decimal digits into `N`. Inside a hex address that leaves the hex
letters, so one cause reads as several keys ("pop at NA1092", "pop at NBN..."). The counts are right, but the ranked
mismatch classes over runs 20261107-030004 and 20261107-170844 are spread across many rows.

Do (test first): normalise a whole hex address or offset token (for example `0x[0-9A-Fa-f]+` and bare hex runs
after "at") into one placeholder before the digit fold, then re-run `causes` on both runs and check that the top
classes in docs/learnings.md (the 9d entry) do not change.

## Result (quick 261112-fdu, 2026-11-12): closed

The fold landed in `tools/reverseapoc/causes.py` (99d2f32d, 995c77bc, 424d7f0f, 2e5fd781, merged 94a4c824). Re-run on
the main checkout (`build/gate/07.2/fdu-causes.txt`): the 66 mismatch rows fold into 19. The 328, 289, 174 and 60
classes keep their counts; the merged `(pop at N)` row (62) ranks fourth, ahead of the 60. The 9d entry in
docs/learnings.md says so. Out of scope: batch's own verdict keys still use `batch._reloc_key` unfolded (gate code).
