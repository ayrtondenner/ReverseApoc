---
phase: 07-mechanics-first-decompilation
plan: 13
subsystem: driver
tags: [driver, views, d-24, landing, ledger, audit, hooks, canary, fakeclaude]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-03: check compiles a build/driver/.../view/src tree from its view root; 07-04: UNIT_FILE_ENV, PROPOSALS_ENV, SESSION_KIND_ENV and matching_write_allowed(unit_file=, proposals=); 07-07: record schema; 07-11: the wrapper's view-mode check and env validation"
provides:
  - "_Claim.view_root / view_unit / view_unit_rel / proposals / proposals_rel and the three view env variables (REVERSEAPOC_SESSION_KIND=matching)"
  - "_Night._make_view: git archive of HEAD's src/include/config, tarfile data filter, include/ always, scaffold into the view, view-head.txt (F34)"
  - "_Night._land: the only writer of src/; _reset puts back only the landed unit"
  - "_Ledger and _view_hashes: the D-24 audit (git-visible paths equal HEAD or the driver's bytes; view files unchanged but the unit and view/build/)"
  - "Deps.scaffold(pick, dest), Deps.pack(pick, dir, src); session.goal_prompt(..., unit_path=)"
  - "hooks.matching_write_allowed without the legacy allowlist; a session without REVERSEAPOC_UNIT_FILE writes nothing"
  - "the canary in view mode under build/driver/canary/"
  - "tests/fakeclaude.py --write-env-unit TEXT and --env-unit-paths"
affects: [07-18, 07-21, 07-31, 07-34, 07-35, 07-38, 07-39]

actuals:
  tokens: 26800
  tasks: 3
  commits: 6
plan_head_before: 8a8f98e5278614aa181fd6101c5ecb58ef29bead
plan_head_after: cd53dbb3492ce3d9625b516c0b8ab06220172056

tech-stack:
  added: []
  patterns:
    - "A session edits only <attempt dir>/view/src/<exe>/<unit>.c; the driver lands it into src/ before the lint and the unchanged gate"
    - "The audit checks the tree against HEAD plus a ledger of the driver's own writes, not against a pre-session snapshot"
    - "Every driver write of attempts.jsonl, status.csv or the feed first checks ledger.holds(rel) (else a guardrail breach), then records the bytes the driver computed it wrote (ledger.set); only the gate subprocesses' output is read back (fix round 1)"

key-files:
  created: []
  modified:
    - tools/reverseapoc/driver.py
    - tools/reverseapoc/session.py
    - tools/reverseapoc/hooks.py
    - tests/fakeclaude.py
    - tests/test_driver.py
    - tests/test_session.py
    - tests/test_hooks.py
    - tests/test_drive.py

key-decisions:
  - "The view is archived from the commit `rev-parse HEAD^{commit}` names, and that commit is written to <attempt dir>/view-head.txt and kept in _Session.view_head (F34)"
  - "Invariant (a) is strict: any git-visible path that is not HEAD and not the driver's ledger bytes is a stray, also one left before the session (the old minor-5 case is now a guardrail stop, not a tool stop)"
  - "Containment puts a driver-owned file (ledger) back to the bytes the driver last wrote; other files keep the Phase 6 rule (HEAD, or the pre-session bytes)"
  - "A view unit that is a link or not a regular file is a stray, and _land refuses to copy it"
  - "The canary claims under build/driver/canary/ through _Claim.runs and is refused (exit 2) when HEAD lacks its matched unit; it never scaffolds"

patterns-established:
  - "_Night._append(record) for every driver record, so the ledger always holds the log's bytes"

requirements-completed: [DEC-02]

coverage:
  - id: D1
    description: "Views from HEAD (src, include, config) via git archive; include/ always; missing unit scaffolded into the view; view head recorded"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_driver.py#test_view_is_head_snapshot, test_view_always_has_include, test_missing_unit_is_scaffolded_into_the_view, test_view_records_its_head_commit, test_pack_reads_the_view_src"
        status: pass
    human_judgment: false
  - id: D2
    description: "Session env carries REVERSEAPOC_UNIT_FILE, REVERSEAPOC_PROPOSALS and REVERSEAPOC_SESSION_KIND=matching; goal_prompt names the view unit after a shape check"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_driver.py#test_session_env_has_view_paths, test_goal_prompt_of_a_night_names_the_view_unit; tests/test_session.py#test_goal_prompt_names_the_view_unit, test_goal_prompt_refuses_a_malformed_unit_path"
        status: pass
    human_judgment: false
  - id: D3
    description: "Landing: the gate sees src/ differ from HEAD only in the claimed unit; a match commits unit, status.csv, feed and log; a mismatch puts back only the unit"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_driver.py#test_view_unit_lands_and_commits, test_failed_gate_restores_only_the_unit"
        status: pass
    human_judgment: false
  - id: D4
    description: "Ledger and view-hash audit; no header writes; pre-gate restore of status.csv and the feed only; F19 log truncation"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_driver.py#test_tracked_edit_outside_the_view_stops_the_night, test_view_edit_outside_the_unit_is_caught, test_view_build_output_is_not_a_stray, test_driver_written_files_are_not_strays, test_a_table_change_the_driver_did_not_write_is_a_stray, test_ledger_explains_only_the_bytes_the_driver_wrote, test_no_header_is_committed, test_pre_gate_restore_keeps_the_log, test_undo_match_drops_only_its_matched_record, test_a_view_unit_that_is_no_longer_a_file_is_a_stray"
        status: pass
    human_judgment: false
  - id: D5
    description: "Hook legacy allowlist removed; the canary runs in view mode with its PASS rule"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_hooks.py#test_claim_without_unit_file_writes_nothing, test_legacy_header_allowance_gone; tests/test_drive.py#test_canary_runs_in_view_mode, test_canary_pass_rule_still_needs_the_denials, test_canary_refuses_without_its_matched_unit"
        status: pass
    human_judgment: false
  - id: D6
    description: "Host suite and ruff green; the container run is deferred to the orchestrator (R-B)"
    verification:
      - kind: other
        ref: "uv run pytest -q (3040 passed, 236 skipped) && uv run ruff check ."
        status: pass
    human_judgment: true
    rationale: "docker is not allowed in a worktree; the orchestrator runs docker compose build && docker compose run --rm test after merge"

duration: 46min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 13: Private views and the landing section in the driver Summary

**Each session now edits a private `build/driver/<run>/<exe>/<func>/attempt-<n>/view/` that the driver archives from HEAD (src/, include/, config/). The driver alone lands the view unit into src/ before the lint and the unchanged gate, and puts back only that unit on a mismatch. The audit checks the tree against HEAD plus a ledger of the driver's own writes, and checks the view against its launch hashes. Matching sessions write no header. The hook's Phase 6 single-session allowlist is gone, and the canary runs in view mode.**

## Performance

- **Duration:** about 46 min
- **Started:** 2026-10-27T17:45Z (approx.)
- **Completed:** 2026-10-27T18:31Z
- **Tasks:** 3, all TDD: a RED commit, then a GREEN commit
- **Files modified:** 8

## Accomplishments

- **Views (Task 1, D-24).**
  - `_make_view` runs `git archive --format=tar <head> -- <trees>` through `deps.git`, for the trees out of src/include/config that `ls-tree` lists at HEAD. It extracts them with `tarfile` and `filter="data"`.
  - It always creates `include/`, so a view never compiles against the committed headers. It writes `view-head.txt` (F34). It scaffolds a missing unit into the view through `Deps.scaffold(pick, dest)`.
  - The pack is built from the view's `src/` (`Deps.pack(pick, dir, src)`).
  - The session env adds the view unit, `proposals.jsonl` and `REVERSEAPOC_SESSION_KIND=matching`.
  - `goal_prompt(..., unit_path=)` names the view unit after an exact shape check.
- **Landing.** `_land` is the first step of `_judge`. It copies the view unit into `src/<exe>/<unit>.c`, refusing a link or a non-file.
  - `_reset` restores only that unit: `git restore --source=HEAD -- <unit>`, or it deletes the copy the driver landed when HEAD has no such unit. It never touches `include/`.
- **Audit (Task 2).**
  - `_Ledger` holds the bytes the driver last wrote to the log, `status.csv` and the feed. As first built it read each file back after a driver write, which would have accepted a tamper as the driver's own bytes. Fix round 1 corrected this: every driver write now first checks that the file still holds the expected bytes, then records the computed bytes. See "Fix round 1" below.
  - `_unexplained` flags every git-visible path that neither equals HEAD nor holds, unstaged, the ledger's bytes.
  - `_view_hashes` covers every view file except the unit and `view/build/`. `_view_changes` adds the unit when it is no longer a regular file. Strays go through the Phase 6 `_guardrail` (quarantine, restore, STOPPED).
- **No headers (D-19).** `_commit_headers`, `_Session.new_headers` and the `include/` arms are removed. `_judge`'s pre-gate snapshot holds only `status.csv` and the feed. `_undo_match` truncates the log to its length before the MATCHED record (F19).
- **Hooks (Task 3).**
  - `matching_write_allowed` returns False without `unit_file`.
  - `_matching_write` denies a session without `REVERSEAPOC_UNIT_FILE` with "a session needs the driver's REVERSEAPOC_UNIT_FILE (D-24) ...".
  - The `_NEW_HEADER` and `_RESERVED_HEADERS` legacy code is gone.
- **Canary.** It claims under `build/driver/canary/` (`_Claim.runs`) and builds a view of HEAD. It is refused before the session when HEAD lacks `src/ufo2p/u_000a34f0.c`. The PASS rule is unchanged.

## Task Commits

1. **Task 1 (tracer): views and the landing section.** RED `fdd832a`, GREEN `aafa993`.
   - Tracer feedback gate: the run was interactive, in end-of-phase mode, with an automated-only verify. I re-ran `uv run pytest -q tests/test_driver.py tests/test_session.py` (green) before expanding.
2. **Task 2: the ledger and view-hash audit, no headers, pre-gate restore.** RED `e4a9ce5`, GREEN `2794edb`.
3. **Task 3: hook legacy removed, canary in view mode.** RED `c4d4cb1`, GREEN `cd53dbb`.

## TDD evidence (RED)

Each RED run wrote pytest JUnit XML (`build/red/t{1,2,3}.xml`, gitignored), and `gsd-tools check tdd-red-evidence` returned `RED_EVIDENCE_OK` / `target_test_failed` each time.

- **t1, target `test_view_unit_lands_and_commits[True]`: 23 failed.**
  - The gate saw `('', SCAFFOLD)` instead of `(' M src/ufo2p/u_00010000.c', VIEW_TEXT)`.
  - The env had no `REVERSEAPOC_UNIT_FILE`, and the views were empty.
  - The reset restored `include/`.
  - `goal_prompt` raised `TypeError` for the `unit_path` keyword, which does not exist yet.
  - Semantic assessment: every target ran and failed on the planned behaviour. There were no collection or import faults.
- **t2, target `test_view_edit_outside_the_unit_is_caught[include/common.h]`: 9 failed, 10 passed.**
  - Failures:
    - three view edits ENDED instead of STOPPED;
    - the between-sessions `status.csv` change was missed;
    - `_Ledger` and `_truncate` were missing;
    - both log tests lost the other writer's record;
    - the pre-existing header case was STOPPED `tool`.
  - The 10 passes are pins of behaviour that Task 1's GREEN already gave: direct src/tools edits and new headers are strays under the view allowlist, `view/build` output is not, and the other undo steps behave as before.
- **t3, target `test_claim_without_unit_file_writes_nothing`: 6 failed, 27 passed.**
  - Failures: the legacy src unit and header writes were allowed, the entry point allowed the new header, and the canary got the night's view path and no view.

## Files Created/Modified

- `tools/reverseapoc/driver.py`:
  - new constants `VIEW_HEAD`, `VIEW_TREES`, `MATCHING_KIND`;
  - `_Claim.runs` and the view properties;
  - new `_Ledger`, `_truncate`, `_make_view`, `_land`, `_unexplained`, `_view_hashes`, `_view_changes`, `_drop_log_tail`, `_append`;
  - `_Session` gains `view_head`, `after` and `view_hashes` and loses `new_headers`;
  - `_reset`, `_judge`, `_restore_pre_gate`, `_partial_gate`, `_commit_match`, `_undo_match`, `_contain_one`, `real_deps`, `load_world` and `run_canary` are updated, and the module docstring with them;
  - `_commit_headers`, `_ensure_unit` and `_UNTRACKED` are removed.
- `tools/reverseapoc/session.py`: `_VIEW_UNIT`, `_view_unit_problem`, and `goal_prompt(..., unit_path=)` with new wording.
- `tools/reverseapoc/hooks.py`: the legacy allowlist is removed and the docstring updated.
- `tests/fakeclaude.py`: `--write-env-unit TEXT` and `--env-unit-paths`.
- `tests/test_driver.py`:
  - Night harness changes: a `VIEW` default write, `_see`, the scaffold and pack recorders, and `prompts`;
  - 23 new test functions;
  - retired header halves and flipped header tests.
- `tests/test_session.py`: the view-unit prompt tests.
- `tests/test_hooks.py`: `matching()` defaults to a view env, the matching-layer write tests now judge the view unit, and two new legacy-removal tests.
- `tests/test_drive.py`: the canary rig commits a made-up matched unit, plus three canary tests.

## Decisions Made

See `key-decisions` in the frontmatter.

## Deviations from Plan

**Orchestrator ruling F19:** `_undo_match` no longer restores the log from a pre-gate snapshot. It truncates `progress/attempts.jsonl` to its size just before the MATCHED append (`_drop_log_tail` / `_truncate`), so a record appended before it stays. The failed-commit tests are kept. The "log" case of `test_a_failed_undo_step_commits_nothing` now makes `_truncate` fail. New test: `test_undo_match_drops_only_its_matched_record`. Commits `e4a9ce5` and `2794edb`.

**Orchestrator ruling F34:**
- **Applied.** The view's commit id is recorded in `<attempt dir>/view-head.txt` and in `_Session.view_head` (`test_view_records_its_head_commit`).
- **Not applied here: the proposals half.** That half says to apply proposals only from readability sessions, or to set `REVERSEAPOC_PROPOSALS` only for them. 07-13 applies no proposal at all, so matching nights keep their placeholders. The plan, and 07-11's wrapper, which requires `REVERSEAPOC_PROPOSALS` in view mode, both set the variable for matching sessions. The "apply only from readability sessions" rule is therefore 07-34's to implement in its writer.

**Orchestrator note (07-03 as built):** views live at `build/driver/<run>/<exe>/<func>/attempt-<n>/view/` and hold `src/` and `include/`. The gate, lint and partial gate still run from the repository root (`command_runner` uses cwd=repo).

**Orchestrator note (07-11 as built):**
- Every view gets `include/`, even when HEAD has none (`test_view_always_has_include`).
- **Known gap, recorded:** in view mode, `attempt context` and `attempt asm` still read the shared config and `common.h`. The driver's own pack does the same: `make_pack` takes `config=roots.config` and `common_h=roots.common_h`, and only `src` comes from the view.

**1. [Rule 3 - Blocking] The audit's view-mode allowlist moved into Task 1.** Once sessions edit the view, the transcript names the view unit. The legacy `_allowed` would call every session a stray. `_allowed` therefore passes `unit_file`/`proposals` from Task 1 on, and the header halves of `test_match_commit_adds_new_files` and `test_a_failed_match_commit_unstages_new_files_too`, plus `test_a_plain_new_header_is_committed_with_literal_pathspecs`, were retired in Task 1's GREEN commit (`aafa993`). The plan had them in Task 2.

**2. [Rule 3 - Test harness] `fakeclaude --env-unit-paths`.** This is not in the plan. The stream fixtures name `/repo/src/ufo2p/u_00010000.c` in their Edit event. With the flag, the stand-in replays that one `file_path` as `REVERSEAPOC_UNIT_FILE`, as a session editing its view unit would. Without the variable, nothing changes. The Night harness passes it always, and a plain `Sess()` now writes its view unit (`--write-env-unit`).

**3. [Rule 2 - Missing critical] A view unit that is no longer a regular file.** `_land` refuses to copy a link or a non-file, and the audit names such a unit as a stray. Test `test_a_view_unit_that_is_no_longer_a_file_is_a_stray` was written in GREEN. I proved it bites by removing the check: the test failed, though the night still stopped through the transcript check. I then restored the check.

**4. [Rule 2 - Missing critical] Canary refusal.** The canary is refused (exit 2) before any session when HEAD lacks the matched unit. Its probe has no scaffold, and a scaffolded unit would make the canary's `attempt check` meaningless. Test: `test_canary_refuses_without_its_matched_unit`.

**5. [Plan clarification] Strict invariant (a).** Dirt the driver did not write is a stray even if it existed before the session.
- `test_an_untracked_header_from_before_the_session_is_named` changed from STOPPED `tool` to STOPPED `guardrail`. The file is copied into quarantine.
- `drive`'s preflight already refuses a dirty tree, so this changes nothing for a real night.

**6. [Test fix during GREEN] `test_claim_without_unit_file_writes_nothing`.** A view-shaped path without the env is denied first by the always layer's build/ rule, not the D-24 reason. The test now asserts that reason for that one target. Commit `cd53dbb`.

**7. [Plan clarification] Signatures.** `ExeWorld.pack` gained an optional `src` (the dry run still passes two arguments). `ExeWorld.scaffold` takes `dest`. `matching_write_allowed` keeps its `tracked` keyword, which no rule reads any more.

---

**Total deviations:** 2 orchestrator rulings (F19 applied, F34 applied in its 07-13 half) and 2 orchestrator notes applied; 4 auto-fixes (Rule 2 x2, Rule 3 x2); 3 clarifications or test fixes.
**Impact on plan:** every must-have truth holds. The extra test option and the earlier allowlist change were needed so the stand-in sessions model view-mode sessions.

## Issues Encountered

None blocking. A harness heredoc mangled one escape in fakeclaude during RED authoring. It was fixed before the RED commit.

## Known Stubs

None.

## Verification

- `uv run pytest -q tests/test_driver.py tests/test_session.py`: green (Task 1 verify, also re-run as the tracer gate).
- `uv run pytest -q tests/test_hooks.py`: 316 passed, 2 skipped (the 2 pre-existing symlink-privilege skips).
- `uv run pytest -q tests/test_drive.py`: 86 passed.
- `uv run pytest -q` (host, worktree): **3040 passed, 236 skipped**.
  - The four touched suites keep the same 5 skips as before this plan: hooks 2 for symlink privileges, plus 3 pre-existing in driver/session/drive.
  - This plan adds no skipping test and no new skip reason.
- `uv run ruff check .`: All checks passed.
- Acceptance:
  - driver.py contains `def _make_view(`, `def _land(`, `class _Ledger` and `def _view_hashes(`, and no `def _commit_headers(`.
  - fakeclaude accepts `--write-env-unit`.
  - test_hooks.py contains `test_claim_without_unit_file_writes_nothing`.
- **Container step deferred to the orchestrator:** `docker compose build && docker compose run --rm test`.

## User Setup Required

None.

## Next Phase Readiness

- 07-18 and 07-21 can wrap `_make_view` and `_land` with claims, the gate lock and workers. The ledger already explains driver writes made during another session. `_undo_match`'s truncation relies on 07-18's gate lock to keep other appends out of the landing section (F19).
- 07-34 can read `view-head.txt` / `_Session.view_head` for `_renames_since`, and must apply proposals only from readability sessions (F34).
- 07-35 (the view-mode watcom-decomp skill, through writing-skills) has to change the skill text. It still says a session may write "a new header under `include/`" and names `src/<exe>/<unit>.c` as the file. The hooks and the audit now deny both.
- 07-39's preflight measures the first real view check's wall time (K2).

Execution context nonce: 4f0f04e95e3d63b7

## Self-Check: PASSED

- FOUND: tools/reverseapoc/driver.py, tools/reverseapoc/session.py, tools/reverseapoc/hooks.py, tests/fakeclaude.py, tests/test_driver.py, tests/test_session.py, tests/test_hooks.py, tests/test_drive.py
- FOUND commits: fdd832a, aafa993, e4a9ce5, 2794edb, c4d4cb1, cd53dbb (`git rev-list --count 8a8f98e..HEAD` = 6 before this SUMMARY commit)
- No STATE.md or ROADMAP.md change.

## Fix round 1

**Finding (Important, the review of 07-13):**
- The problem: `_Ledger.note`, `_append` and the gate and partial-gate `finally` blocks recorded whatever bytes were on disk after each driver write, and nothing checked the file first.
- The risk: with concurrent sessions, a tamper of attempts.jsonl, status.csv or the feed made before a driver append or during a gate would have been recorded as the driver's own bytes. The next commit would then have carried it to main without going through the gate.
- An earlier version of this SUMMARY said the opposite. That claim, and the `_Ledger` docstring, are now corrected.

**Ruling applied (orchestrator):**
- Before every driver write to a ledgered path, the file must still match the ledger: HEAD's bytes, or the driver's last recorded bytes. Otherwise the night stops as a guardrail breach.
- After the write, the ledger records the bytes the driver computed it wrote, never a read-back.

**What changed (`tools/reverseapoc/driver.py`):**
- **New `_Ledger` methods:**
  - `expected(rel)` gives the driver's last bytes, or HEAD's through `git cat-file blob HEAD:<rel>`.
  - `holds(rel)` requires a regular file (never a link) with exactly those bytes.
  - `set(rel, data)` records the computed bytes.
- **`note` is kept only for the gate.** `gate` and `gate --partial` are subprocesses that write status.csv and the feed. Their output is read back only after `_guard` checked that both files held the expected bytes when the gate started. **Residual (in the docstring):** a change made by someone else while the gate runs is taken for the gate's output.
- **Breach handling (`_guard` and `_breach`).** A file that does not hold its bytes is copied to the quarantine (moved when no bytes are expected) and put back to the expected bytes. The attempt in progress is reset, `breached` is set so nothing is committed that night, and the night stops STOPPED `guardrail`.
- **Where each write path records its bytes:**
  - **`_append`, every record:** guard, then the ledger records the expected bytes plus the line (`record_line`, factored out of `append_record`).
  - **`_judge` and `_partial_gate`:** guard status.csv and the feed before the gate. The pre-gate snapshot is now the ledger's expected bytes.
  - **`_restore_pre_gate`:** a file changed since the gate wrote it is a breach (put back to the pre-gate bytes). A good restore records the pre-gate bytes.
  - **`_drop_log_tail` (F19):** guard, truncate, then record the expected prefix.
- **Commit checks:**
  - `_commit_match` runs `_verify_landing` right before `git add`. It checks that status.csv, the feed and the log hold the driver's bytes and that src/ holds the unit it landed. A failure goes through `_undo_match` with reason `guardrail`.
  - `run()` checks every ledgered file once more before the final record and the chore commit (`_ledger_breaches`).
  - A STARTED record that finds the log changed refuses the night.
  - **Residual:** a tamper in the instant between `_verify_landing` and `git add` is not seen.

**Tests:**
- **RED `2286cd0`.** 4 failed, 3 passed. Classifier `RED_EVIDENCE_OK` (target `test_a_log_tamper_between_driver_appends_stops_the_night`, JUnit XML `build/red/f1.xml`).
  - `test_a_log_tamper_between_driver_appends_stops_the_night`: ENDED instead of STOPPED, and the tamper went into the chore commit.
  - `test_a_table_tamper_before_the_gate_stops_the_night`: the gate ran.
  - `test_a_feed_tamper_before_the_partial_gate_stops_the_night`: the partial gate ran.
  - `test_a_log_tamper_before_the_match_commit_is_never_committed`: the match was committed.
  - The 3 passes are `test_an_untampered_night_commits_the_match_and_the_log` (normal path, ruling (c)) and the two F19 tests.
  - The F19 tests' other writer now appends through the driver's own `_append` (`_capture_nights`), as a 07-18 worker of the same process would. A foreign raw append is now, correctly, a breach.
- **GREEN `b12e7c1`.**
  - **Test fix:** the feed test's `git restore` hook re-tampered during the breach's own reset, so it now fires once.
  - **Added in GREEN:** `test_a_table_tamper_before_the_chore_commit_is_never_committed`, for the end-of-night check. I proved it bites by disabling `_ledger_breaches`: it failed, and I then restored the check.
  - **Not tested:** the pre-gate-restore breach branch. Nothing is called between the gate's return and that restore, so a fake has no point at which to tamper.

**Commands and output:**
- `uv run pytest -q tests/test_driver.py tests/test_drive.py tests/test_session.py tests/test_hooks.py`: 574 passed, 5 skipped (the same 5 pre-existing skips).
- `uv run pytest -q` (host, worktree): 3046 passed, 236 skipped. No new skip reason.
- `uv run ruff check .`: All checks passed.
- Container step still deferred to the orchestrator: `docker compose build && docker compose run --rm test`.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
