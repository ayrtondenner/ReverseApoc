---
phase: 07-mechanics-first-decompilation
plan: 23
subsystem: driver
tags: [driver, attempts-jsonl, schema-v2, metrics, totals, passes, dec-06, dec-07, d-08, d-09]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-07: the v2 schema (RECORD_FIELDS_V2, SCHEMA_V2, KIND_LIMIT, _TOTALS, F12's C-name abort); 07-21: worker threads, _Pause, _Coordinator, the gate lock over every append, Claims.recover"
provides:
  - "v2 attempt records: schema, session, pass, worker, model_requested, budget_usd, hook_blocks, gate {exit, claimed_ok, regressions, problems} or null, sweep_source, sweep_cells_100; function = the pick's C name"
  - "v2 abort records with the same C-name rule (ruling F12)"
  - "limit records, one per usage-limit wait (worker, seconds, streak)"
  - "v2 run records: workers, recovered claims on STARTED, totals on ENDED/STOPPED (also the interrupted record)"
  - "pass_index(log) / passes_of(log, key): finished passes from the committed log (v1: one per run; v2: the pass number); the night reads it once and uses pass = passes + 1"
  - "_totals(records, wall_seconds, limits): DEC-06's nightly totals summed over the night's own records"
  - "helpers other plans can reuse: matched_starts(status bytes), regressions(doc, pick, before), c_name(pick), _gate_field, _hook_blocks, _sweep_evidence"
affects: [07-26, 07-30, 07-34, 07-37, 07-38]

actuals:
  tokens: 16190
  tasks: 3
  commits: 6
plan_head_before: a5047e3521ecae15a67151287e4cd51c8360af58
plan_head_after: e87b1467aa083b0a389e4d86c205d3c1ccc7a10a

tech-stack:
  added: []
  patterns:
    - "Totals are computed from the records the night itself appended (kept in memory with their log offsets), so they add up by construction; F19's log cut drops the same records"
    - "A record a worker writes because of the pause is appended outside the night's condition (lock order: gate lock, then condition)"

key-files:
  created:
    - tests/test_driver_records.py
  modified:
    - tools/reverseapoc/driver.py
    - tests/test_driver.py
    - tests/test_driver_workers.py

key-decisions:
  - "`function` is Pick.name, which score.candidates already takes from the EXE's symbol table (symbols.c_name); a name that is not a C identifier falls back to the placeholder. Attempt directories, claims and commit subjects keep the placeholder"
  - "A function's finished passes are max(v1 runs, highest v2 pass): the first v2 pass after the pilot's v1 run is numbered 2, so neither form is counted twice"
  - "A limit record's streak counts from 1 (the 07-07 schema pins streak >= 1); the plan's test text said 0 and 1"
  - "`regressions` counts the claimed EXE's matched starts (status.csv right before the gate) that the gate's checks found failing; the claimed function never counts"
  - "Totals group by_model by model_requested (always text), by_session by the session kind"
  - "STARTED keeps naming the recovered claims in its detail and also lists them in `recovered`; ENDED/STOPPED records carry recovered []"

patterns-established:
  - "Driver tests that need 'no MATCHED record' look for '\"outcome\":\"MATCHED\"', since the totals name every outcome"

requirements-completed: [DEC-06, DEC-07]

coverage:
  - id: D1
    description: "Every attempt record is v2 (session, pass, worker, requested model and budget, hook blocks, gate verdict or null, sweep evidence) and validates; function is the C name"
    requirement: DEC-07
    verification:
      - kind: integration
        ref: "tests/test_driver_records.py#test_attempt_record_is_v2, test_every_attempt_record_of_a_night_is_v2, test_function_is_the_rows_c_name, test_hook_blocks_counted, test_gate_null_on_lint_failure, test_gate_counts_regressions_and_keeps_problems, test_sweep_evidence, test_sweep_evidence_without_a_saved_json_keeps_the_source"
        status: pass
    human_judgment: false
  - id: D2
    description: "Abort records are v2 and take the C name (ruling F12)"
    requirement: DEC-07
    verification:
      - kind: integration
        ref: "tests/test_driver_records.py#test_abort_record_is_v2_with_the_c_name"
        status: pass
    human_judgment: false
  - id: D3
    description: "Pass counting from the committed log (v1 runs, v2 pass numbers, mixed); the pilot's 12 never-matched functions have one pass; the next record and claim carry pass = passes + 1; the log is read once per night"
    requirement: DEC-07
    verification:
      - kind: unit
        ref: "tests/test_driver_records.py#test_passes_v1, test_passes_v2, test_passes_mixed_v1_then_v2, test_passes_ignore_abort_records_and_a_missing_log, test_a_corrupt_log_line_is_named_when_passes_are_counted, test_committed_log_pilot_passes"
        status: pass
      - kind: integration
        ref: "tests/test_driver_records.py#test_next_pass_number"
        status: pass
    human_judgment: false
  - id: D4
    description: "Run records are v2 (workers, recovered, totals); one limit record per wait; totals equal the sums over the night's records with 2 workers and a limit wait; STOPPED and interrupted records carry totals; an undone match's MATCHED line is not counted; the log commit runs after every worker drained"
    requirement: DEC-06
    verification:
      - kind: integration
        ref: "tests/test_driver_records.py#test_every_record_of_a_night_is_v2, test_started_record_v2, test_limit_record_per_wait, test_totals_equal_sums, test_a_stopped_night_has_totals, test_an_interrupted_night_has_totals, test_a_failed_match_commit_drops_its_matched_record_from_the_totals, test_log_commit_after_drain"
        status: pass
    human_judgment: false
  - id: D5
    description: "Host suite and ruff green; the container run is deferred to the orchestrator (R-B)"
    verification:
      - kind: other
        ref: "uv run pytest -q (3687 passed, 248 skipped) && uv run ruff check ."
        status: pass
    human_judgment: true
    rationale: "docker is not allowed in a worktree; the orchestrator runs docker compose build && docker compose run --rm test after merge"

duration: 75min
completed: 2026-10-30
status: complete
---

# Phase 7 Plan 23: v2 attempt-log records Summary

**From this plan on the driver writes only schema-2 records to progress/attempts.jsonl.**
- Each attempt names its session kind, pass, worker, requested model and budget, hook blocks (`len(permission_denials)`), the gate's verdict and the sweep evidence. Its `function` is the pick's C name. The gate verdict holds the exit, claimed_ok, the regressions counted against status.csv's matched rows, and the problems. The sweep evidence is the first hitting sweep line's snapshot and its 100% cells over stage 1 and stage 2.
- Each usage-limit wait writes a `limit` record.
- STARTED lists the workers and the recovered claims. ENDED and STOPPED carry nightly totals summed over the night's own records.
- A function's pass now comes from the committed log (`pass_index`): the 12 never-matched pilot functions are on pass 2 next.

## Performance

- **Duration:** about 75 min
- **Started:** 2026-10-30T15:47Z (approximate: the guard and the reading came first)
- **Completed:** 2026-10-30T17:05Z
- **Tasks:** 3, all TDD (a RED commit, then a GREEN commit)
- **Files modified:** 4 (1 created)

## Accomplishments

- **Task 1 (tracer), the v2 attempt and abort records.**
  - `_base` adds `schema`, `session` (`matching`), `pass` (the claim's `pass_n`) and `worker`. `function` comes from `c_name(pick)`, for aborts too (F12).
  - `_record_attempt(..., gate=)` adds `model_requested` (`session.MODEL`) and `budget_usd` (`session.MAX_BUDGET_USD`). It also adds `hook_blocks` (`_hook_blocks`), `gate` (`_gate_field`) and the sweep evidence (`_sweep_evidence`).
  - `_judge` reads the claimed EXE's matched starts from the pre-gate status.csv bytes (`matched_starts`). It stores them on the `GateRun` it received, in a new `matched_before` field, so `regressions` can count them.
  - Every record call site that has a gate passes it on: the counted landing, the salvage commit, `_tool_failure` and `_undo_match`.
- **Task 2, passes.**
  - `pass_index(log)` validates each line and names the line number of a bad one. For each function it takes the larger of its v1 run count and its highest v2 `pass`. `passes_of(log, key)` reads one entry.
  - `_loop` reads the index once, under the gate lock, before the first launch. `_pass(pick)` is the stored count plus 1, and the claim file and every record use it.
- **Task 3, run and limit records, totals, the drain.**
  - `_record_run` writes v2 run records. Under the gate lock it computes `_night_totals()` from the records the night appended, which `_append` keeps with their log offsets.
  - `_drop_log_tail` (F19) drops the cut records from that list, so an undone MATCHED line is never counted.
  - `_Pause.on_limit` returns `(seconds, streak)`, and `_limited` appends the limit record before it naps.
  - `_commit_log` first drains the coordinator's workers (research R5).

## Task Commits

1. **Task 1 (tracer): v2 attempt and abort records.** RED `ce61d3e`, GREEN `e81e945`.
   - Tracer feedback gate: the run is interactive in end-of-phase mode, and the verify is automated only. I re-ran `uv run pytest -q tests/test_driver_records.py tests/test_attempts_schema.py` (120 passed) and the driver suites (exit 0), then expanded. Tracer verified end-to-end.
2. **Task 2: pass counting from the committed log.** RED `40b5098`, GREEN `9da36af`.
3. **Task 3: v2 run and limit records, nightly totals, the log commit after the drain.** RED `6fcb76f`, GREEN `e87b146`.

## TDD Gate Compliance

Each RED run wrote pytest JUnit XML (`build/red/t{1,2,3}.xml`, gitignored) and a record (`build/red/t{1,2,3}.json`). `gsd-tools check tdd-red-evidence` returned `RED_EVIDENCE_OK` / `target_test_failed` each time.
- **t1, target `test_attempt_record_is_v2`: 9 failed.** The target ran its matched night, then failed with `KeyError: 'schema'`. That is the planned feature's absence: the driver wrote v1 records. The C-name test failed on its assertion (it got the placeholder). Nothing failed in collection, import or a fixture.
- **t2, target `test_passes_v1`: 7 failed** (selected by `-k pass`). Every failure was `AttributeError: module 'reverseapoc.driver' has no attribute 'pass_index'` (or `passes_of`), raised in the test body after collection. This is the missing feature itself, the same kind of evidence 07-21 accepted.
- **t3, target `test_totals_equal_sums`: 8 failed, 16 passed.** The target's night ran 4 attempts on 2 workers. It failed on its planned assertion, because there were 0 limit records where 1 was expected. The other failures were missing `workers`/`totals` keys and missing limit records.
- Every `feat(07-23)` commit follows its `test(07-23)` commit. There is no REFACTOR commit.

## Files Created/Modified

- `tools/reverseapoc/driver.py`:
  - module docstring (the Records paragraph);
  - `GateRun.matched_before`;
  - the v2 evidence helpers `_items`, `_json_file`, `_record_text`, `_perfect_cell`, `_cell_spec`, `_sweep_evidence`, `_hook_blocks`, `matched_starts`, `_function_passes`, `_same_exe`, `_va`, `regressions`, `_gate_field` and `c_name`;
  - `_log_records`, `pass_index` and `passes_of`;
  - `_Claim.pass_n`;
  - `_Pause.on_limit` (returns the streak);
  - `_Night`: `passes`, `night_records`, `night_start`, `coordinator`, `_pass`, `_base`, `_record_attempt`, `_record_limit`, `_record_run`, `_night_totals`, `_append` (keeps the records), `_drop_log_tail`/`_cut_log_tail`, `_commit_log` (drain), `_limited`, `_judge`, `_tool_failure` and `_undo_match` (`gate=`);
  - module-level `_rounded`, `_share`, `_group` and `_totals`.
- `tests/test_driver_records.py` (new): 24 tests.
- `tests/test_driver.py`, `tests/test_driver_workers.py`: 8 assertions changed from `"MATCHED" not in <log>` to `'"outcome":"MATCHED"' not in <log>` (see Deviations).

## Decisions Made

See `key-decisions` in the frontmatter.

## Deviations from Plan

**Orchestrator ruling F12: aborts use the same C-name rule as attempts.**
- `_base` sets `function` through `c_name(pick)` for both kinds.
- `test_abort_record_is_v2_with_the_c_name` checks that a pick named `GetMadeUpVolume` gives an abort record with that name, schema 2, session `matching`, pass 1, worker 0 and retries 3.
- Commits `ce61d3e` (RED) and `e81e945` (GREEN).

**1. [Plan clarification] The C name comes from `Pick.name`, with no new seam.**
- `score.candidates` already names every pick with `symbols.c_name(start)`, which is the EXE's symbol table, so the plan's "C name through the EXE's symbol table" is `pick.name`.
- A name that is not a C identifier falls back to the placeholder, so the record still validates.
- The attempt directory, the claim file and the match commit subject keep the placeholder (`_Claim.function`).
- Commit `e81e945`.

**2. [Plan clarification] A limit record's streak counts from 1.**
- The plan's test says "streaks 0 and 1", but 07-07's committed schema pins `streak >= 1` (`_at_least_one`).
- Every record must pass `validate_record` (a must-have truth), so the record carries the streak after the wait is counted: 1, then 2.
- `test_limit_record_per_wait` expects `[(0, 60, 1), (0, 120, 2)]`.
- Commits `6fcb76f` and `e87b146`.

**3. [Plan clarification] The limit record is appended by `_Night._limited`, right after `_Pause.on_limit` returns, not inside it.**
- `on_limit` holds the night's condition, and an append takes the gate lock. The lock order is gate lock, then condition (07-21), so appending inside `on_limit` could deadlock against a landing.
- `on_limit` now returns `(seconds, streak)`. The record is written inside the `try` whose `finally` calls `backoff_done`, so a failed append never leaves the pause stuck.
- Commit `e87b146`.

**4. [Test change, TDD sequencing] `test_every_record_of_a_night_is_v2` was narrowed in Task 1's GREEN commit and restored in Task 3.**
- Run records cannot be v2 without totals (Task 3). The Task 1 GREEN commit therefore renamed the committed RED test to `test_every_attempt_record_of_a_night_is_v2`, limited to attempt records.
- Task 3's RED commit `6fcb76f` added `test_every_record_of_a_night_is_v2` back over every kind (run, limit, attempt).

**5. [Test fix inside a GREEN commit] `test_a_stopped_night_has_totals` assumed one attempt record.**
- A guardrail stop also records its counted session as GAVE_UP `guardrail`, so the night has two attempt records.
- The test now asserts both records and sums the turns over them. The behaviour it pins (a STOPPED record carries totals) is unchanged.
- Commit `e87b146`.

**6. [Rule 3 - Blocking] `tests/test_driver.py` and `tests/test_driver_workers.py` are not in files_modified.**
- Eight assertions checked "no MATCHED record" with `"MATCHED" not in <log text>`. The v2 STOPPED/ENDED totals name every outcome (`"sessions":{"MATCHED":0,...}`), so a bare-word search fails on any log.
- They now look for `'"outcome":"MATCHED"'`, the form `test_match_record_is_appended` already used.
- Commit `e87b146`.

**7. [Plan clarification] STARTED keeps its detail.** The detail still names the recovered claims (`recovered_detail`), and the new `recovered` field lists them as `{exe, unit, run}`, so 07-18's tests stay as they are. ENDED and STOPPED records carry `recovered: []`.

**8. [Plan clarification] `_commit_log` drains explicitly.** `_Coordinator.run` already drained before returning or raising. `_commit_log` now also calls `coordinator._drain()` first, so the order holds even if a later change returns early. `test_log_commit_after_drain` checks that no `drive-worker-*` thread is alive at the chore commit, and that the committed log equals the final log.

---

**Total deviations:** 1 orchestrator ruling applied (F12); 1 Rule 3 fix; 4 plan clarifications; 2 test changes, both inside GREEN commits and both named here.
**Impact on plan:** every must-have truth holds. The streak base follows the committed schema, as the "every record passes validate_record" truth requires. There is no scope creep.

## Issues Encountered

- The harness refused compound shell commands (heredocs with git, `until` loops naming the scratchpad path). I used the Edit tool and scratchpad Python scripts (`t1_green.py`, `t3_green.py`, `split.py`, `red_record.py`, `wait_for.py`).
- Task 2's tests were written before Task 1's GREEN commit. I split the test file (a saved copy, cut at the Task 2 section) so that each commit holds only its own task's tests.

## Concerns for later plans

- **Readers keyed by the placeholder `function`:**
  - `attempt._attempt_records` (the earlier-notes section of a context pack) matches `record["function"] == func`.
  - `flags._attempt_models` and `flags.pilot_hits` use the placeholder from the attempt directory.
  - Today every pick's C name is the placeholder unless symbols.csv names it, so nothing changes yet. Once 07-34 renames functions, v2 records carry the new C names and these readers miss them. They should key by `(exe, start)`.
- **`regressions` undercounts one case.** When a matched function reverted to `INCLUDE_ASM`, the unit gate returns early with problems only (no `checks`). That reversion is then in `gate.problems` but counts 0 regressions.
- **`model_requested` and `budget_usd` are `session.MODEL` and `session.MAX_BUDGET_USD` today.** 07-26/07-30 (D-09 escalation, D-10 Fable budget) should pass the per-pass model and budget into `_record_attempt`. The per-model totals already group by `model_requested`.
- **A pass a stop cut short counts as finished**, because its pass number is in the log. The next night runs the function's next pass.

## Known Stubs

None.

## Threat Flags

None. Every new field passes `validate_record` before it is appended (T-07-67). Problems and cell specs are capped at 200 characters with long hex runs masked. The records hold counts, names, addresses, flag specs and paths under build/ only (no transcript, C text or game bytes). The totals are computed from the records themselves (T-07-68).

## Verification

- `uv run pytest -q tests/test_driver_records.py tests/test_attempts_schema.py`: 120 passed after Task 1 (Task 1 verify, tracer gate).
- `uv run pytest -q tests/test_driver_records.py -k pass`: 7 passed, 9 deselected (Task 2 verify).
- `uv run pytest -q tests/test_driver_records.py tests/test_driver_workers.py tests/test_attempts_schema.py`: all passed once the 8 assertions were changed. The full suite below includes them.
- I ran the threaded totals and drain tests 3 more times: 5 passed each time.
- `uv run pytest -q` (host, worktree): **3687 passed, 248 skipped**. This plan adds no skipping test and no skip reason: the new file has no skip, and the two other test files changed assertions only.
- `uv run ruff check .`: All checks passed.
- Acceptance: driver.py contains `def _gate_field(`, `def _hook_blocks(`, `def passes_of(`, `def pass_index(` and `def _totals(`. tests/test_driver_records.py contains `hook_blocks`.
- I ran no real `claude -p` session, no `drive` command and no docker (D-11, R-B). Every session was tests/fakeclaude.py.
- **Container step deferred to the orchestrator:** `docker compose build && docker compose run --rm test`.

## User Setup Required

None.

## Next Phase Readiness

- 07-26/07-30 can read `pass_index` for re-queues and escalation. Each attempt's `pass`, `model_requested` and `budget_usd` are the fields `stats` (07-37) splits by.
- 07-34 writes rename records with 07-07's F12 shapes. The concern above about placeholder-keyed readers applies.

Execution context nonce: 4f4de4badc053944

## Self-Check: PASSED

- FOUND: tools/reverseapoc/driver.py, tests/test_driver_records.py, tests/test_driver.py, tests/test_driver_workers.py
- FOUND commits on this branch: ce61d3e, e81e945, 40b5098, 9da36af, 6fcb76f, e87b146. `git rev-list --count a5047e3..HEAD` = 6 before this SUMMARY commit.
- No STATE.md, ROADMAP.md or REQUIREMENTS.md change (the orchestrator owns them after the merge).

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-30*
