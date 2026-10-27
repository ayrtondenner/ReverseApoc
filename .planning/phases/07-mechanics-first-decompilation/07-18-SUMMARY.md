---
phase: 07-mechanics-first-decompilation
plan: 18
subsystem: driver
tags: [driver, locks, claims, d-06, d-24, d-27, concurrency, git]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-13: private views, the landing section (_land/_judge/_commit_match/_undo_match), the _Ledger and _Night._append as the one writer of attempts.jsonl, F19's log truncation"
provides:
  - "tools/reverseapoc/locks.py: LockHeld, ProcessLock (msvcrt LK_NBLCK / flock LOCK_NB on an a+b file), DRIVE_LOCK = build/driver/drive.lock"
  - "_Night.run holds drive.lock for the night; held elsewhere -> REFUSED 'drive lock' (exit 2), no record"
  - "driver.Claims(root, run): take(record) (O_EXCL, ten keys), release(exe, unit), recover() (drive.lock held only)"
  - "driver.CLAIMS_DIR, CLAIM_KEYS, STALE_CLAIMS, recovered_detail(); STARTED detail names recovered claims"
  - "_Night.gate_lock (RLock) around the landing section, gate --partial and every _append; _Night.git_lock and _Night._git for every driver git call"
  - "GIT_OPTIONAL_LOCKS=0 in git_runner's env and every session env; _commit_with_retry (one retry of git add / git commit on index.lock)"
affects: [07-21, 07-23, 07-24, 07-31, 07-39]

actuals:
  tokens: 15200
  tasks: 3
  commits: 6
plan_head_before: 945dd716d7fe95aab6025b64ccd7a0b358685783
plan_head_after: 3f35e7447fe8ded1ba8bcfbde1d995f6eb6b4dd4

tech-stack:
  added: []
  patterns:
    - "Liveness is an OS lock held for the process's life (locks.ProcessLock); never a PID probe"
    - "A unit is owned through one O_EXCL claim file; the reset of the unit happens before the claim is released"
    - "Every shared write and every record append runs under _Night.gate_lock; every driver git call under _Night.git_lock (_Night._git)"

key-files:
  created:
    - tools/reverseapoc/locks.py
    - tests/test_locks.py
    - tests/test_driver_workers.py
  modified:
    - tools/reverseapoc/driver.py
    - tests/test_driver.py

key-decisions:
  - "gate_lock is a threading.RLock, not a Lock: the landing section appends its own attempt record through _append, which also takes the gate lock"
  - "The gate lock covers the whole of _counted's and _salvage's landing (copy, lint, gate, commit or undo, reset, gate --partial, the record), so F19's truncation can only drop its own MATCHED line"
  - "Claims.recover enforces 'drive.lock held' by probing the lock with a second ProcessLock: if the probe gets it, nobody holds it and recover refuses"
  - "A claim that cannot be read is stale with run 'unknown'; a claim of the current run is left in place (the plan's rule)"
  - "The index.lock retry waits INDEX_LOCK_WAIT_S = 1 s through Deps.sleep; only stderr naming index.lock is retried; the chore commit uses the same retry"
  - "commit_paths is removed; _Night._commit_with_retry is the one commit path"

patterns-established:
  - "Another worker in tests is a thread of the same _Night appending through _Night._append (tests/test_driver_workers.py)"
  - "_held_elsewhere(lock): a lock is 'held' when another thread cannot take it, which works for an RLock"

requirements-completed: [DEC-02]

coverage:
  - id: D1
    description: "ProcessLock is exclusive (also within one process), freed by the kernel when the holder exits; DRIVE_LOCK path"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_locks.py#test_process_lock_is_exclusive, test_process_lock_freed_on_exit, test_process_lock_context_raises_lock_held, test_process_lock_release_is_idempotent_and_keeps_the_file, test_drive_lock_path"
        status: pass
    human_judgment: false
  - id: D2
    description: "drive holds drive.lock for the night; a second drive is REFUSED (exit 2) naming the lock with no run record"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_driver_workers.py#test_second_drive_refused, test_drive_lock_is_held_for_the_night_and_freed_after"
        status: pass
    human_judgment: false
  - id: D3
    description: "One O_EXCL claim file per unit with ten keys, held through session and gate, released after the landing decision and on a stop; 8-thread race has one winner"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_driver_workers.py#test_drive_claims_and_releases, test_claim_is_released_when_the_night_stops, test_claim_race_one_winner"
        status: pass
    human_judgment: false
  - id: D4
    description: "Stale claims of another run moved to build/driver/<run>/stale-claims/ and named in STARTED; recover refuses without drive.lock; no os-module kill call"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_driver_workers.py#test_stale_claim_recovered, test_unreadable_stale_claim_is_recovered_too, test_no_stale_claim_leaves_the_started_detail_empty, test_stale_recover_needs_the_drive_lock, test_stale_recover_returns_old_claims_and_keeps_the_current_runs, test_no_pid_probe"
        status: pass
    human_judgment: false
  - id: D5
    description: "Gate lock over the landing, gate --partial and every append (incl. the F19 undo window); git lock over every driver git call; GIT_OPTIONAL_LOCKS=0; index.lock retry once"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_driver_workers.py#test_landing_runs_under_the_gate_lock, test_partial_gate_under_gate_lock, test_every_record_append_holds_the_gate_lock, test_gate_lock_keeps_other_appends_out_of_the_match_undo_window, test_git_calls_serialised, test_every_driver_git_call_holds_the_git_lock, test_optional_locks_off, test_index_lock_retry, test_index_lock_retry_covers_git_add, test_index_lock_twice_undoes_the_match, test_other_commit_failures_are_not_retried"
        status: pass
    human_judgment: false
  - id: D6
    description: "Host suite and ruff green; the container run is deferred to the orchestrator (R-B)"
    verification:
      - kind: other
        ref: "uv run pytest -q (3181 passed, 247 skipped) && uv run ruff check ."
        status: pass
    human_judgment: true
    rationale: "docker is not allowed in a worktree; the orchestrator runs docker compose build && docker compose run --rm test after merge"

duration: 30min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 18: Claims and locks for the driver Summary

**`reverseapoc drive` now holds `build/driver/drive.lock` (a kernel-freed OS lock from the new `locks.py`) for the whole night and refuses a second drive with exit 2. Each attempt owns its unit through one O_EXCL claim file under `build/driver/claims/`, and claims left by a dead run are moved to `build/driver/<run>/stale-claims/` and named in STARTED. A reentrant gate lock covers the landing section, `gate --partial` and every record append, and a git lock covers every driver git call. Git and sessions run with `GIT_OPTIONAL_LOCKS=0`, and `git add`/`git commit` retry once on an index.lock error before the match is undone.**

## Performance

- **Duration:** about 30 min
- **Started:** 2026-10-27T19:23Z
- **Completed:** 2026-10-27T19:53Z
- **Tasks:** 3, all TDD: a RED commit, then a GREEN commit
- **Files modified:** 5 (3 created, 2 modified)

## Accomplishments

- **locks.py (Task 1, D-24).** `ProcessLock(path)` opens the file "a+b" and takes one non-blocking lock: msvcrt `LK_NBLCK` on byte 0, or `flock(LOCK_EX | LOCK_NB)`. It has `try_acquire()`, `release()` and a `with` form that raises `LockHeld`. Two objects on one path conflict even inside one process. `DRIVE_LOCK = build/driver/drive.lock`. No PID is probed.
- **drive.lock (Task 1, D-06).** `_Night.run` takes the lock before the outputs check and the STARTED record, and releases it when the night ends (`_run_locked` holds the old body). If another holder has it, the night returns REFUSED `drive lock` with "another reverseapoc drive is running (build/driver/drive.lock is held)". It writes no record and launches nothing.
- **Claims (Tasks 1-2, D-06).**
  - `Claims.take` creates `build/driver/claims/<exe>__<unit>.json` with `_O_NEW`. The file holds `{run, worker, exe, unit, function, start, kind, pass, model, claimed_at}`, with `claimed_at` in UTC ISO. A half-written claim is unlinked.
  - Each attempt (`_guarded`) takes its unit's claim before its first view and releases it after the landing decision, also when the night stops. The reset runs before the release.
  - `Claims.recover()` refuses unless drive.lock is held. It moves every claim of another run (an unreadable one counts as run "unknown") into the run's `stale-claims/`. `recovered_detail` puts "recovered stale claims: ufo2p/u_x (run old)" in the STARTED record's `detail`; 07-23 moves this to the v2 `recovered` field. A failed recovery refuses the start.
- **Gate lock (Tasks 1 and 3, D-27 P4).** `_Night.gate_lock` (an RLock) covers:
  - all of `_counted` after the session count: land, lint, gate, commit or undo, reset, `gate --partial` and the attempt record;
  - all of `_salvage`;
  - every `_append`.
  Because of this, another worker's record waits for the whole F19 window, from the MATCHED append to the undo's truncation. `test_gate_lock_keeps_other_appends_out_of_the_match_undo_window` proves it with a real second thread.
- **Git lock (Task 3).** `_Night._git` runs `deps.git` under `_Night.git_lock`. Every `_Night` git call uses it, and so do the canary's `probe` calls.
- **GIT_OPTIONAL_LOCKS=0.** `git_runner` sets it in the given env or in a copy of `os.environ`, and `_Claim.env` sets it for sessions.
- **Index.lock retry.** `_commit_with_retry` replaces `commit_paths`. `_git_retry` retries `git add` or `git commit` once, after `INDEX_LOCK_WAIT_S` (1 s, through `Deps.sleep`), when git's stderr names index.lock. A second failure, or any other failure, is a DriverError, and the match is undone as before.

## Task Commits

1. **Task 1 (tracer): drive.lock, unit claims, the landing under the gate lock.** RED `1c128c1`, GREEN `5657280`.
   - Tracer feedback gate: the run is interactive, in end-of-phase mode, with an automated-only verify.
   - I re-ran `uv run pytest -q tests/test_locks.py tests/test_driver_workers.py tests/test_driver.py tests/test_drive.py`: 244 passed, 2 skipped, the pre-existing skips. Then I expanded.
2. **Task 2: stale-claim recovery, the O_EXCL race, the no-PID-probe guard.** RED `3cf68be`, GREEN `23d9ec5`.
3. **Task 3: the git lock, GIT_OPTIONAL_LOCKS=0, the index.lock retry, appends under the gate lock.** RED `a69df09`, GREEN `3f35e74`.

## TDD evidence (RED)

Each RED run wrote pytest JUnit XML (`build/red/t{1,2,3}.xml`, gitignored). `gsd-tools check tdd-red-evidence` returned `RED_EVIDENCE_OK` / `target_test_failed` each time.

- **t1, target `test_drive_claims_and_releases`: 9 failed, 1 passed.**
  - The target failed on its assertion "no claim while the session ran".
  - The other driver tests failed for the planned reasons: no `gate_lock`, a night that still ran, and so on.
  - The five `test_locks.py` tests, and `test_second_drive_refused`, failed with `ModuleNotFoundError` for `reverseapoc.locks`. That module is the planned new artifact, so this is the expected absence, not a harness fault. The imports sit inside the test bodies, so collection succeeded.
  - The one pass was `test_claim_is_released_when_the_night_stops`, vacuous before any claim existed.
  - Semantic assessment: the target ran and failed on the planned behaviour.
- **t2, target `test_stale_claim_recovered`: 4 failed, 3 passed.**
  - The target failed with an empty STARTED detail and no move.
  - `recover` was missing in the other failures.
  - Passes: `test_claim_race_one_winner` (pins Task 1's O_EXCL take), `test_no_pid_probe` (a guard on code that already complies), and `test_no_stale_claim_leaves_the_started_detail_empty` (pins the empty detail).
- **t3, target `test_gate_lock_keeps_other_appends_out_of_the_match_undo_window`: 8 failed, 14 passed.**
  - The target failed with `blocked == [False]`: the other worker's append ran inside the landing window, and F19's truncation dropped it.
  - The other failures:
    - no `_git` / `git_lock`;
    - no GIT_OPTIONAL_LOCKS;
    - no retry: the match was undone, and with 2 lock failures the chore commit's DriverError escaped `drive()`;
    - the STARTED and ENDED appends ran outside the gate lock.
  - Passes: the earlier tasks' tests, plus two pins: `test_partial_gate_under_gate_lock` (already under Task 1's lock) and `test_other_commit_failures_are_not_retried`.

## Files Created/Modified

- `tools/reverseapoc/locks.py` (new): `LockHeld`, `ProcessLock`, `DRIVE_LOCK`.
- `tools/reverseapoc/driver.py`:
  - module docstring;
  - new constants `CLAIMS_DIR`, `CLAIM_KEYS`, `STALE_CLAIMS`, `OPTIONAL_LOCKS`, `INDEX_LOCK`, `INDEX_LOCK_WAIT_S`;
  - `git_runner` env;
  - `_git_stdout`;
  - `Claims`, `_claim_run`, `recovered_detail`;
  - `_Claim.env`;
  - `_Night`: `claims`, `gate_lock`, `git_lock`, `run`/`_run_locked`, `_claimed`, `_guarded`, `_git`, `_git_retry`, `_commit_with_retry`, `_salvage`, `_counted` and `_append`;
  - `commit_paths` removed.
- `tests/test_locks.py` (new): 5 tests.
- `tests/test_driver_workers.py` (new): 22 tests.
- `tests/test_driver.py`: one test's lock count and two docstrings.

## Decisions Made

See `key-decisions` in the frontmatter.

## Deviations from Plan

No orchestrator ruling applied: rulings.md has no 07-18 section. "Rules for every plan" R-A to R-D are followed. No new test skips. Docker was not run (R-B). No driver command was run. No subagents were used.

**Orchestrator dispatch note (07-13 as built), applied:** the gate lock covers the whole F19 window. That window runs from the MATCHED append through `_commit_with_retry` to `_undo_match`'s truncation. Another worker of the same `_Night` appends only through `_Night._append`, which takes the gate lock. The test is `test_gate_lock_keeps_other_appends_out_of_the_match_undo_window`. Commits `a69df09` and `3f35e74`.

**1. [Rule 3 - Blocking] `gate_lock` is a `threading.RLock`, not the plan's `threading.Lock`.**
- **Why:** the landing section writes its own attempt record through `_append`, which takes the gate lock (Task 3). A plain Lock would deadlock on the first match.
- **How the tests check "held":** from another thread (`_held_elsewhere`), which is correct for an RLock.
- **Commits:** `5657280` and `3f35e74`.

**2. [Rule 2 - Missing critical] `Claims.recover` enforces the drive.lock precondition.**
- **Why:** the plan only says recover is "only callable with drive.lock held". Called without the lock, recover could move a live drive's claims.
- **What:** recover now probes the lock with a second `ProcessLock` and raises DriverError when the probe gets it.
- **Test:** `test_stale_recover_needs_the_drive_lock`.
- **Commit:** `23d9ec5`.

**3. [Rule 2 - Missing critical] A claim's exe and unit are validated against the record schema's patterns before they form a file name.** No path can leave `claims/`. Commit `5657280`.

**4. [Rule 1 - Ordering] The attempt's reset runs before its claim is released.**
- **The problem:** first draft, `_guarded`'s `except` reset ran after the `with` released the claim.
- **The risk:** a later worker could claim the unit while the old attempt's `git restore` still ran.
- **Fix:** I moved the try/except inside the `with`. Commit `5657280`.

**5. [Plan clarification] Claim field values.**
- With one worker, `worker` is 0, `pass` is 1, `kind` is "matching", and `model` is null. The driver does not choose a model yet; 07-2x escalation will fill it.
- A unit already claimed by this run stops the night (STOPPED `error`). With one worker, only a claim this run failed to release can cause that.

**6. [Plan clarification] The chore commit uses the same retry.** `_commit_log` goes through `_commit_with_retry`, so an index.lock at the end of a night no longer makes `drive()` raise. Before this, the night's DriverError escaped `drive()`, as RED t3 showed.

**7. [Test change, behaviour change] `test_a_lock_held_through_the_undo_still_records_and_names_what_stays_staged` now fails the commit twice** (`fail_verbs commit: 2`). One index.lock failure is now retried and succeeds. Commit `3f35e74`.

---

**Total deviations:** 1 dispatch note applied; 4 auto-fixes (Rule 1 x1, Rule 2 x2, Rule 3 x1); 2 clarifications; 1 test adjusted to the new retry.
**Impact on plan:** every must-have truth holds. The RLock is required for correctness. No scope creep.

## Issues Encountered

- The harness refused compound shell commands (heredocs, `&&` chains with node). I used the Edit tool and a scratchpad script (`red_record.py`) to build the RED evidence records.

## Known Stubs

- None that block the plan.
- The claim's `model` field is null and `worker`/`pass` are fixed at 0/1 until 07-21 (workers) and model escalation land. This is intentional and documented above.

## Threat Flags

None. The new surface is local gitignored files under build/driver/ and an OS lock, all in the plan's threat model (T-07-52, T-07-53, T-07-54).

## Verification

- `uv run pytest -q tests/test_locks.py tests/test_driver_workers.py tests/test_driver.py tests/test_drive.py`: 244 passed, 2 skipped (Task 1 verify plus test_drive). After Task 3, test_driver and test_drive gave 233 passed and 2 skipped plus the adjusted test, and workers plus locks gave 27 passed.
- `uv run pytest -q tests/test_driver_workers.py -k "stale or race or pid"`: 7 passed (Task 2 verify).
- `uv run pytest -q` (host, worktree): **3181 passed, 247 skipped**.
  - The two new test files have no skips, and test_driver.py keeps its 2 pre-existing skips.
  - The skip total differs from 07-13's 236 because of plans merged since. This plan adds no skipping test and no new skip reason.
- `uv run ruff check .`: All checks passed.
- Acceptance:
  - locks.py has `class ProcessLock` and `DRIVE_LOCK`.
  - driver.py has `class Claims`, `GIT_OPTIONAL_LOCKS` and `def _commit_with_retry(`.
  - test_driver_workers.py has `test_no_pid_probe` and `test_claim_race_one_winner`.
- **Container step deferred to the orchestrator:** `docker compose build && docker compose run --rm test`.

## User Setup Required

None.

## Next Phase Readiness

- 07-21 can run worker threads on one `_Night`. Each worker:
  - takes `Claims.take` with its worker id and skips a unit when take returns False;
  - lands through `_counted`/`_salvage` (gate lock);
  - appends only through `_append`;
  - runs git only through `_git`.
- Sessions still run `_launch` outside the gate lock, and must keep doing so. The audit's `_snapshot`/`git status` runs through the git lock with GIT_OPTIONAL_LOCKS=0.
- 07-23 can move `recovered_detail`'s text into the v2 STARTED record's `recovered` list. `Claims.recover()` already returns `{exe, unit, run}` dicts that match `_RECOVERED`.
- A crash inside a landing still leaves src/ dirty. The existing `_clean_tree` preflight refuses the next start and names the paths (research section 2).

Execution context nonce: f621a742369d20ae

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
