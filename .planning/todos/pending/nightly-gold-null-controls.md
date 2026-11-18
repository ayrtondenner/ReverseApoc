---
title: A nightly gold and null control through the real check path
created: 2026-11-18
source: literature mining of 2026-11-18 (docs/research/notes-ideas-tooling-reproducibility.md #2)
---

# A nightly gold and null control through the real check path

**Why.** Nothing proves each night that the oracle still accepts a known match and rejects a stub (EdgeBench's sleep-control AIs; SWE-bench's gold runs).

**Do.** At drive start, run attempt check on one matched function's committed C (must match) and on a stub (must fail), through the same path agents use; refuse the night if either is wrong.

**Done when.** A test with a broken checker refuses the night; the run record holds the control results.

**Effort / value.** S / high. Evidence and sources: docs/research/notes-ideas-tooling-reproducibility.md #2.
