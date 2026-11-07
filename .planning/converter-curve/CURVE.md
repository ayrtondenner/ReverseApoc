# Converter follow-ups curve (batch 261107-qk9)

What the tools reach, point by point. The `measure_curve.py` beside this file writes it, and it
measures as the closed Phase 7.1 curve did. Point 7 is that curve's last summary row, copied
verbatim as the anchor. Point 8 is the baseline, measured after this harness merged, and each
later point is one follow-up item measured after its merge, with its plan cell naming the item's
quick id.

- **Seed and sample:** seed 20261103, and `SAMPLE.csv` is a byte copy of the Phase 7.1 sample,
  40 rows per bucket from 64 B up, fixed.
- **Cells:** the unit's committed rule and `-4r -oneatx -s -fpi`. A row is exact when either cell is.
- **Outcomes:** `exact`; `near`, compiled with a raw score of at least 90; `compiled`, with
  a lower score; `compile-failed`; `hole-draft`, a refused row that lifted with holes, which can
  never be exact; `refused`, the lifter raised `Unliftable` with holes too; `crash`, the lifter
  raised anything else. `matched` is a status, not an outcome, so matched rows get their own line.
- **Judge-exact:** every `exact` here is the judge's. A row can be judge-exact and still not land:
  tail merging and sibling regressions are the gate's to find.
- **A searched row:** the sample reads the draft's records and the winner's together, never a
  variant that did not win.
- **Move:** the Tier 1 number is converter-only and the sample runs every tool. A change in
  `exact` or `near` on either number is movement, of either sign. The Phase 7.1 stop rule was
  checked through point 3 only, so every point here reads `exempt (D-27)`. The rule:
  stop the phase after two plans in a row that move nothing.
- **Drift:** a row that lands between two points leaves the not-matched tables for the matched
  line, and a new cflags rule for a unit changes its committed cell. Compare points through the
  matched line and the `cflags sha256` cell, never through the not-matched tables alone.

| point | plan | head | cflags sha256 | result-used sha256 | tools | t1 exact | t1 near | s exact | s near | moved | flat streak | stop rule |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | 07.1-07 | 6a20ff0a919faf36e730e1b066d256f07b77caf9 | 5428038aff108e6fa8f545a1a8eda8e37a47827334797b2e12e00660688f4426 | ufo2p 71146929d2fd0ce9c9d0118d2ba55ffcfda8fde278c0bf602576f75f79441479 tacp fe42026431a063ddd9c74374ffa506bbdf0d621beff49c03915d9ac5b0cf1cb0 | converter, search, slots, classify | 21 | 14 | 1 | 0 | no | 0 | exempt (D-27) |
