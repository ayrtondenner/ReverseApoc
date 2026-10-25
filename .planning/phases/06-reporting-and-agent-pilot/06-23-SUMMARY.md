---
phase: 06-reporting-and-agent-pilot
plan: 23
subsystem: driver
tags: [driver, night-loop, attempts-jsonl, schema, guardrail, quarantine, d-07, d-08, d-17, d-23, d-24, d-25, d-34]
status: complete

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "06-17 session.run_session/build_argv/goal_prompt and streamjson.classify/check_init/usage/tool_uses; 06-14 picker.Pick/queue/requeue; 06-12 hooks.matching_write_allowed/candidates; 06-15 attempt wrapper layout (checks.jsonl, checks/NNNN.c, container_prefix, notes path); 06-11/06-18 gate and gate --partial (status.csv, decomphub.progress.json)"
provides:
  - "tools/reverseapoc/driver.py: DriveConfig, Deps, DriveReport, drive, git_runner, commit_message, commit_paths, gate_sha1s, append_record, validate_record, RecordError, RECORD_FIELDS, RUN_REASONS, parse_status, transcript_paths, read_checks, CheckSummary, load_difficult, save_difficult"
  - "progress/attempts.jsonl: the committed public attempt log, empty (0 bytes) until the pilot"
  - "tests/test_driver.py (60 tests incl. parametrized cases), tests/test_attempts_schema.py (the D-23 schema)"
affects: [06-25 drive verb (wires the real Deps), 06-26 pilot, 06-27 phase gate (greps the STOPPED record's reason)]

actuals:
  tokens: 28200   # chars/4 over the three files this plan created (112,811 chars); progress/attempts.jsonl is 0 bytes
  tasks: 3
  commits: 12     # measured: git rev-list --count dd681dc..HEAD before this SUMMARY commit
plan_head_before: dd681dc657a470646624354b0672af9370234b81
plan_head_after: e02b4c28ed42c068e34e8ac0d049f3e945ece3c2

tech-stack:
  added: []
  patterns:
    - "Every effect injected through a frozen Deps dataclass; tests run tests/fakeclaude.py through the real run_session in a tmp git repo with a sanitized git environment"
    - "F3 audit by pre/post snapshot: git status entries + SHA-256 + bytes, pinned out-of-git files by bytes, and a (path, size, mtime_ns) fingerprint"
    - "Every git call through --literal-pathspecs; explicit-path commits only (git add -- / git commit -F -- )"
    - "Guardrail containment: copy/move into build/driver/<run>/quarantine/ with lstat checks per component, O_EXCL|O_NOFOLLOW, never overwrite, restoration independent of the copy"
    - "Records validated against pinned key sets before every append; append-only LF JSON lines"

key-files:
  created:
    - tools/reverseapoc/driver.py
    - tests/test_driver.py
    - tests/test_attempts_schema.py
    - progress/attempts.jsonl
  modified: []

key-decisions:
  - "Only the driver's gate exit 0 is MATCHED; the lint runs first and a failed lint is PARTIAL \"lint\" with the gate never run, so status.csv is untouched"
  - "A LIMIT session that changed the unit or wrote a header is judged (lint, gate); a pass is a counted MATCHED, else it is reset; then the 60/120/240/300 s backoff"
  - "TRANSIENT_TRIES = 3 sessions in a row (the plan's test wording: three times -> one abort record), then the function is left for this pass"
  - "check_init runs on any session that has an init event and on a counted session with a result; a timed-out session without init is not judged by it"
  - "The transcript audit judges write-tool paths against the checkout root and the cwd the CLI reports in its init event (the same directory, possibly spelled differently)"
  - "Each launch starts in a fresh attempt dir: an uncounted launch's directory moves to attempt-<n>-uncounted-<k>, so the counted session's best C path stays attempt-<n>/best/<unit>.c (F7)"
  - "The end-of-night chore commit holds the log plus changed status.csv/feed after ENDED, only the log after a STOP (a gate may have half-written a table), and nothing after a guardrail stop"
  - "A stray edit of a file the driver itself had changed this night goes back to its pre-session bytes, not to HEAD, so the night's partial rows and records survive containment"

patterns-established:
  - "Driver tests: Night harness (tmp repo + fakes) and Sess scripts; never the real claude, docker or network"

requirements-completed: [AGT-01, AGT-02, AGT-03, AGT-04, AGT-06]

coverage:
  - id: D1
    description: "Tracer: one pick, the stand-in edits the unit, the fake gate passes, one feat commit with exactly the unit, status.csv, the feed, attempts.jsonl (and new headers, F5), the D-25 subject, body and trailers; env names the claim with absolute paths (F28), cwd is the checkout (F11), containers removed by the wrapper's prefix"
    requirement: AGT-01
    verification:
      - kind: integration
        ref: "tests/test_driver.py#test_match_commits_one_function, #test_match_record_is_appended, #test_session_env_names_the_claim, #test_match_commit_adds_new_files"
        status: pass
    human_judgment: false
  - id: D2
    description: "Caps and difficult list: 3 counted sessions per function per pass, difficult.json once, back only through requeue; max_sessions and target_matched; empty queue writes ENDED nothing to do"
    requirement: AGT-02
    verification:
      - kind: integration
        ref: "tests/test_driver.py#test_three_attempts_then_difficult, #test_difficult_returns_only_through_requeue, #test_max_sessions_and_target_matched, #test_empty_queue_runs_nothing"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-08 handling: LIMIT backoff 60/120/240 then 300 s polls, not counted, keeps its work; STOP classes and check_init problems end the run; TRANSIENT x3 -> one abort record; timeout counted; a session exception is a STOP"
    requirement: AGT-04
    verification:
      - kind: integration
        ref: "tests/test_driver.py#test_limit_backs_off_and_is_not_counted, #test_limit_polls_every_five_minutes, #test_limit_session_keeps_its_work, #test_a_limit_relaunch_gets_a_fresh_attempt_dir, #test_stop_classes_end_the_run, #test_transient_retries_then_aborts, #test_timeout_is_counted, #test_session_exception_stops_the_run"
        status: pass
    human_judgment: false
  - id: D4
    description: "Gate decides (AGT-06): 100% in the check log with gate exit 1 is PARTIAL; PARTIAL saves the best plain check's C (F10) and runs gate --partial on its repo-relative path (F7); GAVE_UP resets and deletes a scaffolded unit; lint failure is PARTIAL lint; gate exit 2 stops"
    requirement: AGT-06
    verification:
      - kind: integration
        ref: "tests/test_driver.py#test_hundred_percent_with_failing_gate_is_partial, #test_partial_resets_and_logs, #test_gave_up_resets, #test_lint_failure_is_partial_and_commits_nothing, #test_gate_tool_error_stops_the_run"
        status: pass
    human_judgment: false
  - id: D5
    description: "Audit and guardrail (D-17, F3, security rulings): stray writes stop the night; the driver's own changes are in the snapshot; odd include/ entries, pinned out-of-git files and fingerprint changes stop it; strays are restored or quarantined safely, per file, with every path recorded"
    requirement: AGT-01
    verification:
      - kind: integration
        ref: "tests/test_driver.py#test_stray_write_resets_and_stops, #test_session_editing_status_stops_the_night, #test_partial_then_second_session_has_no_guardrail_stop, #test_an_untracked_include_entry_outside_the_header_form_stops, #test_a_session_adding_a_git_hook_stops_and_the_hook_is_quarantined, #test_a_guardrail_stop_restores_tracked_strays_and_quarantines_new_ones, #test_a_linked_quarantine_component_stops_and_writes_nothing, #test_a_refused_quarantine_never_skips_restoration, #test_a_fingerprint_change_stops_the_night, #test_a_raising_session_has_its_strays_contained"
        status: pass
    human_judgment: false
  - id: D6
    description: "attempts.jsonl: records in execution order, never rewritten; schema refuses missing/extra keys, wrong types/enums, F30 reason, 65-hex strings; committed log empty and valid; failed attempts committed at night's end"
    requirement: AGT-03
    verification:
      - kind: unit
        ref: "tests/test_attempts_schema.py (all); tests/test_driver.py#test_records_are_in_order, #test_failed_attempts_are_committed_at_the_end, #test_a_stopped_night_commits_only_the_log, #test_a_guardrail_stop_commits_nothing"
        status: pass
    human_judgment: false
  - id: D7
    description: "The Deps the real night uses (claude argv, docker gate/lint/partial gate, container removal, picker wiring) behave as the fakes assume"
    verification: []
    human_judgment: true
    rationale: "Wiring the real effects is plan 06-25 (drive verb, preflight, canary); no test may run the real claude or docker"

duration: 58min
completed: 2026-10-25
---

# Phase 6 Plan 23: The night driver loop and attempts.jsonl Summary

**`driver.drive(config, deps)`: one fresh stand-in session per attempt in the checkout, D-08 backoff and stop classes, 3 sessions per function then difficult.json, a lint plus container gate that alone decides MATCHED, one explicit-path D-25 commit per match, D-34 resets with PARTIAL best-C partial gates, an F3 audit widened by four security rulings into pinned-path, fingerprint and quarantine containment, and a schema-checked append-only progress/attempts.jsonl committed empty.**

Execution context nonce: a614de404c7eae94

## Performance

- **Duration:** about 58 min (15:51Z to 16:49Z, plus the final suite and this summary)
- **Started:** 2026-10-25T15:51:11Z
- **Completed:** 2026-10-25T16:49Z
- **Tasks:** 3 of 3, plus four security passes ordered by the orchestrator
- **Files created:** 4 (driver.py, two test files, the empty log); none modified

## Accomplishments

- **The loop** (`_Night`): STARTED record, the persisted difficult list minus `deps.requeue`, picks from `deps.queue(difficult)`, at most `attempts_per_function` counted sessions per function, then the difficult list; ENDED on `nothing to do`, `max sessions`, `target matched` or `queue exhausted`.
- **One session:** fresh attempt dir, scaffold if the unit is missing, the context pack, `session.goal_prompt` -> `deps.argv` -> `deps.session(..., cwd=repo_root, env=base + the four REVERSEAPOC_* absolute paths, transcript=<dir>/transcript.jsonl, timeout_s=1800)`, then `deps.remove_containers(attempt.container_prefix(dir))` in a `finally`.
- **After it:** the audit, then `classify`; STOP -> STOPPED `stop signal`; a check_init problem -> STOPPED `init`; LIMIT -> salvage (judge if the unit changed), backoff 60/120/240 then 300 s; TRANSIENT -> reset, 3 in a row -> `abort` record; ATTEMPT_DONE (result or timeout) -> counted.
- **A counted session:** lint (exit 1 -> PARTIAL `lint`, exit 2 -> STOPPED `tool`), gate (exit 0 with both SHA-1s -> record + `commit_paths`; exit 1 -> reset, PARTIAL if the best plain check > 0 with the best C copied to `best/<unit>.c` and `partial_gate(pick, "build/driver/<run>/<exe>/<func>/attempt-<n>/best/<unit>.c", n)`, else GAVE_UP; exit 2 -> STOPPED `tool`).
- **Records:** `attempt` (function, exe, unit, start, run, attempt, outcome, abort_reason, turns, tokens by class, cost_usd, seconds, model, cli_version, check {runs, best_percent, sweep_hit, needs}, pack_bytes, truncated, date), `abort`, `run` (event, reason, detail, sessions, matched). `validate_record` pins every key set and type and refuses any 65+ hex run; `append_record` validates first.
- **End of night:** `chore(driver): attempt log` with explicit literal paths.

## Task Commits

1. **Task 1 (tracer): pick to commit**
   - RED `49c5aa6` (test): 4 tests failed on assertions (no commit, no launch, no scaffold). driver.py was an interface skeleton (types and a no-op `drive`) so the failure is an assertion, not an import.
   - GREEN `4003fb5` (feat): 4 passed. Tracer gate (interactive, end-of-phase, automated-only verify): `uv run pytest -q tests/test_driver.py` re-run, passed, expanded.
2. **Task 2: caps, backoff, stops, audit, reset** (plus the first security ruling)
   - RED `cdd5997` (test): 32 failed, 31 on assertions; the one other failure is `test_session_exception_stops_the_run`, where the injected RuntimeError escaped `drive`, which is the behaviour the test asks for. `transcript_paths` was a stub returning `[]` so its test failed on the assertion.
   - GREEN `78e68d1` (feat): 35 passed. The commit also carries `ruff format` of tests/test_driver.py (layout only).
3. **Task 3: schema, chore commit, empty log**
   - RED `81bd84a` (test): 27 failed on assertions (22 `DID NOT RAISE RecordError`, the log not tracked, 4 chore-commit assertions). `validate_record` and `RecordError` were stubs. `test_schema_accepts_driver_records` and `test_a_guardrail_stop_commits_nothing` passed at RED as pins.
   - GREEN `271ce21` (feat): 70 passed; full host suite 2544 passed, 48 skipped; ruff clean.
4. **Security pass 2 (pinned paths, guardrail cleanup):** RED `97e853f` (5 assertion failures, plus a DriverError: git ran the agent's planted `.git/hooks/pre-commit` during the match commit, the hole being closed), GREEN `9f39c50`.
5. **Security pass 3 (safe quarantine, wider audit, crashes):** RED `971da41` (9 assertion failures, 1 R-A skip; the never-overwrite and build/ exclusion tests are pins), GREEN `855a1b1`.
6. **Security pass 4 (restoration never depends on the quarantine):** RED `1f34dea` (`assert '# changed\n' == '# made up\n'`), GREEN `e02b4c2`.

## Files Created/Modified

- `tools/reverseapoc/driver.py` - the loop, its records, schema, commit, audit, reset and containment
- `tests/test_driver.py` - the Night harness (tmp repo, fakeclaude via run_session, fake gates) and the driver tests
- `tests/test_attempts_schema.py` - the D-23 schema tests
- `progress/attempts.jsonl` - empty, tracked

## Verification

- `uv run pytest -q tests/test_attempts_schema.py tests/test_driver.py`: 89 passed, 1 skipped (`symlink creation needs privileges on this host`, R-A; its junction twin runs on this host).
- `git ls-files --error-unmatch progress/attempts.jsonl`: tracked, 0 bytes.
- Full host suite (worktree, REVERSEAPOC_ORIG/WATCOM_DIR/GHIDRA_EXPORT at the main checkout) at 855a1b1 (third pass): 2568 passed, 43 skipped in 436.72 s. The skips are tools absent on the host (objdiff-cli, ninja, clang, Ghidra), watcom-media absent from a worktree, POSIX-only and privilege cases, plus this plan's one R-A symlink skip.
- `uv run ruff check .`: All checks passed. `ruff format --check` on the three Python files: formatted.
- Acceptance: driver.py contains `Matched-By: reverseapoc drive` and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; a test records the git argv and asserts no `-A`, `--all` or `.` and `--literal-pathspecs` on every add/commit; tests/test_driver.py contains `test_stray_write_resets_and_stops` and `test_three_attempts_then_difficult`.
- No test or command ran the real claude, `drive`, docker or anything that reaches the network. The tests run local git in tmp repos and fakeclaude by absolute path through sys.executable.

## Decisions Made

See key-decisions in the frontmatter.

## Deviations from Plan

**Orchestrator rulings (rulings.md ## 06-23), applied as plan text:**

1. **Orchestrator ruling F3: audit only what the session changed.** `_snapshot` takes `git status --porcelain=v1 --untracked-files=all -z` with SHA-256 (and bytes) of each path right before the session; afterwards only changed entries plus transcript write paths go through `matching_write_allowed`. Tests: `test_partial_then_second_session_has_no_guardrail_stop`, `test_session_editing_status_stops_the_night`.
2. **Orchestrator ruling F5: add new files before the commit.** `commit_paths` runs `git add -- <paths>` then `git commit -F <msg> -- <paths>`. Test: `test_match_commit_adds_new_files` (scaffolded unit + include/x.h).
3. **Orchestrator ruling F7 (consumer):** the partial gate gets `build/driver/<run>/<exe>/<func>/attempt-<n>/best/<unit>.c`. Test: `test_partial_resets_and_logs`.
4. **Orchestrator ruling F10 (consumer):** the best C is the highest-percent plain line's `checks/NNNN.c`, ties to the earliest, sweep lines, null percents and exit-2 lines skipped. Test: `test_partial_resets_and_logs`.
5. **Orchestrator ruling F11 (consumer):** `run_session(..., cwd=config.repo_root)`. Tests: `test_session_env_names_the_claim`, `test_stray_write_resets_and_stops` (the real checkout has no tools/x.py).
6. **Orchestrator ruling F28:** `DriveConfig.tested_major` and `min_cli_version` are passed to `check_init`; REVERSEAPOC_ATTEMPT_DIR/NOTES are absolute. Tests: `test_session_env_names_the_claim`, `test_stop_classes_end_the_run[bad_init_*]`.
7. **Orchestrator ruling F30:** the STOPPED record's key is `reason`, pinned with an enum per event in `validate_record`. Test: `test_schema_refuses_bad_records[stopped without reason]`, `[reason of another event]`.
8. **06-15 notes:** attempts.jsonl uses `kind`/`exe`/`function`, so `contextpack`/`attempt._attempt_records` needed no change; REVERSEAPOC_ATTEMPT_NOTES is `<attempt dir>/notes.md`, absolute; the best C excludes sweep lines and null percents; the lint runs before a match is committed and a failed lint is PARTIAL "lint" (`test_lint_failure_is_partial_and_commits_nothing`); orphan containers are removed through `attempt.container_prefix(attempt_dir)` after every session, also when it raises (`test_session_env_names_the_claim`, `test_session_exception_stops_the_run`).
9. **06-17 notes:** a LIMIT session keeps its work and is gated as usual (`test_limit_session_keeps_its_work`, with the `rejected` fixture plus a unit write, since no 429-then-success fixture exists); a raising `run_session` is a STOP with the reason recorded (`test_session_exception_stops_the_run`). The ruling's "before stopping the night" is read with the plan's truth that LIMIT backs off and is not a STOP.

**Security rulings (security-findings-06-23.md), each RED then GREEN:**

10. **Security ruling (06-23 commit_match):** every git call goes through `--literal-pathspecs`; an untracked include/ entry is committed only if it matches `include/[A-Za-z0-9_]+(/[A-Za-z0-9_]+)*\.h` and passed `matching_write_allowed`; any other untracked include/ entry is a guardrail stop naming it, with nothing committed. Tests: `test_an_untracked_include_entry_outside_the_header_form_stops[include/*.h | include/x[1].h | include/a.txt]` (`*.h` is reported by the fake git, NTFS cannot hold it), `test_a_plain_new_header_is_committed_with_literal_pathspecs`. Commits cdd5997, 78e68d1.
11. **Security ruling (gitignored paths):** the snapshot also keeps the bytes of `.git/config`, every file under `.git/hooks/` and `.githooks/`, `.claude/settings.local.json`, `config/driver/claude-settings.json`, `.venv/pyvenv.cfg` and the venv's `.pth` files; any change is a guardrail stop naming the path. Commits 97e853f, 9f39c50.
12. **Security ruling (guardrail cleanup):** strays are copied (tracked) or moved (new) into `build/driver/<run>/quarantine/<path>`; tracked ones go back with `git restore --source=HEAD --staged --worktree`, `.git` and other pinned files to their pre-session bytes; the record lists stray, restored and quarantined paths; nothing is deleted. One refinement, recorded: a stray edit of a file the driver itself had changed this night (status.csv partial rows, attempts.jsonl) goes back to its pre-session bytes instead of HEAD, so the night's own work survives (`test_a_guardrail_stop_keeps_the_drivers_own_pending_rows`). The attempt's own unit and new headers are copied there too before the reset. Commits 97e853f, 9f39c50.
13. **Security ruling, third pass (HIGH, quarantine write):** the quarantine is created at run start; each component below the checkout is lstat-checked (symlink, junction, reparse point -> refused); the target must resolve inside the quarantine root; files are created `O_CREAT|O_EXCL` (+`O_NOFOLLOW` where it exists), never overwritten (`.1`, `.2` suffixes); a link the session left is kept as a `.link` note naming its target; the pinned snapshot and the fingerprint are taken again after containment and anything still changed is named. Tests: `test_the_quarantine_exists_before_any_session`, `test_a_linked_quarantine_component_stops_and_writes_nothing` (junction on Windows, symlink elsewhere, no skip), `test_a_symlinked_quarantine_at_run_start_stops_before_any_session` (R-A skip on this host), `test_a_quarantined_file_is_never_overwritten`, `test_a_pinned_change_after_containment_is_reported`. Commits 971da41, 855a1b1.
14. **Security ruling, third pass (MEDIUM, blind spots):** `.git/info/exclude`, `.git/info/attributes` and every venv `sitecustomize.py`/`usercustomize.py` are pinned; a (path, size, mtime_ns) fingerprint of the venv's site-packages and every repo `__pycache__` outside build/, .venv and .git is taken right before and after each session; a difference stops the night naming the first paths (lists capped at 50). Tests: `test_more_pinned_paths_stop_the_night[x4]`, `test_a_fingerprint_change_stops_the_night[x2]`, `test_a_pycache_under_build_is_not_fingerprinted`. Commits 971da41, 855a1b1.
15. **Security ruling, third pass (MEDIUM, exception path):** a raising session is measured and contained before the ERROR stop, and the record lists it. Test: `test_a_raising_session_has_its_strays_contained`. Commits 971da41, 855a1b1.
16. **Security ruling, fourth pass:** containment handles each file alone; restoring tracked and pinned files never depends on the quarantine; a new stray whose quarantine is refused stays in place, named "not contained"; each refusal is recorded per file. Test: `test_a_refused_quarantine_never_skips_restoration`. Commits 1f34dea, e02b4c2.

**Auto-fixed / plan-reading deviations:**

17. **[Rule 3 - TDD order] Interface skeletons in RED commits.** Task 1's RED carried a skeleton driver.py, Task 2's a `transcript_paths` stub, Task 3's `validate_record`/`RecordError` stubs, so every RED failed on an assertion rather than an import.
18. **[Plan reading] "exactly one new commit" in test_match_commits_one_function** became exactly one `feat(...)` match commit: the night's ENDED run record (a plan truth) lands in the end-of-night chore commit (Task 3), so a one-match night has two commits (`test_a_match_night_ends_with_the_run_record_in_a_chore_commit`).
19. **[Plan reading] Fixture names.** The plan's `u_x` / `func_XXXXXXXX` are placeholders; the tests use `u_00010000` / `func_00010010`, the made-up claim the 06-17 stream fixtures' tool_use already names, so the transcript audit sees an allowed path.
20. **[Rule 2 - Missing critical] Deps beyond the plan's list:** `requeue`, `matched_callees`, `lint`, `remove_containers` and `today` were added; the lint and the container cleanup are rulings, the others make "returns only through picker.requeue" and dated records injectable.
21. **[Rule 2 - Fail closed] Extra stops, each tested:** gate exit 2, lint exit 2 and partial-gate exit 2 stop the night (`tool`); a passing gate whose JSON does not name both SHA-1s is a tool failure; any unexpected exception in an attempt resets the live session and stops (`error`). The run id must be `[A-Za-z0-9_.-]+`. Detail strings mask 65+ hex runs and are capped at 4000 characters.

**Total deviations:** 9 orchestrator rulings/notes and 7 security rulings applied, 5 auto-fixed or plan-reading deviations. **Impact:** the security rulings widen the audit and add containment; the rest keep to the plan's truths. No scope change beyond the rulings.

## TDD Gate Compliance

Every task and security pass has a `test(06-23)` commit before its `feat(06-23)` or `fix(06-23)` commit: 49c5aa6 -> 4003fb5, cdd5997 -> 78e68d1, 81bd84a -> 271ce21, 97e853f -> 9f39c50, 971da41 -> 855a1b1, 1f34dea -> e02b4c2. No REFACTOR commits.

## Known Limits

- **build/ is not audited (security ruling, by design).** The attempt wrapper writes checks/, checks.jsonl and context.md there, and a matching session can write only through Edit/Write (the matching hook's allowlist, which admits only the attempt's notes.md under build/) and the attempt wrapper. A gitignored write elsewhere is seen only when it lands on a pinned path or in the fingerprinted trees, or in the transcript.
- **The fingerprint and pyc files.** A `__pycache__` file written during a session stops the night. The wrapper imports reverseapoc on the host; if the driver process had not imported (or compiled) a module the wrapper needs, Python would write its .pyc mid-session. 06-25's preflight should compile the package (for example `python -m compileall tools`) or the drive verb should import the wrapper's modules before the first session.
- **A changed (not new) site-packages file** cannot be restored (no bytes are kept, by the ruling's "no contents" design); it is copied to quarantine and named under "still changed after containment".
- **Transcript strays outside the checkout** cannot be restored; they are named only.

## Issues Encountered

- The harness refused some compound shell commands (heredocs, scripts mentioning git, `cd ... && git ...`); file edits ran through the Edit tool or small scripts in the scratchpad, and git steps as plain commands.
- The first full-suite run pointed REVERSEAPOC_GHIDRA_EXPORT at asm/; later runs use the main checkout's build/ghidra, as test_functions_real.py expects.

## Known Stubs

None.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: file-move | tools/reverseapoc/driver.py | Guardrail containment moves and rewrites files in the checkout (strays to build/driver/<run>/quarantine/, pinned files back to earlier bytes, tracked files via git restore); guarded by lstat per component, O_EXCL/O_NOFOLLOW and resolution inside the quarantine root |
| threat_flag: git-write | tools/reverseapoc/driver.py | The driver commits to the checkout (match and chore commits) with explicit literal paths only |

## User Setup Required

None.

## Next Phase Readiness

- 06-25 wires the real Deps: `argv=lambda p: session.build_argv(p, claude=...)`, `session=session.run_session`, `gate`/`partial_gate`/`lint` as `docker compose run --rm -T build uv run --frozen reverseapoc gate|lint ...` parsing `--json`, `remove_containers(prefix)` with `docker ps -a --filter name=<prefix>` then `docker rm -f`, `queue`/`requeue`/`matched_callees` over picker and score, `scaffold` via `units --write-src`, `pack` via `context --out <dir> --json`, `git=git_runner(repo)`, and `DriveConfig(tested_major=TESTED_MAJOR, min_cli_version=MIN_CLI_VERSION)`.
- 06-27 can grep `"reason":"guardrail"` in STOPPED records.
- No tick-rate finding (OpenApoc #997) in this plan.

## Self-Check: PASSED

- Files: tools/reverseapoc/driver.py, tests/test_driver.py, tests/test_attempts_schema.py and progress/attempts.jsonl exist; progress/attempts.jsonl is tracked.
- Commits 49c5aa6, 4003fb5, cdd5997, 78e68d1, 81bd84a, 271ce21, 97e853f, 9f39c50, 971da41, 855a1b1, 1f34dea, e02b4c2 are ancestors of HEAD.
- No modification to STATE.md, ROADMAP.md, orig/, config/, status.csv or build scripts.

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
