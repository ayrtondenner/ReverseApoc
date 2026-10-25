---
phase: 06-reporting-and-agent-pilot
plan: 17
subsystem: driver
tags: [claude-cli, stream-json, session, subprocess, tree-kill, fakeclaude, d-06, d-08]

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "06-12 hooks.ATTEMPT_PREFIX (the Bash allow rule), 06-15 attempt wrapper, 06-16 green baseline"
provides:
  - "tools/reverseapoc/session.py: build_argv (D-06 argv list), goal_prompt (D-07), SessionResult, run_session (cwd, transcript, 30-minute wall clock), kill_tree"
  - "tools/reverseapoc/streamjson.py: parse_line, parse, Disposition, classify (D-08 with documented precedence), check_init (fail closed), usage, tool_uses, parse_version, init_event"
  - "tests/fakeclaude.py: the stand-in claude (--scenario, --write, --spawn-child, --sleep, --exit)"
  - "tests/fixtures/stream/*.jsonl: 27 synthetic streams, one per D-08 signal and per bad init"
affects: [06-23, 06-25, 06-26, driver]

actuals:
  tokens: 14010  # chars/4 over the 32 files this plan created (56,042 chars)
  tasks: 3
  commits: 6  # measured: git rev-list --count 5d391a9..HEAD before this SUMMARY commit
plan_head_before: 5d391a95fc7e771f05cab9d5985e9a315bc99097
plan_head_after: 3e65e49104049191c771a1161ebb786b4c0bb9f3

tech-stack:
  added: []
  patterns:
    - "A subprocess runner with a reader thread, a queue and an injectable monotonic clock, so a deadline holds even when no line arrives"
    - "Tree kill: new process group at spawn, then System32 taskkill /T /F as an argv list (Windows) or killpg SIGKILL (POSIX)"
    - "Liveness probe that cannot kill: GetExitCodeProcess via ctypes on Windows (os.kill there terminates), signal 0 plus a /proc zombie check on POSIX"
    - "Stand-in CLI replaying fixture bytes through sys.stdout.buffer, so the transcript equals the fixture on Windows too"

key-files:
  created:
    - tools/reverseapoc/session.py
    - tools/reverseapoc/streamjson.py
    - tests/fakeclaude.py
    - tests/test_session.py
    - tests/test_streamjson.py
    - tests/fixtures/stream/ (27 .jsonl files)
  modified: []

key-decisions:
  - "classify precedence STOP > LIMIT > TRANSIENT > ATTEMPT_DONE; error words are read only from the CLI's own error text: a result's `result` field only when `is_error` is true (on a successful result it is the agent's last message), plus `errors[]`; never from agent messages (corrected in fix round 1, I2)"
  - "Unknown fails closed (fix round 1, I3 ruling): an api_retry error outside the known sets, an is_error result status other than 429/5xx, or a rejected rate_limit_event with an errorCode other than credits_required is STOP; an is_error 5xx/529 result is TRANSIENT; any other result is ATTEMPT_DONE; no result and no timeout is TRANSIENT"
  - "run_session kills the tree on any exception after Popen and re-raises (fix round 1, I1); on POSIX it also kills the session's group after a normal exit"
  - "EXPECTED_MODEL/EXPECTED_TOOLS live in streamjson; session builds --tools and the read/write part of --allowedTools from EXPECTED_TOOLS and keeps the literal \"claude-opus-5-5\" (acceptance criterion); a test pins session.MODEL == streamjson.EXPECTED_MODEL"
  - "run_session inherits stderr (the driver's console shows it) and gives the session no stdin (DEVNULL)"

patterns-established:
  - "Driver tests run sessions only through tests/fakeclaude.py with sys.executable; never the real claude"

requirements-completed: [AGT-01, AGT-03, AGT-04]

coverage:
  - id: D1
    description: "build_argv returns D-06's argv token for token (prompt right after -p, no --bare, Bash rule from ATTEMPT_PREFIX); goal_prompt names func, unit, wrapper check, notes.md and 25 check runs"
    requirement: AGT-01
    verification:
      - kind: unit
        ref: "tests/test_session.py#test_build_argv_is_d06, #test_goal_prompt_names_the_claim"
        status: pass
    human_judgment: false
  - id: D2
    description: "run_session runs the stand-in in cwd (F11), saves the raw stream byte-identical to the transcript, parses it; the 30-minute wall clock kills the whole tree including a grandchild (F34)"
    requirement: AGT-01
    verification:
      - kind: integration
        ref: "tests/test_session.py#test_run_session_with_fakeclaude_success, #test_timeout_kills_the_tree, #test_session_cwd_keeps_relative_writes_under_it, #test_fakeclaude_write_reaches_the_disk, #test_nonzero_exit_without_result_is_transient, #test_kill_tree_runs_taskkill_as_an_argv_list_on_windows, #test_alive_probe_sees_a_live_process"
        status: pass
    human_judgment: false
  - id: D3
    description: "classify maps every D-08 signal to LIMIT/STOP/TRANSIENT/ATTEMPT_DONE with documented precedence; never an outcome"
    requirement: AGT-04
    verification:
      - kind: unit
        ref: "tests/test_streamjson.py#test_classify_limit, #test_classify_stop, #test_classify_transient, #test_classify_attempt_done, #test_classify_precedence_stop_over_limit_over_transient_over_done, #test_dispositions_carry_no_outcome"
        status: pass
    human_judgment: false
  - id: D4
    description: "check_init names one problem per version/model/tools/MCP/plugin defect and fails closed; usage sums modelUsage; tool_uses lists paths; malformed lines counted"
    requirement: AGT-03
    verification:
      - kind: unit
        ref: "tests/test_streamjson.py#test_check_init_problems, #test_check_init_fails_closed_on_a_missing_or_unreadable_init, #test_usage_sums_model_usage, #test_tool_uses_lists_paths, #test_malformed_lines_are_counted"
        status: pass
    human_judgment: false
  - id: D5
    description: "The stream-json field names match what the real CLI emits (synthetic fixtures follow the Agent SDK types cited in RESEARCH)"
    verification: []
    human_judgment: true
    rationale: "No test may run the real claude; the owner's canary at the pilot checkpoint (06-25/06-26) shows a real init and result event, and check_init stops the run if a field differs"

duration: 13min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 17: Stream-json parser and session runner Summary

**The driver's session layer: D-06's exact `claude -p` argv as a list, the /goal prompt, a runner with a 30-minute wall clock that kills the whole process tree, a D-08 classifier with documented STOP > LIMIT > TRANSIENT > ATTEMPT_DONE precedence, fail-closed init assertions and modelUsage accounting, all proven against a stand-in claude that replays 27 synthetic streams.**

Execution context nonce: f2d0f6cfc04dea38

## Performance

- **Duration:** about 13 min of execution (plan work 14:16Z to 14:29Z, plus this summary)
- **Started:** 2026-10-25T14:16:15Z
- **Completed:** 2026-10-25T14:29Z
- **Tasks:** 3 of 3
- **Files created:** 32 (5 source/test files, 27 fixtures); none modified

## Accomplishments

- `session.build_argv(prompt, *, claude)` returns D-06 token for token; the `--allowedTools` Bash rule is built from `hooks.ATTEMPT_PREFIX` (`Bash(uv run --frozen reverseapoc attempt *)`), `--tools` from `streamjson.EXPECTED_TOOLS`; no `--bare`.
- `session.goal_prompt(function, unit, exe)` validates the three names, then names the claim, the wrapper `check` command, notes.md and "stop after 25 check runs".
- `session.run_session(argv, *, cwd, env, transcript, timeout_s=1800, popen, clock)` runs the session in `cwd` as a new process group, appends every raw stdout line to the transcript as it arrives, parses each line (malformed counted), and at the deadline calls `kill_tree` and reports `timed_out`.
- `streamjson.classify` covers every D-08 signal; `check_init` stops on version, model, tools, MCP or plugin surprises; `usage` sums modelUsage per class; `tool_uses` feeds the transcript audit; `parse_version` reads both `2.1.240` and `2.1.240 (Claude Code)`.
- `tests/fakeclaude.py` replays a fixture byte for byte and can write a file, spawn a sleeping child that reports its own pid, sleep and exit with a code.

## Task Commits

1. **Task 1 (tracer): D-06 argv, /goal prompt, stand-in session classified ATTEMPT_DONE**
   - RED `c250ff1` (test): collection failed with `ModuleNotFoundError: No module named 'reverseapoc.session'`. The feature was absent; this is the repo's precedent for a new module (04-08, 06-02, 06-14).
   - GREEN `40ed703` (feat): 3 passed. Tracer gate (interactive, end-of-phase, automated-only verify): `uv run pytest -q tests/test_session.py` re-run, 3 passed, expanded.
2. **Task 2: every D-08 class and the init assertion**
   - RED `f8fdbc7` (test): collection failed with `ImportError: cannot import name 'ToolUse' from 'reverseapoc.streamjson'`; the classifier arms, check_init, usage and tool_uses did not exist.
   - GREEN `3d9f99c` (feat): `tests/test_streamjson.py` and `tests/test_session.py` 57 passed.
3. **Task 3: wall clock kills the tree; stand-in writes and exits**
   - RED `efb716b` (test): collection failed with `ImportError: cannot import name 'kill_tree' from 'reverseapoc.session'`; the stand-in had no `--write`/`--spawn-child`/`--sleep`/`--exit` yet.
   - GREEN `3e65e49` (feat): 63 passed in the two files; 5 repeated runs of test_session all 9 passed (about 3.8 s each).
   - Mutation probe (scratch, not committed): with `kill_tree` reduced to killing the root only, `test_timeout_kills_the_tree` failed with `AssertionError: child 17736 outlived the tree kill`; the leftover child was then killed by hand.

No REFACTOR commits were needed.

## Files Created/Modified

- `tools/reverseapoc/session.py` - argv, /goal prompt, SessionResult, run_session, kill_tree
- `tools/reverseapoc/streamjson.py` - parsing, Disposition, classify, check_init, usage, tool_uses, parse_version, init_event
- `tests/fakeclaude.py` - the stand-in claude
- `tests/fixtures/stream/*.jsonl` - 27 synthetic streams: success, rate_limit, rejected, http429, limit_text, auth, oauth, hold, billing, credits, low_credit_text, not_logged_in, overloaded, server_error, no_result, max_turns, max_budget, during_execution, malformed, bad_init_{v1,v3,old,model,no_bash,extra_tool,mcp,plugin}
- `tests/test_session.py` (9 tests), `tests/test_streamjson.py` (54 tests)

## Verification

- `uv run pytest -q tests/test_session.py tests/test_streamjson.py`: 63 passed.
- `uv run pytest -q -rs` (host, worktree): 2146 passed, 224 skipped in 52.46 s. Every skip is a real-file test whose orig/ or third_party/ tree is absent from a worktree (orig/*.EXE not present, Watcom 10.6 not installed, watcom-media not present); none is in test_session.py or test_streamjson.py.
- `uv run ruff check .`: All checks passed. `ruff format --check` on the five new Python files: already formatted.
- Acceptance: session.py contains `"claude-opus-5-5"` and `"--strict-mcp-config"`, no `"--bare"`; `def kill_tree(` with `[_taskkill(), "/T", "/F", "/PID", str(pid)]`; the fixtures hold no hex blob of 16+ characters and no game text; streamjson.py documents the precedence.
- No test or command ran the real claude, `drive`, docker or any network call.

## Decisions Made

See key-decisions in the frontmatter.

## Deviations from Plan

**1. Orchestrator ruling F11: a cwd for the session.** `run_session` takes a keyword-only `cwd` and passes it to Popen; `build_argv` keeps `--settings` and `--append-system-prompt-file` repo-relative. fakeclaude resolves `--write PATH` against its own cwd (`Path.cwd() / PATH`). Test: `test_session_cwd_keeps_relative_writes_under_it` (a relative write with `cwd=tmp/checkout` lands there, and neither the repository nor the test's cwd gets the file). Commits efb716b, 3e65e49 (signature from 40ed703).

**2. Orchestrator ruling F34: a child to kill.** fakeclaude gains `--spawn-child`: it starts a child Python that prints its own pid and sleeps 120 s, then emits `{"type":"system","subtype":"fake_child","pid":N}`. `test_timeout_kills_the_tree` asserts that pid is gone within 10 s after `run_session` returns; `test_alive_probe_sees_a_live_process` proves the probe can report a live process. Commits efb716b, 3e65e49.

**3. [Rule 3 - TDD order] fakeclaude's `--write`/`--sleep`/`--exit` moved from Task 1 to Task 3.** Task 1's action lists them, but then Task 3's write and exit tests would have passed at RED (unexpected green). Task 1 shipped `--scenario` only; Task 3's RED failed and its GREEN added the options. Likewise `timeout_s`/`clock` joined `run_session` in Task 3.

**4. [Rule 1 - Flakiness] The tree-kill test uses a 3 s wall clock, not 1 s.** fakeclaude and its child are two Python start-ups (through the venv launcher on Windows), about 0.4 s here; 1 s left too little margin for a loaded host or the container. 3 s is still a tenth of the stand-in's 30 s sleep, and the test also asserts the run returned within 20 s. Constant `_TREE_TIMEOUT_S` in tests/test_session.py, commit 3e65e49.

**5. [Rule 2 - Fail closed] Small additions beyond the plan's lists, each tested:** a rejected rate_limit_event with an unknown errorCode is STOP; limit and credit words are never read from the agent's messages (`test_classify_ignores_limit_words_outside_the_result`; the first version still read a successful result's own text, corrected by fix round 1 I2); `goal_prompt` refuses names that are not identifiers; `check_init` reports an unreadable version or a non-list `tools`; `kill_tree` calls taskkill by its System32 path; `run_session` gives the session no stdin (`claude -p` reads piped stdin). `init_event` and `Parsed` are small helpers not named in the plan.

**6. Orchestrator ruling (fix round 1 I3): unknown error signals become STOP.** This overrides the plan's TRANSIENT wording ("overloaded/server_error with no result, or a non-zero exit with no result") and its "a result event -> ATTEMPT_DONE" arm for error results:
- an `is_error: true` result with a 5xx `api_error_status` (529 included) is TRANSIENT (not counted), even though a result exists;
- 429 stays LIMIT;
- any other `is_error` status (400, 401, 403, a non-integer, ...) is STOP;
- an api_retry error outside the known sets (`cloud_credential_error`, `model_not_found`, `invalid_request`, `max_output_tokens`, `unknown`, a missing or future code) is STOP, even if a clean result follows.
Fixtures `cloud_credential.jsonl` (STOP) and `overloaded_result.jsonl` (TRANSIENT); tests `test_classify_error_results_from_the_review_probes`, `test_classify_server_error_result_is_transient`, `test_classify_other_error_status_stops`, `test_classify_429_result_stays_limit`, `test_classify_unknown_api_retry_error_stops`. Commits 4d216e0 (RED), e40d33c (GREEN).

**Total deviations:** 3 orchestrator rulings applied (F11, F34, fix round 1 I3), 3 auto-fixed (1 TDD ordering, 1 flakiness, 1 fail-closed hardening group), plus the fix round 1 items below. **Impact:** no scope change; every change has a test.

## Fix round 1 (FIX_BASE 451eec1; review-06-17.md, rulings fixround-06-17-r1.md)

| Item | Finding | Fix | Tests | Commits (RED, GREEN) |
|---|---|---|---|---|
| I1 | An exception mid-read left the whole session tree running with no pid returned; `parse_line` let RecursionError escape (one deeply nested line was fatal) | `run_session`: `except BaseException` after Popen kills the tree and reaps if the session still runs, then re-raises; `parse_line` treats RecursionError as malformed | `test_an_exception_mid_read_kills_the_tree_and_propagates` (injected clock raises KeyboardInterrupt on a `--spawn-child` run; root and child gone), `test_run_session_through_an_injected_popen_counts_a_deep_line_as_malformed`, `test_parse_line_counts_deep_nesting_as_malformed` | 26f5158, 8a6be26 |
| I2 | A successful result's `result` (the agent's own words) could trigger LIMIT or STOP | error words read from `result` only when `is_error` is true; `errors[]` still read; docstring and key decision corrected | `test_classify_reads_no_error_words_from_a_successful_result` (3 texts, incl. the review's two probes); every existing error fixture classifies as before | 4d216e0, e40d33c |
| I3 | Unknown error signals fell to TRANSIENT or ATTEMPT_DONE | orchestrator ruling, Deviation 6 above | see Deviation 6 | 4d216e0, e40d33c |
| Minor 1 | No tree kill after a normal exit | POSIX: kill the session's group after the reap (ProcessLookupError ignored); `kill_tree` refuses pid < 1 (killpg(0) is the caller's group). Windows: known limit below | `test_a_normal_exit_kills_the_group_on_posix`, `test_a_normal_exit_kills_nothing_on_windows`, `test_kill_tree_refuses_a_pid_that_names_the_callers_group`, `test_a_descendant_dies_when_the_session_exits_on_posix` (skips on Windows: `POSIX-only: taskkill /T cannot find children after the parent exits`, an R-A reason) | a0ac314, 773fecc |
| Minor 2 | Docstring claimed a TRANSIENT-over-ATTEMPT_DONE precedence that could not happen | docstring rewritten; the precedence test now has a real case (`overloaded` + 529 result -> TRANSIENT) | `test_classify_precedence_stop_over_limit_over_transient_over_done` | 4d216e0, e40d33c |
| Minor 3 | `rate_limit` retry then success is LIMIT (plan-mandated) | unchanged; noted for 06-23 below | - | - |
| Minor 4 | `popen`/`clock` injection never exercised | the I1 tests drive both | (I1 tests) | 26f5158 |
| Minor 5 | TDD order (collection-level REDs) | every fix-round RED failed on an assertion; new tests import only existing names | - | - |
| Minor 6 | Duplicate tools gave "missing none, extra none" | the message names `duplicate <tool>` | `test_check_init_names_duplicate_tools` | 4d216e0, e40d33c |

RED evidence, each failing on an assertion for the right reason:
- 26f5158: `AssertionError: the session root outlived the exception`, `Failed: a deeply nested line was fatal: RecursionError(...)`, `assert RecursionError(...) is None`. The test's own cleanup killed the leftover tree; a wmic scan afterwards found no fakeclaude or sleeper process.
- 4d216e0: 24 AssertionErrors (for example `ATTEMPT_DONE is STOP` for `cloud_credential`, `LIMIT is ATTEMPT_DONE` for the success text, `'duplicate Read' in ...`).
- a0ac314: `assert [] == [4242]`, and `isinstance(AttributeError("module 'os' has no attribute 'killpg'"), ValueError)`.

Verification after the fix round (host, worktree):
- `uv run pytest -q tests/test_session.py tests/test_streamjson.py`: 93 passed, 1 skipped (the POSIX-only test).
- `uv run pytest -q -rs`: 2176 passed, 225 skipped in 49.06 s. The only new skip is the POSIX-only line above; the rest are real-file tests with no orig/ or third_party/ in a worktree.
- `uv run ruff check .`: All checks passed; `ruff format --check` on the five Python files: already formatted.
- No fakeclaude or sleeper process was left after the runs (wmic scan: 0).

### Known limits and container gate items

- **Windows, after a normal exit:** a descendant that outlives claude is not killed. `taskkill /T` finds children through a live parent only, and a Job Object is out of scope. 06-23's orphan-container cleanup by name covers `docker compose run`, not stray host processes.
- **POSIX setsid escape:** `killpg` reaches only the session's own process group. A descendant that calls setsid (a Node child spawned `detached`, a `docker compose run`) escapes it. The driver runs on the Windows host (D-34), where `taskkill /T` follows parent pids, so this matters only if the driver runs on POSIX.
- **Container run (wave gate G4):** the POSIX branch of `kill_tree` (`os.killpg`), the post-exit group kill, the `/proc/<pid>/stat` zombie probe, `test_timeout_kills_the_tree`, `test_an_exception_mid_read_kills_the_tree_and_propagates` and `test_a_descendant_dies_when_the_session_exits_on_posix` have not run under Linux yet. Docker is forbidden in a worktree, so G4 must run tests/test_session.py in the container.

## Issues Encountered

- The harness refused compound shell commands that mention git (`cd ... && git ...`, `$(git rev-parse ...)` in one line) as too complex to verify; the same steps ran as plain separate commands. The plan-head ledger file was therefore not written under .git; the base 5d391a9 comes from the dispatch prompt.

## Known Stubs

None.

## Threat Flags

None. run_session starts a subprocess, which is the plan's own trust boundary (T-06-41/T-06-42 mitigated as planned).

## User Setup Required

None.

## Next Phase Readiness

- 06-23 (driver loop) composes: `build_argv(goal_prompt(...), claude=...)`, `run_session(..., cwd=REPO_ROOT, env=..., transcript=<attempt dir>/transcript.jsonl)`, `init_event` + `check_init` (problem -> STOP), `classify`, `usage(result)` and `tool_uses` for the stray-write audit.
- 06-25 owns the tested-major and minimum-version constants that `check_init` takes as arguments.
- Fixed in fix round 1 (I1): `run_session` itself kills the tree on any exception, Ctrl+C included, so 06-23 needs no wrapper.
- For 06-23 (review minor 3, plan-mandated): an api_retry `rate_limit` followed by a successful result is LIMIT. Gate or keep the session's work before any LIMIT reset, so a match made after a retried 429 is not thrown away.
- For 06-23: an unknown api_retry error is now STOP even when the session then recovered (I3 ruling). If the canary shows a benign code such as `max_output_tokens` retried routinely, the owner may widen the known set.

## Self-Check: PASSED

- Files: tools/reverseapoc/session.py, tools/reverseapoc/streamjson.py, tests/fakeclaude.py, tests/test_session.py, tests/test_streamjson.py and tests/fixtures/stream/ (29 files after fix round 1) exist.
- Commits c250ff1, 40ed703, f8fdbc7, 3d9f99c, efb716b, 3e65e49 and, for fix round 1, 26f5158, 8a6be26, 4d216e0, e40d33c, a0ac314, 773fecc are ancestors of HEAD.
- No modification to STATE.md, ROADMAP.md, orig/, config/ or build scripts.

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
