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
  - "picker.queue -> PickQueue: the EXEs interleaved, easiest first by score's own rank (__CHK, score, start), skipping excluded and difficult (EXE, start) keys, under the per-EXE variety rule (2 per unit, 3 per 64 KiB region); `ended` / `pool_empty(exe)` say why each EXE ended (END_EXHAUSTED or END_BLOCKED)"
  - "picker.pilot: the first 5 UFO2P and 5 TACP picks, interleaved; a short EXE is a PickerError naming it, its count and why it ended"
  - "picker.requeue(difficult, *, matched, callees, pool_empty) (ruling F26)"
  - "picker.matched_starts(exes, *, path_of, read): the status.csv seam; a missing table in an existing config dir means nothing matched, a missing dir is refused, reader errors propagate"
  - "score.Candidate.chk: the __CHK term of score.candidates' rank"
affects: [06-25, 06-driver]
actuals:
  tokens: 6920  # chars/4 over the realized code diff (27678 bytes, 4 files, +605/-1), fix round 1 included
  tasks: 2
  commits: 7  # measured: git rev-list --count 325c606..8ef5059 (4 task commits, 1 docs, 2 fix round 1), before this SUMMARY commit
plan_head_before: 325c6066b67916ec70c794d79ebfabfcea2178c1
plan_head_after: 8ef5059a2bb5921efd50adb0357d9fc1ae456e32
tech-stack:
  added: []
  patterns:
    - "The picker is pure: pools, units, status and the difficult list come in as arguments; the one status seam takes its path and reader as parameters"
    - "A stream that ends says why (PickQueue.ended), so a stopped queue is never mistaken for an empty pool"
key-files:
  created:
    - tools/reverseapoc/picker.py
    - tests/test_driver_pick.py
  modified:
    - tools/reverseapoc/score.py
    - tests/test_score.py
    - .planning/phases/06-reporting-and-agent-pilot/06-14-PLAN.md
key-decisions:
  - "Ordering within an EXE is score's own rank (__CHK, score, start), read from the new Candidate.chk field, never from reason text (fix round 1 ruling I1; D-10's easiest-first governs over the plan's literal (score, start))"
  - "difficult is a Mapping from each capped (EXE, start) to the callees already matched when it was capped, so `requeue` can tell a callee matched since the cap; queue only uses it as a Container of keys"
  - "pilot fails closed: PickerError naming each short EXE, its count of per_exe and its end reason (ruling I2: a raise is simpler for the driver than a shortfall object)"
  - "matched_starts decides 'no table yet' before reading (config/<exe>/ exists, status.csv does not) instead of catching FileNotFoundError, so no reader error is ever swallowed"
  - "Pool keys outside `order` are refused; an `order` entry with no pool is an exhausted EXE"
  - "Units are checked for every non-skipped candidate when the queue is built, before any pick is handed out"
  - "The variety counts the picks the queue yields, per EXE; pilot's discarded overflow picks of one EXE never affect the other EXE"
  - "Partial rows already in status.csv are not excluded by matched_starts; partial-in-this-pass and capped come from the driver's own pass record (D-09)"
patterns-established:
  - "Picker identity is the (EXE, start) key, the same as status.csv and functions.csv rows"
requirements-completed: [AGT-07, AGT-02]
coverage:
  - id: D1
    description: "pilot gives 5 UFO2P + 5 TACP picks, interleaved, easiest first per EXE, and refuses a short EXE naming its count and end reason; queue continues with the other EXE when one runs out"
    requirement: AGT-07
    verification:
      - kind: unit
        ref: "tests/test_driver_pick.py#test_pilot_interleaves_five_and_five"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_queue_continues_with_the_other_exe_when_one_runs_out"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_pilot_refuses_a_short_exe"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_pilot_names_a_variety_shortfall"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_pilot_refuses_per_exe_below_one"
        status: pass
    human_judgment: false
  - id: D2
    description: "Status awareness: excluded and difficult starts never picked; matched_starts reads status through a seam, a missing status.csv in an existing config dir means nothing matched, a missing dir and reader errors are not swallowed; unknown pool keys and unit-less candidates are refused up front"
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
      - kind: unit
        ref: "tests/test_driver_pick.py#test_matched_starts_refuses_an_exe_without_a_config_dir"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_matched_starts_lets_reader_errors_through"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_queue_refuses_pool_keys_outside_order"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_queue_refuses_a_candidate_without_a_unit"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_a_skipped_candidate_needs_no_unit"
        status: pass
    human_judgment: false
  - id: D3
    description: "Stable order by score's own rank: __CHK candidates last; equal (__CHK, score) by ascending start, whatever order the pool arrives in"
    requirement: AGT-02
    verification:
      - kind: unit
        ref: "tests/test_driver_pick.py#test_equal_scores_order_by_start"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_chk_candidates_come_last"
        status: pass
      - kind: unit
        ref: "tests/test_score.py#test_rank_puts_a_chk_caller_after_a_non_caller"
        status: pass
    human_judgment: false
  - id: D4
    description: "Variety rule: at most 2 per unit and 3 per 64 KiB region per EXE (boundary at start // 0x10000); the stream ends instead of breaking the rule and says so; limits are parameters and below 1 refused"
    requirement: AGT-07
    verification:
      - kind: unit
        ref: "tests/test_driver_pick.py#test_at_most_two_per_unit"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_at_most_three_per_region"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_region_boundary_is_start_floor_64k"
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
    description: "requeue: every difficult function on an exhausted pool, else only those with a callee matched since the cap; PickQueue.ended / pool_empty tell an exhausted pool from a variety-blocked one"
    requirement: AGT-07
    verification:
      - kind: unit
        ref: "tests/test_driver_pick.py#test_requeue_on_exhausted_pool"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_requeue_on_matched_callee"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_queue_says_why_each_exe_ended"
        status: pass
      - kind: unit
        ref: "tests/test_driver_pick.py#test_skipped_candidates_do_not_count_as_blocked"
        status: pass
    human_judgment: false
duration: 18min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 14: The driver's picker Summary

**`tools/reverseapoc/picker.py` is a pure, status-aware queue over score's P16 candidates.**
- It interleaves UFO2P and TACP and goes easiest first by score's own rank: __CHK last, then score, then start.
- It skips matched, capped and partial-in-pass starts.
- It applies D-10's per-EXE variety rule (2 per unit, 3 per 64 KiB region) and says why each EXE's stream ended.
- It gives a 5 + 5 pilot that fails closed when an EXE falls short.
- `requeue` brings capped functions back when the pool runs out or one of their callees is matched.

Execution context nonce: 9e44d077205bafaf

## Performance

- **Duration:** about 18 min in total: 6 min for the plan, 12 min for fix round 1
- **Started:** 2026-10-25T04:11:30Z
- **Completed:** 2026-10-25T04:29Z
- **Tasks:** 2, plus fix round 1
- **Files modified:** 4 code/test files, plus this plan's must_haves line (ruling F26)

## Accomplishments
- `queue(pools, *, units, excluded, difficult, max_per_unit=2, max_per_region=3, region_size=0x10000, order=("ufo2p", "tacp"))` returns a `PickQueue`, which iterates `Pick`s:
  - It interleaves the EXEs and goes easiest first within each one by (`Candidate.chk`, score, start).
  - The order is the same on every run.
  - `ended` maps each EXE that has ended to `END_EXHAUSTED` or `END_BLOCKED`. `pool_empty(exe)` feeds `requeue`.
- The variety rule counts per EXE, by `start // 0x10000` region:
  - Of UFO2P's eight look-alikes at 0x0008A0E0..0x0008A1C0, only 3 get picked.
  - When the rule blocks everything left, the EXE's stream ends with `END_BLOCKED`.
- `pilot(...)` returns the first 5 UFO2P and 5 TACP picks, interleaved, or raises `PickerError("pilot short: tacp 2 of 5 (pool exhausted)")`.
- `requeue(difficult, *, matched, callees, pool_empty)` returns the capped functions that are eligible again (D-07).
- `matched_starts(exes, *, path_of, read)` is the seam to status.csv. 06-25 can pass 06-11's `status_path` and `read_status` once the two are merged.

## Task Commits

1. **Task 1 (tracer): interleaved 5 + 5 pilot, exclusions, tie order**
   - RED `0b49ddf` (test): collection failed with `ModuleNotFoundError: reverseapoc.picker`, so the feature was absent. This follows the repo's precedent for a new module (04-08, 06-02).
   - GREEN `a93ffb0` (feat): 8 passed. Tracer gate: I re-ran the verify end to end, and it passed before Task 2.
2. **Task 2: variety rule and difficult re-queue**
   - RED `f000d54` (test): collection failed with `ImportError: requeue`.
   - With only `requeue` added, every variety test failed on its own assertion (for example `[10, 11, 12, 13, 14, 15, ...] != [10, 11, 50, 51, 52]`), plus `TypeError: unexpected keyword argument 'max_per_unit'`.
   - GREEN `b5159fc` (feat): 18 passed.
3. **Plan metadata:** `af68d9b` (docs).
4. **Fix round 1**
   - RED `3e3c45b` (test): test_driver_pick failed at collection with `ImportError: END_BLOCKED`. test_score's new `chk` assertion failed on its own line (1 failed, 22 passed).
   - GREEN `8ef5059` (fix): 29 picker tests and 23 score tests passed. Host suite: 1627 passed, 217 skipped. ruff clean.

## Files Created/Modified
- `tools/reverseapoc/picker.py`: `Pick`, `PickerError`, `PickQueue`, `END_EXHAUSTED`, `END_BLOCKED`, `queue`, `pilot`, `requeue`, `matched_starts`.
- `tools/reverseapoc/score.py`: `Candidate.chk` (default False, set by `candidates`). `to_json` is unchanged.
- `tests/test_driver_pick.py`: 29 tests on synthetic candidates (no game bytes).
- `tests/test_score.py`: `test_rank_puts_a_chk_caller_after_a_non_caller` also pins `Candidate.chk`.
- `.planning/phases/06-reporting-and-agent-pilot/06-14-PLAN.md`: the must_haves `requeue` line now carries `pool_empty` (ruling F26).

## Decisions Made
See key-decisions in the frontmatter. The AGT-02 edge must_have, as built, reads: "candidates with equal (__CHK, score) are ordered by start address ascending, so the queue is stable across runs". Per the ruling, the PLAN file was not edited again.

## Deviations from Plan

- **Orchestrator ruling F26: one requeue signature.** `requeue(difficult, *, matched, callees, pool_empty)` uses the action's form, and the must_haves line in 06-14-PLAN.md now matches. `test_requeue_on_exhausted_pool` covers `pool_empty=True` and `pool_empty=False`.
- **Orchestrator plan note (dispatch): status seam.** I added `matched_starts` so status.csv is read through a fakeable seam, and a missing status.csv counts as "nothing matched yet". 06-11's status.py is not in this base. In fix round 1 the signature became `(exes, *, path_of, read)`; see M1.
- **Orchestrator ruling I1 (fix round 1): score's own rank.** D-10's "easiest-first" governs over the plan's literal (score, start) key.
  - score.py's `Candidate` gains `chk` (from `features.chk`).
  - The picker orders by (`chk`, score, start) and never matches on reason text.
  - Test: `test_chk_candidates_come_last`. test_score now pins the field.
- **Orchestrator ruling I2 (fix round 1): shortfall signal.**
  - `pilot` raises `PickerError` naming each short EXE, its count of `per_exe` and its end reason.
  - `queue` returns a `PickQueue` whose `ended` and `pool_empty(exe)` say whether a pool is exhausted or the variety rule blocks the rest. Candidates skipped as excluded or difficult do not count as blocked.
  - `test_pilot_caps_each_exe_at_five` is replaced by `test_pilot_refuses_a_short_exe`, `test_pilot_names_a_variety_shortfall`, `test_queue_says_why_each_exe_ended` and `test_skipped_candidates_do_not_count_as_blocked`.
- **Review minors (fix round 1):**
  - M1: `matched_starts(exes, *, path_of, read)` checks before reading. config/<exe>/ present and no status.csv means nothing matched. A missing config directory is a `PickerError`, which catches a wrong EXE key. A `ValueError` or a `FileNotFoundError` for any other file, raised by the reader, propagates. Tests: `test_matched_starts_refuses_an_exe_without_a_config_dir`, `test_matched_starts_lets_reader_errors_through[2]`.
  - M2: pool keys outside `order` (for example `"UFO2P.EXE"`) are refused: `test_queue_refuses_pool_keys_outside_order`.
  - M3: units are checked for every non-skipped candidate when `queue` is called: `test_queue_refuses_a_candidate_without_a_unit`, `test_a_skipped_candidate_needs_no_unit`.
  - M4: `per_exe` below 1 is refused: `test_pilot_refuses_per_exe_below_one`.
  - M5: 64 KiB boundary test: `test_region_boundary_is_start_floor_64k`.
  - M6: note only, see Next Phase Readiness. A TODO comment sits on `STATUS_MATCHED`.

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Input validation for the variety limits and units**
- **Found during:** Task 2 (and Task 1 for units)
- **Issue:** without validation:
  - `region_size=0` would raise ZeroDivisionError deep inside the generator;
  - a limit below 1 would block every pick without saying why;
  - a candidate missing from `units` would be counted under one shared empty unit.
- **Fix:** `PickerError` names the bad limit or the start that has no unit.
- **Files modified:** tools/reverseapoc/picker.py, tests/test_driver_pick.py
- **Verification:** `test_variety_limits_below_one_are_refused` (3 cases), `test_queue_refuses_a_candidate_without_a_unit`
- **Committed in:** a93ffb0, b5159fc

**2. [Formatting] Test assertion reflowed in the GREEN commit**
- **Found during:** Task 1 GREEN
- **Issue:** `ruff format --check` wanted a different layout for one assertion in the RED test file.
- **Fix:** I split it into a variable plus an assert. Behaviour is unchanged.
- **Committed in:** a93ffb0

**3. [Rule 1 - Bug, test] Wrong expectation in a fix-round RED test**
- **Found during:** fix round 1 GREEN
- **Issue:** `test_skipped_candidates_do_not_count_as_blocked` expected `ended == {ufo2p: ...}` only. TACP is in `order` with no pool, so it ends exhausted too.
- **Fix:** the test now asserts `ended[ufo2p]` and `pool_empty(tacp)`.
- **Committed in:** 8ef5059

---

**Total deviations:** 4 orchestrator directions (F26, status seam, I1, I2), the 5 review minors M1-M5, and 3 auto-fixes (1 missing critical, 1 formatting, 1 test expectation).
**Impact on plan:** No scope creep. Picking stays pure; the only filesystem access is the existence checks in `matched_starts`. score.py's change is one defaulted field, and its JSON output is unchanged.

## Issues Encountered
- tools/reverseapoc/score.py was already failing `ruff format --check` at base 325c606 (the `assess` loop, L311-312). That is outside this plan's scope, and `ruff check` is clean.

## User Setup Required
None. No external service configuration is required.

## Next Phase Readiness
- 06-25 (`drive`) can build the pools per EXE the way `_cmd_score` does. It needs:
  - `pools`: `ScoreReport.candidates`, which now carry `chk`;
  - `units`: `{row.start: row.unit}` from the functions.csv rows;
  - `excluded`: `matched_starts(..., path_of=<status_path>, read=<read_status>)`, plus the partial-in-pass and capped starts.

  It then calls `pilot` or `queue`, and passes `q.pool_empty(exe)` to `requeue`.
- Pools are keyed by the lower-case EXE stem (`"ufo2p"`, `"tacp"`), not the manifest's target name `"UFO2P.EXE"`. `queue` refuses any other key, and `matched_starts` refuses an EXE with no config directory.
- **TODO for 06-25 (review M6):** switch `picker.STATUS_MATCHED` to 06-11's status.py constant when the two are merged. Also check that 06-11's `read_status` raises something other than a silent success for a malformed table.
- Edge probe row AGT-07 / unclassified stays **unresolved**, as the plan flagged. The ordering and variety tests pin it.

## Fix round 1

| Finding | Ruling / fix | Test | Commit |
|---------|--------------|------|--------|
| I1 sort key drops score's __CHK-last rank | `Candidate.chk` in score.py; picker orders by (`chk`, score, start) | `test_chk_candidates_come_last`, test_score `test_rank_puts_a_chk_caller_after_a_non_caller` | 3e3c45b (RED), 8ef5059 |
| I2 pilot silently short; queue silent on why it ended | `pilot` raises PickerError per short EXE with count and end reason; `PickQueue.ended` / `pool_empty` | `test_pilot_refuses_a_short_exe`, `test_pilot_names_a_variety_shortfall`, `test_queue_says_why_each_exe_ended`, `test_skipped_candidates_do_not_count_as_blocked` | 3e3c45b, 8ef5059 |
| M1 any FileNotFoundError meant nothing matched | `matched_starts(exes, *, path_of, read)`: existence check first, missing config dir refused, reader errors propagate | `test_missing_status_means_nothing_matched`, `test_matched_starts_refuses_an_exe_without_a_config_dir`, `test_matched_starts_lets_reader_errors_through` (ValueError, other FileNotFoundError) | 3e3c45b, 8ef5059 |
| M2 unknown pool keys ignored | refused with PickerError | `test_queue_refuses_pool_keys_outside_order` | 3e3c45b, 8ef5059 |
| M3 unit check lazy, mid-stream | checked in `queue` before any pick | `test_queue_refuses_a_candidate_without_a_unit`, `test_a_skipped_candidate_needs_no_unit` | 3e3c45b, 8ef5059 |
| M4 per_exe unvalidated | below 1 refused | `test_pilot_refuses_per_exe_below_one` | 3e3c45b, 8ef5059 |
| M5 no region-boundary test | added | `test_region_boundary_is_start_floor_64k` | 3e3c45b |
| M6 STATUS_MATCHED duplicates 06-11 | TODO in picker.py and in Next Phase Readiness for 06-25 | none (note only) | 8ef5059 |

Verification after the fix round:
- `uv run pytest -q tests/test_driver_pick.py tests/test_score.py`: 52 passed.
- `uv run pytest -q`: 1627 passed, 217 skipped.
- `uv run ruff check .`: clean.
- Docker was not run.

## Self-Check: PASSED
- FOUND: tools/reverseapoc/picker.py, tests/test_driver_pick.py
- FOUND commits, all ancestors of HEAD: 0b49ddf, a93ffb0, f000d54, b5159fc, af68d9b, 3e3c45b, 8ef5059
- Acceptance: picker.py contains `def queue(` and `def pilot(`. The tests contain `test_at_most_three_per_region` and `test_requeue_on_matched_callee`.
- Verification results are listed under "Fix round 1" above.
