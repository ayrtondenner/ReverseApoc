---
id: SEED-261025-3ga
status: dormant
planted: 2026-10-25
planted_during: Milestone 1, Phase 6 (Reporting and agent pilot)
trigger_when: planning Milestone 2 (first priority of the milestone)
scope: large
---

# SEED-261025-3ga: Milestone 2 priority, a 100% byte-matching, human-readable decomp of UFO2P and TACP

## Why This Matters

The owner set this as Milestone 2's priority on 2026-10-25. Milestone 1 matches only the functions behind the OpenApoc checklist items (Phase 7). A full decomp gives complete, readable source, and every other Milestone 2 item builds on it:
- the Learning AI spec ([[SEED-261025-o1r]]);
- the post-100% docs refresh ([[SEED-261025-8ob]]);
- the edition diff ([[SEED-261025-q3c]]);
- the claims that can only be closed with full coverage, such as "this item has no effect anywhere" or "this cheat is beta-only".

## When to Surface

**Trigger:** planning Milestone 2. It sets the milestone's main track.

This is Track A of the layout in [[SEED-261025-l4y]]. It starts on day one with the targeted batch A1 (the CD search wrapper and its error path, the Learning AI code, any #997 callees Phase 7 left unmatched), then works through subsystem batches until 100%.

## Scope Estimate

**Large.** Milestone 1 counts 1,633 game functions in UFO2P and 1,596 in TACP in `config/<exe>/functions.csv`, about 716 KB of game code per EXE. The Phase 6 driver and Phase 7's scaled run are the starting point.

## Done Gate

- Every game function in both EXEs is matched: `check` shows objdiff 100% and passes the relocation check.
- `rebuild` plus `cmp` against `orig/` are silent.
- `readlint` is clean.
- Runtime library rows count as matched only through `libmatch`, as they do today.

## Breadcrumbs

- `.planning/REQUIREMENTS.md` v2: TWIN-01, AUTO-01, NAME-01, SIM-01 and DATA-01 are likely enablers at this scale.
- `.planning/ROADMAP.md`, Phase 7 (DEC-01..06): the mechanics-first driver this scales from.
- `docs/workflow.md`, `docs/matching.md`.
