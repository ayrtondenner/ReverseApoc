---
phase: 07-mechanics-first-decompilation
plan: 21
subsystem: driver
tags: [driver, workers, threads, d-06, d-07, usage-limit, stop-all, night-cap, cli]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-18: drive.lock, Claims (O_EXCL), the reentrant gate lock over landings and appends, the git lock; 07-13: private views, _land/_reset of one unit, the _Ledger audit; 07-07: the v2 schema (unused here, records stay v1)"
provides:
  - "DriveConfig.workers (1: the Phase 6 loop on the calling thread); _Coordinator (main thread, owns the picker, defers a pick whose unit is busy) and _Worker (one function's pass per worker thread)"
  - "_Pause: one usage-limit pause for every worker; the LIMIT worker waits the backoff, then exactly one probe launches; a non-LIMIT probe clears it"
  - "run_session(..., on_start, on_end): the session pid reaches the driver's pid registry; Deps.kill (session.kill_tree) kills every live tree on a stop"
  - "stop-all: the first failure (or a KeyboardInterrupt on the main thread) stops every worker; killed sessions are audited, contained and reset uncounted; one STOPPED record"
  - "the shared night cap: _reserve/_release/_count (sessions + reserved < max_sessions); target_matched 0 = off"
  - "drive --workers N (default 3), --max-sessions default 60, --target-matched default 0 (_non_negative, \"0 = off\")"
  - "tests/fakeclaude.py --any-unit; tests/test_driver_workers.py WNight (the Night harness for worker threads)"
affects: [07-23, 07-26, 07-30, 07-31, 07-34, 07-35, 07-39]

actuals:
  tokens: 19250
  tasks: 3
  commits: 6
plan_head_before: 0fd68778633ad39c153ad7d3e7093c3e340240fa
plan_head_after: d247ee7abc7bcfb9498f2e0dc6dd20ac4dfdd007

tech-stack:
  added: []
  patterns:
    - "Workers are threads of one _Night; shared state sits behind the night's Condition (counters, dispatch, pause, stop); the lock order is gate lock, then the condition"
    - "Per-worker state is thread-local (_Night.local: worker, live, slot)"
    - "Concurrency tests prove overlap and order with barriers and events (F39), never with sleeps"

key-files:
  created: []
  modified:
    - tools/reverseapoc/driver.py
    - tools/reverseapoc/session.py
    - tools/reverseapoc/cli.py
    - tests/test_driver_workers.py
    - tests/test_session.py
    - tests/test_cli.py
    - tests/test_drive.py
    - tests/test_driver.py
    - tests/fakeclaude.py

key-decisions:
  - "One worker runs its pass inline on the calling thread, so --workers 1 is the Phase 6 driver exactly (same order, same exceptions); DriveConfig.workers defaults to 1, the verb to 3"
  - "The pre-session snapshot and the audit hold the gate lock: another worker's half-done landing (its unit in src/, its gate writing status.csv) would otherwise read as a stray"
  - "A night-cap slot is reserved per attempt and kept across that attempt's LIMIT/TRANSIENT relaunches; it becomes the counted session or goes back when the attempt ends uncounted"
  - "The LIMIT worker that starts or renews the pause waits the backoff itself; then any worker's next launch is the probe. A LIMIT from a session launched before the pause leaves the streak alone"
  - "After a stop nothing new launches or lands: a session that ends after it is audited (strays contained), reset, and neither counted nor recorded; its containment is named in the STOPPED detail"
  - "After any worker's breach (J2, sticky) no match commit happens: _verify_landing refuses it"
  - "The backoff wait uses the stop event when Deps.sleep is the real time.sleep, so a stop or Ctrl+C never waits out a 300 s poll"

patterns-established:
  - "WNight: per-thread session scripts chosen by the unit the prompt claims; before/after hooks in the session thread; on_pid once the driver has a session's pid"
  - "_held(night, n): wait on the pause's condition until n workers are held (each wait is announced with notify_all)"

requirements-completed: [DEC-02, DEC-06]

coverage:
  - id: D1
    description: "N sessions run at once (three units pass a barrier of three); one unit never runs two sessions at once (the second pick is deferred, then runs); workers=1 is serial on the calling thread"
    requirement: DEC-02
    verification:
      - kind: integration
        ref: "tests/test_driver_workers.py#test_three_workers_overlap, test_same_unit_never_concurrent, test_workers_one_is_serial"
        status: pass
    human_judgment: false
  - id: D2
    description: "Gate calls never overlap and each sees src/ equal to HEAD but the landing unit; worker B's broken view unit never reaches worker A's gate (T-07-63)"
    requirement: DEC-02
    verification:
      - kind: integration
        ref: "tests/test_driver_workers.py#test_gates_never_overlap, test_broken_view_does_not_leak"
        status: pass
    human_judgment: false
  - id: D3
    description: "One LIMIT pauses every worker until its 60 s backoff passes; exactly one probe per backoff; a second LIMIT backs off 120 s; a success resumes all (T-07-61)"
    requirement: DEC-06
    verification:
      - kind: integration
        ref: "tests/test_driver_workers.py#test_limit_pauses_all, test_one_probe_after_backoff; tests/test_driver.py#test_limit_backs_off_and_is_not_counted, test_limit_polls_every_five_minutes"
        status: pass
    human_judgment: false
  - id: D4
    description: "STOP from one worker or Ctrl+C on the main thread kills every registered live session tree; each attempt is contained and reset, nothing of theirs counts; one STOPPED record (T-07-62)"
    requirement: DEC-06
    verification:
      - kind: integration
        ref: "tests/test_driver_workers.py#test_stop_kills_all_live_sessions, test_keyboard_interrupt_stops_workers; tests/test_session.py#test_run_session_reports_the_pid_at_start_and_end, test_run_session_reports_a_real_childs_pid, test_on_end_runs_when_the_session_raises"
        status: pass
    human_judgment: false
  - id: D5
    description: "The night cap is shared with slot reservations; an uncounted abort gives its slot back; target 0 is off; empty queue launches nothing; drive --workers/--max-sessions/--target-matched defaults 3/60/0 and their refusals"
    requirement: DEC-06
    verification:
      - kind: integration
        ref: "tests/test_driver_workers.py#test_cap_shared_across_workers, test_uncounted_session_releases_slot, test_target_matched_zero_is_off, test_empty_queue_no_session, test_drive_config_defaults_follow_d07; tests/test_cli.py#test_cli_drive_defaults, test_cli_drive_refuses_bad_caps, test_cli_drive_passes_workers_and_target_zero; tests/test_drive.py#test_drive_defaults, test_the_night_gets_the_verbs_caps_and_workers"
        status: pass
    human_judgment: false
  - id: D6
    description: "Host suite and ruff green; the container run is deferred to the orchestrator (R-B)"
    verification:
      - kind: other
        ref: "uv run pytest -q (3440 passed, 247 skipped) && uv run ruff check ."
        status: pass
    human_judgment: true
    rationale: "docker is not allowed in a worktree; the orchestrator runs docker compose build && docker compose run --rm test after merge"

duration: 32min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 21: The concurrent driver Summary

**One `reverseapoc drive` now runs `--workers` sessions at once (default 3). The main thread's `_Coordinator` hands each function's pass to a `_Worker` thread and defers, never drops, a pick whose unit another pass holds. The audit and every landing hold the gate lock, so a gate always sees src/ equal to HEAD but the unit it lands. A usage limit pauses every worker behind one `_Pause` with exactly one probe launch per backoff. Any worker's stop, or Ctrl+C on the main thread, kills every live session tree through a pid registry that `run_session(on_start, on_end)` feeds; each attempt is then contained and reset, and one STOPPED record is written. The night cap of 60 is shared through slot reservations, and `--target-matched` defaults to 0, which means off.**

## Performance

- **Duration:** about 32 min
- **Started:** 2026-10-27T20:30:04Z
- **Completed:** 2026-10-27T21:01:52Z
- **Tasks:** 3, all TDD: a RED commit, then a GREEN commit
- **Files modified:** 9 (none created)

## Accomplishments

- **Workers (Task 1, D-06).**
  - `DriveConfig.workers`.
  - `_Coordinator.run` replaces `_loop`'s body. For each free worker it takes the first deferred pick whose unit is free, or else the queue's next new pick; a pick whose unit is busy is deferred. It stops handing out picks on a stop or once a cap is reached, drains every worker, then re-raises the first failure on the main thread.
  - `_Worker` runs `_Night._function` (one pass, up to 3 sessions, each under its unit's claim). With one worker the pass runs inline on the calling thread, which is the Phase 6 driver exactly.
  - The live session is per worker (thread-local), and so are the worker number (it goes into the claim's `worker` field) and the reserved slot.
  - The counters and the difficult list sit under the night's Condition.
  - The pre-session snapshot and the audit run under the gate lock.
- **The pause and stop-all (Task 2, D-07).**
  - `_Pause.wait_to_launch` blocks every launch while the pause holds. `on_limit` starts the pause, or renews it for the probe, and returns the backoff (60, 120, 240, then 300 s by the shared streak). `backoff_done` makes the next launch the probe, and `on_clear` (from the probe) clears the pause for all and restarts the streak.
  - `session.run_session` gains `on_start(pid)` and `on_end(pid)`. `on_end` runs in a `finally`, so it also runs when the session raises.
  - `_Night` keeps `pids` (worker -> pid). `_stop_all` sets the stop event and kills every registered tree with `Deps.kill` (`session.kill_tree`). A session that registers just as the night stops is killed at once.
  - A killed session's worker removes its containers, audits it (strays quarantined and put back), resets the unit and leaves quietly (`_Halt`). Its session is neither counted nor recorded.
  - The first failure writes the STOPPED record, with every halted worker's containment added to its detail.
  - KeyboardInterrupt on the main thread stops and drains the workers before it is recorded as STOPPED `interrupted` and re-raised.
- **The cap and the flags (Task 3, D-07).**
  - `_reserve` takes a slot before each attempt (`sessions + reserved < max_sessions`). It waits while attempts still running hold every free slot, and returns False once a cap is reached or the night stops.
  - `_count` turns the slot into a counted session, and `_release` gives it back when the attempt ends uncounted.
  - `_end` treats `target_matched` 0 as off. `DriveConfig` and `DriveOptions` default to 60 sessions with the target off, and `DriveOptions.workers` defaults to 3.
  - In cli.py, `--workers` uses `_positive` with default 3, `--max-sessions` defaults to 60, and `--target-matched` uses the new `_non_negative` with default 0 and the help text "0 = off". `run_drive` passes `workers` to the night.

## Task Commits

1. **Task 1 (tracer): workers overlap sessions, one gate at a time.** RED `18ca25f`, GREEN `ad04001`.
   - Tracer feedback gate: the run is interactive, in end-of-phase mode, with an automated-only verify. I re-ran `uv run pytest -q tests/test_driver_workers.py` (36 passed) and `uv run ruff check .`, then expanded. Tracer verified end-to-end.
2. **Task 2: the shared pause, stop-all with the pid registry, KeyboardInterrupt.** RED `3d0dc7a`, GREEN `d83a28c`.
3. **Task 3: the shared night cap, `--workers`, the new defaults.** RED `5ca097e`, GREEN `d247ee7`.

## TDD evidence (RED)

Each RED run wrote pytest JUnit XML (`build/red/t{1,2,3}.xml`, gitignored). `gsd-tools check tdd-red-evidence` returned `RED_EVIDENCE_OK` / `target_test_failed` each time.

- **t1, target `test_three_workers_overlap`: 5 failed, 1 passed.**
  - All five new tests failed with `TypeError: DriveConfig.__init__() got an unexpected keyword argument 'workers'`.
  - That is the planned feature's absence (no workers option, so no concurrent sessions), raised in the test body after collection succeeded. It is not a fixture or import fault, the same kind of evidence 07-18 accepted for its missing module.
  - The one pass is the pre-existing `test_git_calls_serialised`, selected by `-k serial`.
- **t2, target `test_limit_pauses_all`: 7 failed, 3 passed.**
  - The target ran its night and failed on its first assertion: the night was STOPPED, not ENDED, because the driver had no shared pause.
  - The other failures: `run_session` had no `on_start`/`on_end` keyword, and `Deps` had no `kill` field.
  - The 3 passes are pre-existing tests that `-k probe` selects (`test_no_pid_probe` and the two alive-probe tests).
- **t3, target `test_cap_shared_across_workers`: 10 failed, 5 passed.**
  - The target failed on its planned assertion: 6 counted sessions, not 5, because freed workers launched without a reserved slot.
  - The other failures: target 0 ended the night at once, the defaults were 30/10, and there was no `--workers` flag.
  - The 5 passes pin behaviour that already held: the uncounted abort, the empty queue, two refusals `_positive` already made, and the existing options test.

## Files Created/Modified

- `tools/reverseapoc/driver.py`: the module docstring; `DriveConfig` (workers, the new defaults); `Deps.kill`; `_Halt`, `_TICK_S`, `_Pause`, `_Worker`, `_Coordinator`; `_Night`:
  - the state: `local`, `cond`, `stop`, `failure`, `halt_notes`, `pause`, `pids`, `killed`, `reserved`;
  - the methods: `live`/`worker`, `_reserve`/`_release`/`_count`, `_fail`/`_note`/`_stop_all`/`_kill`/`_on_start`/`_on_end`/`_stopped_workers`/`_halt_if_stopping`/`_raise_failure`, `_end`, `_loop`, `_function`, `_attempt`, `_limited`/`_nap` (these replace `_backoff`), `_launch`, `_audit`, `_verify_landing`, `_landing`, `_salvage`, `_counted` and `_commit_match`;
  - `DriveOptions` (workers, the new defaults); `run_drive` (passes workers).
- `tools/reverseapoc/session.py`: `run_session(..., on_start, on_end)`; the body after the launch moved into `_run_started`.
- `tools/reverseapoc/cli.py`: `_non_negative`; `_add_drive_command` (`--workers`, the defaults); `_cmd_drive` (passes workers).
- `tests/test_driver_workers.py`: WNight and 15 new tests.
- `tests/test_session.py`: 3 tests.
- `tests/test_cli.py`: 3 tests (one parametrized ×5).
- `tests/test_drive.py`: the defaults test updated (60/0/3), plus 1 test.
- `tests/test_driver.py`: `Night._session` passes the driver's hooks on to `run_session`.
- `tests/fakeclaude.py`: `--any-unit`.

## Decisions Made

See `key-decisions` in the frontmatter.

## Deviations from Plan

**Orchestrator ruling F39: events and barriers for overlap and ordering.**
- Overlap is proven by a `threading.Barrier(3)` that only three concurrent sessions can pass.
- The order "the second pick of a unit waits" is proven by an event: the first session waits until the pick in the free unit has started.
- "B is still running at A's gate" is proven by B's session waiting on an event set by A's gate.
- "No launch during the pause" is proven by the pause's condition (`_held`) and a launch count read inside the fake backoff sleep.
- "Exactly one probe" is proven by the ordered start/end event log.
- Two timed waits remain, and neither decides a pass on its own:
  - `WIDEN_S` = 0.05 s inside the fake gate gives an unlocked second gate room to overlap. A correct driver passes regardless.
  - `fakeclaude --sleep 60` stands for a live session that must be killed. The assertion is on the registry's kill calls, not on time.
- Every wait has a 30 s timeout, so a broken driver fails instead of hanging.
- Commits `18ca25f`, `3d0dc7a`, `5ca097e`.

**1. [Rule 2 - Missing critical] The pre-session snapshot and the audit hold the gate lock.**
- **Why:** without it, worker A's audit could run while worker B's landing had its unit in src/ or its gate writing status.csv. Both read as strays under D-24 (a), and the night would stop as a guardrail breach.
- **Commit:** `ad04001`.

**2. [Rule 2 - Missing critical] J2 holds across workers.**
- **Why:** before, nothing stopped worker A's match commit from running after worker B's breach.
- **Fix:** `_verify_landing` refuses the commit (undo, STOPPED `guardrail`) once `breached` is set.
- **Commit:** `ad04001`.

**3. [Rule 2 - Missing critical] A session that starts as the night stops is killed.**
- **Why:** the stop could otherwise miss a session that starts at that moment.
- **Fix:** `_on_start` registers the pid and reads the stop flag under one lock, and `_stop_all` sets the flag before it reads the registry, so neither order loses a kill.
- **Commit:** `d83a28c`.

**4. [Rule 2 - Missing critical] The backoff wait ends early on a stop.**
- **Why:** a stop or Ctrl+C should not wait out a 300 s poll on another worker.
- **Fix:** `_nap` waits on the stop event when `Deps.sleep` is the real `time.sleep`. An injected sleep (the tests' fake clock) is called as before, so `night.sleeps` stays exact.
- **Commit:** `d83a28c`.

**5. [Rule 3 - Blocking] `tests/test_driver.py` (not in files_modified): `Night._session` accepts and forwards `on_start`/`on_end`.** The driver now passes them to every session. Commit `d83a28c`.

**6. [Rule 3 - Test harness] `fakeclaude --any-unit`.** The stream fixtures' Edit names `src/ufo2p/u_00010000.c`. With the flag, a session claiming any other unit replays that write as its own view unit; without it, the transcript audit would call every other unit's session a stray. Commit `18ca25f`.

**7. [Plan clarification] Slot reservation is per attempt.**
- The plan says "a slot is reserved before each launch".
- The slot is reserved before each attempt and kept across that attempt's LIMIT and TRANSIENT relaunches. It is given back when the attempt ends uncounted (a transient abort, a stop).
- Why: a relaunch never queues behind a new pick for its own slot, and the count is the same, since only counted sessions use slots.

**8. [Plan clarification] Pause rules.**
- The worker whose LIMIT starts or renews the pause waits the backoff itself (through `Deps.sleep`, as in Phase 6). After that, any worker's next launch is the probe.
- A LIMIT from a session launched before the pause leaves the pause and the streak as they are.
- With one worker every launch after a LIMIT is the probe, so the Phase 6 tests (`[60, 120]`, `[60, 120, 240, 300, 300]`) pass unchanged.

**9. [Plan clarification] Halted sessions.**
- After a stop nothing new launches or lands. A session that ends after the stop is audited (strays contained), reset, and neither counted nor recorded.
- Its containment, or a later worker's guardrail stop, is added to the first stop's detail. The first failure's reason is kept.

**10. [Plan clarification] Defaults.** `DriveConfig.workers` defaults to 1 so `drive(config, deps)` callers keep the serial driver; the verb (`DriveOptions`, `--workers`) defaults to 3. `DriveConfig`'s `max_sessions`/`target_matched` defaults follow `DriveOptions` (60/0).

**11. [Plan clarification] Records stay v1, as the plan says.** No `worker` field and no `limit` record yet; 07-23 adds the v2 records.

**12. [Test change] `tests/test_drive.py::test_drive_defaults`** now expects (60, 0, 3) instead of (30, 10) (D-07). Commit `5ca097e`.

---

**Total deviations:** 1 orchestrator ruling applied (F39); 6 auto-fixes (Rule 2 ×4, Rule 3 ×2); 5 clarifications; 1 test changed to the new defaults.
**Impact on plan:** every must-have truth holds. The Rule 2 fixes keep the Phase 6/07-13 guarantees (audit, J2, kill on stop) true with concurrent workers. No scope creep.

## Issues Encountered

- The harness refused compound shell commands (heredocs, `cd && git` chains with `$(...)`). I used the Edit tool and a scratchpad script (`red_record.py`) for the RED records.
- `docs/workflow.md` still lists the drive defaults as 30/10 (lines 71-77) and does not name `--workers`. Plan 07-35 owns that docs update ("docs/workflow.md names `--workers`, `--max-sessions`, `--target-matched`"), so I left it: it is outside this plan's files.

## Known Stubs

None.

## Threat Flags

None. The new surface (worker threads, the pid registry, `kill_tree` on registered pids) is in the plan's threat model (T-07-61, T-07-62, T-07-63). `test_no_pid_probe` still passes: no os-module kill call, and pids are only killed through `session.kill_tree`.

## Verification

- `uv run pytest -q tests/test_driver_workers.py`: 36 passed (Task 1 verify and tracer gate).
- `uv run pytest -q tests/test_driver_workers.py tests/test_session.py`: 71 passed, 1 skipped (Task 2 verify; the skip is the pre-existing POSIX-only test).
- I ran the 8 overlap, pause and stop tests 3 more times: 8 passed each time (15-35 s).
- `uv run pytest -q tests/test_driver.py tests/test_drive.py`: 234 passed, 2 skipped (the pre-existing skips), after Task 2.
- `uv run pytest -q tests/test_driver_workers.py tests/test_cli.py tests/test_drive.py tests/test_session.py`: 269 passed, 1 skipped (Task 3 verify).
- `uv run pytest -q` (host, worktree): **3440 passed, 247 skipped**. That is the same skip total as 07-18; this plan adds no skipping test and no new skip reason.
- `uv run ruff check .`: All checks passed.
- Acceptance:
  - driver.py contains `class _Coordinator`, `class _Worker` and `class _Pause`.
  - `session.run_session` has the `on_start` keyword.
  - `uv run reverseapoc drive --help` prints `--workers N ... default: 3`, `--max-sessions N ... default: 60` and `--target-matched N ... 0 = off; default: 0`.
- No real `claude -p` session, no `drive` command and no docker were run (D-11, R-B). Every session was tests/fakeclaude.py.
- **Container step deferred to the orchestrator:** `docker compose build && docker compose run --rm test`.

## User Setup Required

None.

## Next Phase Readiness

- 07-23 can add `worker` to each v2 record (`_Night.worker`), a `limit` record per pause (`_Pause.on_limit` returns the seconds; `paused_until` holds the end), and `workers` and `recovered` to the run records.
- 07-26/07-30: the claim's `pass` is still 1 and `model` null. The coordinator is where per-pass state goes (D-08 re-queues, D-09 escalation).
- 07-39's preflight measures three concurrent container checks plus a gate on Docker Desktop (research R1/K2); the owner can lower `--workers` per night.
- Known limit, unchanged: on Windows `kill_tree` cannot reach grandchildren once the root has exited. Containers are still removed by name prefix after each attempt, killed ones included.

Execution context nonce: 36b3c54a172149c8

## Self-Check: PASSED

- FOUND: tools/reverseapoc/driver.py, tools/reverseapoc/session.py, tools/reverseapoc/cli.py, tests/test_driver_workers.py, tests/test_session.py, tests/test_cli.py, tests/test_drive.py, tests/test_driver.py, tests/fakeclaude.py
- FOUND commits on this branch: 18ca25f, ad04001, 3d0dc7a, d83a28c, 5ca097e, d247ee7. `git rev-list --count 0fd6877..HEAD` = 6 before this SUMMARY commit.
- No STATE.md, ROADMAP.md or REQUIREMENTS.md change (the orchestrator owns them after the merge).

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
