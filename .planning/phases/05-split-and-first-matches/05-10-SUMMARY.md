---
phase: 05-split-and-first-matches
plan: 10
subsystem: tooling
tags: [ghidra, analyzeHeadless, java, ghidrascript, decompiler, csv, pytest]

requires:
  - phase: 05-split-and-first-matches
    provides: "05-03 requires_ghidra()/GHIDRA_DIR and the Ghidra-loadable synthetic LE; 05-04 functions.csv schema that the export feeds"
provides:
  - "tools/reverseapoc/ghidra.py: GhidraError, GhidraFunction, ExportResult, DraftResult, SCRIPT_DIR, LOADER, PROCESSOR, CSPEC, EXPORT_COLUMNS, DEFAULT_EXPORT_DIR, DEFAULT_ASM_DIR, CONTAINER_HINT, install_dir, headless_argv, export_functions, export_drafts, draft_name, read_ghidra_export, ghidra_version"
  - "tools/reverseapoc/ghidra_scripts/ExportFunctions.java: entries, body bounds, counts, thunk, convention and name per function (0x%08X), CSV-quoted names"
  - "tools/reverseapoc/ghidra_scripts/ExportDrafts.java: DecompInterface drafts to <out dir>/func_XXXXXXXX.c"
  - "tests/test_ghidra.py: 24 tests against a fake analyzeHeadless runner and synthetic export text"
affects: [05-12, 05-16, ghidra-export verb, reconcile, decompile drafts]

actuals:
  tokens: 8200
  tasks: 2
  commits: 5
plan_head_before: 532a74582239727dd92c0ee200d1d3e8d81b87cf
plan_head_after: 3b43ab6ec779e41b71bac6473fa3f510837c58f7

tech-stack:
  added: []
  patterns:
    - "analyzeHeadless argv is a list from named parts; the project dir is a TemporaryDirectory that exists before the run and is removed after it, plus -deleteProject"
    - "Every refusal (manifest name, output inside orig/, missing install, missing EXE) runs before anything is written or the runner is called (_preflight)"
    - "A stale output (functions.raw.csv or a requested func_X.c) is deleted before each run, so only this run's files can pass"

key-files:
  created:
    - tools/reverseapoc/ghidra.py
    - tools/reverseapoc/ghidra_scripts/ExportFunctions.java
    - tools/reverseapoc/ghidra_scripts/ExportDrafts.java
    - tests/test_ghidra.py
  modified: []

key-decisions:
  - "The output directory per EXE is the lowercase manifest stem (ufo2p), matching config_dir; the Ghidra project name is p_<STEM> (p_UFO2P)"
  - "export_functions/export_drafts take an optional manifest= and resolve target_name through select_target, so free text never becomes a path (T-05-22)"
  - "The adapter accepts only the writer's exact format: 0x plus 8 upper-case hex digits, decimal counts, thunk true/false, non-empty name, body_min <= body_max"
  - "ExportFunctions.java quotes a name or convention holding a comma, quote or line break, and the adapter reads it with the csv module"
  - "export_drafts reports addresses without a draft in DraftResult.missing instead of raising: the Java script prints and skips them by design"
  - "The env is not scrubbed for analyzeHeadless (unlike the Watcom wrapper): Ghidra needs JAVA_HOME/HOME and its own settings dir"

patterns-established:
  - "Ghidra drivers return a result with format() and to_json() for the CLI verb 05-12 adds"

requirements-completed: [SPL-01]

coverage:
  - id: D1
    description: "analyzeHeadless driver: argv order (-import, -loader LeLoader, -processor watcom:LE:32:default, -cspec watcom, -postScript ExportFunctions.java <out>, -scriptPath <ghidra_scripts>, -deleteProject), project dir exists during the run and is gone after, CSV read back with count"
    requirement: SPL-01
    verification:
      - kind: unit
        ref: "tests/test_ghidra.py#test_export_runs_headless_and_reads_the_csv"
        status: pass
    human_judgment: false
  - id: D2
    description: "Adapter refuses header-only exports, wrong headers, malformed rows (named by data row) and duplicated entries (named by address); rows come back sorted by entry"
    requirement: SPL-01
    verification:
      - kind: unit
        ref: "tests/test_ghidra.py#test_header_only_export, test_rows_sorted_and_unique, test_bad_rows[5 cases], test_quoted_name_reads_back"
        status: pass
    human_judgment: false
  - id: D3
    description: "Driver refusals: missing install names the container command (D-05), output inside orig/ refused before the runner, missing EXE and unknown target refused, non-zero exit or missing CSV raises with the exit code, stale export never read"
    requirement: SPL-01
    verification:
      - kind: unit
        ref: "tests/test_ghidra.py#test_missing_install, test_refuses_output_in_orig, test_missing_exe_is_refused, test_unknown_target_is_refused, test_runner_failure[exit-1,no-csv], test_runner_failure_never_reads_a_stale_export"
        status: pass
    human_judgment: false
  - id: D4
    description: "ghidra_version reads application.version from Ghidra/application.properties"
    requirement: SPL-01
    verification:
      - kind: unit
        ref: "tests/test_ghidra.py#test_version, test_version_without_the_key"
        status: pass
    human_judgment: false
  - id: D5
    description: "export_drafts argv (-postScript ExportDrafts.java <asm>/<exe>/ghidra 0x...), refusal inside orig/ and of bad addresses, written/missing report"
    requirement: SPL-01
    verification:
      - kind: unit
        ref: "tests/test_ghidra.py#test_drafts_argv, test_drafts_report_written_and_missing, test_drafts_refuse_bad_addresses[3 cases]"
        status: pass
    human_judgment: false
  - id: D6
    description: "The two Java GhidraScripts compile and behave correctly under Ghidra 12.1.4 on a real import"
    requirement: SPL-01
    verification: []
    human_judgment: true
    rationale: "Ghidra and its jars are not on the host or in the image yet; the scripts are first compiled and run by plan 05-12's container smoke test, which owns any Java fix"

duration: 6min
completed: 2026-10-24
status: complete
---

# Phase 5 Plan 10: Headless Ghidra export driver, Java export scripts and validated adapter Summary

**`reverseapoc.ghidra` builds the analyzeHeadless argv as a list (LeLoader, `watcom:LE:32:default`, cspec `watcom`, temp project with `-deleteProject`). It runs the committed `ExportFunctions.java`, which writes addresses and names only, and reads the CSV back through an adapter that refuses empty, malformed or duplicated exports. `ExportDrafts.java` (DecompInterface) writes decompile drafts into the gitignored `asm/<exe>/ghidra/`. Every refusal (output in orig/, missing install with the container command, missing EXE) runs before the runner is called.**

Execution context nonce: af7337b7c571c187

## Performance

- **Duration:** 6 min
- **Started:** 2026-10-24T00:54:40Z
- **Completed:** 2026-10-24T01:00:34Z
- **Tasks:** 2
- **Files modified:** 4 (all new)

## Accomplishments
- The driver: `headless_argv` gives the verified research Pattern 2 command, and `export_functions` runs it in a temporary project dir that exists before the run (Pitfall 6) and is removed after it. It checks the exit code and that the CSV exists, then returns `ExportResult(path, count, seconds)` with `format()`/`to_json()`.
- `ExportFunctions.java`: one row per function with `entry,body_min,body_max,addresses,ranges,thunk,calling_convention,name`, addresses `0x%08X` from `getOffset()`. It writes no bytes, listing or relocations (P4).
- `read_ghidra_export`: returns rows sorted by entry. It refuses a header-only export (`export holds no functions`), a wrong header, malformed rows (named by data row number) and duplicated entries (named by address).
- `ghidra_version(install)` reads `application.version`; `install_dir()` uses GHIDRA_INSTALL_DIR, else /opt/ghidra.
- `export_drafts` and `ExportDrafts.java`: write the D-16 drafts to `asm/<exe>/ghidra/func_XXXXXXXX.c` and report addresses with no draft. Stale drafts are deleted before each run.

## Task Commits

1. **Task 1 (tracer): driver runs analyzeHeadless (faked), adapter reads the export**: `c3bc166` (test, RED), `a758ec5` (feat, GREEN). Tracer gate (interactive, end-of-phase, automated-only verify): I re-ran `uv run pytest -q tests/test_ghidra.py` (1 passed) and `uv run ruff check .` (clean), then expanded.
2. **Task 2: adapter validation, version, drafts and refusals**: `baf7e68` (test, RED), `884d9de` (feat, GREEN), `3b43ab6` (feat, default output roots; see Deviations).

## TDD notes (RED evidence, semantic assessment)
- Task 1 RED (`c3bc166`): collection ImportError, because `reverseapoc.ghidra` did not exist yet. That is a load-level failure, not an assertion-level RED. The plan is `type: execute` and `workflow.tdd_mode` is unset, so the plan-level TDD gate does not apply. Noted for the end-of-phase TDD review, as 05-03 did.
- Task 2 RED (`baf7e68`): 19 failed, 4 passed. The failures were the planned behaviour: no GhidraError for header-only, duplicate, non-hex, bad-thunk, short and unprefixed rows; no refusal for a missing install, orig/ output or missing EXE; no exit-code check; and `ghidra_version`/`export_drafts` absent (AttributeError). Four already passed at RED. Task 1's tracer, the wrong-header case and the quoted-name case passed because Task 1's adapter already checked the header and used the csv module. The unknown-target case passed because `select_target` was already in Task 1. GREEN `884d9de`: 23 passed.

## Files Created/Modified
- `tools/reverseapoc/ghidra.py`: driver, preflight refusals, drafts, adapter, version.
- `tools/reverseapoc/ghidra_scripts/ExportFunctions.java`: headless export of entries, bodies and names.
- `tools/reverseapoc/ghidra_scripts/ExportDrafts.java`: DecompInterface drafts for given addresses.
- `tests/test_ghidra.py`: 24 tests with a fake runner and made-up addresses; no game bytes.

## Decisions Made
See `key-decisions` in the frontmatter. The main one: target names resolve through the manifest (`select_target`). The per-EXE output directory is the lowercase stem, as in `config_dir`.

## Deviations from Plan

No orchestrator ruling amends 05-10, so none was applied.

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Stale outputs deleted before each run**
- **Found during:** Task 1 and Task 2
- **Issue:** analyzeHeadless can exit 0 when a post-script fails. A CSV or draft left by an earlier run would then pass as this run's output.
- **Fix:** `export_functions` unlinks `functions.raw.csv`, and `export_drafts` unlinks each requested `func_X.c`, before the run.
- **Verification:** `test_runner_failure_never_reads_a_stale_export`, `test_drafts_report_written_and_missing`
- **Committed in:** `a758ec5`, `884d9de`

**2. [Rule 2 - Missing critical] Extra refusals beyond the plan's list**
- **Found during:** Task 2
- **Issue:** The plan named the install and orig/ refusals only. A missing EXE or a free-text target name would have reached the runner.
- **Fix:** `_preflight` also refuses a missing `orig/<EXE>` (with the `reverseapoc ingest` hint) and a name not in the manifest. `export_drafts` also refuses an empty address list and addresses outside 0..0xFFFFFFFF. The adapter refuses an empty name and `body_min > body_max`.
- **Verification:** `test_missing_exe_is_refused`, `test_unknown_target_is_refused`, `test_drafts_refuse_bad_addresses[none,negative,too-big]`
- **Committed in:** `884d9de`

**3. [Rule 2 - Missing critical] CSV quoting in ExportFunctions.java**
- **Found during:** Task 1
- **Issue:** The research skeleton joins cells with bare commas. A Ghidra name holding a comma would shift the columns.
- **Fix:** The Java `cell()` quotes a cell that holds a comma, a quote or a line break, and the adapter reads it with `csv.reader`.
- **Verification:** `test_quoted_name_reads_back`
- **Committed in:** `a758ec5`

**4. [Rule 2 - Missing critical] Named gitignored default roots**
- **Found during:** after Task 2
- **Issue:** The plan states the defaults `build/ghidra/<exe>/` and `asm/<exe>/ghidra/`, but no constant held them for the 05-12 verb.
- **Fix:** `DEFAULT_EXPORT_DIR` and `DEFAULT_ASM_DIR`, with a test that both sit under a gitignored top-level directory. The test went in with the constants (it passed on first run), so this addition has no separate RED commit.
- **Verification:** `test_default_outputs_are_gitignored`
- **Committed in:** `3b43ab6`

---

**Total deviations:** 4 auto-fixed (all Rule 2)
**Impact on plan:** All four harden the export path against stale or unsafe input. No change to the planned API, and no scope beyond SPL-01/D-16.

## Issues Encountered
- I wrote one file through Python `Path.write_text` on Windows, which left CRLF in the working copy. Git normalized it to LF in the commit (the committed blob has 0 CR bytes). I converted the working copy back to LF.
- The Java scripts could not be compiled here: the host JDK has no Ghidra jars, and the image has no Ghidra yet. That is plan 05-12's smoke test, as the plan's flagged assumptions say.

## Threat Flags
None. The surface (a subprocess with list argv, outputs refused inside orig/, drafts under gitignored asm/) is the one in the plan's threat model (T-05-21..23).

## User Setup Required
None.

## Next Phase Readiness
- 05-12 can wire the `ghidra-export` verb straight onto `export_functions`/`export_drafts`/`ghidra_version` and the `DEFAULT_*` roots. Its container smoke test is the first real compile of both Java scripts.
- The reconcile step should take only `entry` from `GhidraFunction` as a start candidate (bodies are address sets).

## Self-Check: PASSED
- FOUND: tools/reverseapoc/ghidra.py, tools/reverseapoc/ghidra_scripts/ExportFunctions.java, tools/reverseapoc/ghidra_scripts/ExportDrafts.java, tests/test_ghidra.py
- FOUND commits: c3bc166, a758ec5, baf7e68, 884d9de, 3b43ab6 (5 = `git rev-list --count 532a745..HEAD` before this SUMMARY commit)
- `uv run pytest -q`: 1024 passed, 177 skipped; `uv run ruff check .`: clean
- Acceptance: `-k "header_only or sorted or bad_rows or version or missing_install or orig or runner_failure or drafts"` selected 19 and all passed (needed at least 8); `grep "extends GhidraScript"` gives 1 line in ExportFunctions.java; `grep DecompInterface` gives 3 lines in ExportDrafts.java

---
*Phase: 05-split-and-first-matches*
*Completed: 2026-10-24*
