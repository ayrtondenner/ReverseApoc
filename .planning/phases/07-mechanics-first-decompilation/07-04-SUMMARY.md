---
phase: 07-mechanics-first-decompilation
plan: 04
subsystem: hooks
tags: [hooks, guardrails, claude-code, pretooluse, views, cflags, naming-state]

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: the two-layer PreToolUse hook (always + matching), matching_write_allowed, the notes exemption
provides:
  - "UNIT_FILE_ENV / PROPOSALS_ENV / SESSION_KIND_ENV / SESSION_KINDS constants, read by 07-11, 07-13, 07-35, 07-36"
  - "view mode: a session writes only its build/driver/.../view/src/<exe>/<unit>.c, notes.md and proposals.jsonl"
  - "inline-asm, pragma and #include scans on the view unit in both layers"
  - "config/cflags.txt and config/cflags-proposals.toml protected for every session (D-12, D-27 P3)"
  - "D-19 deny reason for config/<exe>/symbols.csv and include/ in view mode"
  - "readability session kind sharing the view-mode allowlist; unknown kinds denied"
affects: [07-11, 07-13, 07-35, 07-36, driver audit]

actuals:
  tokens: 7300
  tasks: 3
  commits: 6
plan_head_before: 0f9de364337258572e5dcddb10a133cd2c95c821
plan_head_after: b82c1915880fb0e5a2c5b25051df5912b3281122

tech-stack:
  added: []
  patterns:
    - "per-session driver paths come from the claude process env and are exempt from build/ only at their exact shape (every repo-relative form under build/ must fit)"
    - "an env path that is set but unusable never falls back to a looser allowlist"

key-files:
  created: []
  modified:
    - tools/reverseapoc/hooks.py
    - tests/test_hooks.py

key-decisions:
  - "A set-but-unusable REVERSEAPOC_UNIT_FILE denies every write rather than falling back to the legacy Phase 6 allowlist (fail closed)"
  - "A readability session without REVERSEAPOC_UNIT_FILE is denied every write: the legacy allowlist would let it create include/ headers, which are D-19 naming state"
  - "Only an absent REVERSEAPOC_SESSION_KIND means a legacy matching run; an empty string, a case variant or trailing space is an unknown kind and denies writes"
  - "The proposals exemption needs no claim (proposals.jsonl under build/driver/); the unit file exemption needs the claim's exe and unit"
  - "In legacy mode REVERSEAPOC_PROPOSALS is ignored by the matching allowlist (Phase 6 behaviour kept until 07-13)"

patterns-established:
  - "_session_relative(env, payload, root, name) replaces _notes_relative for every driver env path"

requirements-completed: [DEC-02, DEC-03]

coverage:
  - id: D1
    description: "View-mode sessions write only their private view unit, notes.md and proposals.jsonl; the view unit is scanned for inline asm, pragmas and path includes"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_hooks.py#test_view_unit_is_writable, test_view_mode_denies_src_and_others, test_view_unit_is_scanned, test_proposals_file_is_writable, test_view_unit_include_rule"
        status: pass
    human_judgment: false
  - id: D2
    description: "config/cflags.txt and config/cflags-proposals.toml are denied to every edit tool in every session, with a reason naming D-12 and the owner's reverseapoc flags verbs"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_hooks.py#test_always_layer_protects_cflags, test_always_layer_protects_the_proposal_queue, test_always_allows_near_miss_paths"
        status: pass
    human_judgment: false
  - id: D3
    description: "View mode denies config/<exe>/symbols.csv and include/ with a D-19 reason; legacy mode unchanged"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_hooks.py#test_view_mode_denies_symbols_csv_with_d19_reason, test_view_mode_denies_headers_with_d19_reason, test_legacy_mode_unchanged"
        status: pass
    human_judgment: false
  - id: D4
    description: "Readability kind shares the view allowlist; unknown kinds deny writes; env path exemptions hold only at the exact shape and claimed unit"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_hooks.py#test_readability_kind_same_allowlist, test_unknown_kind_denies_writes, test_unit_file_for_another_unit_is_not_exempt, test_unit_file_outside_build_driver_is_not_exempt, test_session_paths_need_every_build_form_to_fit"
        status: pass
    human_judgment: false
  - id: D5
    description: "Host suite and ruff green; the container run is deferred to the orchestrator (R-B)"
    verification:
      - kind: other
        ref: "uv run pytest -q (2722 passed, 229 skipped) && uv run ruff check ."
        status: pass
    human_judgment: true
    rationale: "The container run (docker compose run --rm test) is not allowed in a worktree; the orchestrator runs it after merge"

duration: 15min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 04: Hooks for views, cflags and naming state Summary

**Per-session view mode for the PreToolUse hooks: a session may write only its private `build/driver/.../view/src/<exe>/<unit>.c`, its notes.md and proposals.jsonl, and the asm, pragma and include scans run on that view unit. Both cflags files are now owner-only in every session. symbols.csv and include/ are denied with a D-19 reason. The readability kind shares the allowlist, and an unknown session kind is denied every write.**

## Performance

- **Duration:** about 15 min
- **Started:** 2026-10-27T14:50:44Z
- **Completed:** 2026-10-27T15:05:39Z
- **Tasks:** 3 (all TDD: RED commit, then GREEN commit)
- **Files modified:** 2

## Accomplishments

- The always layer exempts `REVERSEAPOC_UNIT_FILE` from build/ only at `build/driver/.../view/src/<exe>/<unit>.c` and only for the claimed exe and unit. It exempts `REVERSEAPOC_PROPOSALS` only as `proposals.jsonl` under build/driver/. The view unit is scanned like src/ (T-07-11, T-07-12).
- `matching_write_allowed(rel, *, claim, notes, tracked, unit_file=None, proposals=None)` is still the one predicate shared with the driver's audit. View mode allows the unit file, notes and proposals and nothing else. Legacy mode behaves exactly as in Phase 6.
- `config/cflags.txt` and `config/cflags-proposals.toml` are in `_PROTECTED_FILES`. The deny reason names D-12, Phase 5 D-18 and `reverseapoc flags approve` / `flags default`, which write from Python (T-07-10). No exemption was added.
- In view mode, symbols.csv and include/ are denied with "the driver is the only writer of shared naming state (D-19); write a proposal to proposals.jsonl instead". Every other refused path gets the D-24 reason.
- `REVERSEAPOC_SESSION_KIND`: when absent, the session is a legacy matching run. `readability` gets the view allowlist. Any other value is denied every write, and the reason lists SESSION_KINDS.

## Task Commits

1. **Task 1: tracer, view-mode sessions.** RED `8522065` (test), GREEN `49834ed` (feat). The tracer gate ran in interactive end-of-phase mode with an automated-only verify: I re-ran `uv run pytest -q tests/test_hooks.py` (272 passed) before Task 2 started.
2. **Task 2: owner-only cflags files and D-19 denies.** RED `1e3bee3` (test), GREEN `2ccd926` (feat).
3. **Task 3: readability kind and shape checks.** RED `80de2ea` (test), GREEN `b82c191` (feat).

## TDD evidence (RED)

GSD's `check tdd-red-evidence` classifier has no pytest adapter (it supports TAP, JUnit XML, swift-testing, unittest and go test). The RED evidence below is the real pytest result, and I checked each failure by hand to confirm it failed for the planned reason.

- **Task 1 RED (`8522065`):** `uv run pytest -q tests/test_hooks.py -k "view_unit or view_mode or proposals_file"` gave 4 failed. Each one failed on its planned assertion:
  - the view unit and proposals.jsonl were denied as `build/ is protected`;
  - the asm edit was denied with the build/ reason instead of the asm rule;
  - in view mode, src/ufo2p/u_000a34f0.c was still allowed.
  None of the failures was an import, collection or fixture error.
- **Task 2 RED (`1e3bee3`):** the plan's `-k "cflags or proposal_queue or d19 or legacy"` gave 7 failed and 4 passed.
  - Failures: both cflags files were allowed (the Write payload was not denied), and the five D-19 cases got the D-24 reason.
  - The 4 passes are pins, not RED targets: `test_legacy_mode_unchanged` holds by design (it pins Phase 6 behaviour), and the F9 near-miss `.bak` cases are allowed both before and after the change.
- **Task 3 RED (`80de2ea`):** 5 failed, 23 passed.
  - Failures: readability without a unit file was still allowed src/ and include/, and all four unknown-kind values were allowed to write.
  - Passes: the shape tests (`another_unit`, `outside_build_driver`, `view_unit_include_rule`) and `test_session_env_names` already passed at RED. Task 1's GREEN had implemented the exact-claim and view-shape checks as its action text required, so these tests pin T-07-12 and T-07-11 rather than drive new code.

## Files Created/Modified

- `tools/reverseapoc/hooks.py`:
  - new constants `UNIT_FILE_ENV`, `PROPOSALS_ENV`, `SESSION_KIND_ENV`, `SESSION_KINDS`, `_PROPOSALS_NAME`, `_VIEW_UNIT`, `_SYMBOLS`;
  - new helpers `_is_proposals`, `_is_view_unit`, `_exempt`, `_env_forms`, `_session_paths`, `_fold`, `_naming_state`, `_view_denial`;
  - `_session_relative` replaces `_notes_relative`;
  - `_protected(rel, *, notes, session)`, `_always`, `matching_write_allowed` and `_matching_write` are extended;
  - the module docstring is updated.
- `tests/test_hooks.py`: 16 new test functions (plus parametrized cases), the `view_env` / `_view_unit` / `_every_edit_tool` / `_owner_only` helpers, and the F9 near-miss list change.

## Decisions Made

See `key-decisions` in the frontmatter. All five are fail-closed choices inside the plan's scope. None of them changes the env names or the view path shape.

## Deviations from Plan

**Orchestrator ruling F9:** `test_always_allows_near_miss_paths` no longer lists `config/cflags.txt`, which is now protected. I added `config/cflags.txt.bak` and `config/cflags-proposals.toml.bak` as near misses. Commit `1e3bee3`.

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] An unusable REVERSEAPOC_UNIT_FILE fell back to the legacy allowlist**
- **Found during:** Task 1
- **Issue:** If `_session_relative` could not place the env unit file, it returned None, which put the session into legacy mode. That would allow `src/<exe>/<unit>.c` and new headers for a session that was meant to be confined to its view.
- **Fix:** `_matching_write` now denies every write when `REVERSEAPOC_UNIT_FILE` is set but unusable.
- **Files modified:** tools/reverseapoc/hooks.py
- **Committed in:** 49834ed

**2. [Rule 2 - Missing critical] Readability without a view unit**
- **Found during:** Task 3
- **Issue:** The plan says readability "uses the view-mode allowlist unchanged" but does not say what happens when the unit file env is missing. Without that env, the session would get the legacy allowlist, which includes new include/ headers (D-19 naming state).
- **Fix:** A readability session without `REVERSEAPOC_UNIT_FILE` is denied every write, and the reason names the env variable. Covered by `test_readability_kind_same_allowlist`.
- **Committed in:** 80de2ea (test), b82c191 (fix)

**3. [Plan clarification] "Tighten `_session_paths`" made concrete**
- **Found during:** Task 3
- **Issue:** Task 1 already required the shape and the claim, so Task 3's "tighten" had no obvious target left.
- **Fix:** An env path now counts only when every repo-relative form of it under build/ fits the shape, instead of any one form (for example, a nested checkout under build/). `test_session_paths_need_every_build_form_to_fit` covers this. It was written in the GREEN step, not in a separate RED commit. I confirmed it bites by switching `all` back to `any`, seeing it fail, and restoring `all`.
- **Committed in:** b82c191

---

**Total deviations:** 1 orchestrator ruling applied (F9), 2 auto-fixed (Rule 2), 1 clarification.
**Impact on plan:** All three changes tighten behaviour. The env names, the view shape and the `matching_write_allowed` keywords are exactly as planned.

## Issues Encountered

- `ruff format --check` reports pre-existing unformatted lines in tests/test_hooks.py (at old lines 916 and 971). They are out of scope, and the project's gate is `ruff check`, which is green.

## Verification

- `uv run pytest -q tests/test_hooks.py`: 310 passed.
- `uv run pytest -q tests/test_hooks.py -k "cflags or proposal_queue or d19 or legacy"`: 11 passed.
- `uv run pytest -q` (host): 2722 passed, 229 skipped. Every skip is a pre-existing real-file skip (orig/, Watcom or watcom-media are absent from the worktree; one POSIX-only taskkill case). This plan adds no new skip reason.
- `uv run ruff check .`: all checks passed.
- **Container step deferred to the orchestrator:** `docker compose build && docker compose run --rm test`.

## User Setup Required

None.

## Next Phase Readiness

- 07-11 (attempt wrapper) and 07-13 (driver views) can set `REVERSEAPOC_UNIT_FILE`, `REVERSEAPOC_PROPOSALS` and `REVERSEAPOC_SESSION_KIND`, and pass `unit_file=` and `proposals=` to `matching_write_allowed` in the audit. 07-13 removes legacy mode.
- Once this merges to main, every Claude Code session in the repo, the owner's and GSD executors' included, is denied edits of `config/cflags.txt` and `config/cflags-proposals.toml`. That is intended by D-12 and D-27 P3: the owner's `reverseapoc flags approve|default` writes from Python.

## Self-Check: PASSED

- FOUND: tools/reverseapoc/hooks.py, tests/test_hooks.py
- FOUND commits: 8522065, 49834ed, 1e3bee3, 2ccd926, 80de2ea, b82c191 (`git rev-list --count 0f9de36..HEAD` = 6 before this SUMMARY commit)
- Acceptance criteria:
  - `UNIT_FILE_ENV = "REVERSEAPOC_UNIT_FILE"` and `def _session_paths(` are in hooks.py.
  - `matching_write_allowed` has the `unit_file` and `proposals` keywords.
  - `_PROTECTED_FILES` has the keys `config/cflags.txt` and `config/cflags-proposals.toml`.
  - `test_unit_file_for_another_unit_is_not_exempt` and `test_unknown_kind_denies_writes` are in tests/test_hooks.py.

## Fix round 1

**Finding (Important):** the guard in `_matching_write` that denies every write when `REVERSEAPOC_UNIT_FILE` is set but unusable (hooks.py, `if view and unit_rel is None`) had no test. With the guard removed, the suite stayed green, and such a session would have fallen back to the legacy src/ and include/ allowlist.

**Tests added (commit `777fb76`, tests only, no production change):**
- `test_unusable_unit_file_denies_every_write[outside|home|nul|symlink-inside|symlink-outside]`. For each unusable env value, a write to the legacy src/ unit, a new include/fx.h or notes.md is denied, and the reason names `REVERSEAPOC_UNIT_FILE`. The view unit and proposals.jsonl are denied too. The symlink cases skip on this host with the R-A reason "symlink creation needs privileges on this host"; they run in the container.
- `test_unit_file_with_two_forms_denies_every_write`. This covers the symlink branch on this host. A patched `os.path.realpath` maps an alias in the checkout to the view unit, so the env path has two forms and does not name a single path. Every write is denied.
- `test_wrong_shape_unit_file_keeps_the_view_allowlist`. A unit file under build/ with the wrong shape can be placed, so the guard does not handle it. The session stays in view mode and never gets the legacy allowlist: src/, include/, the wrong-shape file and the real view path are all denied. notes.md stays writable, as the view allowlist intends.

**Revert proof:** I temporarily deleted the guard's three lines and ran `uv run pytest -q tests/test_hooks.py -k "unusable_unit_file or wrong_shape_unit_file or two_forms"`. Result: 4 failed, 1 passed, 2 skipped. The four failures were `[outside]`, `[home]`, `[nul]` and `two_forms`, and each one failed on the legacy write to `src/ufo2p/u_000a34f0.c` being allowed. The test that passed is the wrong-shape test, which does not depend on the guard (view mode itself denies). The 2 skips are the symlink cases on this host. I then restored the guard, and `git diff tools/reverseapoc/hooks.py` was empty.

**Verification:**
- `uv run pytest -q tests/test_hooks.py`: 315 passed, 2 skipped (the skips are the two symlink cases).
- `uv run ruff check .`: all checks passed.

Execution context nonce: c0d63afacb6537f7

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
