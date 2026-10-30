---
phase: 07-mechanics-first-decompilation
plan: 26
subsystem: driver
tags: [driver, picker, tier-queue, callees-first, scc, passes, dec-02, d-04, d-08, d-22, d-23]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-05 callgraph (sccs, with_edges, edge kinds); 07-10 mechanics (load, read_members, signed_tiers, tier_status, HUB_KINDS); 07-21 workers and the coordinator's busy units; 07-22 Tier 1 signed; 07-23 pass_index / passes from the committed log"
provides:
  - "picker.TierItem, picker.TierQueue (next_item / next_eligible, take, finish, use_passes, preview, items) and picker.tier_queue over the signed tiers"
  - "driver.ExeWorld.ranks (every game/thunk row as score ranks it, no P16 filter) and ExeWorld.graph (callgraph.build_for, built once)"
  - "driver.tier_source / tier_picks; real_deps queues the tier queue when a tier is signed; the coordinator's tier path; _function returns MATCHED / CAPPED / None and counts a capped pass in night.passes"
  - "the dry run and night_top_picks draw from the tier queue (ruling F8); tier picks in the dry-run JSON carry tier, level and pass"
affects: [07-30, 07-34, 07-39, 07-41]

actuals:
  tokens: 15450
  tasks: 3
  commits: 5
plan_head_before: 5f5bbb2f564847cc9863bfa887e76cfa40aa7c6a
plan_head_after: 999727c95224860e7422c793168c4c7f0bcac27c

tech-stack:
  added: []
  patterns:
    - "The tier queue is asked for its best eligible pick each time a worker is free (eligibility changes as passes end), rather than iterated once"
    - "One pass index: the night's `passes` dict is bound into the queue (use_passes); the night writes it, the queue only reads it"

key-files:
  created: []
  modified:
    - tools/reverseapoc/picker.py
    - tools/reverseapoc/driver.py
    - tests/test_driver_pick.py
    - tests/test_drive_real.py

key-decisions:
  - "Order key (finished passes, tier, member before hub, level, rank, EXE order); rank is score's own (__CHK, score, start)"
  - "An SCC waits as one node: a member is eligible when every group callee of its SCC outside the SCC is matched or has finished a pass"
  - "Midrow edges do not order or block (owner ruling Q1, 07-22: a switch table is no call); hand edges of mechanics.toml do"
  - "capped at least once = finished passes > 0, read from the same pass index the records use (no separate capped set)"
  - "A row of two signed tiers is queued once, in the first; a tier's hubs are the hub-role rows its items reach"
  - "The selection is work-conserving: hubs and the next tier run when no earlier item is eligible (members waiting on an in-flight callee do not idle a free worker)"
  - "The tier dry run shows 10 picks (DRY_RUN_TIER_PICKS = the pilot's size), each function once at its next pass"

patterns-established:
  - "Mutation checks pin characterization tests: each order-key term, the signed filter, the pass count, the pass-index binding, the claim check and the rank were broken one at a time and each made a test fail"

requirements-completed: [DEC-02, DEC-03]

coverage:
  - id: D1
    description: "The tier queue: a signed tier's members callees first (SCC levels, leaves first), hub/asm/closure rows never block, midrow edges ignored, picks carry unit, name, size and score"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_driver_pick.py#test_tier_queue_leaves_first, test_tier_queue_waits_for_an_in_flight_callee, test_scc_members_do_not_block_each_other, test_hub_and_asm_never_block, test_midrow_edges_do_not_order_members, test_tier_queue_picks_carry_unit_name_size_and_score, test_tier_queue_refuses_a_member_without_a_unit"
        status: pass
    human_judgment: false
  - id: D2
    description: "The driver uses the tier queue when a tier is signed, the Phase 6 pool otherwise"
    requirement: DEC-02
    verification:
      - kind: integration
        ref: "tests/test_driver_pick.py#test_driver_uses_tier_queue_when_signed"
        status: pass
    human_judgment: false
  - id: D3
    description: "Unlimited passes (D-08), claimed units skipped not dropped, hubs after members then the next tier, unsigned or changed tiers not queued, empty queue ends 'nothing to do' exit 0, deterministic order, passes from the log not difficult.json"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_driver_pick.py#test_pass_ordering, test_pass_ordering_lets_a_capped_callee_free_its_caller, test_claimed_unit_skipped_not_dropped, test_hubs_after_members, test_a_row_of_two_tiers_is_queued_once_in_the_first, test_unsigned_tier_not_queued, test_empty_queue, test_ordering_deterministic"
        status: pass
      - kind: integration
        ref: "tests/test_driver_pick.py#test_empty_queue_ends_the_night_with_nothing_to_do, test_tier_queue_reads_passes_from_the_log_not_difficult_json, test_a_capped_function_returns_for_its_next_pass_the_same_night"
        status: pass
    human_judgment: false
  - id: D4
    description: "Dry run and night drafts draw from the tier queue; dry-run tier picks carry tier, level and pass (ruling F8)"
    requirement: DEC-02
    verification:
      - kind: integration
        ref: "tests/test_driver_pick.py#test_dry_run_tier_picks, test_dry_run_text_names_tier_level_and_pass, test_night_top_picks_draw_from_the_tier_queue, test_tier_preview_is_distinct_and_callees_first; tests/test_drive.py (Phase 6 dry-run keys unchanged)"
        status: pass
      - kind: integration
        ref: "REVERSEAPOC_ORIG=<main>/orig uv run pytest -q tests/test_drive_real.py (3 passed: the real queue's members equal tier_status for tiers 1 and 2)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Host suite and ruff green; the container run is deferred to the orchestrator (R-B)"
    verification:
      - kind: other
        ref: "uv run pytest -q (3746 passed, 249 skipped) && uv run ruff check ."
        status: pass
    human_judgment: true
    rationale: "docker is not allowed in a worktree; the orchestrator runs docker compose build && docker compose run --rm test after merge"

duration: 37min
completed: 2026-10-30
status: complete
---

# Phase 7 Plan 26: The tier picker Summary

**Once config/mechanics.toml has a signed tier with a matching digest, the driver works the signed tiers' must-match members callees first. The member call graph is condensed to SCCs and taken leaves first, ranked by score's own rank with no P16 filter. Then each tier's hubs follow, then the next tier, never an asm row. Every eligible function runs pass N before any runs pass N+1, and a capped function comes back the same night. The dry run and the night's draft picks are the tier queue's first picks, and the dry run lists each with its tier, level and pass.**

Execution context nonce: ea1443b12c5c0bd1

## Performance

- **Duration:** about 37 min
- **Started:** 2026-10-30T20:16:51Z
- **Completed:** 2026-10-30T20:53Z
- **Tasks:** 3, all TDD
- **Files modified:** 4 (no file created)

## Accomplishments

- **picker.py:**
  - `TierItem(tier, level, rank, pick, hub, pass_n)`.
  - `TierQueue`:
    - `next_item` / `next_eligible(claimed_units)`;
    - `take` / `finish(matched=)`;
    - `use_passes`, which binds the night's pass index;
    - `preview(count)`;
    - `items`.
  - `tier_queue(mech, members, graphs, ranks, units, *, matched, passes)`.
  - What gets queued:
    - Groups come in this order: signed tiers ascending, each tier's members before its hubs, EXEs in order.
    - A tier's members are the role-member rows with a member item of that tier. Its hubs are the role-hub rows that a tier item reaches.
    - asm and closure rows are never queued.
  - How a group is ordered:
    - The group's call graph covers every edge kind except midrow, plus the hand edges. It is condensed with `callgraph.sccs`.
    - The level is 0 for a leaf SCC. Otherwise it is one more than the level of the deepest callee SCC.
    - An item waits only for its SCC's callees in the same group.
- **driver.py:**
  - `ExeWorld.ranks` and `ExeWorld.graph`, filled by `load_world`.
  - `tier_source` / `tier_picks`.
  - `real_deps`: with a signed tier, `queue` is the tier queue and `requeue` returns `()`.
  - The coordinator's tier path: `_tier_pick`. `release` tells the queue whether the pass matched.
  - `_function` returns `MATCHED`, `CAPPED` or None, and counts a capped pass in `night.passes`.
  - `pilot_picks` and `night_top_picks` draw from the tier queue (F8). `_pick_doc` and the text line add tier, level and pass for tier picks only.
- **Real figures** over the committed config and the main checkout's orig/. These are counts and addresses only, saved in gitignored `build/red/tier-figures.txt`.
  - Signed tiers are (1, 2).
  - Tier 1 queues 973 members (`tier_status` total 973) over levels 0..15, with 485 leaves. It also queues 343 hubs over levels 0..18.
  - Tier 2's must-match set is 409. 228 of those rows are also Tier 1 members, so they are queued in Tier 1, and 181 are queued as Tier 2 members.
  - The first dry-run pick is ufo2p 0x000126E0, tier 1, level 0, pass 1.

## Task Commits

1. **Task 1 (tracer): the tier queue and the driver wiring.** RED `198e276`, GREEN `80d9557`.
   - Tracer feedback gate: the run is interactive in end-of-phase mode, and the verify is automated only. I re-ran `uv run pytest -q tests/test_driver_pick.py` after the GREEN commit: 37 passed. The acceptance grep found `class TierQueue` and `def tier_queue(`. Tracer verified end-to-end; I then expanded.
2. **Task 2: passes, claimed units, hubs after members, tier order, empty queue.** One test-only commit, `f21d0a1`, with no feat commit (see TDD Gate Compliance).
3. **Task 3: the dry run's tier picks.** RED `a315ed7`, GREEN `999727c`.

## TDD Gate Compliance

Each RED run wrote pytest JUnit XML and a record under `build/red/` (gitignored). `gsd-tools check tdd-red-evidence` judged the records.

- **t1, target `test_tier_queue_leaves_first`: RED_EVIDENCE_OK / target_test_failed, 8 failed.**
  - The picker tests failed in the test body with `AttributeError: module 'reverseapoc.picker' has no attribute 'tier_queue'`.
  - The driver test failed with `TypeError: ExeWorld.__init__() got an unexpected keyword argument 'ranks'`.
  - Both are the missing feature itself (the same kind of evidence 07-21 and 07-23 accepted). Nothing failed in collection or import.
- **t2: unexpected GREEN (fail-fast rule 1), investigated.**
  - All 11 Task 2 tests passed before any Task 2 code. That was after I fixed a setup bug in one test: it had no build/driver/ directory.
  - Cause: Task 1's GREEN already held the plan's full order key. `next_item` needs one total order, so the key (passes, tier, hub, level, rank) went in with Task 1, together with the in-night pass count that `_function` keeps.
  - The feature existed, so I checked that the tests are not vacuous. I broke the code one way at a time and restored it with `git checkout -- <file>` after each:
    - M1, passes dropped from the key: 3 tests failed.
    - M2, member-before-hub dropped: `test_hubs_after_members` failed. I first changed the test so the hubs rank better than the members.
    - M3, unsigned tiers queued: `test_unsigned_tier_not_queued` failed.
    - M4, the capped pass not counted: `test_a_capped_function_returns_for_its_next_pass_the_same_night` failed.
    - M5, the night's pass index not bound: `test_tier_queue_reads_passes_from_the_log_not_difficult_json` failed.
    - M6, claimed units ignored, and M7, __CHK dropped from the rank: `test_claimed_unit_skipped_not_dropped` and `test_ordering_deterministic` failed.
  - Task 2 therefore has one `test(07-26)` commit pinning behaviour that already held, and no `feat` commit.
- **t3, target `test_dry_run_tier_picks`: RED_EVIDENCE_OK / target_test_failed, 4 failed.**
  - The dry run still took the Phase 6 pilot path and was refused: `pilot short ... pool exhausted`.
  - `preview` did not exist yet.
  - `night_top_picks` returned no tier picks.
- Every `feat(07-26)` commit follows its `test(07-26)` commit. There is no REFACTOR commit.

## Files Created/Modified

- `tools/reverseapoc/picker.py`:
  - the module docstring's tier paragraph;
  - `Rank`, `Passes`, `Ranks`, `Units`;
  - `TierItem` and `TierQueue`;
  - `_call_graph`, `_levels`, `_group_rows`, `_tier_pick`, `_Group`, `_groups`, `_group_items` and `tier_queue`.
- `tools/reverseapoc/driver.py`:
  - the module docstring's "Tiers" paragraph;
  - `CAPPED` and `DRY_RUN_TIER_PICKS`;
  - `Deps.queue`'s contract;
  - `ExeWorld.ranks` / `graph`, `_ranks` and `load_world`;
  - `TierSource`, `tier_source`, `tier_picks` and `real_deps`;
  - `_Worker.outcome`;
  - `_Coordinator.tiers`, `run`, `release`, `_eligible` and `_tier_pick`;
  - `_Night._function` and the `_pass` docstring;
  - `DryPick`, `_pick_of`, `_pick_doc`, `pilot_picks`, `night_top_picks`, `dry_run` and the drafts call.
- `tests/test_driver_pick.py`: 26 new tests.
- `tests/test_drive_real.py`: the Phase 6 pilot test switches `tier_source` off, and `test_real_tier_queue_holds_the_signed_tiers_members` is new.

## Decisions Made

See `key-decisions` in the frontmatter.

## Deviations from Plan

**Orchestrator ruling F8: the dry-run branch (`pilot_picks`) and `night_top_picks` both draw from the tier queue.**
- `_pick_doc` adds `tier`, `level` and `pass` only for tier picks.
- tests/test_drive.py is unchanged, and its Phase 6 dry-run tests still pin the 8 keys and the 10 pilot picks.
- `test_dry_run_tier_picks` goes through `run_drive` with seams.
- Commits `a315ed7` and `999727c`.

**Orchestrator note (07-23 as built): difficult.json is dropped from the tier picker.**
- With a signed tier, `real_deps.queue` ignores the difficult list and `requeue` returns `()`.
- The coordinator binds the night's `passes` (`pass_index` of the committed log, counted up by every capped pass) into the queue. The records and the queue therefore read one pass index.
- `test_tier_queue_reads_passes_from_the_log_not_difficult_json` has the log say the leaf has one finished pass while difficult.json lists the other member. The other member runs first, on pass 1. Mutation M5 shows the test bites.
- difficult.json is still written when a pass is capped. It stays the cache of the Phase 6 picker, which is the fallback when no tier is signed.

**1. [Plan clarification] The `TierQueue` interface.**
- The plan sketched `TierQueue(items, callees, *, matched, capped_once, passes)`. "Capped at least once" is now finished passes > 0, read from the same pass index, so there is no second set that could disagree.
- `take`, `finish`, `use_passes`, `next_item`, `preview` and `items` are added. The coordinator and the dry run need them.

**2. [Plan clarification] An SCC waits as one node.**
- The truth's "every in-tier member callee outside its own SCC" is applied to the condensed SCC, as in "condensed to SCCs".
- In A <-> B, B -> C, both A and B wait for C. Once C is done, neither blocks the other. This is the plan's test text "C first, then A and B both eligible".

**3. [Plan clarification] Midrow edges are not calls for the order.**
- The owner's 07-22 Q1 ruling says hub and SCC figures ignore midrow edges, which are switch-table artefacts. The tier order follows every other edge kind plus the hand edges.

**4. [Plan clarification] Hubs and later tiers wait only for eligible members.**
- The next pick is the eligible item with the least key. When every remaining member of a tier waits on an in-flight callee, a free worker takes a hub or the next tier's member rather than idling.
- `test_hubs_after_members` pins the plan's case (every member matched or claimed).

**5. [Rule 3 - Blocking] tests/test_drive_real.py is outside files_modified.**
- Tier 1 is signed in the committed config, so `pilot_picks` now returns tier picks on the real files. The real-file test's 5 + 5 pilot assertions would fail with orig/ present (main checkout, container).
- The test now switches `tier_source` off for the Phase 6 check.
- A new real test checks the queue against the mechanics API, with no hard-coded counts:
  - the queued members equal the union of `tier_status` members of the signed tiers;
  - Tier 1's equal its own;
  - no asm row is queued;
  - the 10 dry-run picks are distinct, unmatched Tier 1 members, a leaf first.
- With `REVERSEAPOC_ORIG` set to the main checkout's orig/: 3 passed. Commit `999727c`.

**6. [Test fix inside a GREEN commit] The night tests commit status tables in gate's own format.**
- The night harness's made-up `status.csv` is refused by `status.read_status`, which `real_deps` reads. Commit `80d9557`.

**7. [Test fix inside a GREEN commit] The preview test's expectation.**
- It expected the leaf, which already has 2 finished passes, first. D-08 puts the pass-1 picks it frees before its pass 3. The code was right. Commit `999727c`.

**8. [TDD] Task 2 has no feat commit.** See TDD Gate Compliance.

---

**Total deviations:** 1 orchestrator ruling (F8) and the 07-23 note, 1 Rule 3 fix, 4 plan clarifications, 2 test fixes inside GREEN commits, 1 TDD sequencing note.
**Impact on plan:** every must-have truth and the prohibition hold: no asm row, and no row of an unsigned or changed tier, is ever queued. There is no scope creep.

## Issues Encountered

- **Compound shell commands.** The harness refused compound shell commands: heredocs with git, and `$(...)` beside a git call. I used the Edit tool, a scratchpad script for the RED records (`red_record.py`) and literal values.
- **A stray Python REPL.** A probe command started an interactive Python REPL in the background. I killed it by PID (it was one of my own `-I -` processes). Nothing else was touched.

## Concerns for later plans

- **A gate may mark other functions of the landed unit matched.**
  - The gate can write matched rows for other functions of the same unit when they pass.
  - The tier queue learns only of the claimed function's match during the night. Its matched set is read from status.csv when the queue is built.
  - The Phase 6 picker has the same limit. The next night reads every match.
- **Model escalation per pass is not wired here.**
  - `_pass` now counts in-night passes, so D-09's "pass 3 or more runs on Fable" can read it.
  - The model and budget per pass are 07-30's.
- **Keys and renames.** `pass_index` and the queue key functions by `(exe, start)`, so 07-34's renames do not affect them. The record's `function` name changes; its `start` does not.
- **Tier 2 overlap.** 228 of Tier 2's 409 must-match rows are Tier 1 members. They run in Tier 1's order. Coverage per tier still reads `tier_status`.

## Known Stubs

None.

## Threat Flags

None.
- T-07-76 is mitigated: only `mechanics.signed_tiers` (signed, digest matching) feeds the queue, and asm rows are excluded by role. `test_unsigned_tier_not_queued`, `test_hub_and_asm_never_block` and the real test cover it.
- T-07-77 is mitigated: finished passes order first, which `test_pass_ordering` covers.
- No new file, network or trust surface: the queue reads the committed mechanics and status files only.

## Verification

- Task 1: `uv run pytest -q tests/test_driver_pick.py`: 37 passed. The driver suites (`test_driver.py`, `test_driver_workers.py`, `test_driver_records.py`, `test_drive.py`): 321 passed, 2 skipped.
- Task 2: `uv run pytest -q tests/test_driver_pick.py -k "pass or claimed or hubs or unsigned or empty or deterministic"`: 10 passed.
- Task 3: `uv run pytest -q tests/test_driver_pick.py tests/test_drive.py`: 139 passed.
- `uv run pytest -q` (host, worktree): **3746 passed, 249 skipped**, exit 0.
  - The one new skip is `test_real_tier_queue_holds_the_signed_tiers_members`. It skips through test_drive_real.py's existing module fixture, with the existing real-file reason `orig/UFO2P.EXE not present (run uv run reverseapoc ingest)`. That reason never fires on the main checkout or in the container.
  - No new skip reason was added.
  - The module docstring edit came after this run. It changed text only, and the picker and drive tests re-ran green after it (139 passed).
- `REVERSEAPOC_ORIG=<main checkout>/orig uv run pytest -q tests/test_drive_real.py`: 3 passed.
- `uv run ruff check .`: All checks passed.
- Acceptance:
  - picker.py contains `class TierQueue` and `def tier_queue(`;
  - tests/test_driver_pick.py has `test_pass_ordering` and `test_empty_queue`;
  - the dry-run JSON pick objects carry `tier`, `level` and `pass` (`test_dry_run_tier_picks`).
- I ran no real `claude -p` session, no `drive` command (not even the dry run, which went through `run_drive` in tests only) and no docker (D-11, R-B).
- **Container step deferred to the orchestrator:** `docker compose build && docker compose run --rm test`.

## User Setup Required

None.

## Next Phase Readiness

- 07-39 can run `drive --dry-run --json` on the main checkout and read `tier`, `level` and `pass` for each pick.
- 07-30 can read `night.passes` / `_pass` for D-09's model escalation.

## Self-Check: PASSED

- FOUND: tools/reverseapoc/picker.py, tools/reverseapoc/driver.py, tests/test_driver_pick.py, tests/test_drive_real.py.
- FOUND commits on this branch: 198e276, 80d9557, f21d0a1, a315ed7, 999727c. `git rev-list --count 5f5bbb2..HEAD` = 5 before this SUMMARY commit.
- No STATE.md, ROADMAP.md or REQUIREMENTS.md change (the orchestrator owns them after the merge).

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-30*
