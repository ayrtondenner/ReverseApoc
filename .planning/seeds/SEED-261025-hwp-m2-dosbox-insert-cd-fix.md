---
id: SEED-261025-hwp
status: dormant
planted: 2026-10-25
planted_during: Milestone 1, Phase 6 (Reporting and agent pilot)
trigger_when: Milestone 2, once the game's file-search wrapper and its "missing CD" error path are matched
scope: medium
---

# SEED-261025-hwp: Fix the "Please insert CD" bug in DOSBox, proven with the decomp

## Why This Matters

The owner wants a DOSBox PR that fixes the bug. The decomp is the means to prove the fix and to test and verify it.

The cause, as traced by OpenApoc's JonnyH in March 2024:
- It is not a CD check. Before a battle, UFO2P copies map files and runs two FindFirst/FindNext searches at the same time, which is legal under DOS.
- DOSBox's directory cache for host-folder drives has 2,048 search slots. A FindFirst that only tests whether a file exists never frees its slot.
- After hours of play the slots run out. DOSBox resets all of them, the other live search fails, and the game reports the missing file as "insert CD".

Where it stands:
- Filed as dosbox-x#4904 (2024-03-16) and still open. The maintainer reproduced it independently in July 2026, and found a second leak: the same path gets a new slot each time it is searched.
- DOSBox Staging has the same reset-all code and no issue filed.
- Steam ships DOSBox 0.72 with a host-folder `mount c`.

## What the Decomp Adds

- The exact call sequence of the game's search wrapper.
- What its error path tests (only a failed find, or also MSCDEX/volume checks).
- From those, a tiny Watcom/DOS reproducer that hits the bug in seconds instead of hours. Attach it to #4904 and use it as the regression test for the fix.

The two EXEs link `_dos_findfirst_` and `_dos_findnext_` at UFO2P `0x000C15D2`/`0x000C15EF` and TACP `0x000C31F6`/`0x000C3213`. These are runtime rows in `functions.csv`.

## The Fix Direction (to confirm)

- Do not wipe every slot when they run out. Evict the least-recently-used slot, or rebuild an evicted search's state from what DOS keeps in the DTA.
- Fix the duplicate-slot leak as well.

Targets: DOSBox-X #4904 first, then the same fix for DOSBox Staging.

## Before Filing

- This is outward-facing, so the owner decides when and how it is filed.
- Coordinate with JonnyH, who owns #4904, so nobody duplicates work.
- No-CD cracks stay out of scope.

## When to Surface

**Trigger:** Milestone 2, once the search wrapper and error path are matched.

## Scope Estimate

**Medium.** A reproducer, a C++ patch to DOSBox's `drive_cache.cpp`, and upstream review.

## Breadcrumbs

- https://github.com/joncampbell123/dosbox-x/issues/4904
- UFOpaedia "Known Bugs (Apocalypse)" (rev 124000).
- Steam thread https://steamcommunity.com/app/7660/discussions/0/4361249244255131228/
- `config/ufo2p/functions.csv` and `config/tacp/functions.csv` (`rt_dosfind` rows).
- A possible link, not yet checked: the Learning AI file code ([[SEED-261025-o1r]]) runs a FindFirst existence check at mission start.
