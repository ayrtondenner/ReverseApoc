---
title: Lift signed divide by a power of two
created: 2026-11-05
source: owner ruling at plan 07.1-06's checkpoint
---

# Lift signed divide by a power of two

The largest refusal left in the converter, and not in Phase 7.1's plans. The owner said yes to it as follow-up work outside that phase.

**What it is.** `x / 2^n` compiles to `mov; sar; sub; sar` or `mov; sar; shl; sbb; sar`. Measured at plan 03's close: `op: cdq` is 124 first refusals, and 90 of the 113 rows checked hold one of these forms. The other 23 hold `cdq; xor eax, edx`, which is `abs`. `op: sbb` reads low only because `op: cdq` masks it: 134 of 138 `sbb` uses are this idiom. No plain `idiv` is refused.

**How to measure it.** Use the Phase 7.1 curve gate: `.planning/phases/07.1-matching-tooling/measure_curve.py`, with the matched-row control over the exact rows.

**Expect less than the count suggests.** It turns refused rows into drafts, and a draft is not a match. Spike 010 lifted more rows while exact stayed flat.

## Result (2026-11-07): built and measured, todo closed

Built in quick-batch item 261107-qkb (merge `67c25cf1`): both Watcom 10.6 forms, `mov; sar 31; sub; sar 1` (or `cdq; sub; sar 1`) and `mov; sar 31; shl n; sbb; sar n`, lift to `v / 2^n` in any register pair, proven by a clean-room probe round trip (`probe/cg_divide.c`). `cdq; xor eax, edx` (abs) stays refused.

Measured with `.planning/converter-curve/measure_curve.py`, point 8 (baseline) against point 9, Tier 1 converter-only:
- exact 18 and near 12 at both points: no new exact or near row;
- `op: cdq` first refusals 125 to 31 and `op: sbb` 3 to 0; hole drafts 308 to 240, compiled drafts 422 to 484, compile-failed 22 to 27.

As expected, the idiom turns refused rows into whole drafts, mostly at 256 B and up, not into matches.
