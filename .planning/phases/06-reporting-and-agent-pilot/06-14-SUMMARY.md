---
phase: 06-reporting-and-agent-pilot
plan: 14
subsystem: tooling
tags: [python, picker, score, driver, AGT-07, D-07, D-09, D-10]
requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "06-06: score.assess / ScoreReport.candidates with the LE header's page size and the push-imm __CHK rule"
  - phase: 06-reporting-and-agent-pilot
    provides: "06-09: the check/land provenance work in the wave-3 base (no API used here)"
provides:
  - "picker.Pick (exe, start, name, unit, size, score) and picker.PickerError"
  - "picker.queue: the EXEs interleaved, easiest first by (score, start), skipping excluded and difficult (EXE, start) keys, under the per-EXE variety rule (2 per unit, 3 per 64 KiB region)"
  - "picker.pilot: the first 5 UFO2P and 5 TACP picks, interleaved"
  - "picker.requeue(difficult, *, matched, callees, pool_empty) (ruling F26)"
  - "picker.matched_starts(exes, *, read): the status.csv seam; a missing table means nothing matched"
affects: [06-25, 06-driver]
actuals:
  tokens: 4392  # chars/4 over the realized code diff (17568 bytes, 2 files, +419)
  tasks: 2
  commits: 4  # measured: git rev-list --count 325c606..b5159fc, before this SUMMARY commit
plan_head_before: 325c6066b67916ec70c794d79ebfabfcea2178c1
plan_head_after: b5159fcb3a10b101a461307a455fd4e2e4fe32d7
tech-stack:
  added: []
  patterns:
    - "The picker is pure: pools, units, status and the difficult list come in as arguments; the one status seam takes its reader as a parameter"
key-files:
  created:
    - tools/reverseapoc/picker.py
    - tests/test_driver_pick.py
  modified:
    - .planning/phases/06-reporting-and-agent-pilot/06-14-PLAN.md
key-decisions:
  - "Ordering within an EXE is (score, start) as the plan says, not ScoreReport's (has __CHK, score, start); a __CHK function can therefore come before a non-__CHK one of higher score. Flagged for the driver plan (06-25) and Phase 7 tuning"
  - "difficult is a Mapping from each capped (EXE, start) to the callees already matched when it was capped, so `requeue` can tell a callee matched since the cap; queue only uses it as a Container of keys"
  - "A candidate whose start has no unit in `units` is refused with PickerError naming the start, rather than sharing an empty unit name"
  - "The variety counts the picks the queue yields, per EXE; pilot's discarded overflow picks of one EXE never affect the other EXE"
  - "Partial rows already in status.csv are not excluded by matched_starts; partial-in-this-pass and capped come from the driver's own pass record (D-09)"
patterns-established:
  - "Picker identity is the (EXE, start) key, the same as status.csv and functions.csv rows"
requirements-completed: [AGT-07, AGT-02]
coverage:
  - id: D1
    description: "pilot gives 5 UFO2P + 5 TACP picks, interleaved, easiest first per EXE; queue continues with the other EXE when one runs out"
    requirement: AGT-07
    verification:
      - kind: unit
        ref: "tests/test_driver_pick.py#test_pilot_interleaves_five_and_five"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_queue_continues_with_the_other_exe_when_one_runs_out"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_pilot_caps_each_exe_at_five"
        status: pass
    human_judgment: false
  - id: D2
    description: "Status awareness: excluded and difficult starts never picked; matched_starts reads status through a seam, a missing status.csv means nothing matched"
    requirement: AGT-07
    verification:
      - kind: unit
        ref: "tests/test_driver_pick.py#test_queue_skips_excluded_and_difficult"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_matched_starts_reads_status_through_the_seam"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_missing_status_means_nothing_matched"
        status: pass
    human_judgment: false
  - id: D3
    description: "Stable order: equal scores by ascending start, whatever order the pool arrives in"
    requirement: AGT-02
    verification:
      - kind: unit
        ref: "tests/test_driver_pick.py#test_equal_scores_order_by_start"
        status: pass
    human_judgment: false
  - id: D4
    description: "Variety rule: at most 2 per unit and 3 per 64 KiB region per EXE; the queue ends instead of breaking the rule; limits are parameters and below 1 refused"
    requirement: AGT-07
    verification:
      - kind: unit
        ref: "tests/test_driver_pick.py#test_at_most_two_per_unit"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_at_most_three_per_region"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_variety_counts_per_exe"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_variety_exhaustion_ends_the_queue"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_variety_limits_are_parameters"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_variety_limits_below_one_are_refused"
        status: pass
    human_judgment: false
  - id: D5
    description: "requeue: every difficult function on an exhausted pool, else only those with a callee matched since the cap"
    requirement: AGT-07
    verification:
      - kind: unit
        ref: "tests/test_driver_pick.py#test_requeue_on_exhausted_pool"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_requeue_on_matched_callee"
        status: pass
    human_judgment: false
duration: 6min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 14: The driver's picker Summary

**`tools/reverseapoc/picker.py`: a pure, status-aware queue over score's P16 candidates. It interleaves UFO2P and TACP, goes easiest first by (score, start), skips matched, capped and partial-in-pass starts, applies D-10's per-EXE variety rule (2 per unit, 3 per 64 KiB region), and gives the 5 + 5 pilot. A `requeue` brings capped functions back when the pool runs out or one of their callees is matched.**

Execution context nonce: 9e44d077205bafaf

## Performance

- **Duration:** about 6 min
- **Started:** 2026-10-25T04:11:30Z
- **Completed:** 2026-10-25T04:16:46Z
- **Tasks:** 2
- **Files modified:** 2 code files (plus this plan's must_haves line, ruling F26)

## Accomplishments
- `queue(pools, *, units, excluded, difficult, max_per_unit=2, max_per_region=3, region_size=0x10000, order=("ufo2p", "tacp"))` yields `Pick`s. It interleaves the EXEs, goes easiest first within each EXE, and keeps the same order on every run.
- The variety rule counts per EXE, using a `start // 0x10000` region. Among UFO2P's eight look-alikes at 0x0008A0E0..0x0008A1C0, only 3 get picked. When the rule blocks everything left, the queue ends.
- `pilot(...)` returns the first 5 UFO2P and 5 TACP picks, interleaved.
- `requeue(difficult, *, matched, callees, pool_empty)` returns the capped functions that are eligible again (D-07).
- `matched_starts(exes, *, read)` is the seam to status.csv. It takes the reader as an argument, so tests can fake it, and a missing table (FileNotFoundError) means nothing is matched. 06-25 can pass 06-11's `read_status` once the two are merged.

## Task Commits

1. **Task 1 (tracer): interleaved 5 + 5 pilot, exclusions, tie order**
   - RED `0b49ddf` (test): collection failed with `ModuleNotFoundError: reverseapoc.picker`, so the feature was absent. This follows the repo's precedent for a new module (04-08, 06-02).
   - GREEN `a93ffb0` (feat): 8 passed. Tracer gate: verify was re-run end to end and passed before Task 2.
2. **Task 2: variety rule and difficult re-queue**
   - RED `f000d54` (test): collection failed with `ImportError: requeue`. I then added only `requeue` and ran the tests again. Every variety test failed on its own assertion (for example `[10, 11, 12, 13, 14, 15, ...] != [10, 11, 50, 51, 52]`), plus `TypeError: unexpected keyword argument 'max_per_unit'`. So the RED was for the intended reason.
   - GREEN `b5159fc` (feat): 18 passed. Host suite: 1616 passed, 217 skipped. ruff clean.

**Plan metadata:** this SUMMARY commit (docs).

## Files Created/Modified
- `tools/reverseapoc/picker.py`: `Pick`, `PickerError`, `queue`, `pilot`, `requeue`, `matched_starts`.
- `tests/test_driver_pick.py`: 18 tests on synthetic candidates (no game bytes).
- `.planning/phases/06-reporting-and-agent-pilot/06-14-PLAN.md`: the must_haves `requeue` line now carries `pool_empty` (ruling F26).

## Decisions Made
See key-decisions in the frontmatter. One of them needs a reviewer to look at it:
- **(score, start) ordering drops the __CHK-first rank.** `ScoreReport.candidates` ranks functions without a __CHK prologue first, because the default `-s` applies to them. The plan states the key (score, start) twice (the action text and the AGT-02 edge must-have), so I followed the plan. If the pilot should keep score's (has __CHK, score, start) rank, that is a one-line change to the sort key in `_exe_picks` plus a test. That call belongs to 06-25 or Phase 7.

## Deviations from Plan

- **Orchestrator ruling F26: one requeue signature.** `requeue(difficult, *, matched, callees, pool_empty)` uses the action's form, and the must_haves line in 06-14-PLAN.md now matches. `test_requeue_on_exhausted_pool` covers the `pool_empty=True`/`False` behaviour.
- **Orchestrator plan note (dispatch): status seam.** I added `matched_starts(exes, *, read)` so status.csv is read through a fakeable seam, and a missing status.csv counts as "nothing matched yet". This is needed because 06-11's status.py is built in the same wave and is not in this base. Tests: `test_matched_starts_reads_status_through_the_seam`, `test_missing_status_means_nothing_matched`.

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Input validation for the variety limits and units**
- **Found during:** Task 2 (and Task 1 for units)
- **Issue:** `region_size=0` would raise ZeroDivisionError deep inside the generator. A limit below 1 would block every pick without saying why. A candidate missing from `units` would otherwise be counted under one shared empty unit.
- **Fix:** `PickerError` names the bad limit or the start that has no unit.
- **Files modified:** tools/reverseapoc/picker.py, tests/test_driver_pick.py
- **Verification:** `test_variety_limits_below_one_are_refused` (3 cases), `test_queue_refuses_a_candidate_without_a_unit`
- **Committed in:** a93ffb0, b5159fc

**2. [Formatting] Test assertion reflowed in the GREEN commit**
- **Found during:** Task 1 GREEN
- **Issue:** `ruff format --check` wanted a different layout for one assertion in the RED test file.
- **Fix:** I split it into a variable and an assert. The behaviour is unchanged.
- **Committed in:** a93ffb0

---

**Total deviations:** 2 orchestrator directions applied (F26, status seam) plus 2 auto-fixes (1 missing critical, 1 formatting).
**Impact on plan:** No scope creep. The picker stays pure, with no I/O.

## Issues Encountered
None.

## User Setup Required
None. No external service configuration is required.

## Next Phase Readiness
- 06-25 (`drive`) can build the pools the way `_cmd_score` does, per EXE: `ScoreReport.candidates`, plus `units` from functions.csv rows (`{row.start: row.unit}`) and `excluded = matched_starts(..., read=<status reader>) | partial-in-pass | capped`. It then calls `pilot` or `queue`.
- Pools are keyed by the lower-case EXE stem (`"ufo2p"`, `"tacp"`), not the manifest's target name `"UFO2P.EXE"`. The driver has to map between the two.
- Edge probe row AGT-07 / unclassified stays **unresolved**, as the plan flagged. The ordering and variety tests pin it.

## Self-Check: PASSED
- FOUND: tools/reverseapoc/picker.py, tests/test_driver_pick.py
- FOUND commits: 0b49ddf, a93ffb0, f000d54, b5159fc (all ancestors of HEAD)
- Acceptance: picker.py contains `def queue(` and `def pilot(`; tests contain `test_at_most_three_per_region` and `test_requeue_on_matched_callee`
- Verification: `uv run pytest -q tests/test_driver_pick.py` 18 passed; `uv run pytest -q` 1616 passed, 217 skipped; `uv run ruff check .` clean
