---
id: SEED-261025-l4y
status: dormant
planted: 2026-10-25
planted_during: Milestone 1, Phase 6 (Reporting and agent pilot)
trigger_when: planning Milestone 2 (read this first; it orders the other Milestone 2 seeds)
scope: large
---

# SEED-261025-l4y: Milestone 2 layout, the full decomp in parallel with everything that doesn't need it

## Why This Matters

The owner approved this layout on 2026-10-25. The full decomp is the milestone's priority and its long pole: about 3,200 game functions, likely many months. Most other Milestone 2 items need only a small set of functions, so they run alongside it instead of waiting for 100%.

Two things make parallel work possible:
- **Different resources.** The decomp is mostly machine time (the driver matching functions unattended). Tracks B and C are mostly owner time (maintainers, reviews, a PR).
- **The decomp runs in an order we choose.** Its first batch matches the functions the other tracks need.

## Layout

**Track A: the decomp** ([[SEED-261025-3ga]]). Starts on day one.
- **A1, a targeted batch:**
  - the game's file-search wrapper and its "missing CD" error path;
  - the Learning AI code (Tier 1 file I/O, the Tier 2 learning update, and as much of Tier 3 as is reachable);
  - any #997 callees Phase 7 left unmatched.
- **A2..An:** the remaining functions in batches by subsystem (cityscape, tactical, ...) until 100%. Each batch is a phase, so progress stays visible.

**Track B: OpenApoc-facing.** Starts on day one.
- **B1:** the DOSBox differential harness ([[SEED-261025-hft]]). Needs nothing new from the decomp.
- **B2:** the #997 pilot spec ([[SEED-261025-os5]]): `dosbox-verified`, then OpenApoc review. Needs B1.
- There is no "agree terms with OpenApoc" step (owner, 2026-10-25). We write specs as they make sense to us, and the owner flags format concerns if OpenApoc raises any.

**Track C: the DOSBox fix** ([[SEED-261025-hwp]]).
- **C1:** the DOSBox-X patch can start on day one, since the cause is known. The reproducer waits for A1. Then the PR.

**After A1:** a draft of the Learning AI spec ([[SEED-261025-o1r]]). The owner approved drafting it before 100%.

**After 100%:**
- the docs sweep ([[SEED-261025-8ob]]);
- the edition-diff verdict ([[SEED-261025-q3c]]), whose early steps (hashing a bought disc, diffing functions as they match) can happen at any time;
- the final pass on the Learning AI spec, adding what the tactical AI's use of the tables shows.

## Practical Notes

- GSD phases can declare their own `Depends on`, and `/gsd-workstreams` or `/gsd-manager` run parallel phases.
- The host and container test suites cannot run at the same time (they share `build/test-cc` and `build/test-cclog`), so parallel tracks take turns at the gate.
- `/gsd-new-milestone` turns this layout into real phases. Until then the roadmap does not change.

## Scope Estimate

**Large.** It covers the whole milestone.
