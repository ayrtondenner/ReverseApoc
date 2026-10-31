---
phase: 07-mechanics-first-decompilation
plan: 34
subsystem: driver
tags: [d-19, d-29, rename, proposals, headers, symbols, driver, f12, f34]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-19: proposals.read_proposals, parse_line, rename_problem, header_problem, linker_name"
  - phase: 07-mechanics-first-decompilation
    provides: "07-16: SymbolTable.c_name through unitdefs.c_name_of; the rename path pinned through gate"
  - phase: 07-mechanics-first-decompilation
    provides: "07-18: Claims, gate_lock, git_lock, _commit_with_retry"
  - phase: 07-mechanics-first-decompilation
    provides: "07-30: claim model and coauthor(model); 07-13: view-head.txt (F34) and _land"
provides:
  - "driver: DriveConfig.session (matching | readability); _Claim.session drives the hooks' session kind, the claim file's kind and the v2 records' session"
  - "driver: _apply_proposals(session) after a readability session's audit and before its landing (ruling F34: never after a matching one)"
  - "driver: _apply_pending, _plan_rename, _plan_header, _affected_units, _affected_headers, _includers, _blocked, _rename_claim, _gated_commit, _commit_naming, _record_rename, _retry_deferred, _renames_since, _c_names_at"
  - "driver: RENAMED_BY = 'Renamed-By: reverseapoc drive', rename_gate_argv(targets), Deps.rename_gate, Deps.data_ranges, ExeWorld.data_ranges (wired in real_deps and load_world)"
  - "driver._land rewrites the view unit with every rename committed since the view's HEAD"
  - "unitdefs.file_scope_names(text), unitdefs.included_headers(text)"
  - "attempt._attempt_records keys a placeholder's records by start too (earlier_notes keeps a renamed function's history)"
  - "tests/test_rename.py (33 tests)"
affects: [07-35, 07-36, 07-38, 07-39, 07-40, 07-41]

actuals:
  tokens: 20000
  tasks: 3
  commits: 6
plan_head_before: ce7fc2dacd79b9f2cfefe62b4aea4676d34c2c13
plan_head_after: 35fd9069c0a139bb18b06b39343be88ed8cda561

tech-stack:
  added: []
  patterns:
    - "A naming change is a _NamingPlan (bytes of every path, gate targets, subject, the old->new map), applied by one all-or-nothing step: HEAD check, rename claim, write, gate, commit or byte-for-byte restore"
    - "Renames are rewritten as one simultaneous whole-word substitution over bytes, so a chain or swap of names never cascades"
    - "A proposal record is built in F12's shape and validated before the append; a REFUSED proposal its fields cannot hold falls back to op null with the proposal named in the reason"

key-files:
  created:
    - tests/test_rename.py
  modified:
    - tools/reverseapoc/driver.py
    - tools/reverseapoc/unitdefs.py
    - tools/reverseapoc/attempt.py

key-decisions:
  - "Proposals apply only when the claim's session is readability (DriveConfig.session, default matching), per ruling F34; 07-38 adds the readability landing, prompt and CLI flag"
  - "The last line for a row (exe, kind, address) or a header path wins, as the readability skill says; earlier lines are REFUSED as superseded"
  - "Blocked = an affected unit (not the session's own) with a claim file or a coordinator pass on it; the rename takes claim files of kind rename on the other units and marks them busy in the coordinator so none is dispatched meanwhile"
  - "Deferred proposals are retried after every claim release (_claimed, on normal exit) and once at the night's end; a DEFERRED record is written once"
  - "A rename with no affected unit, and a header with no includer, run `gate --all` (rename_gate_argv with no targets)"
  - "Naming commits carry the proposing model's Co-Authored-By line before Renamed-By; the proposal's evidence text is not copied into the commit (it may quote game strings)"
  - "A naming gate or commit that fails as a tool stops the night (TOOL) after the restore and a REFUSED record; a commit holding bytes the driver did not write, or a foreign commit under it, stops it as a breach"

patterns-established:
  - "_renames_since(view_head) diffs symbols.csv between the view's commit and HEAD; every landing takes it"

requirements-completed: [DEC-02, DEC-04]

coverage:
  - id: D1
    description: "One readability session's rename proposal becomes one refactor(<exe>) commit holding symbols.csv, every committed user, status.csv and the feed, with Renamed-By; one gate over all affected units; a failing gate restores every byte; matching sessions apply nothing (F34)"
    requirement: DEC-02
    verification:
      - kind: integration
        ref: "tests/test_rename.py#test_rename_end_to_end, test_fake_gate_saw_all_units, test_gate_failure_restores, test_matching_sessions_apply_no_proposal, test_records_name_the_readability_session, test_log_lists_the_rename_after_its_commit"
        status: pass
    human_judgment: false
  - id: D2
    description: "Collisions (symbols.csv, header names, common.h typedefs, file-scope names), malformed and unreadable files, non-identifier names (op null), superseded lines, all REFUSED without a night stop; v2 rename records validate (F12)"
    requirement: DEC-04
    verification:
      - kind: integration
        ref: "tests/test_rename.py#test_collision_refused, test_malformed_file_refused, test_unreadable_file_is_one_refusal, test_name_that_is_no_identifier_is_a_null_op_refusal, test_last_line_for_a_row_wins, test_src_names_hold_header_and_file_scope_names[*]"
        status: pass
    human_judgment: false
  - id: D3
    description: "Header proposals: written and gated with every includer (also through other headers); reserved headers refused; a failing gate restores; a rename rewrites a driver-written header naming the row"
    requirement: DEC-04
    verification:
      - kind: integration
        ref: "tests/test_rename.py#test_header_proposal_gates_includers, test_header_includers_through_other_headers, test_header_proposal_failing_gate_restores, test_new_header_without_includers_writes_it, test_reserved_header_refused, test_rename_rewrites_a_header_that_names_it"
        status: pass
    human_judgment: false
  - id: D4
    description: "DEFERRED behind another live claim and applied after its release; two renames of one unit land in proposal order; the rename claim is released; a claim lost meanwhile defers; commit and gate failures restore and stop"
    requirement: DEC-02
    verification:
      - kind: integration
        ref: "tests/test_rename.py#test_deferred_behind_live_claim, test_deferred_still_held_at_the_end_stays_deferred, test_two_renames_one_unit_in_order, test_rename_claim_is_released, test_unit_claimed_meanwhile_is_deferred, test_commit_failure_restores_and_stops, test_gate_error_restores_and_stops"
        status: pass
    human_judgment: false
  - id: D5
    description: "Renames carried into views at landing; a session's own unit never blocks it; a renamed function keeps its pass count and history"
    requirement: DEC-02
    verification:
      - kind: integration
        ref: "tests/test_rename.py#test_view_picks_up_rename_at_landing, test_renames_since_maps_old_to_new, test_own_claim_not_blocking, test_renamed_function_keeps_pass_count_and_history"
        status: pass
    human_judgment: false
  - id: D6
    description: "Host suite and ruff green; the container run is deferred to the orchestrator (R-B)"
    verification:
      - kind: other
        ref: "uv run pytest -q (3900 passed, 251 skipped) && uv run ruff check ."
        status: pass
    human_judgment: true
    rationale: "docker is not allowed in a worktree; the orchestrator runs docker compose build && docker compose run --rm test after merge"

duration: 39min
completed: 2026-10-31
status: complete
---

# Phase 7 Plan 34: The driver lands rename and header proposals Summary

**After a readability session the driver reads its proposals.jsonl, validates each proposal against the live naming state (symbols.csv, functions.csv, runtime publics, every file-scope name of the committed units, the session's view unit and the include/ headers), and applies the valid ones under the gate lock: symbols.csv through write_symbols_csv, the exact old C name rewritten as a whole word in every committed user and driver-written header, one container gate over every affected unit and includer, then one `refactor(<exe>): rename <old> to <new>` (or `refactor(include): write include/<name>.h`) commit with `Renamed-By: reverseapoc drive`, or a byte-for-byte restore. Proposals behind another live claim are DEFERRED and retried after each release; every landing rewrites the view unit with the renames committed since its HEAD.**

Execution context nonce: ebf90bafa37f689a

## Performance

- **Duration:** about 39 min (00:32Z to 01:11Z)
- **Started:** 2026-10-31T00:32:01Z
- **Completed:** 2026-10-31T01:10:56Z
- **Tasks:** 3, each TDD: a RED commit, then a GREEN commit
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- **Session kind (F34).** `DriveConfig.session` (default `matching`, validated against `SESSIONS`). The claim carries it into the session env (`REVERSEAPOC_SESSION_KIND`), the claim file's `kind` and the v2 records' `session`. `_after_session` applies proposals only for readability sessions. It runs after the audit and the init check, before `_counted` and `_salvage`.
- **Reading.** `_read_proposal_file` calls `read_proposals`. If a line is bad, it reads the file again line by line through `parse_line`. Each bad line becomes a REFUSED record with op null that names the line. A file too large or not UTF-8 gives one REFUSED record. The last line for a row (or a header path) wins, and earlier lines are REFUSED as superseded.
- **Rename (Task 1).** `_plan_rename`:
  - `rename_problem` with the live state;
  - the new symbols.csv rows (`_renamed_rows`, written with `write_symbols_csv`);
  - every committed `src/<exe>/*.c` that uses the old name as a whole word (bytes regex `\b...\b`);
  - every driver-written header that names it, with that header's includers gated too.
- **All-or-nothing step.** `_gated_commit`:
  - every path must equal HEAD;
  - one multi-unit claim of kind `rename` on the other affected units, which are also marked busy in the coordinator;
  - write, gate (the guard, pre-gate and ledger rules of `_judge`);
  - commit through `_commit_with_retry` with explicit literal paths;
  - verify each committed blob (`_committed_as`) and that no foreign commit came in (`_foreign_commits`).
  - Any refusal puts every path back. status.csv and the feed are restored to their pre-gate bytes.
- **Header (Task 2).** `_plan_header`:
  - `header_problem`, then refused when the file already holds the text;
  - `_includers` finds the committed units of both EXEs that include the header, also through other committed headers (`unitdefs.included_headers`);
  - no includer: `gate --all`.
- **Collisions (ruling).** `src_names` comes from `unitdefs.file_scope_names`. It holds every identifier at brace, parenthesis and bracket depth 0 and every `#define`d macro, read from the committed units, the session's view unit and every committed header. So the common.h typedefs (s8..u32) and every name a driver-written header declares are taken.
- **Deferral (Task 2).**
  - `_blocked`: an affected unit other than the session's own with a claim file, or a coordinator pass on it, gives DEFERRED. The record is written once, with a reason.
  - `_retry_deferred(own)` runs after every claim release in `_claimed` (normal exit) and once at the end of `_loop`.
  - A rename claim lost to a race is DEFERRED too.
- **Views (Task 3).** `_renames_since(view_head)` diffs symbols.csv between the view's commit and HEAD: per EXE, old to new. `_land` rewrites the view unit with one simultaneous substitution before copying it. A session that proposes a rename of its own unit's function gets its view unit rewritten in place after the commit.
- **Readers keyed by name (07-23 note).**
  - `pass_index`/`passes_of`, `flags._attempt_models` and `flags.pilot_hits` already key by start.
  - `attempt._attempt_records` (earlier_notes) matched only by the function name. It now also matches the start when given the placeholder.
  - `test_renamed_function_keeps_pass_count_and_history` pins all four readers.

## Task Commits

1. **Task 1 (tracer, TDD): one rename proposal becomes one gated commit.** RED `32b2859`, GREEN `b0bdd1b`.
   - Tracer feedback gate: interactive, end-of-phase, automated-only verify. I re-ran `uv run pytest -q tests/test_rename.py` (6 passed) and the driver suites (453 passed, 2 skipped), then expanded.
2. **Task 2 (TDD): collisions, refusals, header proposals, deferral.** RED `791c750`, GREEN `999c9ec`.
3. **Task 3 (TDD): renames carried into views at landing; own claim never blocks.** RED `e7eee84`, GREEN `35fd906`.

## TDD evidence (RED)

Each RED run wrote JUnit XML under `build/red/` (gitignored, `0734-t{1,2,3}.xml`). `gsd-tools check tdd-red-evidence` returned `RED_EVIDENCE_OK` / `target_test_failed` each time.

- **t1, target `test_rename_end_to_end` (5 failed, 1 passed).**
  - Failed on its assertion: no rename commit.
  - The RED skeleton added only `DriveConfig.session` and the `Deps.rename_gate`/`data_ranges` seams, so the tests fail on assertions, not on a TypeError.
  - The pass is `test_matching_sessions_apply_no_proposal`, true by absence.
- **t2, target `test_header_proposal_gates_includers` (11 failed, 15 passed).**
  - Failed on its assertion: Task 1 refused every header op.
  - The other header and src_names cases also failed on assertions. The two unitdefs helper tests failed on AttributeError: they are the new API.
  - Task 1's GREEN already held deferral, supersession and ordering, so those Task 2 cases passed as pins (see Deviations).
- **t3, target `test_view_picks_up_rename_at_landing` (3 failed, 1 passed).**
  - Failed on its assertion: the landed unit still named func_00020010.
  - `test_renames_since_maps_old_to_new` failed on AttributeError (the new method), and the history test on its assertion.
  - `test_own_claim_not_blocking` passed as a pin of Task 1's in-place view rewrite.
- **Self-review fixes, proved by mutation.** Each of the three fixes (DEFERRED caught before REFUSED; the pre-gate bytes kept until the commit succeeds; status/feed restored on a gate exception) was undone in turn by a scratch script that restored driver.py afterwards. Each mutant failed its test: `meanwhile`, `commit_failure` and `gate_error` each gave 1 failed.

## Verification

- `uv run pytest -q tests/test_rename.py`: 33 passed (Task 1 verify).
- `uv run pytest -q tests/test_rename.py -k "collision or malformed or header or deferred or order"`: 15 passed (Task 2 verify).
- `uv run pytest -q tests/test_driver.py tests/test_driver_workers.py tests/test_drive.py tests/test_driver_records.py tests/test_escalation.py tests/test_attempts_schema.py`: 453 passed, 2 skipped. These were the pre-existing skips, on Task 1 GREEN.
- `uv run pytest -q` (full host suite, worktree): **3900 passed, 251 skipped**.
  - The skip count equals 07-30's baseline of 251.
  - test_rename.py has no skip, and there is no new skip reason. The reasons are the existing orig/, third_party/watcom, clang, objdiff-cli and taskkill skips.
- `uv run ruff check .`: All checks passed.
- Acceptance greps: driver.py contains `def _apply_proposals(`, `Renamed-By: reverseapoc drive`, `def _retry_deferred(`, `def _renames_since(`, `read_proposals(` and `write_symbols_csv(`. test_rename.py contains `Renamed-By`.
- **Container step deferred to the orchestrator:** `docker compose build && docker compose run --rm test`.

## Files Created/Modified

- `tools/reverseapoc/driver.py`:
  - module docstring;
  - `DriveConfig.session`, `Deps.rename_gate`, `Deps.data_ranges`;
  - `_Claim.session` and its use in env, claim file and records;
  - the naming-proposals block of `_Night`, the module-level helpers (`_Pending`, `_NamingPlan`, `_Refusal`, `_Deferral`, `_rewrite`, `_token`, `_read_proposal_file`, `_latest_first`, `rename_gate_argv`, ...) and `RENAMED_BY`;
  - `_land`'s rename rewrite;
  - `ExeWorld.data_ranges` and its wiring in `real_deps`/`load_world`.
- `tools/reverseapoc/unitdefs.py`: `file_scope_names`, `included_headers`.
- `tools/reverseapoc/attempt.py`: `_attempt_records` keys by start too.
- `tests/test_rename.py` (new): 33 tests on a tmp repo with the stand-in claude and a fake rename gate. Every name and address in it is made up.

## Decisions Made

See key-decisions in the frontmatter.

## Deviations from Plan

**Orchestrator rulings applied (rulings.md "## 07-34"):**
- **Orchestrator ruling F12:** rename records are written in the per-op shapes `driver._rename_problem` pins:
  - op rename fills exe/address/old/new;
  - op header fills path;
  - an unparseable line has op null and is REFUSED;
  - a commit appears only when APPLIED;
  - DEFERRED and REFUSED carry a reason (07-07 as built).
  - A REFUSED proposal those fields cannot hold, such as a name that is no C identifier, falls back to op null, with the proposal named in the reason.
- **Orchestrator ruling F34:** proposals are applied only after readability sessions, through the new `DriveConfig.session`. Matching nights keep the placeholders; `test_matching_sessions_apply_no_proposal` pins that. The view's HEAD commit is `_Session.view_head` (07-13's view-head.txt), which `_renames_since` reads.
- **Note (07-19 as built):**
  - `parse_line` runs per line, and a ProposalError becomes a REFUSED record with op null.
  - `src_names` uses a public unitdefs helper (`file_scope_names`); the private `_file_scope` is not copied.
  - It holds the typedef names of include/common.h and every name declared in a committed include/ header (`test_src_names_hold_header_and_file_scope_names[u8|SND_MAX|helper_count]`).
- **Note (07-23 as built):** `attempt._attempt_records` matched records only by the placeholder name. It now also matches by start. `pass_index`/`passes_of` and flags' `_attempt_models` and `pilot_hits` already keyed by start. `test_renamed_function_keeps_pass_count_and_history` pins the pass count, earlier_notes and `_attempt_models` across a rename. attempt.py is outside files_modified, as the note asks.
- **Rules for every plan:**
  - R-A: no new skip.
  - R-B: docker deferred.
  - R-C: no driver command was run.
  - R-D: no subagents.

**Auto-fixed and design deviations:**

1. **[Rule 2 - Correctness] Rename claims also mark the coordinator's busy map.**
   - The issue: a claim file alone would let the coordinator hand a renamed unit to another worker mid-rename. That worker's `_claimed` would then stop the night with "already claimed".
   - Commit `b0bdd1b`.
2. **[Rule 1 - Bug, self-review] Three failure-path bugs, fixed in `35fd906`.**
   - `_Deferral` (a `_Refusal` subclass) was caught as REFUSED.
   - `pre_gate` was cleared before the commit, so a failing commit could not restore status.csv and the feed.
   - A gate exception did not restore them either.
   - Each has a test proved by mutation (see TDD evidence). A tool failure is now also recorded REFUSED before the night stops.
3. **[Rule 1 - Bug] `attempt._attempt_records` matches by name or start.** A by-start-only match dropped records without a `start` key, and test_attempt_wrapper's fixture has such records. The full suite caught it (2 failures), and it was fixed before the Task 3 GREEN commit.
4. **Task boundaries.** Task 1's GREEN already built the deferral, supersession, ordering and rename-claim machinery: the shared all-or-nothing step needed them. So several Task 2 tests passed in Task 2's RED as pins. The Task 2 RED target, the header proposal, failed as planned.
5. **`_retry_deferred` is called from `_claimed`** (after each attempt's claim release, normal exit only) and at the end of `_loop`, not from `_Coordinator.release`. That is the point where a claim file is released, so the plan's "after each release" holds at claim granularity.
6. **API beyond the plan's list:**
   - `DriveConfig.session`;
   - `Deps.rename_gate` (default: a tool-exit GateRun) and `Deps.data_ranges` (default: none, so every data rename is refused);
   - `ExeWorld.data_ranges`;
   - `rename_gate_argv`, `RENAMED_BY`;
   - `unitdefs.included_headers`.
7. **Header commit subject** `refactor(include): write include/<name>.h`. The plan names only the rename subject.
8. **No includer or no user:** `gate --all`, which writes nothing.

**Total deviations:** the rulings F12 and F34 plus notes 07-19 and 07-23 applied; 2 Rule 1 fixes (one with 3 parts) and 1 Rule 2 fix; 5 documented design choices.
**Impact:** every must-have truth holds. The changes narrow what the driver applies, or make its failure paths restore fully.

## Known Stubs

- None that block this plan's goal.
- A readability night still uses the matching prompt and the matching landing. Only the proposal step reads `session` so far. Plan 07-38 adds the readability `/goal`, its landing (LANDED/REFUSED) and `drive --session readability`.
- Until then no CLI path sets `session`. A readability night whose landing gate matched would hit RecordError (MATCHED is no readability outcome) before any commit, so it stops instead of mis-committing.

## Threat Flags

None beyond the plan's register:
- **T-07-100:** validation, collision checks, header scans, the all-or-nothing gate, the byte-for-byte restore and the post-commit blob check.
- **T-07-101:** the multi-unit rename claim plus coordinator busy marks, DEFERRED behind other claims, views rewritten at landing.
- The proposal's evidence text is deliberately kept out of commit messages, because it may quote game strings.

## Issues Encountered

- The harness refused heredocs and compound commands that mention git, and Python heredocs whose text contains "git". I applied every edit from scratchpad scripts (`edit0734_*.py`) instead.
- The first full-suite run lost its failure lines to `| tail`. `pytest --lf` recovered the two failures (deviation 3).

## Follow-ups for other plans

- The watcom-readability skill (07-36) still says the driver's rename step and header writing are "planned, not built yet". It should be updated through superpowers:writing-skills; this plan did not touch it.
- 07-38 calls `_apply_proposals` from its readability flow, or keeps `_after_session`. It sets `DriveConfig.session` from `drive --session`.

## User Setup Required

None.

## Next Phase Readiness

07-38 can build the readability landing on top of this: proposals are applied first, the own claim never blocks, and the view unit lands under the new names.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-31*

## Self-Check: PASSED

- FOUND: tests/test_rename.py, tools/reverseapoc/driver.py, tools/reverseapoc/unitdefs.py, tools/reverseapoc/attempt.py
- FOUND commits: 32b2859, b0bdd1b, 791c750, 999c9ec, e7eee84, 35fd906 (`git rev-list --count ce7fc2d..HEAD` was 6 before the SUMMARY commit)
- No STATE.md or ROADMAP.md change.

## Fix round 1

FIX_BASE was d65b874. The branch guard passed: branch `worktree-agent-a7b5b519f2c68f44a`, in the agent namespace. The findings come from the task review (`review-07-34.md`): two Important issues and two Minors I was asked to fix.

**Changes.**
- **I1: `gate --all`'s splices.**
  - The problem: `gate_sha1s` read splices only from `checks[].splice`. A real `gate --all --json` puts them at the top-level `splice` (gate.GateResult.to_json).
  - So in production every naming run through `gate --all` was refused: a new header with no includer, and a rename with no committed user.
  - The fix: `_splice_lists` yields both shapes, so the match landing reads them the same way.
  - The fake rename gate in tests/test_rename.py now builds its JSON with `GateResult(...).to_json()`: per-unit splices inside each check, `--all` splices at the top level. That is the shape that had hidden the bug.
- **I2: header proposals' names.** `_plan_header` now also runs `_header_names_problem`.
  - The names come from the new `unitdefs.declared_names`: every macro a header `#define`s, every struct/union/enum tag, every enumerator, and the declared name of each declarator (typedef names, objects, prototypes, function pointers). Names a declaration only uses, such as types and parameters, are not included.
  - Each name first passes the rename path's `name_problem`: keywords, reserved names, and placeholders (func_/D_/FUN_/sub_/DAT_/LAB_/PTR_/UNK_).
  - Then it must not already be:
    - a C or linker name of a symbols.csv row of either EXE;
    - a runtime public of either EXE (runtime.csv publics and functions.csv runtime rows, read as func and as data);
    - a file-scope name of any other committed file: units of both EXEs and other headers (`_src_names(..., exclude=<the header>)`).
  - The header's own committed names stay its own, so rewriting it may keep them.
  - **Consequence:** a header can no longer carry a prototype of an existing function, because that name is a symbols.csv or unit name. Units keep their own externs. This is the reviewer's fail-closed rule.
- **S7 (Minor).**
  - `_read_proposal_file` refuses a `proposals.jsonl` that is a link, a junction or not a regular file, as one REFUSED line; it never follows it.
  - The fallback re-read is capped at PROPOSALS_FILE_MAX.
  - `_src_names` never reads the view unit through a link.
- **Minor 1.**
  - The commit message (`coauthor()`) and the read of HEAD now run inside the restore path. A raise there puts every path back, restores status.csv and the feed, and stops the night (TOOL).
  - A `_write_plan` failure is now reported as "the proposal's paths could not be written", not as a gate failure.

**RED (`544475e`): 16 failed, 33 passed.**
- Target `test_gate_sha1s_reads_both_gate_shapes`. Classifier: `RED_EVIDENCE_OK` / `target_test_failed` (`build/red/0734-fr1.xml`).
- These failed on assertions:
  - the `gate --all` rename;
  - `test_new_header_without_includers_writes_it`, now that the fake prints the real shape;
  - the four placeholder-header cases and the six collision cases (symbols, symbols-linker, runtime, unit, other header, tag);
  - the link refusal;
  - the pre-commit raise.
- `test_declared_names` failed on AttributeError: it tests new API.
- `test_rewriting_a_header_may_keep_its_own_names` passed as a pin.

**Fix:** `25800c8`.

**Commands and output after the fix.**
- `uv run pytest -q tests/test_rename.py`: 49 passed. The link test ran, with a directory junction; it did not skip.
- `uv run pytest -q` (host, worktree): **3916 passed, 251 skipped**, with no new skip. That run includes test_driver.py, test_driver_workers.py and test_drive.py.
- `uv run ruff check .`: All checks passed.
- Container step still deferred to the orchestrator: `docker compose build && docker compose run --rm test`.

**Deviations (fix round).**
- `unitdefs.py` gained `declared_names`, and `file_scope_names` now shares the directive scan (`_code_lines`) with it.
- The match landing's `gate_sha1s` reads the top-level splice too. That changes nothing for a per-unit gate, whose top-level list is empty.

## Fix round 2

FIX_BASE was 636f960. The branch guard passed: branch `worktree-agent-a7b5b519f2c68f44a`, in the agent namespace. The finding comes from the re-review (`rereview-07-34-r1.md`): one new Important issue in the I2 fix, plus the bounded-read minor.

**Changes.**
- **I1: a header rewrite was refused because of names its users only use.**
  - The problem: `_header_names_problem` compared the header's names with `file_scope_names` of the other files. That function also lists names a file only uses, such as `extern snd_level g_level;` or `extern struct mixer g_mix;`.
  - So every header that a unit refers to at file scope could not be rewritten. That blocked D-19's "add a struct field".
  - The fix: the other files' names now come from `unitdefs.declared_names` (`_declared_elsewhere`, over the units of both EXEs and the other committed headers).
  - The names the committed version of the header already declares are allowed.
- **Tags.** `declared_names` counts a struct/union/enum tag only with a body (`struct x {`) or as a bare forward declaration (`struct x;`). A use such as `struct x *p` no longer counts, so a new header may refer to another header's tag.
- **Function definitions.** A function body (a brace group after `)`) now ends its statement in `declared_names`, so every definition's name counts. Before, only the last one did.
- **Bounded read (Minor).**
  - `proposals.read_bounded` opens the file once and reads at most PROPOSALS_FILE_MAX + 1 bytes from that handle. A larger file is refused whole; the size in the message comes from fstat.
  - `proposals.parse_proposals(data)` parses those bytes. `read_proposals` is now these two steps.
  - `driver._read_proposal_file` reads once through `read_bounded` and parses the same bytes, with `parse_proposals` and then line by line, so there is no second read.

**RED (`bbb9fdb`).**
- Target `test_header_rewrite_keeps_the_types_its_users_name`: the re-review's probe. It was REFUSED: "snd.h declares mixer, which is already a file-scope name in src/ufo2p/u_00020000.c".
- Classifier: `RED_EVIDENCE_OK` / `target_test_failed` (`build/red/0734-fr2.xml`).
- Also failing:
  - `test_new_header_may_use_another_headers_tag` and `test_declared_names_of_units_and_tag_uses`, on assertions;
  - `test_proposals_are_read_once_and_bounded` (test_proposals.py), on AttributeError: it tests new API.
- The fix-round-1 collision tests stayed green. They still refuse for the right reason, which is now "declared in include/mix.h" or the unit's own declaration.

**Fix:** `2258aa3`.

**Commands and output after the fix.**
- `uv run pytest -q tests/test_rename.py tests/test_proposals.py`: 227 passed.
- `uv run pytest -q` (host, worktree): **3920 passed, 251 skipped**, with no new skip.
- `uv run ruff check .`: All checks passed.
- Container step still deferred to the orchestrator: `docker compose build && docker compose run --rm test`.

**Deviations (fix round 2).**
- `tools/reverseapoc/proposals.py` (07-19's module) gained `read_bounded` and `parse_proposals`, and `read_proposals` is now built from them. Its behaviour and messages are unchanged.
- The plan's key link to `read_proposals(` is now `read_bounded` plus `parse_proposals`, which are the same read in two steps. `_read_proposal_file`'s docstring names it.
- With the fix-round-1 rule, a header still cannot newly declare a prototype of an existing function. A rewrite may keep one the committed header already declares.
