---
phase: 07-mechanics-first-decompilation
plan: 31
subsystem: tooling
tags: [dec-04, d-17, d-18, d-20, readlint, attempt-wrapper, readability, tdd]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-27 readlint (run_readlint, ReadlintResult, Violation, --src/--config roots); 07-11 view mode (Claim.kind, view_root, unit_file, proposals); 07-14 CheckLogLine/sweep shape; 07-19 proposals (read_proposals, rename_problem)"
provides:
  - "A readability session's plain `attempt check` runs readlint on the host over its view unit after the container check; exit 0 only when every compiled function still passes, every splice is identical and readlint is clean"
  - "attempt.Lint, attempt.lint_view, attempt.Pending, attempt.READABILITY, attempt.RL01"
  - "CheckLogLine.readlint_violations / readlint_waivers (default None, after source)"
  - "Ruling F18: RL01 hits covered by the session's own valid rename proposal are reported as pending renames and do not fail the verdict"
affects: [07-35, 07-36, 07-38, 07-39, 07-40]

actuals:
  tokens: 8543
  tasks: 2
  commits: 4
plan_head_before: a5047e3521ecae15a67151287e4cd51c8360af58
plan_head_after: 20c634d828d9712dfd3f60647d0c823d65d97b5d

tech-stack:
  added: []
  patterns:
    - "Readability verdict = container check over the whole unit (every compiled function and splice) combined with host readlint: a tool error in either is 2, a failure in either is 1"
    - "A unit readlint did not check is a tool error: a readability verdict never passes unlinted (fail closed)"
    - "Pending rename (F18): rename_problem against the view's naming state; the driver re-checks against the full state at landing"

key-files:
  created: []
  modified:
    - tools/reverseapoc/attempt.py
    - tests/test_attempt_wrapper.py

key-decisions:
  - "readlint runs only for a plain check of a readability session; a sweep (a diagnostic) and every matching check are unchanged and log null readlint fields"
  - "A readability check's container half requires every compiled function at objdiff 100% with relocations and bytes ok and every splice identical, not only the claimed function (D-17: a readability edit may move no bytes)"
  - "A readlint tool error keeps the run's measurements on the line but sets exit 2 and null readlint counts; it is the same reserved slot, so the budget advances once"
  - "F18 option taken: report RL01 hits on names with a valid pending proposal as `pending rename` (not the in-memory apply option); readlint_violations counts only the failing hits"
  - "Pending-rename validity uses proposals.rename_problem with the view's symbols.csv, functions.csv (runtime rows included), the view units' function definitions as src_names, no extra runtime aliases, and the D_ placeholder's own address as the data range; the EXE's data objects are not read on the host"

patterns-established:
  - "The agent sees the verdict it will be judged by through the one command it already has (no new ATTEMPT_FORMS entry)"

requirements-completed: [DEC-04]

coverage:
  - id: D1
    description: "Readability `attempt check` prints the check half and readlint (rule, line, message, waivers, allowlisted); verdict OK only when both pass; `readlint: clean` for a clean unit; a matching check is unchanged"
    requirement: DEC-04
    verification:
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_readability_check_runs_readlint, test_readability_clean, test_readability_check_failure_wins_over_a_clean_lint, test_readability_check_needs_every_function, test_matching_check_unchanged"
        status: pass
    human_judgment: false
  - id: D2
    description: "checks.jsonl readlint_violations/readlint_waivers (null for matching and sweep), readlint tool error is a tool line using one budget step, unchecked unit fails closed, forms unchanged, F11 positional construction"
    requirement: DEC-04
    verification:
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_checks_line_has_readlint_counts, test_checks_line_counts_waivers, test_readlint_tool_error, test_readlint_unchecked_unit_is_a_tool_error, test_readability_forms_unchanged, test_check_log_line_positional_construction"
        status: pass
    human_judgment: false
  - id: D3
    description: "Ruling F18: pending renames (func and data) do not fail the verdict; refused, other-row and unreadable proposals cover nothing"
    requirement: DEC-04
    verification:
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_pending_rename_does_not_fail_the_verdict, test_invalid_rename_keeps_the_violation, test_a_data_placeholder_rename_is_pending, test_unreadable_proposals_count_no_pending_rename"
        status: pass
      - kind: other
        ref: "uv run pytest -q (3681 passed, 248 skipped) && uv run ruff check . (clean)"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-10-30
status: complete
---

# Phase 7 Plan 31: the readability session's feedback loop in attempt.py Summary

**A readability session's `attempt check` now runs readlint on its view unit on the host after the container check. The summary shows both halves: the check verdict over every compiled function and splice, and readlint's violations with rule, line and message, plus waivers and allowlisted references. The verdict is OK (exit 0) only when both pass. checks.jsonl records `readlint_violations` and `readlint_waivers`. A readlint tool error is a tool line (exit 2) in the same budget slot. RL01 hits that the session's own valid rename proposal covers are shown as pending renames (ruling F18).**

Execution context nonce: 03a0e7f738a50a92

## Performance

- **Duration:** 15 min (the full host suite took 6.5 min of it)
- **Started:** 2026-10-30T16:32:51Z
- **Completed:** 2026-10-30T16:48:11Z
- **Tasks:** 2 (Task 1 a tracer; both TDD)
- **Files modified:** 2

## Accomplishments

- **The readability half.** When `REVERSEAPOC_SESSION_KIND=readability`, `_locked_check` calls `lint_view(claim)` after the runner returns, in the same lock and slot, so the budget advances once.
  - `lint_view` calls `run_readlint([view unit], src_root=<view>/src, config_root=<view>/config, units=[EXE/UNIT])`.
  - A ReadlintError (or OSError) becomes `readlint: TOOL ERROR: <one-line message>`.
  - If readlint checked no file (the unit is not matched in the view's status.csv), that is also a tool error: a readability verdict never passes unlinted.
- **Verdict.**
  - The container half must pass for the whole unit: every compiled function at objdiff 100% with relocations and bytes ok, and every splice identical.
  - Exit codes combine as follows: a tool error in either half gives 2, a failure in either gives 1, and only both passing gives 0.
  - The head line uses its own table: `OK: every function still matches, every splice is identical and readlint is clean`, `FAILED: see the check and readlint lines (both must pass)`, or `TOOL ERROR`.
  - The body starts with `check: OK|FAILED|TOOL ERROR`, then the Phase 6 per-function lines, then `readlint: clean, N waivers, M allowlisted references` (or `readlint: K violation(s), ...` followed by `path:line: RLnn message` lines).
- **Matching sessions and sweeps are unchanged.** A test asserts that readlint never runs and that the Phase 6 head line comes out verbatim.
- **checks.jsonl.** `CheckLogLine.readlint_violations` and `readlint_waivers` are ints for a readability check. They are null for matching lines, sweep lines and readlint tool errors.
- **Ruling F18, pending renames.** An RL01 hit on `func_XXXXXXXX` or `D_XXXXXXXX` is reported as `pending rename: path:line: func_X -> name` and is not counted as a violation when:
  - the session's proposals.jsonl holds a rename for that row (same exe, kind and address; the last one wins), and
  - `proposals.rename_problem` accepts it against the view's naming state.
  - A refused proposal is named (`rename proposal refused: <why>`). An unreadable proposals.jsonl covers nothing, and the summary says so.

## Task Commits

1. **Task 1: Tracer - a readability check prints the check verdict and readlint**
   - `2e0f7c2` (test, RED)
   - `5dc33bc` (feat, GREEN)
   - Tracer gate: interactive mode, `end-of-phase`, verify is automated only. The verify (`uv run pytest -q tests/test_attempt_wrapper.py`, 114 passed) was re-run and passed before expanding.
2. **Task 2: The checks.jsonl record, tool errors, the forms guard (plus F11 and F18)**
   - `2ad0b5d` (test, RED)
   - `20c634d` (feat, GREEN)

No REFACTOR commits. The ruff fixes (one long line, import order) were made before each GREEN commit.

## TDD Gate Compliance

Each task has a `test(07-31)` commit before its `feat(07-31)` commit. RED evidence is a pytest JUnit report classified with `gsd-tools check tdd-red-evidence`. The records are in build/red/ (gitignored).

| Task | Target test | Verdict | Run | Semantic assessment |
|------|-------------|---------|-----|---------------------|
| 1 | `test_readability_check_runs_readlint` | RED_EVIDENCE_OK / target_test_failed | 8 selected, 4 failed (`07-31-t1.xml`) | Failed on `assert _run([...]) == 1` (got 0): there was no readlint step. The other three targets failed on their verdict and `check:` assertions. `test_matching_check_unchanged` passed vacuously, as expected: it pins today's behaviour. |
| 2 | `test_readlint_tool_error` | RED_EVIDENCE_OK / target_test_failed | 126 tests, 10 failed (`07-31-t2.xml`) | Failed with `KeyError: 'readlint_violations'`: the field did not exist yet. Its exit-2 and budget assertions already passed through Task 1's tool error. The F11 test failed on AttributeError (missing field). The F18 tests failed on the exit (1 vs 0) and on the missing proposals note. All of these are the planned missing behaviour, not load faults. `test_readability_forms_unchanged` and `test_readlint_unchecked_unit_is_a_tool_error` passed vacuously (Task 1 already failed closed). |

## Files Created/Modified

- `tools/reverseapoc/attempt.py`:
  - module docstring;
  - `READABILITY`, `FUNCTIONS_CSV`, `SYMBOLS_CSV`, `RL01`;
  - `_splices_ok`, `_unit_passes` and `_check_line(whole_unit=)`;
  - `_READABILITY_VERDICT` and `_CHECK_HALF`;
  - `Pending`, `Lint`, `lint_view`, `_placeholder`, `_renamable`, `_proposed_names`, `_naming_state`, `_src_names`;
  - `_combined` and `_finish`;
  - `_summary(lint=, check_exit=)` and `_record(lint=)`;
  - the two `CheckLogLine` fields.
- `tests/test_attempt_wrapper.py`: 15 new tests (18 cases with the parametrized one) and a `readable` fixture.

## Decisions Made

See key-decisions in the frontmatter.

## Deviations from Plan

**1. Orchestrator ruling F4: Task 2's verify no longer runs tests/test_driver_records.py.**
- That file is created by 07-23 in the same wave and does not exist in this worktree.
- Task 2's verify here was `uv run pytest -q tests/test_attempt_wrapper.py && uv run pytest -q && uv run ruff check .`.
- The orchestrator runs `uv run pytest -q tests/test_driver_records.py` after the wave-6 merge.

**2. Orchestrator ruling F11: field order and defaults.**
- `readlint_violations` and `readlint_waivers` are fields with default None, placed after `source`.
- tests/test_skill.py is unchanged and passes, including its nine-argument positional `CheckLogLine`.
- `test_check_log_line_positional_construction` pins this.

**3. Orchestrator ruling F18: a readability session can see its verdict OK.**
- Option taken: an RL01 hit on a name with a valid pending proposal is reported as a "pending rename" and does not fail the verdict. The in-memory apply option was not used.
- What "valid" means here: `proposals.read_proposals` followed by `proposals.rename_problem`, checked against:
  - the view's symbols.csv and functions.csv;
  - the function definitions of the view's units as `src_names`;
  - `runtime_names=()` (functions.csv runtime rows are still checked);
  - the D_ placeholder's own address as the data range. The host does not read the EXE's data objects.
- The driver re-checks every proposal against the full naming state at landing (07-34), and the gate and readlint run again before commit (D-17, T-07-91).
- 07-36's skill text and 07-38's /goal are not this plan's to edit.

**4. [Rule 2 - fail closed] A unit readlint skips is a readability tool error.**
- `run_readlint` reports a unit that is not matched in the view's status.csv as skipped and exits 0.
- Taken at face value, that would let a readability check pass unlinted. `lint_view` therefore turns "no file checked" into exit 2, naming the skip reason (`test_readlint_unchecked_unit_is_a_tool_error`).

**5. [Rule 2 - correctness] The check half covers the whole unit.**
- The truth says "every defined function still objdiff 100%". The matching verdict reads only the claimed function.
- A readability check now also requires every compiled function and every splice to pass (`test_readability_check_needs_every_function`).

**6. Test naming.** The plan's `test_forms_unchanged` already exists (07-11). The Task 2 forms guard is `test_readability_forms_unchanged`. It also asserts that `attempt --readlint`, `attempt readlint` and `attempt check --units ...` are refused before any run.

---

**Total deviations:** 3 orchestrator rulings applied (F4, F11, F18), 2 fail-closed/correctness additions (Rule 2), 1 test rename.
**Impact on plan:** none on scope. Everything stays in the plan's two files; driver.py is untouched (the flagged assumption held: `_check_line` in driver.py ignores the new keys).

## Issues Encountered

- The harness refused compound shell commands in this worktree, including the branch guard script. The guard's assertions were run as separate plain commands instead: branch `worktree-agent-a129ce18aa902e713`, HEAD `a5047e35...`, base matched.
- Another agent rewrote `red_record.py` in the shared scratchpad while I was using it. I left it alone and used `red_record_0731.py` for Task 2.

## Container step deferred to the orchestrator

- `docker compose build && docker compose run --rm test` (R-B: never run from a worktree).
- After the wave-6 merge, also run `uv run pytest -q tests/test_driver_records.py` (ruling F4).

## Verification

- `uv run pytest -q tests/test_attempt_wrapper.py`: 127 passed (109 before this plan).
- `uv run pytest -q tests/test_attempt_wrapper.py tests/test_skill.py`: 140 passed.
- `uv run pytest -q` (host, worktree): 3681 passed, 248 skipped. Every skip is a pre-existing real-file reason (orig/ EXEs, Watcom 10.6 and watcom-media are absent from the worktree). There is no new skip reason, and none of the new tests skips.
- `uv run ruff check .`: all checks passed.

## User Setup Required

None.

## Next Phase Readiness

- 07-38 (readability sessions) can rely on the wrapper's combined verdict. 07-36 and 07-38 should say that names are checked at landing after the driver applies proposals (F18).
- 07-34's src_names helper, once it exists, could replace `_src_names` (function definitions only today).

## Self-Check: PASSED

- The modified files exist. Commits 2e0f7c2, 5dc33bc, 2ad0b5d and 20c634d are on this branch (`git log`), and the working tree is clean.
- Acceptance criteria hold: attempt.py imports `run_readlint`, and tests/test_attempt_wrapper.py contains `test_readlint_tool_error`.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-30*
