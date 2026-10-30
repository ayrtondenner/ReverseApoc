---
phase: 07-mechanics-first-decompilation
plan: 30
subsystem: driver
tags: [driver, cli, model-escalation, opus, fable, budgets, init-check, co-author, canary, d-07, d-09, d-25]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-42: session.model_for_pass, build_argv(model=, max_budget_usd=, max_turns=), FABLE_BUDGET_USD, MODEL_NAMES, streamjson.check_init(expected_model=); 07-23: the pass from the committed log, v2 records with model_requested / budget_usd; 07-26: the tier queue and its abort count"
provides:
  - "driver: every claim carries the pass's model (session.model_for_pass) and that model's budget; Deps.argv and Seams.argv are (prompt, *, model, max_budget_usd, max_turns)"
  - "driver: _check_init and the canary pass the requested model as expected_model= (T-07-88)"
  - "driver.coauthor(model) over session.MODEL_NAMES; COAUTHOR = coauthor(OPUS_MODEL); commit_message(..., requested_model=) (T-07-89)"
  - "driver.session_budget; DriveConfig.max_budget_usd, fable_budget_usd, max_turns, budget_for"
  - "DriveOptions.max_budget_usd, fable_budget_usd, max_turns, session_minutes, canary_model; the canary JSON's model_requested and init_model"
  - "cli: drive --max-budget-usd --fable-budget-usd --max-turns --session-minutes, and drive --canary --model"
  - "picker.TierQueue.finish(capped=): a finished pass clears the abort count (orchestrator ruling, deferred minors)"
  - "tests/fakeclaude.py --model (echo into the init event) and --init-model (force another one)"
affects: [07-39, 07-41]

actuals:
  tokens: 16500
  tasks: 3
  commits: 7
plan_head_before: 3201acece585a61cf16e52855aa84eb6843aa043
plan_head_after: 0b1a665c63bbe32c5ed4cd71c9e4360f0a6bf14e

tech-stack:
  added: []
  patterns:
    - "The requested model and its budget ride on the claim (_Claim.model / budget_usd), so the argv, the init check, the record and the co-author all read one value"
    - "The stand-in claude echoes a requested model into its init event only when asked (--model), so the Opus fixtures still replay byte for byte"

key-files:
  created:
    - tests/test_escalation.py
  modified:
    - tools/reverseapoc/driver.py
    - tools/reverseapoc/cli.py
    - tools/reverseapoc/picker.py
    - tests/fakeclaude.py
    - tests/test_driver.py
    - tests/test_drive.py
    - tests/test_driver_workers.py
    - tests/test_driver_pick.py
    - docs/workflow.md

key-decisions:
  - "The model and budget are fixed per claim (_Night._claim): model_for_pass(pass) and DriveConfig.budget_for(model). A function capped twice in one night therefore escalates to Fable that same night, because night.passes counts each capped pass"
  - "commit_message keeps `model` (the init event's string, for the body's `model` line) and takes a new required keyword, requested_model, for the trailer. The init check has already matched the two"
  - "coauthor reads session.MODEL_NAMES when it is called, so a model missing from the table raises DriverError inside the match commit's try. The match is then undone (no commit, no MATCHED record) and the night STOPs with reason tool"
  - "The claim file's `model` now holds the requested model. It was null before"
  - "drive --model is canary-only: without --canary, _cmd_drive exits 2 before any driver call. A night always takes each pass's model from D-09"
  - "The canary's init line always names the init event's model string, passing or failing, and its JSON adds model_requested and init_model, so the owner can report the string (research A9)"
  - "TierQueue.finish clears the abort count on a matched or capped pass. A pass cut short by the night cap or a stop has no outcome and keeps the count"

patterns-established:
  - "The argv fakes in the night and drive harnesses take Deps.argv's keyword signature. The night harness adds --model for any requested model other than Opus"

requirements-completed: [AGT-11, DEC-06, DEC-02]

coverage:
  - id: D1
    description: "Escalation in the driver: passes 1-2 on claude-opus-5-5 with the Opus budget, pass 3+ on claude-fable-5-1 with the Fable budget, the pass coming from the committed log; the argv comes from build_argv; the record names model_requested and budget_usd next to the init's model; the claim names the model"
    requirement: AGT-11
    verification:
      - kind: integration
        ref: "tests/test_escalation.py#test_escalation_from_log, test_pilot_function_next_pass_is_opus, test_a_function_with_no_pass_runs_pass_1_on_opus, test_budgets_and_turns_come_from_the_config, test_the_claim_names_the_requested_model"
        status: pass
    human_judgment: false
  - id: D2
    description: "The init check expects the requested model, in both directions; the STOPPED record names both models"
    requirement: AGT-11
    verification:
      - kind: integration
        ref: "tests/test_escalation.py#test_driver_passes_requested_model, test_an_opus_request_answered_by_fable_stops_the_night"
        status: pass
    human_judgment: false
  - id: D3
    description: "The co-author comes from the requested model; Fable matches name Claude Fable 5.1, Opus matches keep COAUTHOR; an unknown model raises DriverError and nothing is committed"
    requirement: DEC-06
    verification:
      - kind: unit
        ref: "tests/test_escalation.py#test_coauthor_by_model, test_commit_message_uses_the_requested_models_coauthor"
        status: pass
      - kind: integration
        ref: "tests/test_escalation.py#test_a_fable_match_commit_names_fable, test_an_opus_match_commit_keeps_the_opus_line, test_an_unknown_model_is_never_committed; tests/test_driver.py#test_match_commits_one_function (COAUTHOR unchanged)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The canary passes its requested model to check_init; drive --canary --model asks for that model with its budget; the canary's init line and JSON name the init's model string"
    requirement: AGT-11
    verification:
      - kind: integration
        ref: "tests/test_escalation.py#test_canary_passes_requested_model, test_canary_fails_when_its_init_names_another_model, test_canary_model_flag, test_canary_prints_init_model, test_a_failed_canary_init_still_names_the_init_model"
        status: pass
    human_judgment: false
  - id: D5
    description: "Every D-07 value is a drive flag (--max-budget-usd 5, --fable-budget-usd 12.5, --max-turns 40, --session-minutes 30), zero or negative exits 2, and the values reach the night config; --model is checked and canary-only"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_escalation.py#test_drive_budget_flags, test_the_drive_flags_reach_the_options, test_the_night_gets_the_budgets_turns_and_session_clock, test_canary_model_flag"
        status: pass
    human_judgment: false
  - id: D6
    description: "Orchestrator ruling (deferred minors): a finished pass clears the abort count, a pass cut short keeps it, and the coordinator reports a capped pass; the night-cap wording is fixed"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_driver_pick.py#test_a_finished_pass_clears_the_abort_count, test_a_pass_cut_short_keeps_the_abort_count"
        status: pass
      - kind: integration
        ref: "tests/test_driver_pick.py#test_the_coordinator_tells_the_tier_queue_a_pass_finished_capped"
        status: pass
    human_judgment: false
  - id: D7
    description: "The real CLI accepts claude-fable-5-1, and its init event reports an accepted model string"
    verification: []
    human_judgment: true
    rationale: "Research A9: only the owner's Fable canary (plan 07-39, D-11, D-25) can show it; no executor runs a real claude session"
  - id: D8
    description: "Host suite and ruff green; the container run is deferred to the orchestrator (R-B)"
    verification:
      - kind: other
        ref: "uv run pytest -q (3841 passed, 251 skipped) && uv run ruff check ."
        status: pass
    human_judgment: true
    rationale: "docker is not allowed in a worktree; the orchestrator runs docker compose build && docker compose run --rm test after merge"

duration: 23min
completed: 2026-10-30
status: complete
---

# Phase 7 Plan 30: Model escalation in the driver Summary

**Each session now asks for its pass's model. Passes 1 and 2 of a function run on `claude-opus-5-5` with `--max-budget-usd`, and pass 3 and later run on `claude-fable-5-1` with `--fable-budget-usd`; the pass comes from the committed log. The init check expects that model, and each match commit's `Co-Authored-By:` line names it. Every D-07 cap is a `drive` flag, and `drive --canary --model claude-fable-5-1` runs the owner's Fable canary, which reports the model string the init event gave.**

Execution context nonce: 9114c98bfc361942

## Performance

- **Duration:** about 23 min of work, plus about 15 min of test runs (the full host suite takes 7 min)
- **Started:** 2026-10-30T22:54:32Z
- **Completed:** 2026-10-30T23:17Z
- **Tasks:** 3 (1 tracer, 2 auto; all TDD)
- **Files modified:** 10 (1 created)

## Accomplishments

- **Escalation (D-09, D-25).**
  - `_Night._claim(pick, n)` builds each attempt's claim: the pass (`_pass`, from 07-23's committed-log index plus the passes capped tonight), its model (`session.model_for_pass`), and that model's budget (`DriveConfig.budget_for` → `session_budget`).
  - `_launch` builds the argv through `Deps.argv(prompt, model=, max_budget_usd=, max_turns=)`. The real seam is `build_argv(prompt, claude=claude, **values)`.
  - The v2 attempt record's `model_requested` / `budget_usd` and the claim file's `model` come from the claim, not from constants.
  - The 12 never-matched pilot functions start at pass 2 on Opus (`test_pilot_function_next_pass_is_opus`).
- **Init check (T-07-88).** `_check_init` passes `expected_model=session.claim.model`. A Fable session no longer stops the night as "not claude-opus-5-5". An answer from another model stops it either way, and the STOPPED detail names both models. The CLI-version check is unchanged.
- **Co-author (T-07-89).**
  - `coauthor(model)` builds the trailer from `session.MODEL_NAMES` and raises `DriverError` for a model the table lacks. `COAUTHOR = coauthor(OPUS_MODEL)`.
  - `commit_message(..., requested_model=)` uses the requested model for the trailer. A model the table lacks is undone before any commit.
- **Canary.**
  - It asks for `options.canary_model` with that model's budget and turns, and passes the model to `check_init` as `expected_model=`.
  - The init line reads `init: claude <ver>, model <init model>, ...`, or `<problems> (init model <x>)` when the init fails. The JSON adds `model_requested` and `init_model`.
- **Flags (D-07).**
  - New `drive` flags: `--max-budget-usd` (5), `--fable-budget-usd` (12.5), `--max-turns` (40) and `--session-minutes` (30, which becomes the per-session `wall_clock_s`). The budgets use `_positive_float` (finite and above 0) and the counts `_positive`.
  - `--model MODEL` (checked against `MODEL_NAMES`) works only with `--canary`.
  - `drive --help` prints `--fable-budget-usd` and `--model`.
- **Stand-in claude.** `--model M` echoes M into the init event. `--init-model M` forces another string for the mismatch cases. Without either, every line replays byte for byte.

## Task Commits

1. **Task 1 (tracer): escalation, budgets, the requested-model init check.** RED `2d47364`, GREEN `ffee7bf`, harness fix `b6532e9` (see Deviations 2).
   - Tracer feedback gate: row 3 (interactive, `human_verify_mode` end-of-phase, automated-only verify). After the GREEN commit I re-ran `uv run pytest -q tests/test_escalation.py tests/test_driver.py tests/test_drive.py`: 242 passed, 2 skipped. Tracer verified end-to-end; expanded.
2. **Task 2: the canary's requested model; co-author by model.** RED `04a07dc`, GREEN `91e05f3`.
3. **Task 3: the drive flags and the canary's `--model`; the orchestrator's deferred minors.** RED `68096f1`, GREEN `0b1a665`.

## TDD Gate Compliance

`workflow.tdd_mode` is not set, so the `tdd-red-evidence` classifier gate does not apply. The phase-7 rule holds: each task has a `test(07-30)` commit before its `feat(07-30)` commit.

- **Task 1 RED (`2d47364`): 7 failed.**
  - The night tests failed in the driver: `Argv.__call__() missing 3 required keyword-only arguments: 'model', 'max_budget_usd', and 'max_turns'`. The driver still called `argv(prompt)`, so the night STOPPED `error` where ENDED or STOPPED `init` was expected.
  - The config test failed with `DriveConfig.__init__() got an unexpected keyword argument 'fable_budget_usd'`.
  - Semantic assessment: each failure is the missing feature. There was no collection or import fault.
- **Task 2 RED (`04a07dc`): 5 failed, 9 passed.**
  - `driver.coauthor` did not exist (AttributeError).
  - `commit_message` had no `requested_model`.
  - A Fable match carried the Opus trailer.
  - An unknown model was committed.
  - The canary called `check_init` with no `expected_model` (`seen == [None]`).
  - Two new tests passed from the start, as pins. `test_canary_fails_when_its_init_names_another_model` passed because `check_init` already defaults to Opus. `test_an_opus_match_commit_keeps_the_opus_line` passed because the Opus trailer was already the default.
- **Task 3 RED (`68096f1`): 7 failed, 1 passed.**
  - The parser had no `model`, `max_budget_usd` and so on.
  - `DriveOptions` had no `canary_model`.
  - `TierQueue.finish` had no `capped` keyword.
  - The test that a pass cut short keeps its abort count passed from the start, as a pin.
- **GREEN:** the Task 3 verify command passed: escalation, cli and drive 213 passed; host suite 3841 passed, 251 skipped; ruff clean.
- There is no REFACTOR commit.

## Files Created/Modified

- `tools/reverseapoc/driver.py`:
  - the module and `DriveConfig` docstrings (the night-cap wording);
  - `coauthor`, `COAUTHOR`, `session_budget`;
  - `DriveConfig.max_budget_usd` / `fable_budget_usd` / `max_turns` / `budget_for`;
  - `Deps.argv` / `Seams.argv` signature;
  - `_Claim.model` / `budget_usd`, `_Night._claim`, the claim file's `model`;
  - `_launch`, `_check_init`, `_record_attempt`, `commit_message(requested_model=)`, `_commit_match`;
  - the coordinator's `finish(..., capped=)`;
  - `DriveOptions` (budgets, turns, session minutes, canary model) and `_run_drive_locked`;
  - the canary (`_canary_checks(model=)`, `_after_session(model=)`, `_init_text`, the argv and the JSON fields), `default_seams`.
- `tools/reverseapoc/cli.py`: `_positive_float`, `_model`, the new `drive` flags, `_cmd_drive` (`--model` needs `--canary`), and the `--max-sessions` help text.
- `tools/reverseapoc/picker.py`: `TierQueue.finish(capped=)` clears the abort count; the module docstring.
- `tests/test_escalation.py` (new): 20 tests.
- `tests/fakeclaude.py`: `--model` and `--init-model`.
- `tests/test_driver.py`, `tests/test_driver_workers.py`, `tests/test_drive.py`: the argv fakes take the keyword signature. The night harness adds `--model` for any requested model other than Opus, and the canary rig records the requested values.
- `tests/test_driver_pick.py`: 3 tests for the abort-count ruling.
- `docs/workflow.md`: the `drive` flag table (current defaults, the new flags, `--model`), a model-escalation paragraph, and the canary's init check.

## Decisions Made

See `key-decisions` in the frontmatter.

## Deviations from Plan

**Orchestrator ruling (deferred minors) (1): the stale night-cap wording.**
- I fixed it in the driver module docstring (~:9), the `DriveConfig` docstring (~:225) and `docs/workflow.md` (~:76).
- Every launched session counts toward the cap, aborted ones included. A LIMIT relaunch keeps its slot.
- The same stale words ("counted sessions of all workers") were in `drive --max-sessions --help` and the `DriveOptions` docstring, so I fixed them there too.
- The workflow.md table also had stale defaults (`--max-sessions` 30, `--target-matched` 10). It now shows 60 and 0, and lists `--workers` and the new flags.
- Commit `0b1a665`.

**Orchestrator ruling (deferred minors) (2): 07-26's abort count is never cleared.**
- `TierQueue.finish(key, *, matched, aborted=False, capped=False)` drops the key's abort count when the pass finished (matched or capped). A pass cut short (no outcome) keeps it.
- The coordinator passes `capped=worker.outcome == CAPPED`.
- Tests in `tests/test_driver_pick.py`:
  - `test_a_finished_pass_clears_the_abort_count`;
  - `test_a_pass_cut_short_keeps_the_abort_count`;
  - `test_the_coordinator_tells_the_tier_queue_a_pass_finished_capped`. I added this one to pin the driver wiring after the GREEN code, in the same commit.
- `picker.py` and `test_driver_pick.py` are outside files_modified; the ruling required both.
- Commits `68096f1` (RED) and `0b1a665` (GREEN).

**Orchestrator notes (07-42, 07-26, 07-23 as built): applied as planned.**
- The driver uses `model_for_pass`, `build_argv(model=, max_budget_usd=, max_turns=)`, `FABLE_BUDGET_USD`, `MODEL_NAMES` and `check_init(expected_model=)`.
- The pass is the night's `_pass` (07-23's committed-log index plus passes capped tonight, the index the 07-26 tier queue reads).
- The v2 records' `model_requested` / `budget_usd` now carry the per-pass values.
- session.py and streamjson.py are not edited (prohibition).

**1. [Rule 3 - Blocking] `tests/test_driver_workers.py` is outside files_modified.**
- Its `_argv` fake took only the prompt. After Task 1 every worker night would raise TypeError.
- It now takes the keyword signature, and its assertions are unchanged.
- Commit `ffee7bf`.

**2. [Rule 1 - Bug, test harness] The night harness's stand-in did not echo a Fable request.**
- `test_driver_records::test_next_pass_number` (07-23) runs a function on pass 3. That pass now asks for Fable, but the fixtures' init names Opus, so the night STOPPED `init`.
- `Night._argv` in `tests/test_driver.py` now passes `--model <model>` to fakeclaude for any requested model other than Opus.
- Opus sessions still replay byte for byte, so the `bad_init_*` cases are unchanged. The test's assertions are unchanged.
- Commit `b6532e9`.

**3. [Plan clarification] `commit_message` keeps `model` and adds `requested_model`.**
- The body's `model ...` line still shows the init event's string, as Phase 6 D-25 has it. The trailer uses the requested model.
- `requested_model` is a required keyword, so no caller can fall back to Opus by default.

**4. [Plan clarification] The canary report names the init model in its init line.**
- The init line names the string when it passes and when it fails. The JSON also adds the top-level `model_requested` and `init_model`.
- The canary's text output still ends with the literal `CANARY PASS` / `CANARY FAIL` line the owner steps match.

**5. [Rule 2] The claim file's `model` holds the requested model.**
- It was `null`. Plan 07-21's stale-claim test plants its own record, so nothing else changed.

**Total deviations:** 2 orchestrator rulings (deferred minors), the orchestrator's as-built notes applied, 1 Rule 3 fix, 1 Rule 1 harness fix, 1 Rule 2 change and 2 plan clarifications.
**Impact on plan:** every must-have truth holds. Neither prohibition was crossed: no real session ran, and session.py and streamjson.py are not edited. There is no scope creep beyond the ruling-required picker change.

## Issues Encountered

- The harness refused compound shell commands (heredocs with git, a variable as a command operand). I used the Edit tool and two scratchpad scripts for the multi-site driver edits.

## Concerns for later plans

- **flags.py still accepts only Opus for flag-approved landings.**
  - `flags.KNOWN_MODEL` carries the comment "07-30 widens", and `flags._coauthor` refuses any attempt whose `model` is not `claude-opus-5-5`.
  - From now on, a candidate written by a Fable attempt cannot be flag-approved. A candidate written by both models would need two co-author lines.
  - flags.py was not in this plan's files, so I did not change it. Widening it to `driver.coauthor(model)` per attempt (and deciding the mixed-model case) is a small follow-up for the orchestrator to rule on.
- **Research A9 is still open.** The owner's Fable canary (07-39) shows whether CLI 2.1.308 accepts `claude-fable-5-1` and what init string it reports. The canary now prints that string. If it differs from the model id, add it to `streamjson.ACCEPTED_INIT_MODELS["claude-fable-5-1"]`.
- **No Fable-budget confirmation step in code.** D-10 asked the owner to confirm the Fable cap before the first Fable session, and D-25 settled it at 12.50. The default is 12.5, and `--fable-budget-usd` overrides it per run.

## Known Stubs

None.

## Threat Flags

None. T-07-88 (the requested-model init check in the night and the canary), T-07-89 (`coauthor` refuses an unknown model before the commit) and T-07-90 (the separate Fable budget flag, the shared night cap unchanged) are mitigated as planned. There is no new network, file or trust surface.

## Verification

- Task 1: `uv run pytest -q tests/test_escalation.py tests/test_driver.py tests/test_drive.py`: 242 passed, 2 skipped. Acceptance: driver.py contains `model_for_pass(` and `expected_model=`. PASS.
- Task 2: `uv run pytest -q tests/test_escalation.py tests/test_driver.py`: 162 passed, 2 skipped. Acceptance: driver.py contains `def coauthor(`. PASS.
- Task 3: `uv run pytest -q tests/test_escalation.py tests/test_cli.py tests/test_drive.py`: 213 passed. Acceptance: `uv run reverseapoc drive --help` prints `--fable-budget-usd` and `--model`. PASS.
- `uv run pytest -q` (host, worktree): **3841 passed, 251 skipped**, exit 0.
  - This plan adds no skip marker.
  - Every skip reason in the run is an existing, allowed one: clang, objdiff-cli, Watcom not installed, orig/ not present, POSIX-only.
  - The full run started before the last coordinator test and the canary paragraph of docs/workflow.md. Those two were checked separately: `tests/test_driver_pick.py tests/test_driver_workers.py`, 117 passed.
- `uv run ruff check .`: All checks passed.
- Extra regression runs:
  - `tests/test_flags.py tests/test_session.py tests/test_streamjson.py tests/test_driver_records.py`: 280 passed, 1 skipped.
  - `tests/test_stats.py tests/test_attempts_schema.py`: 160 passed.
  - `REVERSEAPOC_ORIG=<main checkout>/orig uv run pytest -q tests/test_drive_real.py`: 3 passed.
- I ran no real `claude -p`, no `drive` command (not even a dry run) and no docker (D-11, R-B). Every session was tests/fakeclaude.py.
- **Container step deferred to the orchestrator:** `docker compose build && docker compose run --rm test`.

## User Setup Required

None.

## Next Phase Readiness

- 07-39: the owner's Fable canary is `uv run reverseapoc drive --canary --model claude-fable-5-1 --run <fresh id>`. Its init line and JSON `init_model` show the string to report.
- 07-41 / `stats`: records carry the per-pass `model_requested` and `budget_usd`, so the per-model split (D-09) reads real values.

## Self-Check: PASSED

- FOUND: tests/test_escalation.py, tools/reverseapoc/driver.py, tools/reverseapoc/cli.py, tools/reverseapoc/picker.py, tests/fakeclaude.py.
- FOUND on this branch (3201ace..HEAD, 7 commits): 2d47364, ffee7bf, b6532e9, 04a07dc, 91e05f3, 68096f1, 0b1a665.
- No change to STATE.md, ROADMAP.md or REQUIREMENTS.md (the orchestrator owns them after the merge).

## Fix round 1

The task review (`review-07-30.md`) found one Important issue and one Minor issue I was asked to fix. FIX_BASE was 0e656bb. The branch guard passed (branch `worktree-agent-aabe21fd8e0241174`, agent namespace).

**Orchestrator ruling F33: flag-approved landings name the co-author of each model that wrote them.**
- The problem: `flags.KNOWN_MODEL` and `flags._coauthor` still refused any attempt that was not Opus, so a Fable-written candidate could never be flag-approved. The "07-30 widens" comment was false.
- This was the "Concerns" item above. The orchestrator ruled that 07-30 owns F33, so `tools/reverseapoc/flags.py` and `tests/test_flags.py` join this plan as a recorded deviation.
- The fix:
  - `flags._attempt_models` maps each attempt record to its (pass, model). The model is the v2 record's `model_requested`, else v1's `model`. A v1 record counts as pass 1.
  - `flags._coauthors` passes each hitting attempt's model through `driver.coauthor`. It returns one `Co-Authored-By:` line per distinct model, in pass order and then evidence order.
  - An attempt with no record, or a model the table does not name, is refused as before. The FlagsError names the attempt and the model.
  - `_Landing.coauthors` is now a tuple, and the approve message spreads it before `Matched-By`.
  - `KNOWN_MODEL` and its stale comment are gone.
  - The edit stays inside the co-author code and its two call sites, clear of the lint hotfix's approve change on main.
- **[Rule 1, same fix] A v2 record is found by its start.** 07-23 gives a v2 record its C name as `function`, while the attempt directory in the evidence path keeps the `func_` placeholder. A function with a real C name would have been "model unknown". Records are now keyed by (run, exe, start, attempt), with the function-name key kept as a fallback.
- Tests in `tests/test_flags.py`:
  - `test_approve_a_fable_candidate_names_fable`;
  - `test_approve_finds_a_v2_record_named_by_its_c_name`;
  - `test_approve_a_mixed_candidate_gets_one_trailer_per_model_in_pass_order`. Its evidence lists the Fable attempt first, and the trailers come out Opus, then Fable;
  - the refusal case `v2 unknown model`.
  - The existing refusals (`unknown model`, `other model`, `no attempt record`) and `test_approve_lands_one_commit` (the Opus `COAUTHOR`) are unchanged and green.

**Review minor: the canary's claim carries its requested model.**
- `_run_canary_locked` builds its `_Claim` with `model=options.canary_model` and that model's budget. The canary argv now reads both from the claim.
- Test: `tests/test_escalation.py::test_the_canary_claim_carries_its_requested_model`.

**RED** (`5842529`): 4 failed.
- The three approve tests were refused with "only claude-opus-5-5 has a known co-author line". The C-name case reported "model unknown".
- The canary claim test got `('claude-opus-5-5', 5)` where `('claude-fable-5-1', 20.0)` was expected.
- The new refusal case passed from the start, as a pin.

**Commits:**
- `5842529` test(07-30): add failing tests for per-model flag-approval co-authors and the canary claim's model
- `637c113` fix(07-30): flag approvals name each model's co-author; the canary claim carries its model
- this SUMMARY commit

**Counts:**
- Covering suites `tests/test_flags.py tests/test_escalation.py tests/test_drive.py`: 197 passed.
- `uv run pytest -q` (host, worktree): **3847 passed, 251 skipped**, exit 0, with no new skip.
- `uv run ruff check .`: All checks passed.
- `REVERSEAPOC_ORIG=<main>/orig uv run pytest -q tests/test_drive_real.py`: 3 passed.
- Container step still deferred to the orchestrator: `docker compose build && docker compose run --rm test`.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-30*
