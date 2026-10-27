---
phase: 07-mechanics-first-decompilation
plan: 09
subsystem: tooling
tags: [d-29, d-12, d-22, unitdefs, configure, check, drift, renames]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-03: check selects the cflags rule by logical path; check._configure loads configure.py by path"
provides:
  - "tools/reverseapoc/unitdefs.py: find (renamed-aware D-12 finder by start), c_name_of, c_names, placeholders, load_configure, MARKER_ANY, DEFINITION_ANY, C_KEYWORDS, UnitDefs"
  - "check.source_marks(text, rows, *, names=None, all_names=None) -> SourceMarks(marked, defined, problems, marked_starts, defined_starts)"
  - "check.exe_c_names(symbols) and account_unit pairing rows with markers/definitions by start (ruling F27 b)"
  - "configure.check_unit_source(text, unit_functions, *, names=None, all_names=None); the unit loop passes symbols.csv C names"
  - "tests/test_drift.py compares status.csv matched starts with defined starts (defined_starts), planted rename case"
affects: [07-14, 07-16, 07-27, 07-34, 07-40]

actuals:
  tokens: 14100
  tasks: 2
  commits: 4
plan_head_before: 2815ddb72530220a0d7d474ae1abe1284dda210f
plan_head_after: 278db5fadbfd52ba2dab4fb65953fcd9622a56a5

tech-stack:
  added: []
  patterns:
    - "Which rows a unit file defines or marks: ask unitdefs.find with C names (unitdefs.c_names of functions.csv + symbols.csv); compare by start, never by functions.csv name"
    - "configure.py is loaded once per process through unitdefs.load_configure (check._configure delegates)"

key-files:
  created:
    - tools/reverseapoc/unitdefs.py
    - tests/test_unitdefs.py
  modified:
    - tools/reverseapoc/check.py
    - configure.py
    - tests/test_drift.py
    - tests/test_check.py
    - tests/test_configure.py
    - tools/reverseapoc/contextpack.py

key-decisions:
  - "A stale placeholder definition of a renamed row is one problem (naming old and new name); the row's 'neither' problem is suppressed for it"
  - "Any marker naming no game/thunk row of the unit (unknown identifier included) is a problem; a definition of an unknown non-placeholder identifier is a helper and ignored; with all_names, another unit's renamed C name is refused"
  - "UnitDefs carries source_problems (file-level problems) besides problems, so check.source_marks no longer filters configure messages by suffix"
  - "check._configure and unitdefs share one configure.py module via unitdefs.load_configure (looks in sys.modules under configure, __main__ and _reverseapoc_configure first)"
  - "configure's private _file_scope_definitions and _function_problem moved into unitdefs; _PLACEHOLDER/_MARKER/_DEFINITION kept for contextpack"

patterns-established:
  - "D-29 finder: unitdefs.find(text, unit_rows, names=c_names, placeholders=placeholders(rows)) is the one answer to 'what does this unit define'"

requirements-completed: [DEC-02, DEC-04]

coverage:
  - id: D1
    description: "unitdefs.find maps definitions and markers to row starts through C names; old-placeholder markers count, stale placeholder definitions, duplicates, defined-and-marked, cross-unit names and non-#if 0 conditionals are problems"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_unitdefs.py (26 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "c_name_of / c_names / placeholders: the one naming rule (func minus trailing _, data minus leading _, func name without _ refused)"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_unitdefs.py#test_c_name_of"
        status: pass
      - kind: unit
        ref: "tests/test_unitdefs.py#test_c_names"
        status: pass
    human_judgment: false
  - id: D3
    description: "check.source_marks returns marked_starts/defined_starts; account_unit reads the unit with the EXE's C names, so a renamed unit checks and lands (ruling F27 b)"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_check_accounts_a_renamed_unit_by_start"
        status: pass
      - kind: unit
        ref: "tests/test_check.py#test_source_marks_with_c_names_finds_a_renamed_function"
        status: pass
    human_judgment: false
  - id: D4
    description: "D-22 drift test by start: committed tables show no drift; a planted rename shows no name drift; deleting the renamed definition is drift naming the start"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_drift.py#test_drift_by_start"
        status: pass
      - kind: unit
        ref: "tests/test_drift.py#test_matched_rows_equal_defined_functions"
        status: pass
    human_judgment: false
  - id: D5
    description: "configure's D-12 check accepts a unit defining a renamed function (symbols.csv read once per EXE), refuses stale placeholder definitions and malformed func names; default behaviour unchanged; markers-only unit passes (DEC-04 edge)"
    requirement: DEC-04
    verification:
      - kind: unit
        ref: "tests/test_configure.py#test_main_accepts_a_unit_defining_a_renamed_function"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_d12_default_names_unchanged"
        status: pass
      - kind: unit
        ref: "tests/test_unitdefs.py#test_markers_only_define_nothing"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 09: The shared renamed-aware unitdefs finder (D-29 points 2 and 3) Summary

**One finder, `unitdefs.find`, reads a unit file through configure's translation phases and maps definitions and INCLUDE_ASM markers of any C identifier to row starts through symbols.csv C names. configure's D-12 check, `check.source_marks` / `account_unit` and the D-22 drift test all use it, so a function renamed in symbols.csv passes configure, check and CI.**

Execution context nonce: a7b91ec209b9020e

## Performance

- **Duration:** about 12 min from the recorded start (context reading before that)
- **Started:** 2026-10-27T16:15:00Z
- **Completed:** 2026-10-27T16:27:02Z
- **Tasks:** 2
- **Files modified:** 8 (2 created, 6 modified)

## Accomplishments

- `tools/reverseapoc/unitdefs.py`:
  - `find(text, unit_rows, *, names, placeholders, all_names=None) -> UnitDefs(defined, marked, problems, source_problems)`, keyed by start.
  - `MARKER_ANY` and `DEFINITION_ANY` match any identifier. `C_KEYWORDS` holds the C89 keywords and Watcom's keywords from `include/watcom_compat.h`.
  - Naming helpers: `c_name_of`, `c_names`, `placeholders`.
  - `load_configure` loads configure.py.
- Rules the finder applies:
  - A definition must use the current C name.
  - A marker may use the current C name or the old placeholder.
  - A stale placeholder definition is a problem, and so are duplicates, a row both defined and marked, and a marker or definition naming another row or no row.
  - Any conditional except `#if 0` fails closed.
- `check.source_marks(..., names=, all_names=)` returns `marked_starts` and `defined_starts`. `account_unit` passes `exe_c_names(symbols)` and pairs rows by start. That is ruling F27 (b).
- `configure.check_unit_source(..., names=None, all_names=None)` delegates to the finder and keeps the existing message wording. The unit loop reads `config/<exe>/symbols.csv` once per EXE (`_exe_names`). A func name without its trailing `_` is refused with a ConfigureError.
- `tests/test_drift.py` compares by start (`defined_starts`, `exe_names`). Messages now name the start. The planted rename is covered.

## Task Commits

1. **Task 1 (tracer, TDD): unitdefs finder; source_marks and the drift test by start.** RED `0168774` (test), GREEN `65d12ec` (feat).
2. **Task 2 (TDD): configure's D-12 check through the finder with symbols.csv C names.** RED `3279635` (test), GREEN `278db5f` (feat).

No REFACTOR commits were needed.

## TDD evidence

- **Task 1 RED (`0168774`):**
  - Target `tests/test_check.py::test_check_accounts_a_renamed_unit_by_start`.
  - It failed on `assert result.ok`. The account reported `func_00010010 ... neither exported nor marked INCLUDE_ASM (expected public Bar_)`, because the pre-D-29 parser does not see the marker `INCLUDE_ASM(Bar);`.
  - JUnit report: `build/red/07-09-t1.xml`, gitignored. Classifier: `RED_EVIDENCE_OK` / `target_test_failed`.
  - Semantic assessment: the target ran and failed on the planned behaviour (a renamed marker is unseen). This was not a setup fault.
  - The other two new check tests failed with `AttributeError` (no `marked_starts`) and `TypeError` (no `names` keyword).
  - `tests/test_unitdefs.py` and `tests/test_drift.py` failed at collection with `ModuleNotFoundError: reverseapoc.unitdefs`. That is a load failure, not RED evidence by itself, which is why the check test was the classified target.
- **Task 2 RED (`3279635`):**
  - Target `tests/test_configure.py::test_main_accepts_a_unit_defining_a_renamed_function`.
  - It failed on `assert 1 == 0`: configure refused the unit because D-12 read `func_00010010` as neither defined nor marked.
  - JUnit report: `build/red/07-09-t2.xml`. Classifier: `RED_EVIDENCE_OK` / `target_test_failed`.
  - Semantic assessment: a real behavioural failure.
  - The `check_unit_source(..., names=)` cases failed with `TypeError` (the keyword was missing). `test_main_refuses_a_stale_placeholder_definition` and the underscore case failed on their assertions.
  - The `runStartedAt` values in both records were typed by hand as approximations, not captured. The report mtimes are real.
- **Tracer feedback gate** (interactive, end-of-phase, automated-only verify): after GREEN I re-ran `uv run pytest -q tests/test_unitdefs.py tests/test_drift.py tests/test_check.py` plus test_configure and test_gate: 397 passed, 3 skipped. Then I expanded to Task 2.

## Verification (done gate)

- `uv run pytest -q` in the worktree: **2903 passed, 232 skipped**. Every skip is a pre-existing platform or owner-file skip (no `orig/` or `third_party/` in the worktree), and this plan adds no new skip.
- With the owner's files (`REVERSEAPOC_ORIG`, `REVERSEAPOC_WATCOM_DIR` pointing at the main checkout), the touched suites (test_check_real, test_gate, test_check, test_configure, test_drift, test_unitdefs, test_contextpack) gave **440 passed, 9 skipped**. All skip reasons are already allowed: objdiff-cli/ninja "(run in the container)", "Windows file names cannot hold", non-UTF-8 byte names, and symlink privileges.
- `uv run ruff check .`: All checks passed.
- `uv run python configure.py --help`: OK.
- `configure.py` run on the committed tree, with output to the scratchpad: 841 units written. The committed src/ passes the D-12 check through the finder, with the committed symbols.csv (`main_`, `stackavail_`) loaded.
- Acceptance greps:
  - unitdefs.py has `def find(` and `def c_name_of(`.
  - test_drift.py has `defined_starts`.
  - configure.py `def check_unit_source(` takes `names`.

## Container steps deferred to the orchestrator

- `docker compose run --rm test` (full container suite). Nothing in this plan is container-only, so this is the standard container run of the done gate.

## Files Created/Modified

- `tools/reverseapoc/unitdefs.py` (new): the finder, the naming rule and the configure loader.
- `tools/reverseapoc/check.py`:
  - `_configure` delegates to `unitdefs.load_configure`.
  - `SourceMarks` gains `marked_starts` and `defined_starts`.
  - `source_marks` takes `names` and `all_names`.
  - New `exe_c_names`.
  - `account_unit` pairs rows by start.
- `configure.py`:
  - `check_unit_source(..., names, all_names)` and `_exe_names`.
  - `_check_source(..., names=)`.
  - `_file_scope_definitions` and `_function_problem` removed; they moved into unitdefs.
- `tools/reverseapoc/contextpack.py`: a docstring reference to the removed `_file_scope_definitions` now points at unitdefs. Docstring only.
- `tests/test_unitdefs.py` (new), `tests/test_drift.py`, `tests/test_check.py`, `tests/test_configure.py`.

## Decisions Made

See key-decisions in the frontmatter. In short:
- A stale placeholder definition gives one problem naming both names, not an extra "neither".
- Markers fail closed on any name that maps to no row of the unit.
- File-level problems are a separate tuple, `UnitDefs.source_problems`, so check needs no suffix matching.
- configure.py is loaded once per process and shared between check and unitdefs.

## Deviations from Plan

**1. Orchestrator ruling F27: drift test hash, and C names in account_unit.**
- (a) `test_drift_by_start`: the planted rename rewrites the unit's C, so the test asserts `name_drift == []`. It then refreshes the planted unit's matched rows' `source_sha256` (what gate would write) and asserts `drift == []`.
- (b) `account_unit` passes `exe_c_names(symbols)` into `source_marks` and pairs rows by `marked_starts` / `defined_starts`. The new check_unit-level test `test_check_accounts_a_renamed_unit_by_start` covers a renamed definition (Foo) plus a marker under the new name (Bar).

**2. [Rule 3 - Blocking] test_configure used configure's private `_file_scope_definitions`.**
- Found during: Task 2.
- Issue: `test_define_continuation_hides_a_definition` called the private helper that moved into unitdefs.
- Fix: the same assertion now runs through `unitdefs.find(...).defined == {}`.
- Committed in: `278db5f`.

**3. [Rule 1 - Consistency] Stale docstring in contextpack.py.**
- `contextpack.py` is outside the plan's files_modified. I changed one docstring line that named the removed helper. No behaviour change.
- Committed in: `278db5f`.

**4. Loader sharing (not in the plan text).**
- The plan says unitdefs loads configure.py by path "the same way" as check.
- To avoid two configure modules whose `_ConditionalError` classes differ, I made `unitdefs.load_configure` the one loader and `check._configure` delegates to it, still cached and still raising CheckError.
- It also recognises configure.py running as `__main__`, so `python configure.py` does not load itself a second time.

**5. Behaviour change (intended, fail closed): markers.**
- An `INCLUDE_ASM(x);` whose identifier maps to no game or thunk row of the unit is now a problem. Before, a non-placeholder name was silently ignored because the old regex only saw `func_` names.
- No committed unit is affected: configure on the committed tree passes.

**6. Behaviour change: messages.**
- configure reports a conditional problem together with any #include problems. Before, it returned only the conditional.
- Drift messages now name the start (`<name> at 0x...`).

**Total deviations:** 1 orchestrator ruling applied (F27 a and b), 2 auto-fixed (1 blocking, 1 consistency), and 3 documented design choices.
**Impact:** no scope creep. Every change serves D-29 points 2 and 3.

## Flagged assumptions (from the plan, unchanged)

- `contextpack.definitions` still finds only placeholder definitions, through configure's `_DEFINITION`. A renamed caller's C head is therefore missing from later matching packs. This is recorded for Milestone 2. Matching nights (07-39) run before readability nights (07-40).
- `gate._reverted` still compares `row.name` with `source_marks(...).marked`, using placeholder names by default. Plan 07-16 owns that change, together with `SymbolTable.c_name`.

## Threat Flags

None. The finder reads only unit files; nothing new crosses a trust boundary. T-07-25 is mitigated by the stale, duplicate and cross-unit problems and the fail-closed conditionals. T-07-26 is mitigated by the comparison by start plus the planted rename and deletion cases.

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None.

## Next Phase Readiness

- 07-16 can build `SymbolTable.c_name` and `gate._reverted` on `unitdefs.c_name_of` and `source_marks(...).marked_starts`.
- 07-27 (readlint) and 07-34 (the rename step) can call `unitdefs.find` with `unitdefs.c_names(...)`.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*

## Self-Check: PASSED

## Fix round 1

**Finding (Important, from the review).** `find` merged `{**all_names, **names}`, so for the unit's own rows the later map won. With the default `names` (the placeholders) and `all_names` set to the EXE's c_names, a renamed row was read under its old placeholder. The result: the stale placeholder definition was accepted, and the correct `Foo` definition was refused as "neither".

**Orchestrator ruling, applied.** The API should be impossible to misuse.
- A row of the unit takes its C name from `names` when the caller passes it. Otherwise it takes it from `all_names`, which holds the EXE's current C names and is authoritative. Only when neither map is given does the placeholder apply.
- `all_names` alone decides which starts lie outside the unit. Entries of `names` for other starts are ignored.

**Changes.**
- `unitdefs.find`:
  - `names` is now optional (`placeholders` is required, then `names=None, all_names=None`).
  - `_Names.of` looks a row up in `names`, then `all_names`, then falls back to its placeholder. `other` is built from `placeholders` and `all_names` only.
  - A map that gives one row of the unit two C names is refused with UnitDefsError. This is a new defensive guard; `test_two_c_names_for_one_row_are_refused` covers it and was added with the fix as a characterization test.
- `configure.check_unit_source` and `check.source_marks` no longer pass placeholders as `names`. They pass `names` and `all_names` through unchanged.
- Production callers now pass the EXE's C names as `all_names`: configure's unit loop (`_check_source`), `account_unit` and the drift test's `defined_starts`.

**Tests (RED first, `bf58299`).**
- `tests/test_unitdefs.py`:
  - `test_renamed_row_reads_by_its_current_name[all_names-only|explicit-names]`: the reviewer's probe through `find`.
  - `test_all_names_alone_decides_rows_outside_the_unit`.
  - `test_neither_names_nor_all_names_reads_placeholders`.
- `tests/test_configure.py`: `test_d12_reads_a_renamed_row_by_its_current_name[all_names-only|explicit-names]`, the probe through `check_unit_source`.
- `tests/test_check.py`: `test_source_marks_with_all_names_reads_a_renamed_row_by_its_current_name`.

**RED evidence.**
- Results before the fix:
  - The `all_names`-only probes in configure and check failed on their assertions; the stale definition was accepted, so `(problem,) =` unpacked an empty list.
  - The `find` tests without `names` failed with TypeError, because `names` was a required keyword.
  - `test_all_names_alone...` failed on its assertion, because `names` used to decide outside rows.
  - The explicit-`names` cases already passed, as expected: the bug needed `names` to be the placeholders.
- Classifier on `tests/test_configure.py::test_d12_reads_a_renamed_row_by_its_current_name[all_names-only]` (JUnit `build/red/07-09-fix1.xml`): `RED_EVIDENCE_OK` / `target_test_failed`.
- Semantic assessment: the target failed on the planned behaviour, a stale definition being accepted. This was not a setup fault.

**Fix:** `0278039`.

**Commands and output after the fix.**
- `uv run pytest -q tests/test_unitdefs.py tests/test_configure.py tests/test_check.py tests/test_drift.py`: 320 passed, 3 skipped.
- `uv run pytest -q` (full host suite): 2911 passed, 232 skipped. The skips are the same platform and owner-file skips as before; none is new.
- `uv run ruff check .`: All checks passed.
- `uv run python configure.py --output <scratchpad>/build.ninja` on the committed tree: 841 units written, so D-12 passes.
