---
phase: 07-mechanics-first-decompilation
plan: 03
subsystem: tooling
tags: [cflags, check, gate, provenance, d-27, views]

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "check/gate/compiler pipeline with provenance stamps, gate --partial, object_root"
provides:
  - "compiler.source_rule / compile_source take rule_path (cflags rule by the logical src/<exe>/<unit>.c)"
  - "check.unit_rule_path and check._compile_root_for (view root = src parent holding include/)"
  - "check._compile(..., rule_path, root); check_source(rule_path=); check_provenance(rule_path=)"
  - "gate._committed_options: gate EXE/UNIT and --partial refuse uncommitted --cflags/--watcom-manifest/--watcom-dir"
  - "tests/test_check_real.py::test_view_unit_compiles_under_its_logical_rule (K4, container evidence in 07-29)"
affects: [07-11, 07-13, 07-17, 07-24, 07-29]

actuals:
  tokens: 8200
  tasks: 3
  commits: 5
plan_head_before: 0f9de364337258572e5dcddb10a133cd2c95c821
plan_head_after: a957fcb806b1f651587dd91e3399e9f3af07d7dd

tech-stack:
  added: []
  patterns:
    - "A unit compiled from anywhere passes rule_path=unit_rule_path(stem, unit) and root=_compile_root_for(src_root)"
    - "Write-mode gate paths call _committed_options first; gate --all stays the dry run"

key-files:
  created: []
  modified:
    - tools/reverseapoc/compiler.py
    - tools/reverseapoc/check.py
    - tools/reverseapoc/gate.py
    - tests/test_compiler.py
    - tests/test_check.py
    - tests/test_gate.py
    - tests/test_check_real.py

key-decisions:
  - "_compile_root_for (after fix round 1): only a D-24 view, <repo>/build/driver/.../view/src with include/ beside it, compiles from its view root; every other tree, outside the repository included, from REPO_ROOT"
  - "gate --partial refuses a saved file outside the repository or whose compile root would not be REPO_ROOT"
  - "input_provenance gets no rule_path keyword: it receives the already-selected rule; selection lives in source_rule, which compile_source and check_provenance both call with rule_path"
  - "check_source takes rule_path (default unit_rule_path for a unit file); the cmain386 runtime pair (unit_file=False) keeps its own path's rule"
  - "sweep cells unchanged: one-rule `*` file, no rule_path, REPO_ROOT"

patterns-established:
  - "Logical rule path: src/<exe>/<unit>.c names the cflags rule wherever the file sits"

requirements-completed: [DEC-03, DEC-02]

coverage:
  - id: D1
    description: "cflags rule selected by the logical path src/<exe>/<unit>.c (compiler.source_rule, compile_source)"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_compiler.py#test_source_rule_by_logical_path"
        status: pass
      - kind: unit
        ref: "tests/test_compiler.py#test_compile_source_by_logical_path"
        status: pass
    human_judgment: false
  - id: D2
    description: "check compiles every unit of a view under its own rule with the view as compile root; the committed tree from REPO_ROOT"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_check_compiles_a_view_unit_under_its_rule"
        status: pass
      - kind: unit
        ref: "tests/test_check.py#test_default_tree_compile_passes_repo_root"
        status: pass
      - kind: unit
        ref: "tests/test_check.py#test_compile_root_for_each_kind_of_tree"
        status: pass
      - kind: unit
        ref: "tests/test_check.py#test_committed_src_compiles_from_the_repository"
        status: pass
    human_judgment: false
  - id: D3
    description: "check_provenance selects rule and root as the compile did; a stamp from another rule is stale"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_provenance_agrees_with_the_compile_rule"
        status: pass
    human_judgment: false
  - id: D4
    description: "gate EXE/UNIT and gate --partial refuse uncommitted compile options (exit 2, tables and feed byte-identical); gate --all --cflags still runs and writes nothing"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_gate.py#test_gate_unit_refuses_other_compile_options"
        status: pass
      - kind: unit
        ref: "tests/test_gate.py#test_gate_cli_refuses_other_compile_options"
        status: pass
      - kind: unit
        ref: "tests/test_gate.py#test_gate_partial_refuses_other_compile_options"
        status: pass
      - kind: unit
        ref: "tests/test_gate.py#test_gate_all_accepts_other_cflags"
        status: pass
      - kind: unit
        ref: "tests/test_gate.py#test_gate_cli_with_the_committed_options_spelled_out_still_writes"
        status: pass
    human_judgment: false
  - id: D5
    description: "gate --partial scores the saved file under src/<exe>/<unit>.c's rule"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_gate.py#test_gate_partial_uses_the_unit_rule"
        status: pass
    human_judgment: false
  - id: D6
    description: "Real view compile under the unit's rule (K4): wibo/container run of test_view_unit_compiles_under_its_logical_rule"
    verification:
      - kind: integration
        ref: "tests/test_check_real.py#test_view_unit_compiles_under_its_logical_rule"
        status: unknown
    human_judgment: true
    rationale: "Skips on the host (objdiff-cli absent); its container run is plan 07-29's evidence step. A native host compile of a view copy (ad-hoc, not committed) succeeded under the unit rule."

duration: 37min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 03: D-27 rule-by-logical-path and committed-options gate Summary

**Every unit is compiled under the cflags rule of its logical path src/<exe>/<unit>.c, with a D-24 view compiling from its own root and the land step's provenance check choosing rule and root the same way, and gate's write modes refuse any --cflags/--watcom-manifest/--watcom-dir other than the committed ones.**

## Performance

- **Duration:** about 37 min
- **Started:** 2026-10-27T14:40Z (approx.)
- **Completed:** 2026-10-27T15:17Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- `compiler.source_rule` and `compile_source` take `rule_path`. With `rule_path=None` the behaviour is exactly as before.
- `check.unit_rule_path(stem, unit)` and `check._compile_root_for(src_root)`. `_compile` passes `rule_path` and `root` to `compile_fn`. `check_source` (the claimed unit), `_land_exe` (every unit the land step compiles) and `check_provenance` (ninja's land step) all select the rule and the root the same way. `_compile_root` was replaced by `_compile_root_for`.
- `gate._committed_options(roots)` runs first in `gate_units` and `gate_partial`. Its message names the offending flag and points to `gate --all`, the dry run. `gate_all` is unchanged.
- `gate_partial` passes `rule_path=unit_rule_path(stem, unit)` to `check_source`.
- Real test `test_view_unit_compiles_under_its_logical_rule` (K4). It builds a view under `build/test-view/<hex>/view`, adds a temporary rule with `-ot` for `src/ufo2p/u_000a34f0.c`, and asserts that the stamp records `-ot`, that the object is under the view's `build/check-custom/`, and that the other units keep their committed rule.

## Task Commits

1. **Task 1 (tracer, TDD): rule by logical path through check_unit**: RED `fb154a4` (test), GREEN `8cf9bc3` (feat)
2. **Task 2 (TDD): gate refuses uncommitted options; --partial scores under the unit rule**: RED `783eceb` (test), GREEN `efb1f9b` (feat)
3. **Task 3: real view compile test (K4) and the full host suite**: `a957fcb` (test)

No REFACTOR commits were needed.

## TDD evidence

- **Task 1 RED:** 7 new tests failed for the missing behaviour: `TypeError` because `source_rule`/`compile_source` did not take `rule_path`, the fake compiler saw `rule_path`/`root` as `None`, `_compile_root_for` was missing, and provenance was stale with "the flags changed" because the copy was checked under `*`. Classifier on `test_provenance_agrees_with_the_compile_rule` (pytest JUnit XML): `RED_EVIDENCE_OK` / `target_test_failed`. Semantic assessment: the target ran and failed on its planned assertion (provenance chose `*` by physical path). This was not a setup or import fault.
- **Task 2 RED:** 10 new tests failed. The unpatched gate wrote rows and exited 0 instead of refusing (`DID NOT RAISE CheckError`, CLI `0 == 2`), and `rule_path` was `None` for `--partial`. Classifier on `test_gate_cli_refuses_other_compile_options[cflags]` and `test_gate_partial_uses_the_unit_rule`: both `RED_EVIDENCE_OK` / `target_test_failed`. Semantic assessment: real behavioural failures. A first RED run of the CLI case exited 1 for the wrong reason (the fixture's matched row had no unit file, so the cross-check failed). I fixed the fixture so the unpatched gate really writes, and only then committed RED. Two pinning tests pass both before and after by design: `gate --all --cflags` stays the dry run, and the committed paths spelled out still write.
- **GREEN:** `uv run pytest -q tests/test_compiler.py tests/test_check.py` gave 176 passed. `uv run pytest -q tests/test_gate.py tests/test_cli.py` gave 191 passed.
- Tracer feedback gate (interactive, end-of-phase, automated-only verify): I re-ran Task 1's verify after GREEN. It passed, then I continued to Task 2.

## Verification (done gate)

- `uv run pytest -q` in the worktree: **2699 passed, 230 skipped**. All skips are platform or owner-file skips, because the worktree has no `orig/` or `third_party/`.
- `REVERSEAPOC_ORIG=<main>/orig REVERSEAPOC_WATCOM_DIR=<main>/third_party/watcom uv run pytest -q`: **2878 passed, 51 skipped**.
- The only new skip is from this plan's real test: `objdiff-cli is not on PATH (run in the container)`, which R-A/F40 allow. It skips in the fixture, before anything is copied.
- `uv run ruff check .`: All checks passed.
- `uv run pytest -q tests/test_check_real.py -k view_unit`: 1 skipped (objdiff-cli, host).
- Acceptance greps: `def source_rule(` has `rule_path`; `def _compile_root_for(` is present; `def _committed_options(` is present and called in `gate_units` (L580) and `gate_partial` (L800).
- Extra host evidence for K4, from an ad-hoc script in the scratchpad (not committed, view removed after). A native Windows `compile_source` of a view copy, with root = the view and `rule_path=src/ufo2p/u_000a34f0.c`, compiled OK under `-4r -s -fpi -ot`, with stamp flags matching. `-i=` was `include;..\..\..\..\..\..\..\third_party\watcom\10.6\H`. The other unit, u_00089980, compiled under `*`. The wibo/container run is still 07-29's evidence.

## Container steps deferred to the orchestrator

- container step deferred to the orchestrator: `docker compose run --rm test` (full container suite incl. `tests/test_check_real.py::test_view_unit_compiles_under_its_logical_rule`). Per the plan this test's container run is plan 07-29's evidence step (main checkout).

## Files Created/Modified

- `tools/reverseapoc/compiler.py`: `rule_path` on `source_rule` and `compile_source`.
- `tools/reverseapoc/check.py`: `unit_rule_path`, `_compile_root_for` (replaces `_compile_root`), `_compile(..., rule_path, root)`, `check_source(rule_path=)`, land step and `check_provenance` select by logical path.
- `tools/reverseapoc/gate.py`: `COMMITTED_OPTIONS`, `_committed_options`, `gate_partial` passes `rule_path`.
- `tests/test_compiler.py`, `tests/test_check.py`, `tests/test_gate.py`: the TDD tests listed under coverage.
- `tests/test_check_real.py`: `test_view_unit_compiles_under_its_logical_rule` and its `view` fixture.

## Decisions Made

- **check_source takes `rule_path`.** Its default for a unit file is `unit_rule_path(exe.stem, unit)`, so `gate --partial` threads it explicitly and a fake `check_source` can observe it. The cmain386 runtime pair (`unit_file=False`) keeps the rule of its own path.
- **Sweep is untouched.** It keeps its one-rule `*` file, passes no `rule_path` and uses root REPO_ROOT, as today.

## Deviations from Plan

**1. Orchestrator ruling F40: real-test skips.**
- `test_view_unit_compiles_under_its_logical_rule` skips through `requires_runner()` / `requires_objdiff()` first, inside the `view` fixture and before anything is copied.
- The later orig/Watcom checks only run where objdiff-cli exists, which means the container. Their text ends in "(run in the container)", so no custom skip text reaches G3 or 07-41.

**2. [Plan text vs. code] `input_provenance` gets no `rule_path` keyword.**
- **Found during:** Task 1.
- **Issue:** The must-have truth lists `input_provenance` among the functions taking `rule_path`. But `input_provenance(rule, src, ...)` receives the already-selected `Rule` and never selects one, so the keyword would be dead.
- **Fix:** Selection lives in `source_rule`. `compile_source` and `check_provenance` both call it with `rule_path`, so the stamp and the land-step check use the same rule. `test_provenance_agrees_with_the_compile_rule` and `test_compile_source_by_logical_path` pin this.
- **Files modified:** none beyond the plan's files.

**3. [Rule 1 - test fixture] Task 2 RED fixture corrected before the RED commit.**
- The first version of `published()` seeded a matched row without its unit file. That made the unpatched CLI gate exit 1 (cross-check), not 0, which was the wrong RED reason.
- `published()` now writes that unit file, so a passing check really writes, and the refusal is what the test measures.

**4. [Plan text vs. code, found in review, fixed in fix round 1] The compile root of trees that are not views.**
- **Found during:** the orchestrator's task review (Important finding 1). My first version wrongly listed this under Decisions.
- **Issue:** As first committed (`8cf9bc3`), `_compile_root_for` compiled any tree outside the repository from its parent. It also compiled any in-repo `<x>/src` with `<x>/include` beside it from `<x>`. The plan says REPO_ROOT for every tree that is not a D-24 view. Two consequences:
  - `gate --partial` (`src_root=saved.parent`) could score a saved file outside the repo against the grandparent's `include/` and write that score to the public status.csv. Before 07-03, the compile refused that file.
  - An in-repo `<x>/src` beside an `<x>/include` that is not a view compiled against non-committed headers.
- **Fix (orchestrator ruling, fix round 1):**
  - Only `<repo>/build/driver/.../view/src` with `include/` beside it compiles from its view root. Every other tree, including any outside the repository, compiles from REPO_ROOT.
  - I did not keep the "parent" behaviour for the read-only `check` path. The `cc` edge always compiles from REPO_ROOT, so the only users of "parent" were tests. The `env`/`tree` test fixtures now stand their tmp root in for REPO_ROOT instead.
  - In addition, `gate --partial` refuses a saved file outside the repository, or one whose compile root would not be REPO_ROOT, because its rows go to status.csv.
- **Real test:** the K4 view moved from `build/test-view/` to `build/driver/test-view/<hex>/view`, so it really is a view. It now also asserts the view-relative `-fo=` guest path in the compile log.
- **Commits:** RED `0d269b8`, fix `a0ac57e`.

---

**Total deviations:** 1 orchestrator ruling applied (F40), 2 plan-text deviations (`input_provenance`; the compile root, corrected in fix round 1), 1 test-fixture fix before RED.

**Impact:** As first returned, the claim that every plan truth held except `input_provenance` was wrong. The compile root truth ("any other tree with the repository root") did not hold until fix round 1. It holds now. The only remaining gap is the inert `input_provenance` keyword. The behaviour that truth exists for (the stamp and the land check agree on the rule) is tested.

## Issues Encountered

- **A view must be checked with `--build` inside the view.** Because a view now compiles from its own root, `compile_rule`'s existing rule that the object lies inside the root means the build dir has to be in the view. D-24's wrapper already runs `check --src/--config/--build/--log` against the view, and the real test does the same. 07-11 must keep it that way. A view checked with the repository's `build/` would now be refused with "outside <view>".

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- 07-11 (D-24 views), 07-17 (flag re-gates on `build/flags/<id>/src`), 07-24 (approve gates under the committed cflags) and 07-29 (container run of the K4 test) can build on `rule_path`, `_compile_root_for` and `_committed_options`.

## Fix round 1

The orchestrator's review raised Important finding 1: `_compile_root_for` compiled trees that are not views from their parent. The ruling was to follow the plan text, so only a `build/driver/.../view/src` view compiles from its own root. See Deviation 4.

**What changed:**
- `check.VIEW_PARTS` and `VIEW_DIR` define where views live.
- `check._is_view(src)` holds only for `<repo>/build/driver/.../view/src` with `include/` beside it.
- `_compile_root_for` returns the view directory for a view and REPO_ROOT for everything else.
- `gate._saved_file` refuses a saved file outside the repository ("must be inside the repository") and one whose compile root would not be REPO_ROOT ("would compile from the compile root ...").
- The test fixtures `env` (test_check.py) and `as_committed` (test_gate.py) stand their tmp root in for `check.REPO_ROOT`, loading configure.py first.
- The real K4 view moved to `build/driver/test-view/<hex>/view` and asserts the view-relative `-fo=` guest path in `cc.log`.

**New tests (RED `0d269b8`, 7 failed for the intended reason, either the parent returned instead of REPO_ROOT or `DID NOT RAISE CheckError`; fix `a0ac57e`):**
- `tests/test_check.py::test_a_tree_outside_the_repository_compiles_from_the_repository`
- `tests/test_check.py::test_an_in_repo_src_with_include_that_is_no_view_compiles_from_the_repository[flags-copy|elsewhere|driver-not-view|view-outside-driver]`
- `tests/test_gate.py::test_partial_refuses_a_saved_file_outside_the_repository`
- `tests/test_gate.py::test_partial_refuses_a_saved_file_compiled_from_a_view_root`
- `tests/test_check.py::test_compile_root_for_each_kind_of_tree`, updated: its outside-repo assertion moved to the new test.

**Commands and output:**
- `uv run pytest -q tests/test_check.py tests/test_gate.py tests/test_compiler.py`: 275 passed.
- `uv run pytest -q` (worktree): 2706 passed, 230 skipped.
- The same with `REVERSEAPOC_ORIG` and `REVERSEAPOC_WATCOM_DIR` pointing at the main checkout: 2885 passed, 51 skipped. The new real test skips with `objdiff-cli is not on PATH (run in the container)`, which F40 allows.
- `uv run ruff check .`: All checks passed.

The container step is still deferred to the orchestrator: `docker compose run --rm test`, which covers the K4 real test (plan 07-29).

Execution context nonce: 4808b1bf97b2f35b

## Self-Check: PASSED

- FOUND: tools/reverseapoc/compiler.py, tools/reverseapoc/check.py, tools/reverseapoc/gate.py, tests/test_compiler.py, tests/test_check.py, tests/test_gate.py, tests/test_check_real.py
- FOUND commits: fb154a4, 8cf9bc3, 783eceb, efb1f9b, a957fcb (all ancestors of HEAD)
- No STATE.md or ROADMAP.md change.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
