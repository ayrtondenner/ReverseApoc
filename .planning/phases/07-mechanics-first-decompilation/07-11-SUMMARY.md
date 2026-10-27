---
phase: 07-mechanics-first-decompilation
plan: 11
subsystem: tooling
tags: [attempt-wrapper, views, d-24, env-validation, sweep]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-03: check compiles a build/driver/.../view/src tree from its view root (rule by logical path); 07-04: UNIT_FILE_ENV, PROPOSALS_ENV, SESSION_KIND_ENV, SESSION_KINDS"
provides:
  - "attempt.Claim.unit_file / proposals / kind and the view_root property"
  - "container_check_argv(claim, *, sweep, name, roots): view mode adds --src/--config/--cflags/--build/--log under <attempt dir>/view, repo-relative POSIX"
  - "attempt._unit_file / _proposals / _kind: exact-shape validation of the driver's three new env paths (exit 2)"
  - "attempt.config_root / unit_path / src_root: the trees a claim's check and pack read"
  - "check.sweep compiles a view's cells from the view root (the view's include/)"
affects: [07-13, 07-35, 07-36]

actuals:
  tokens: 6800
  tasks: 2
  commits: 4
plan_head_before: 2815ddb72530220a0d7d474ae1abe1284dda210f
plan_head_after: 4dfc7f07927e11922c438127fdf739b392dffe32

tech-stack:
  added: []
  patterns:
    - "A driver env path is accepted only when it resolves to the exact expected path AND its parts below the attempt dir are spelled exactly as written (case-folding hosts)"
    - "View mode is keyed on Claim.unit_file; every reader (snapshot, claim row, sweep rule, pack units) picks the view tree through one helper"

key-files:
  created: []
  modified:
    - tools/reverseapoc/attempt.py
    - tools/reverseapoc/check.py
    - tests/test_attempt_wrapper.py
    - tests/test_check.py

key-decisions:
  - "REVERSEAPOC_PROPOSALS is required in view mode and optional (but validated when set) in legacy mode"
  - "A session kind other than matching (readability) is refused without REVERSEAPOC_UNIT_FILE, mirroring the hook's deny-all"
  - "Only an absent REVERSEAPOC_SESSION_KIND means matching; empty, case variants and trailing spaces are refused (as in 07-04's hook)"
  - "In view mode the claim's functions.csv row is read from the view's config/, the tree the container check is given"
  - "check.sweep passes its src root in CompileOptions, so only a D-24 view changes compile root; every other tree still compiles from REPO_ROOT"

patterns-established:
  - "_names(value, expected, attempt_dir, roots): resolved equality plus exact spelling of the tail below the attempt dir"

requirements-completed: [DEC-02]

coverage:
  - id: D1
    description: "With REVERSEAPOC_UNIT_FILE set, attempt check runs check <claim> with the view's five roots (repo-relative POSIX) before --json; --sweep still appended; legacy argv unchanged"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_view_mode_argv"
        status: pass
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_legacy_mode_argv_unchanged"
        status: pass
    human_judgment: false
  - id: D2
    description: "The snapshot checks/NNNN.c, the claim row, the sweep's default rule and the context pack's unit texts come from the view"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_view_mode_snapshot_reads_the_view_unit"
        status: pass
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_view_mode_claim_row_comes_from_the_view_config"
        status: pass
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_sweep_default_rule_from_view_cflags"
        status: pass
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_view_mode_context_reads_the_view_units"
        status: pass
    human_judgment: false
  - id: D3
    description: "Env validation: unit file, proposals path and session kind accepted only at the exact shape; refusals exit 2 before any run"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_unit_file_must_be_the_view_unit"
        status: pass
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_proposals_must_be_in_the_attempt_dir"
        status: pass
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_session_kind_values"
        status: pass
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_a_readability_session_needs_a_view"
        status: pass
    human_judgment: false
  - id: D4
    description: "ATTEMPT_FORMS unchanged; no agent form passes a root option"
    verification:
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_forms_unchanged"
        status: pass
    human_judgment: false
  - id: D5
    description: "A sweep of a D-24 view compiles every cell from the view root; other trees from REPO_ROOT"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_sweep_compiles_a_view_against_the_views_include"
        status: pass
    human_judgment: false
  - id: D6
    description: "A real view check in the container (wall time against CHECK_TIMEOUT) is measured by 07-13"
    verification: []
    human_judgment: true
    rationale: "No docker in a worktree (R-B); the driver that creates real views is 07-13, which measures the view check's wall time"

duration: 10min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 11: View-rooted attempt checks Summary

**When the driver sets REVERSEAPOC_UNIT_FILE, `attempt check` runs the container check with `--src/--config/--cflags/--build/--log` under the session's `<attempt dir>/view/`, snapshots the view unit, reads the claim row, sweep rule and pack unit texts from the view, and refuses any unit-file, proposals or session-kind env that is not of the exact shape the driver creates. A sweep of a view now compiles against the view's own include/.**

## Performance

- **Duration:** about 10 min
- **Started:** 2026-10-27T16:12:01Z
- **Completed:** 2026-10-27T16:22:15Z
- **Tasks:** 2 (both TDD: RED commit, then GREEN commit)
- **Files modified:** 4

## Accomplishments

- `Claim` gained `unit_file`, `proposals`, `kind` and `view_root`. `container_check_argv` takes `roots` and, in view mode, puts the five view roots (repo-relative POSIX) between the claim and `--json`. Legacy argv is byte-for-byte Phase 6.
- `_unit_file`, `_proposals` and `_kind` validate the env in the style of `_notes`. A path must resolve to the expected path, and its parts below the attempt dir must be spelled exactly. On this case-folding host, `view/SRC/...` and `U_000A34F0.c` would otherwise resolve onto the real file (proved: with the spelling check disabled, those two cases pass the refusal test's guard and fail).
- `config_root`, `unit_path` and `src_root` choose the view's trees. The snapshot, the pre-run claim-row check, `_default_spec` (view `config/cflags.txt`) and `cmd_context` (view `src/`) use them.
- `check.sweep` carries its src root in `CompileOptions`, so a D-24 view's sweep cells compile from the view root with the view's `include/` (orchestrator note for 07-11).
- `ATTEMPT_FORMS` is unchanged and pinned against the Phase 6 tuple (T-07-32).

## Task Commits

1. **Task 1 (tracer, TDD): view-rooted argv and snapshot.** RED `15ee9a2` (test), GREEN `9ebcf04` (feat).
   - Tracer feedback gate (interactive, end-of-phase, automated-only verify): I re-ran `uv run pytest -q tests/test_attempt_wrapper.py` after GREEN (83 passed), then went on to Task 2.
2. **Task 2 (TDD): env validation, view cflags, view units, view sweeps.** RED `b3075f8` (test), GREEN `4dfc7f0` (feat).

## TDD evidence (RED)

- **Task 1 RED (`15ee9a2`):** 3 failed, 1 passed (the legacy pin). The classifier ran on the pytest JUnit XML (`build/red/t1.xml`, gitignored) with target `test_view_mode_argv` and returned `RED_EVIDENCE_OK` / `target_test_failed`.
  - The argv had `--json` at index 7 where `--src` was expected.
  - The snapshot held src/'s bytes.
  - The claim row came from the shared config.
  - Semantic assessment: every target ran and failed on its planned assertion. There was no import or collection fault.
- **Task 2 RED (`b3075f8`):** 24 failed, 5 passed. The classifier ran on `build/red/t2.xml` with target `test_unit_file_must_be_the_view_unit[other-unit]` and returned `RED_EVIDENCE_OK` / `target_test_failed`.
  - 8 failures were `DID NOT RAISE AttemptError` (unit file).
  - 13 were `assert 0 == 2`: proposals, legacy proposals, session kinds and readability without a view.
  - The sweep hit was `'wcc386@10.6 -4r -ot -s -fpi'` instead of None, because the shared cflags were read.
  - The context pack lacked the view text.
  - The view sweep root was REPO_ROOT instead of the view.
  - The passes are pins: `test_forms_unchanged` and `test_unit_file_relative_to_the_repository_is_accepted`, which Task 1's resolving read already satisfied.

## Verification

- `uv run pytest -q tests/test_attempt_wrapper.py`: 108 passed.
- `uv run pytest -q tests/test_attempt_wrapper.py tests/test_check.py`: 221 passed.
- `uv run pytest -q` (host, worktree): **2894 passed, 232 skipped**. Every skip is a pre-existing platform or owner-file skip (orig/, Watcom, watcom-media, objdiff/ninja/clang/Ghidra "run in the container", symlink privileges, POSIX-only). This plan adds no test that skips and no new skip reason.
- `uv run ruff check .`: All checks passed.
- Acceptance: attempt.py imports `UNIT_FILE_ENV` from hooks and `Claim.view_root` exists. tests/test_attempt_wrapper.py contains `test_unit_file_must_be_the_view_unit`.
- **Container step deferred to the orchestrator:** `docker compose build && docker compose run --rm test`.

## Files Created/Modified

- `tools/reverseapoc/attempt.py`:
  - view constants: `VIEW_DIR`, `VIEW_SRC`, `VIEW_CONFIG`, `VIEW_BUILD`, `VIEW_CFLAGS`, `VIEW_LOG`, `PROPOSALS_FILE`;
  - new `Claim` fields and `view_root`;
  - new functions `_names`, `_unit_file`, `_proposals`, `_kind`, `config_root`, `unit_path`, `src_root`, `_view_argv`;
  - `container_check_argv(..., roots)`;
  - `_default_spec`, `_locked_check`, `cmd_check` and `cmd_context` now read the view in view mode.
- `tools/reverseapoc/check.py`: `sweep` puts `src_root` in its `CompileOptions`, and `_compile_cell` uses `dataclasses.replace(o, cflags=rule)`.
- `tests/test_attempt_wrapper.py`: the `view` fixture and 12 new test functions (with their parametrized cases).
- `tests/test_check.py`: `test_sweep_compiles_a_view_against_the_views_include`.

## Decisions Made

See `key-decisions` in the frontmatter. Each one is fail-closed or consistency-driven, and none changes the view layout or the env names.

## Deviations from Plan

**1. Orchestrator note for 07-11 (07-03 as built): a view sweep compiles against the view's include/.**
- The rulings say sweep cells must compile against the view's `include/` (pass the view's src root), not `src_root=None`.
- **Fix:** `check.sweep` passes `src_root=Path(src_root)` in its `CompileOptions`, so `_compile_root_for` returns the view directory only for a D-24 view. Every other tree still compiles from REPO_ROOT, as before.
- **Files:** `tools/reverseapoc/check.py` and `tests/test_check.py`. Neither is in the plan's `files_modified`; the ruling directed the change.
- **Commits:** `b3075f8` (test), `4dfc7f0` (feat).
- The other parts of the note already hold. A view is checked with `--build <view>/build`. `default_runner` runs with `cwd=ROOTS.repo` (the repository root), and the container argv paths are repo-relative.

**2. [Rule 2 - Missing critical] Readability sessions need a view.**
- **Found during:** Task 2.
- **Issue:** The plan lists the accepted kinds but does not say what happens to a readability session without a unit file. 07-04's hook denies that session every write.
- **Fix:** `_kind` refuses any non-matching kind when `REVERSEAPOC_UNIT_FILE` is unset. Test: `test_a_readability_session_needs_a_view`.
- **Commit:** `4dfc7f0`.

**3. [Rule 2 - Missing critical] Exact spelling below the attempt dir.**
- **Issue:** On a case-folding host, `Path.resolve()` returns the on-disk case, so `_notes`'s resolved comparison alone would accept `view/SRC/...`.
- **Fix:** `_names` also compares the written (normalised, unresolved) parts below the attempt dir. It does not compare the whole path, so a short-name or drive-letter spelling of the repository prefix still passes. The hooks' shapes are exact only in that tail.
- **Commit:** `4dfc7f0`.

**4. [Plan clarification] Proposals required in view mode, optional in legacy mode.**
- **Issue:** The plan says "must be `<attempt dir>/proposals.jsonl`" without saying when the variable may be absent.
- **Decision:** A view session must set it. A legacy session may omit it, but if it is set it is validated.

**5. [Plan clarification] The claim row is read from the view config in view mode.**
- `cmd_check` validates the claim against the same `functions.csv` the container check will read (`--config <view>/config`).
- Test: `test_view_mode_claim_row_comes_from_the_view_config`.

**6. [Test fix during GREEN] The context test observes the unit-text root.**
- **Issue:** The RED version also asserted that the text of another (unclaimed) view unit appears in the pack. The pack holds only matched neighbours' definition heads, never a whole other unit, so that assertion could never hold.
- **Fix:** In GREEN, that assertion became a spy on `attempt._unit_texts` asserting that it reads the view's `src/`. The claimed unit's view text is still asserted in the printed pack.
- **Commit:** `4dfc7f0`.

---

**Total deviations:** 1 orchestrator note applied (view sweep root), 2 Rule-2 additions, 2 clarifications, 1 test fix.
**Impact on plan:** every must-have truth holds as written. The extra file (check.py) is the one the orchestrator's note for this plan requires.

## Issues Encountered

- `check.sweep`'s `watcom_tree` test helper creates directories without `exist_ok`. The new sweep test therefore reuses the tree that `run_sweep` wrote instead of calling the helper twice.

## User Setup Required

None.

## Next Phase Readiness

- 07-13 can now create views at `build/driver/<run>/<exe>/<func>/attempt-<n>/view/` (with `src/`, `include/`, `config/` and `build/`) and set `REVERSEAPOC_UNIT_FILE`, `REVERSEAPOC_PROPOSALS` and, for readability, `REVERSEAPOC_SESSION_KIND`.
- The wrapper refuses, with exit 2, any other shape, and any view session that lacks the proposals path.
- 07-13 still has to measure a view check's wall time against `CHECK_TIMEOUT = 580` s (flagged assumption).

Execution context nonce: c57f5f5d16affe2a

## Self-Check: PASSED

- FOUND: tools/reverseapoc/attempt.py, tools/reverseapoc/check.py, tests/test_attempt_wrapper.py, tests/test_check.py
- FOUND commits: 15ee9a2, 9ebcf04, b3075f8, 4dfc7f0 (`git rev-list --count 2815ddb..HEAD` = 4 before this SUMMARY commit)
- No STATE.md or ROADMAP.md change.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
