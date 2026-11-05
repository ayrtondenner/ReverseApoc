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
