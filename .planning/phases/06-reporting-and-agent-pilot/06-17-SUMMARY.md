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
  - "classify precedence STOP > LIMIT > TRANSIENT > ATTEMPT_DONE; result text is read only from the result event (result, errors[]), never from agent messages, so the model cannot stop or stall the run by writing the words"
  - "A rejected rate_limit_event with an errorCode other than credits_required is STOP (unknown, fail closed); any result event of any subtype is ATTEMPT_DONE; no result and no timeout is TRANSIENT"
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

**5. [Rule 2 - Fail closed] Small additions beyond the plan's lists, each tested:** a rejected rate_limit_event with an unknown errorCode is STOP; limit and credit words are read only from the result event (`test_classify_ignores_limit_words_outside_the_result`); `goal_prompt` refuses names that are not identifiers; `check_init` reports an unreadable version or a non-list `tools`; `kill_tree` calls taskkill by its System32 path; `run_session` gives the session no stdin (`claude -p` reads piped stdin). `init_event` and `Parsed` are small helpers not named in the plan.

**Total deviations:** 2 orchestrator rulings applied, 3 auto-fixed (1 TDD ordering, 1 flakiness, 1 fail-closed hardening group). **Impact:** no scope change; every change has a test.

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
- `run_session` does not kill the tree if the driver itself raises mid-read (for example Ctrl+C); 06-23 may want a try/finally around it.

## Self-Check: PASSED

- Files: tools/reverseapoc/session.py, tools/reverseapoc/streamjson.py, tests/fakeclaude.py, tests/test_session.py, tests/test_streamjson.py and tests/fixtures/stream/ (27 files) exist.
- Commits c250ff1, 40ed703, f8fdbc7, 3d9f99c, efb716b, 3e65e49 are ancestors of HEAD.
- No modification to STATE.md, ROADMAP.md, orig/, config/ or build scripts.

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
