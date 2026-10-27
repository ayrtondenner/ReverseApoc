---
phase: 07-mechanics-first-decompilation
plan: 07
subsystem: driver
tags: [attempts-jsonl, schema, driver, stats, metrics]

requires: []
provides:
  - "attempts.jsonl schema 2: v2 attempt, abort, run, limit and rename record shapes beside the unchanged v1 shapes"
  - "validate_record dispatching on `schema` (absent -> v1, int 2 -> v2, anything else refused)"
  - "the nightly totals shape (_TOTALS) for v2 STOPPED/ENDED run records"
  - "per-op rename record shapes (orchestrator ruling F12) for the 07-34 writer"
affects: [07-23, 07-34, 07-37, 07-38, 07-30]

actuals:
  tokens: 5600
  tasks: 2
  commits: 5
plan_head_before: 0f9de364337258572e5dcddb10a133cd2c95c821
plan_head_after: e320cba

tech-stack:
  added: []
  patterns:
    - "Schema versioning by an explicit `schema` key: v1 lines carry none, v2 lines carry the int 2; one table per version keyed by kind"
    - "Cross-field rules that key sets cannot state live in small per-kind helpers (_run_problem, _rename_problem) called from _kind_problem"

key-files:
  created: []
  modified:
    - tools/reverseapoc/driver.py
    - tests/test_attempts_schema.py

key-decisions:
  - "`schema` must be the int 2: a bool, float, string, null or any other int is refused, and a v1 record carrying `schema` is refused"
  - "`model_requested` is required non-null text: tightening a schema later breaks committed lines, loosening it does not"
  - "Nightly totals nest the token classes as `tokens` {input, output, cache_read, cache_creation}, the same shape as an attempt record, and `sessions` is a fixed five-key object over every v2 outcome"
  - "A REFUSED or DEFERRED rename names its reason; a commit appears exactly when APPLIED; a header op's path must match include/<name>.h"

patterns-established:
  - "v2 tables reuse the v1 tables by spreading them, then override the fields that change (function -> _C_NAME)"

requirements-completed: [DEC-07, DEC-06]

coverage:
  - id: D1
    description: "v2 attempt records validate beside v1 lines in one log; v1 lines validate unchanged; the committed 42-line log still validates"
    requirement: DEC-07
    verification:
      - kind: unit
        ref: "tests/test_attempts_schema.py#test_v2_attempt_accepted"
        status: pass
      - kind: unit
        ref: "tests/test_attempts_schema.py#test_mixed_log_validates"
        status: pass
      - kind: unit
        ref: "tests/test_attempts_schema.py#test_committed_log_follows_the_schema"
        status: pass
      - kind: unit
        ref: "tests/test_attempts_schema.py#test_v1_record_with_schema_key_refused"
        status: pass
    human_judgment: false
  - id: D2
    description: "Readability vs matching outcomes per session (D-18) and renamed C names in v2 function fields (D-19)"
    requirement: DEC-07
    verification:
      - kind: unit
        ref: "tests/test_attempts_schema.py#test_v2_readability_outcomes"
        status: pass
      - kind: unit
        ref: "tests/test_attempts_schema.py#test_v2_function_accepts_a_renamed_name"
        status: pass
    human_judgment: false
  - id: D3
    description: "v2 run records with recovered claims and the nightly totals shape (DEC-06); v2 abort; limit records"
    requirement: DEC-06
    verification:
      - kind: unit
        ref: "tests/test_attempts_schema.py#test_v2_run_records"
        status: pass
      - kind: unit
        ref: "tests/test_attempts_schema.py#test_v2_abort_record"
        status: pass
      - kind: unit
        ref: "tests/test_attempts_schema.py#test_limit_record"
        status: pass
    human_judgment: false
  - id: D4
    description: "Per-op rename record shapes (ruling F12) and the 64-character hex rule over v2 records"
    requirement: DEC-07
    verification:
      - kind: unit
        ref: "tests/test_attempts_schema.py#test_rename_record"
        status: pass
      - kind: unit
        ref: "tests/test_attempts_schema.py#test_schema_refuses_bad_v2_records"
        status: pass
      - kind: unit
        ref: "tests/test_attempts_schema.py#test_v2_hex_rule"
        status: pass
    human_judgment: false

duration: 13min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 07: attempts.jsonl v2 schema Summary

**Schema 2 for progress/attempts.jsonl: `validate_record` now reads v1 lines (no `schema`) and v2 lines (`"schema": 2`) side by side, with pinned shapes for the v2 attempt (session, pass, model_requested, budget_usd, worker, hook_blocks, gate verdict, sweep cells), abort, run (workers, recovered claims, nightly totals), limit and per-op rename records.**

## Performance

- **Duration:** about 13 min
- **Started:** 2026-10-27T14:50:34Z
- **Completed:** 2026-10-27T15:03Z
- **Tasks:** 2 of 2
- **Files modified:** 2

## Accomplishments

- `RECORD_FIELDS_V2` for `attempt`, `abort`, `run`, `limit` and `rename`; `RECORD_FIELDS` (v1) is byte-for-byte unchanged, so the 42 committed v1 lines still validate and nothing in the log was rewritten (D-23).
- `validate_record` dispatches on `schema`: absent -> v1, the int 2 -> v2, anything else (1, 3, 2.0, "2", true, null) is a RecordError; an unknown kind is reported with its schema version.
- v2 attempt: `function` accepts any C identifier (renamed functions, D-19) while `start` stays the `0x%08X` key; `outcome` is checked against the session's enum (matching: MATCHED/PARTIAL/GAVE_UP; readability: LANDED/PARTIAL/REFUSED/GAVE_UP; D-18).
- v2 run: `workers` >= 1, `recovered` list of `{exe, unit, run}`, `totals` null exactly on STARTED and a full `_TOTALS` object on STOPPED/ENDED (sessions by outcome, turns, tokens, cost_usd, session_seconds, wall_seconds, hook_blocks, regressions_stopped, limit_waits {count, seconds}, aborts, by_model, by_session); reasons reuse RUN_REASONS.
- `limit {kind, schema, run, worker, seconds, streak, date}` and `rename` with the F12 per-op shapes.
- The no-hex-run-over-64 rule covers v2 records (keys of by_model included, since `_strings` yields dict keys).

## Task Commits

1. **Task 1 (tracer): v1 and v2 attempt records side by side**
   - RED `59146f8` test(07-07): add failing tests for v2 attempt records beside v1
   - GREEN `6f3c142` feat(07-07): validate v2 attempt records beside v1 lines
   - Tracer gate: interactive, `human_verify_mode` end-of-phase, automated-only verify; re-ran `uv run pytest -q tests/test_attempts_schema.py` (68 passed) and expanded.
2. **Task 2: v2 abort/run/limit/rename kinds and the nightly totals shape**
   - RED `454123e` test(07-07): add failing tests for v2 abort, run, limit and rename records
   - GREEN `2e3efd6` feat(07-07): v2 abort, run, limit and rename records and the nightly totals
   - Pin `e320cba` test(07-07): pin RecordError for a record whose kind is not a string

## TDD Gate Compliance

- **Task 1 RED:** 10 new tests failed, all on the v1 validator refusing the v2 keys as `extra` (the planned reason: no v2 table yet); the refusal tests already passed because v1 refuses extra keys. Evidence `uv run pytest -q tests/test_attempts_schema.py --junitxml=...`, exit 1, target `test_v2_attempt_accepted`; `gsd-tools check tdd-red-evidence` -> `RED_EVIDENCE_OK` (target_test_failed, junit, 68 tests, 10 failed). Semantic assessment: the target executed and failed on its assertion (`_problem(...) is None`) with "extra ['budget_usd', 'gate', ...]", the missing-feature reason; no collection or import fault.
- **Task 2 RED:** 9 tests failed with "unknown v2 record kind" (run, limit, rename, abort tables missing). Evidence exit 1, target `test_v2_run_records`; classifier -> `RED_EVIDENCE_OK`. Semantic assessment: the target ran and failed on `_problem(_started_v2()) is None`, the planned reason. `test_v2_hex_rule` passed at RED: Task 1's v2 attempt table already routed v2 attempts through the generic hex scan, so it pins existing behaviour.
- **GREEN:** both feat commits follow their test commits; 110 then 111 schema tests pass. RED evidence records live in the gitignored `build/tdd/` of the worktree.
- No REFACTOR commit (the message tidy-up and one tightened test went into Task 2's GREEN commit).

## Files Created/Modified

- `tools/reverseapoc/driver.py`: `SCHEMA_V2`, `SESSIONS`, `LANDED`, `SESSION_OUTCOMES`, `_C_NAME`, `_GATE`, `KIND_LIMIT`, `KIND_RENAME`, `RENAME_OUTCOMES`, `_TOTALS`, `_RECOVERED`, `RECORD_FIELDS_V2`; `validate_record` split into `_record_fields` (schema dispatch) and `_kind_problem` (`_run_problem`, `_rename_problem`).
- `tests/test_attempts_schema.py`: builders `_attempt_v2`, `_abort_v2`, `_run_v2`, `_started_v2`, `_totals`, `_limit`, `_rename`; tests for every behaviour in the plan plus a 45-case `BAD_V2` refusal table.

## Decisions Made

- `schema` must be exactly the int 2 (`type(value) is int`), so `true` (== 1 in Python) and `2.0` are refused.
- `model_requested` is non-null text. Loosening a schema later keeps committed lines valid; tightening it does not, so the strict choice is the reversible one.
- `_TOTALS.tokens` is a nested object with the four token classes, the same shape as an attempt record's `tokens`, so 07-23 can sum them directly; `sessions` is a fixed object over all five v2 outcomes (zeros allowed).
- `by_model` maps any text key and `by_session` maps only `matching`/`readability`, each to `{sessions, matched, cost_usd}`.
- Rename: a REFUSED or DEFERRED rename names its `reason`; `commit` (40 lowercase hex, `_SHA1`) appears exactly when APPLIED; a header op's `path` must match `include/<name>.h` (`_HEADER`). A proposal with a malformed path or name cannot fit the rename/header shapes, so 07-34 logs it as the unparseable shape (op null, REFUSED, reason).
- `LANDED` is new; `REFUSED` reuses the existing driver constant (same value "REFUSED").

## Deviations from Plan

**1. Orchestrator ruling F12: per-op rename shapes; v2 `abort.function` takes C names.**
- op `rename`: exe/address/old/new required (old/new C identifiers), path null; op `header`: path required, exe/address/old/new null; unparseable line: op null, exe/address/old/new/path null, outcome REFUSED, reason non-null; commit only for APPLIED. v2 abort `function` relaxed to `_C_NAME`.
- Tests: `test_rename_record` (six op/outcome shapes) and the rename/header/unparseable rows of `BAD_V2`; `test_v2_abort_record` checks a renamed name.
- Commits: `454123e` (RED), `2e3efd6` (GREEN).

**2. [Rule 1 - Bug] A record whose `kind` is unhashable (e.g. a list) raised TypeError, not RecordError.**
- Found during: Task 1 (rewriting the kind lookup into `_record_fields`).
- Fix: a non-string kind is an unknown kind (RecordError). Pinned by the `unhashable kind` row of `BAD` in `e320cba`. A test written after the fix (characterisation); on the base commit `dict.get` with a list raises TypeError, which `pytest.raises(RecordError)` does not catch.

**3. Test refinements inside the Task 2 GREEN commit.** Two refusal messages were reworded while GREEN ("an APPLIED rename names its commit", "a STOPPED record needs its totals") and the `by_session` refusal case was tightened so only the key is wrong (a valid share under an unknown session kind). Both are in `2e3efd6`.

**Total deviations:** 1 orchestrator ruling applied, 1 auto-fixed (Rule 1), 1 process note. **Impact:** F12 makes the schema fit what 07-34 and 07-23 write; no scope creep.

## Issues Encountered

- `uv run ruff format --check tools/reverseapoc/driver.py` reports the file as not format-clean, from code that predates this plan (lines around the drive verb and canary). `ruff check .` (the done gate) is green. Out of scope; not touched.
- The harness refused compound git commands; plain separate commands were used.

## Container step deferred to the orchestrator

R-B: no docker in worktrees. After merge, run: `docker compose run --rm test` (the CLAUDE.md done gate in the container). This plan adds no skip and no container-specific behaviour.

## Verification

- `uv run pytest -q tests/test_attempts_schema.py`: 111 passed.
- `uv run pytest -q` (host, worktree): 2755 passed, 229 skipped before the last pin commit; every skip is a pre-existing real-file or tool skip (orig/ EXEs, Watcom installs, watcom-media, the POSIX-only taskkill test). No new skip reason.
- `uv run ruff check .`: all checks passed.
- `git diff 0f9de36 HEAD -- progress/attempts.jsonl`: empty (no committed line rewritten).
- Acceptance: `RECORD_FIELDS_V2` and `SCHEMA_V2 = 2` present; `KIND_LIMIT = "limit"` and `KIND_RENAME = "rename"` present (driver.py:416-417); `test_committed_log_follows_the_schema` passes on the 42 committed lines.

## Known Stubs

None. The driver still writes v1 records; plan 07-23 switches it to v2 (stated in the plan's objective).

## Flagged assumptions (carried from the plan)

- DEC-06: whether a night's totals equal the sum of its attempt records stays unresolved here; plan 07-23, which writes the totals, tests it.

## Next Phase Readiness

- 07-23 can write v2 attempt/abort/run/limit records; 07-34 can write rename records in the F12 shapes; 07-37 `stats` can read both versions through one `validate_record`.

Execution context nonce: ba2304cc8a42a495

## Self-Check: PASSED

- FOUND: tools/reverseapoc/driver.py, tests/test_attempts_schema.py
- FOUND commits: 59146f8, 6f3c142, 454123e, 2e3efd6, e320cba (all ancestors of HEAD)

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
