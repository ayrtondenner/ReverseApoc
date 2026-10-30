---
phase: 07-mechanics-first-decompilation
plan: 42
subsystem: driver
tags: [session, streamjson, model-escalation, d-09, d-25, opus, fable, init-check]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-21: run_session(on_start, on_end) in session.py; build_argv unchanged when this plan started"
provides:
  - "session.OPUS_MODEL, FABLE_MODEL, MODEL (= OPUS_MODEL), ESCALATE_AFTER_PASSES = 2, FABLE_BUDGET_USD = 12.5"
  - "session.model_for_pass(n): Opus for passes 1-2, Fable for 3+, ValueError below 1 (D-09)"
  - "session.build_argv(prompt, *, claude, model=MODEL, max_budget_usd=MAX_BUDGET_USD, max_turns=MAX_TURNS); defaults give D-06's argv"
  - "session.MODEL_NAMES: {claude-opus-5-5: Claude Opus 5.5, claude-fable-5-1: Claude Fable 5.1}"
  - "streamjson.ACCEPTED_INIT_MODELS; check_init accepts only the requested model's listed init ids and fails closed on an unknown requested model"
affects: [07-30, 07-39]

actuals:
  tokens: 2640
  tasks: 2
  commits: 4
plan_head_before: a5047e3521ecae15a67151287e4cd51c8360af58
plan_head_after: b239bfc1f3cdf9d8277422ae3da7b025c2d23890

tech-stack:
  added: []
  patterns:
    - "Per-model tables live where their consumer lives (ACCEPTED_INIT_MODELS in streamjson, MODEL_NAMES in session), with literal ids in streamjson (it cannot import session), and a test pins their keys to agree"

key-files:
  created: []
  modified:
    - tools/reverseapoc/session.py
    - tools/reverseapoc/streamjson.py
    - tests/test_session.py
    - tests/test_streamjson.py

key-decisions:
  - "The model check moved into streamjson._model_problem: an unknown requested model gives 'requested model ... has no accepted init IDs (D-09)'; a mismatch gives 'model X is not accepted for the requested Y (D-09)'. Both contain 'model', so the bad_init_model case still sees exactly one model problem"
  - "build_argv's new keyword arguments default to the module constants, so driver.py's existing call (build_argv(prompt, claude=claude)) is unchanged until 07-30 wires per-pass values"
  - "MAX_BUDGET_USD stays 5 (Opus, D-07); FABLE_BUDGET_USD = 12.5 (D-25) is a separate constant, not a table, because 07-30 picks the budget by model and the owner can override both per run"

patterns-established:
  - "Two tables keyed by model id are pinned to agree by one test (test_model_tables_agree), so a model added to one and not the other fails the suite"

requirements-completed: [DEC-06, AGT-11]

coverage:
  - id: D1
    description: "model_for_pass: Opus for passes 1-2, Fable for 3 and later, ValueError below 1 (D-09)"
    requirement: AGT-11
    verification:
      - kind: unit
        ref: "tests/test_session.py#test_model_for_pass, test_model_for_pass_refuses_a_pass_below_one"
        status: pass
    human_judgment: false
  - id: D2
    description: "build_argv takes per-session model, budget and turns; defaults reproduce the Phase 6 D-06 argv"
    requirement: DEC-06
    verification:
      - kind: unit
        ref: "tests/test_session.py#test_build_argv_kwargs, test_build_argv_is_d06"
        status: pass
    human_judgment: false
  - id: D3
    description: "Tracer: pass 3's argv asks for Fable with the 12.5 USD budget, and a Fable init passes check_init for the Fable request"
    requirement: AGT-11
    verification:
      - kind: unit
        ref: "tests/test_streamjson.py#test_escalated_argv_passes_its_init_check"
        status: pass
    human_judgment: false
  - id: D4
    description: "check_init: mismatch either way is one D-09 model problem naming both ids; an unknown requested model fails closed even when echoed"
    requirement: AGT-11
    verification:
      - kind: unit
        ref: "tests/test_streamjson.py#test_init_rejects_mismatch, test_init_unknown_expected_model, test_check_init_problems"
        status: pass
    human_judgment: false
  - id: D5
    description: "MODEL_NAMES and ACCEPTED_INIT_MODELS name the same two models"
    requirement: AGT-11
    verification:
      - kind: unit
        ref: "tests/test_session.py#test_model_tables_agree"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-10-30
status: complete
---

# Phase 7 Plan 42: Model escalation library half Summary

**`session.model_for_pass` (Opus 5.5 for passes 1-2, Fable 5.1 after; D-09), a Fable budget default of 12.5 USD (D-25), `build_argv` taking per-session model/budget/turns with the D-06 argv as its default, and a requested-model init check (`ACCEPTED_INIT_MODELS`) that fails closed on mismatches and unknown models.**

Execution context nonce: 3094d2df17690933

## Performance

- **Duration:** about 10 min of work, plus a 6 min full host suite run
- **Started:** 2026-10-30T16:30:08Z
- **Completed:** 2026-10-30T16:40:17Z
- **Tasks:** 2 (1 tracer, 1 auto, both TDD)
- **Files modified:** 4

## Accomplishments

- D-09's pass-to-model rule as a library export: `model_for_pass`, `ESCALATE_AFTER_PASSES = 2`, `OPUS_MODEL`, `FABLE_MODEL`, with `MODEL = OPUS_MODEL` kept for Phase 6 callers.
- D-25's budget as `FABLE_BUDGET_USD = 12.5` next to `MAX_BUDGET_USD = 5` (Opus, D-07).
- `build_argv(prompt, *, claude, model, max_budget_usd, max_turns)` emits the values in D-06's positions. `test_build_argv_is_d06` passes unchanged.
- `streamjson.ACCEPTED_INIT_MODELS` (literal ids) and `_model_problem`: only the requested model's listed init ids pass. A mismatch in either direction is one problem that names both ids and cites D-09. A requested model missing from the table is a problem even when the init echoes it (T-07-124). The CLI-version check (Phase 6 D-36) is untouched.
- `session.MODEL_NAMES` for 07-30's co-author line, with its keys pinned to `ACCEPTED_INIT_MODELS` by `test_model_tables_agree` (T-07-125).

## Task Commits

1. **Task 1 (tracer): pass 3 asks for Fable and its init passes**
   - RED `6f4442e` test(07-42): add failing tests for pass-to-model rule and per-session argv
   - GREEN `8e8dabb` feat(07-42): pass-to-model rule, per-session argv values, accepted init models
2. **Task 2: mismatches and unknown models fail closed; the tables agree**
   - RED `dd367c3` test(07-42): add failing tests for model mismatch, unknown model, table agreement
   - GREEN `b239bfc` feat(07-42): fail-closed init model check and MODEL_NAMES table

## TDD Gate Compliance

`workflow.tdd_mode` is not set in `.planning/config.json`, so the `tdd-red-evidence` classifier gate does not apply. The phase-7 rule still holds: each task has a RED test commit before its GREEN commit.

- **Task 1 RED** (`6f4442e`): 8 new cases failed. `test_build_argv_kwargs` raised TypeError (unexpected keyword `model`). The `test_model_for_pass*` cases and the tracer raised AttributeError (no `session.model_for_pass`). Semantic assessment: each test ran and failed because the feature under test was missing. There were no collection, import or fixture faults, and the other 157 tests passed.
- **Task 2 RED** (`dd367c3`): 4 failures. Both mismatch directions failed on `assert "D-09" in problem` (the old message cited D-35). `test_init_unknown_expected_model` failed on `assert len(problems) == 1` because the unknown model was accepted (`[]`). `test_model_tables_agree` raised AttributeError (no `MODEL_NAMES`). Semantic assessment: every failure hit the planned assertion or the missing export. Note that rejecting a mismatch already worked before this plan (Phase 6 D-35). What this RED proved missing was the D-09 citation and the fail-closed handling of unknown models.
- **GREEN:** `uv run pytest -q tests/test_session.py tests/test_streamjson.py` gave 168 passed, 1 skipped (the existing POSIX-only skip).
- **Tracer gate:** row 3 (interactive, `human_verify_mode: end-of-phase`, automated-only verify). The verify was re-run after the Task 1 GREEN commit (165 passed, 1 skipped), so expansion went ahead with no checkpoint.

## Verification

- Task 1 acceptance: session.py contains `ESCALATE_AFTER_PASSES = 2` and `def model_for_pass(`, and streamjson.py contains `ACCEPTED_INIT_MODELS`. PASS.
- Task 2 acceptance: session.py contains `MODEL_NAMES`, and `uv run pytest -q tests/test_streamjson.py -k "mismatch or unknown_expected"` reports `2 passed`. PASS.
- `uv run pytest -q` (full host suite, worktree, final code): **3674 passed, 248 skipped**. No new skips (this plan adds no skip markers).
- `uv run ruff check .`: All checks passed.
- Container suite: container step deferred to the orchestrator: `docker compose run --rm test`.

## Files Created/Modified

- `tools/reverseapoc/session.py`: the model constants, `ESCALATE_AFTER_PASSES`, `FABLE_BUDGET_USD`, `MODEL_NAMES`, `model_for_pass`, and `build_argv` keyword arguments.
- `tools/reverseapoc/streamjson.py`: `ACCEPTED_INIT_MODELS` and `_model_problem`; `check_init` calls it.
- `tests/test_session.py`: `test_build_argv_kwargs`, `test_model_for_pass` (4 cases), `test_model_for_pass_refuses_a_pass_below_one` (2 cases), `test_model_tables_agree`.
- `tests/test_streamjson.py`: `_init_with_model`, `test_escalated_argv_passes_its_init_check`, `test_init_rejects_mismatch`, `test_init_unknown_expected_model`.

## Decisions Made

See key-decisions in the frontmatter. In short: the model check is a helper that returns one problem or None, the `build_argv` defaults keep driver.py's call unchanged, and the Fable budget is a separate constant.

## Deviations from Plan

No orchestrator ruling applies to 07-42 (rulings.md has no 07-42 section).

**1. [Rule 3 - Blocking] `test_init_rejects_mismatch` is one test that checks both directions, not a parametrized pair**
- **Found during:** Task 2 (GREEN acceptance check)
- **Issue:** The RED version was parametrized over the two directions, so the acceptance selector `-k "mismatch or unknown_expected"` reported 3 passed, not the required 2.
- **Fix:** One test function loops over both (reported, requested) pairs with the same assertions, including the D-09 one that failed in RED.
- **Files modified:** tests/test_streamjson.py
- **Verification:** the selector reports `2 passed`. Both directions are still asserted.
- **Committed in:** `b239bfc` (Task 2 GREEN)

**Total deviations:** 1 auto-fixed (1 blocking). **Impact:** test shape only, with the same coverage. No change in scope.

## Issues Encountered

None.

## Known Stubs

None.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- 07-30 can wire `model_for_pass(pass)`, `build_argv(..., model=, max_budget_usd=)`, `check_init(..., expected_model=model)` and `MODEL_NAMES[model]` into the driver, the co-author line and the drive flags. driver.py still calls `check_init` without `expected_model`, so the Opus default applies until then.
- Research A9 is still open: the owner's Fable canary (07-39) shows what init model string CLI 2.1.308 reports for `claude-fable-5-1`. If the string differs, add it to `ACCEPTED_INIT_MODELS["claude-fable-5-1"]`, which is the one place to extend.

## Self-Check: PASSED

- FOUND: tools/reverseapoc/session.py, tools/reverseapoc/streamjson.py, tests/test_session.py, tests/test_streamjson.py
- FOUND on this branch (a5047e3..HEAD): 6f4442e, 8e8dabb, dd367c3, b239bfc

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-30*
