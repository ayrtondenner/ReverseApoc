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

## Fix round 1

**Findings (task review plus two automated security findings), with the orchestrator's rulings:**
- **C1 (Critical, security S2): pinned paths were checked against each session's launch snapshot.**
  - The pinned paths are .git/config, the git hooks, the settings files and the .pth files.
  - A session launched after another live session's stray had that stray in its baseline.
  - Once stop-all killed it, its audit "restored" the stray.
  - Ruling: one night-level baseline.
- **I1 (Important, security S1): a live session's write between `_verify_landing` and `git commit -- <paths>` was committed.**
  - `git commit` re-reads the worktree after the check.
  - Ruling: verify the committed blobs after the commit. On a mismatch, move HEAD back off the driver's own commit only, then undo.
- **The reviewer's open point: another session's write elsewhere in the tree (for example another unit's src/ file during A's gate) could ride along unchecked.**
  - Ruling: right before the match commit, every other git-visible path must equal HEAD or hold the driver's bytes.
- **I2 (Important): after Ctrl+C, a halted worker's own guardrail stop was never re-raised.**
  - Its strays were missing from the STOPPED `interrupted` record.
  - Ruling: list them.

**What changed (`tools/reverseapoc/driver.py`, `c119c09`):**
- **C1, the baseline:**
  - `_loop` takes `pinned_base = _pinned_state()` once, before the first launch.
  - `_measure`, `_contain_one` and `_still_changed` compare with it and restore to it, through `_pinned_baseline`. Outside a night (the canary's probe) the snapshot is used as before.
- **C1, the launch check:** under the gate lock, each launch compares its snapshot with the baseline (`_pinned_drift`). A difference is contained (back to the baseline) and stops the night (STOPPED `guardrail`) before the session starts.
- **I1, the commit check:**
  - `_commit_match` records HEAD before the commit, then `_verify_commit` compares `cat-file blob <new>:<path>` for the four paths with `landed_bytes` and `ledger.expected`.
  - On a difference, `git update-ref HEAD <old> <new>` moves HEAD back. Its old-value guard means it only acts while HEAD is still that commit, and nothing else is reset.
  - Each path is then contained (`_breach`) and `_Breach` goes into the existing `_undo_match`.
  - Commits still go through plain `git commit`, so hooks run.
- **Open point, the clean-tree check:**
  - `_verify_landing` now takes the session. After its existing checks it runs `git status`, and every path `_unexplained` names other than the landing unit is contained by `_contain` (tracked: copied, then back to HEAD; new: moved to the quarantine).
  - The night is then marked breached and the commit refused through `_Breach`. A new helper, `_contained_text`, writes the detail.
- **I2:** `_stopped_workers` adds the night's `failure` (a halted worker's `_Stop` reason and detail) to the interrupted text.

**Tests (RED `2f4bb5b` and `4d5199a`, then the fix `c119c09`), all in tests/test_driver_workers.py:**
- **C1:**
  - `test_a_later_sessions_baseline_never_restores_anothers_stray` follows the reviewer's sequence: A writes a stray to `.claude/settings.local.json`, then B launches; A's session waits for B's start or the night's stop. It checks that the file ends with its pre-night bytes and that the stray is in the quarantine.
  - `test_containment_restores_the_night_baseline_not_the_launch_snapshot` covers the audit half: `_measure` and `_contain` against the baseline. I added it in the second RED commit once the launch check meant the integration test no longer reaches B's audit.
- **I1:** `test_a_write_between_the_landing_check_and_the_commit_is_never_committed[unit|status.csv]`. The write is injected at the match commit's `git add`. The test checks: STOPPED `guardrail`, no feat commit (HEAD back on the base), no tampered bytes in HEAD or the worktree, the attempt GAVE_UP, and the tampered copy quarantined.
- **Open point:** `test_another_dirty_path_at_the_match_commit_is_a_breach[untracked src unit|tracked tools/keep.py]`. A file written during A's gate gives STOPPED `guardrail` with no feat commit, the path named in the detail, put back and quarantined.
- **I2:** `test_an_interrupt_record_lists_a_halted_workers_strays`. Ctrl+C while the second worker's session leaves `tools/x.py`: the STOPPED `interrupted` detail names it, and it is quarantined and gone from the tree.
- **RED:** the first commit's 6 tests failed on their planned assertions. Classifier `RED_EVIDENCE_OK`, target `test_a_later_sessions_baseline_never_restores_anothers_stray`, `build/red/f1.xml`.
  - B wrote the stray back.
  - The tampered unit and the tampered status.csv were committed (two cases).
  - The night ENDED with another path dirty (two cases).
  - The interrupted detail lacked `tools/x.py`.
  - The second RED commit's audit-half test failed: B's measure still reported a pinned change against its launch bytes.
- **One test assertion relaxed in the fix commit.**
  - A's own audit also keeps a quarantine copy of the restored settings file, because the restore changed its mtime (a fingerprint). That copy holds the original bytes.
  - The test now requires the stray among the kept copies and allows nothing but the stray or the original bytes, instead of only the stray.
  - Old code still fails it: the file ended as the stray.

**Residuals (recorded, not changed):**
- A write made and reverted by another session inside the window of A's gate could still sway the gate's status.csv rows. Two things still catch the writer: its transcript audit and the clean-tree check at the next commit.
- The chore commit at night end still has 07-13's window between `_ledger_breaches` and `git add`.

**Commands and output:**
- `uv run pytest -q tests/test_driver_workers.py tests/test_driver.py tests/test_drive.py tests/test_session.py`: 318 passed, 3 skipped (the pre-existing skips).
- `uv run pytest -q` (host, worktree): 3447 passed, 247 skipped. No new skip and no new skip reason.
- `uv run ruff check .`: All checks passed.
- Container step still deferred to the orchestrator: `docker compose build && docker compose run --rm test`.

## Fix round 2

**Findings:** these come from the re-review of fix round 1 (`rereview-07-21-r1.md`, "New Breakage in the Fix Diff"). The orchestrator ruled that the two Minor findings, N3 and N4, are also fixed in this round.

- **N1 (Important): `_verify_commit` gave a false breach for a CRLF unit.**
  - The repo has `* text=auto eol=lf`, so git stores the LF form, but the check compared raw bytes.
  - Fix: the check now compares object ids, for every path it checks (`_committed_as`):
    - the expected bytes are hashed with `git hash-object --path=<rel> --stdin`, which applies the path's attributes the same way the commit did;
    - the result is compared with `git rev-parse --verify --quiet <new>:<rel>`;
    - "no bytes expected" (None) means the path must be absent from the commit.
  - To support this, the git seam now takes an optional stdin:
    - `git_runner`'s `git(args, input=None)`;
    - `_Night._git(args, *, input=None)`, which calls `deps.git(args)` unchanged when there is no input;
    - the `Deps.git` and `Seams.git` annotations are now `Callable[..., CompletedProcess]`.
- **N2 (Important): the `update-ref HEAD old new` guard was not tied to the driver's own commit.**
  - Fix: `_foreign_commits` runs after the commit. HEAD counts as the driver's commit only if it has exactly one parent, that parent is `old`, and its subject equals the driver's message subject (the optional check, included).
  - If it is not, HEAD is never moved:
    - the record names each commit in `old..new` whose subject is not the driver's, as `<sha12> <subject>`;
    - any blobs that are wrong are still named and contained (`_breach`);
    - `_Kept` stops the night as `guardrail`, with no `_undo_match`.
  - When HEAD is the driver's commit, the `update-ref` old-value guard remains a compare-and-swap on that verified commit.
- **N3 (Minor): the launch check restored a tracked pinned path from the launch snapshot, which held the stray.**
  - Fix: in `_contain_one`, once the night baseline is set, every name in `session.pinned_changed` is restored to `pinned_base[name]`, tracked or not, then unstaged as before. Outside a night (the canary), the old rule still applies.
- **N4 (Minor): an exception from `_verify_commit` other than `_Breach` went into `_undo_match`'s no-commit path.**
  - Fix: every check after the commit runs inside one `try`: `rev-parse`, the anchor check, `rev-parse <new>:<rel>` and `hash-object`.
  - Any exception there becomes `_Kept`, with the error in the detail. `_commit_match` catches `_Kept` before `_Breach`, sets `breached=True` (so there is no chore commit) and stops as `guardrail`. status.csv and the log are never put back under the kept commit.
  - The same applies when `update-ref` fails after a blob mismatch, which before this round also reached `_undo_match` while the commit stayed in history.

**Tests (all in tests/test_driver_workers.py):**
- `test_a_crlf_unit_under_an_eol_rule_is_committed_without_a_guardrail_stop` (N1):
  - the test repo commits its own `.gitattributes` (`* text=auto eol=lf`);
  - the test git env has `GIT_CONFIG_NOSYSTEM=1` and `core.autocrlf=false`, so the outcome is the same on this Windows host and in the Linux container;
  - the session writes the view unit with CRLF;
  - the match must be committed, with the LF form in the commit.
- `test_a_foreign_commit_during_the_match_commit_never_moves_head` (N2), 4 cases: {(a) before the driver's commit, (b) after it} x {clean, tampered status.csv}.
  - (a) is injected at the match commit's `git add`, after the driver has read `old`.
  - (b) is injected at the first git call after the match `git commit`, which is the post-commit `rev-parse`.
  - Each case requires: STOPPED `guardrail`, the foreign and match commits both still in history, and the foreign sha in the detail. The tampered cases also require the path to be named and the tampered bytes to be gone from the worktree.
- `test_a_launch_check_puts_a_tracked_pinned_file_back_to_the_night_baseline` (N3):
  - the test commits `config/driver/claude-settings.json`, and the stray is written in `pack` (after the baseline, before the launch snapshot);
  - nothing launches, the file ends with its pre-night bytes and is clean in `git status`;
  - the detail has no "still changed after containment";
  - the stray is in the quarantine.
- `test_a_failed_check_after_the_match_commit_keeps_the_commit_and_reverts_nothing` (N4):
  - the post-commit `rev-parse` raises;
  - the night stops `guardrail` with the error in the detail;
  - the commits are exactly the match commit (no chore commit);
  - worktree status.csv equals HEAD's, and the worktree log starts with HEAD's log.

**RED evidence:** all 7 tests failed on their planned assertions. The classifier returned `RED_EVIDENCE_OK` for target `test_a_crlf_unit_under_an_eol_rule_is_committed_without_a_guardrail_stop` (`build/red/f2.json`, `build/red/f2.xml`). Semantic check of each failure:
- N1: "the match commit ... holds bytes the driver did not write: src/ufo2p/u_00010000.c; HEAD moved back", a guardrail stop on a genuine match.
- N2 clean cases: ENDED `queue exhausted`, with no stop.
- N2 tampered cases: HEAD was moved back, and the foreign commit was dropped from history.
- N3: the record said "restored: config/driver/claude-settings.json; ...; still changed after containment: config/driver/claude-settings.json", and the file ended as the stray.
- N4: STOPPED `tool` through the undo path.

**Commits:**
- `09e8e01` test(07-21): add failing tests for fix round 2 (N1-N4)
- `cabf847` fix(07-21): anchored, attribute-aware post-commit check; tracked pinned paths back to the night baseline
- this SUMMARY commit

**Deviations:**
- **[Rule 3 - Blocking] tests/test_driver.py changed, though it is not in the plan's files_modified.**
  - `Night._recorded_git`, the shared git fake of the driver tests, had to accept the new optional stdin (`input=None`) so that `hash-object --stdin` reaches the real git.
  - The change is three lines. Every other call is unchanged, and an argv-only fake still works for any call without stdin.
  - `Rig.git` in tests/test_drive.py got the same change (that file is in the plan).
- **N2's optional subject check is implemented but has no dedicated test.** No test puts a commit with the driver's subject on `old`. The parent check is what the four N2 cases exercise.

**Residuals (recorded, not changed):**
- A KeyboardInterrupt raised inside `_verify_commit` after the commit still goes to `_commit_match`'s `BaseException` undo path. That path re-raises the interrupt and records `interrupted`. The window is the same few git calls as N4.
- In the kept case with a tampered landed unit, `_breach` resets the live attempt, which runs `git restore --source=HEAD` on the unit. The worktree unit therefore ends as the kept commit's (tampered) blob. The tampered bytes are also in the quarantine and named in the record, and the night stops `guardrail` with nothing more committed.

**Commands and output:**
- `uv run pytest -q tests/test_driver_workers.py tests/test_driver.py tests/test_drive.py tests/test_session.py tests/test_cli.py`: 431 passed, 3 skipped (the pre-existing skips).
- `uv run pytest -q` (host, worktree): 3454 passed, 247 skipped. That is 7 more passes than round 1 (3447 / 247). There are no new skips: every skip is a pre-existing real-file skip (orig/, Watcom, watcom-media, Ghidra export not present in the worktree).
- `uv run ruff check .`: All checks passed.
- Container step still deferred to the orchestrator: `docker compose build && docker compose run --rm test`.

Execution context nonce: a596cd2757a044f9

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
