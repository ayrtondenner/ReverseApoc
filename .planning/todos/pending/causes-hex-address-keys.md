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
