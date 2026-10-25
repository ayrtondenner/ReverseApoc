---
phase: 06-reporting-and-agent-pilot
plan: 04
subsystem: tooling
tags: [discover, capstone, lint, ghidra, functions-csv, units, di-19]

requires: []
provides:
  - "discover end rule: a function ends at its trailing jump tables when no reached target follows (row 11)"
  - "regenerated config/ufo2p/functions.csv and config/tacp/functions.csv (26 ends, end column only)"
  - "lint refuses an explicitly named non-.c path (row 13b)"
  - "ExportDrafts.java: per-address ERROR line for an unparsable address, explicit address factory (row 8)"
  - "CSV-only unit tiling test on the committed CSVs (row 16b); real test reuses cli's runtime seeding (row 16a)"
affects: [06-16, 06-27, functions.csv, boundaries, units]

actuals:
  tokens: 8258
  tasks: 3
  commits: 7
plan_head_before: 021a58ba7441665b1eb5486caef92c91f23ad9c2
plan_head_after: f0dc6bf9a8ad8f31f93a36e2fa46c26fb9301e19

tech-stack:
  added: []
  patterns:
    - "Measure-before-commit gate for boundary rules: dump {start: end} for both real EXEs before and after, commit only a measured and owner-approved change set"
    - "Real-file verifies from a worktree through a wrapper that sets the F19 env vars (REVERSEAPOC_ORIG / _WATCOM_DIR / _GHIDRA_EXPORT)"

key-files:
  created: []
  modified:
    - tools/reverseapoc/discover.py
    - tools/reverseapoc/lint.py
    - tools/reverseapoc/ghidra_scripts/ExportDrafts.java
    - config/ufo2p/functions.csv
    - config/tacp/functions.csv
    - tests/test_discover.py
    - tests/test_lint.py
    - tests/test_ghidra.py
    - tests/test_units.py
    - tests/test_functions_real.py

key-decisions:
  - "Row 11: owner chose option (a) on 2026-10-25: land the end-rule fix; CSV regeneration done in 06-04, not 06-16 (orchestrator ruling, so main never carries a stale CSV)"
  - "Reachability for the row 11 rule: forward jump targets and case labels of the code scanned so far, plus the case labels of the trailing tables themselves; any of them in [table end, limit) keeps the function going"
  - "test_functions_real.py requires only the RUNTIME_VERSION (10.6) tree and asserts every committed runtime row lists it, so cli's rule loads exactly that tree"

patterns-established:
  - "A named-but-wrong input is refused with an error naming it, never skipped silently"

requirements-completed: [AGT-06, AGT-08]

coverage:
  - id: D1
    description: "discover ends a function at its trailing jump table when no reached target follows (row 11)"
    requirement: AGT-06
    verification:
      - kind: unit
        ref: "tests/test_discover.py#test_code_after_ret_and_table_is_not_absorbed"
        status: pass
      - kind: unit
        ref: "tests/test_discover.py#test_table_then_padding_still_ends_at_padding"
        status: pass
      - kind: unit
        ref: "tests/test_discover.py#test_case_label_after_the_table_stays_in_the_function"
        status: pass
      - kind: integration
        ref: "build/di19-11/before.json vs after.json: exactly the 26 listed ends change"
        status: pass
    human_judgment: false
  - id: D2
    description: "functions.csv regenerated for both EXEs; the real drift tests pass with 0 SKIPPED"
    requirement: AGT-06
    verification:
      - kind: integration
        ref: "tests/test_functions_real.py + tests/test_discover_real.py with F19 env vars (build/06-04-real.out: 24 passed, 0 SKIPPED)"
        status: pass
    human_judgment: false
  - id: D3
    description: "lint refuses an explicit non-.c path naming it, before clang lookup (row 13b)"
    requirement: AGT-06
    verification:
      - kind: unit
        ref: "tests/test_lint.py#test_lint_refuses_an_explicit_non_c_path"
        status: pass
    human_judgment: false
  - id: D4
    description: "ExportDrafts.java reports an unparsable address and continues; resolves through the address factory (row 8)"
    requirement: AGT-08
    verification:
      - kind: unit
        ref: "tests/test_ghidra.py#test_export_drafts_script_handles_bad_addresses"
        status: pass
    human_judgment: true
    rationale: "The test asserts the script text only; the Java is compiled and run by Ghidra in the container (test_ghidra_real.py, plan 06-16), which the host cannot do."
  - id: D5
    description: "Unit tiling proven on the committed CSVs without orig/ (row 16b); real test calls cli's runtime seeding (row 16a)"
    requirement: AGT-06
    verification:
      - kind: unit
        ref: "tests/test_units.py#test_committed_units_tile_their_rows"
        status: pass
      - kind: integration
        ref: "tests/test_functions_real.py (F19 run, build/06-04-real.out)"
        status: pass
    human_judgment: false

duration: 75min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 04: DI-19 code minors (rows 8, 11, 13b, 16a, 16b) Summary

**discover now ends a function at its trailing jump tables when no reached target follows. That moved 26 real ends, which the owner approved and both functions.csv files were regenerated for. lint refuses a named non-.c file. ExportDrafts.java logs an unparsable address and keeps going. The committed unit tiling is proven without orig/.**

Execution context nonce: f33f0ec210e007af

## Performance

- **Duration:** about 75 min, including two orchestrator round-trips at the row 11 checkpoint
- **Completed:** 2026-10-25T01:42:39Z
- **Tasks:** 3 of 3
- **Files modified:** 10

## Accomplishments

- **Row 11:**
  - Rule change in `_EndScan.end_of`: after a terminal instruction followed by jump tables, the function now ends at the end of those tables, unless something already scanned reaches past them. "Reached" means a forward jump target, a case label of a table already skipped, or a case label of the trailing tables themselves, lying in [table end, limit).
  - Measured on both EXEs: 26 ends move.
  - Owner decision: (a), 2026-10-25. The fix is committed and both functions.csv files are regenerated in this plan.
- **Row 13b:** `lint` now raises LintError `<path> is not a .c source` for an explicitly named file without the `.c` suffix. This happens in `collect_sources`, before clang is looked up. Directories still expand as before.
- **Row 8:** ExportDrafts.java changes:
  - Each address parse is guarded by `catch (NumberFormatException ...)`, which prints `ERROR <address>: ...` and moves on to the next address.
  - Addresses resolve through `currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(offset)`.
  - `toAddr` is gone.
- **Row 16b:** `test_committed_units_tile_their_rows[ufo2p|tacp]` checks the committed units.csv and functions.csv without orig/. A planted tmp copy with one unit end moved into a row must be caught, so the check cannot pass vacuously.
- **Row 16a:** `tests/test_functions_real.py` now seeds runtime rows through `cli._seeded_runtime_rows`, so the copy of cli's version rule is gone. `test_units_tile_the_code` stays as the LE-specific check (code object bounds).

## Row 11 measurement

These are addresses only. The scratch script stayed in the session scratchpad; its output went to the gitignored `build/di19-11/before.json` and `after.json` by shell redirection.

| EXE | starts | changed ends |
|-----|--------|--------------|
| UFO2P.EXE | 1946 | 13 |
| TACP.EXE | 1930 | 13 |

- In all 26 cases the old end was the next start.
- The fix cuts 4 to 12 bytes between the table end and the 16-aligned next start. None of those bytes was ever decoded by the descent, none is a case label, and none holds a fixup field. About half are zero bytes: TACP 60 of 108, UFO2P 49 of 96.
- None of the 26 lies in a matched unit (UFO2P u_000a34f0, TACP u_00054f20).

The 26 rows (start: old end -> new end). The regenerated functions.csv changes only the end column of exactly these rows; boundaries.csv, units.csv and symbols.csv are unchanged:

- UFO2P.EXE:
  - 0x00022040: 0x000221F0 -> 0x000221EC
  - 0x00025D40: 0x00025EE0 -> 0x00025EDC
  - 0x0002FFC0: 0x00030080 -> 0x00030074
  - 0x00034B90: 0x00034CD0 -> 0x00034CC4
  - 0x0004AB30: 0x0004ADA0 -> 0x0004AD98
  - 0x0004AF90: 0x0004B1B0 -> 0x0004B1A8
  - 0x00052100: 0x00052150 -> 0x00052148
  - 0x00063DD0: 0x000640B0 -> 0x000640AC
  - 0x00086380: 0x000863F0 -> 0x000863E8
  - 0x00089240: 0x00089360 -> 0x0008935C
  - 0x000A9AF0: 0x000A9ED0 -> 0x000A9EC8
  - 0x000AC510: 0x000AC610 -> 0x000AC60C
  - 0x000B84A0: 0x000B8550 -> 0x000B8544
- TACP.EXE:
  - 0x000161B0: 0x00016820 -> 0x00016818
  - 0x0003BAC0: 0x0003BB80 -> 0x0003BB74
  - 0x00042110: 0x00042330 -> 0x00042324
  - 0x0004D360: 0x0004D570 -> 0x0004D56C
  - 0x0004F340: 0x0004F470 -> 0x0004F464
  - 0x00050E40: 0x00050EF0 -> 0x00050EE8
  - 0x00052740: 0x000528C0 -> 0x000528B4
  - 0x00061520: 0x000615A0 -> 0x00061598
  - 0x00068570: 0x00068BD0 -> 0x00068BCC
  - 0x00072EA0: 0x00072F40 -> 0x00072F3C
  - 0x000840C0: 0x00084400 -> 0x000843F4
  - 0x000888C0: 0x00088F20 -> 0x00088F18
  - 0x000B2510: 0x000B26F0 -> 0x000B26EC

How the CSVs were regenerated:
1. `uv run reverseapoc functions <EXE> --orig <main>/orig --watcom-dir <main>/third_party/watcom --ghidra-export <main>/build/ghidra/<stem>/functions.raw.csv`, run first with `--output <scratchpad>` as a preview.
2. A scratch checker confirmed that only those 26 end cells differ and that boundaries.csv is byte-identical.
3. The same command was then run with `--write`.
4. `git diff --numstat config/` showed 13 lines changed in each functions.csv and nothing else under config/.

## Task Commits

1. **Task 1: row 11**
   - `5cf5392` (test, RED)
   - `2114911` (test: strict xfail while the owner decided)
   - `f4e63a4` (fix, GREEN, xfail removed)
   - `47b633d` (chore: functions.csv regeneration)
2. **Task 2: rows 13b and 8**
   - `dbc3d42` (test, RED)
   - `8078685` (fix, GREEN)
3. **Task 3: rows 16b and 16a**
   - `f0dc6bf` (test)

## TDD evidence

- **Task 1, RED:** `test_code_after_ret_and_table_is_not_absorbed` failed on its planned end assertion: `{CODE: 0x10014}` instead of the table end `0x10011`. The trailing `xor; ret` was being absorbed. The two companion pins passed, as planned.
  - Semantic assessment: the target test executed and failed for the intended reason.
- **Task 1, GREEN:** 17 of 17 tests in tests/test_discover.py pass.
- **Task 2, RED:** both new tests failed on their planned assertions:
  - lint: `cli_main([...common.h]) == 0`, not 1, because the header was silently skipped.
  - drafts: `catch (NumberFormatException` was absent from the script.
- **Task 2, GREEN:** tests/test_lint.py and tests/test_ghidra.py: 35 passed. The 3 skips are pre-existing clang/Ghidra skips.
- **Task 3:** the plan asks for a test that passes on committed data. The planted case inside the test is the proof that it can fail.
- pytest's console report is not one of the formats `check tdd-red-evidence` supports, so RED was judged by inspecting the target assertion, as above.

## Verification

- `uv run pytest -q tests/test_discover.py`: 17 passed.
- Measurement comparison: exactly the 26 listed ends, and the same key sets before and after.
- `uv run pytest -q tests/test_lint.py tests/test_ghidra.py`: 35 passed, 3 skipped (pre-existing, clang/Ghidra).
- `uv run pytest -q tests/test_units.py`: 20 passed.
- F19 real run, `tests/test_functions_real.py tests/test_discover_real.py`: 24 passed and no SKIPPED (`build/06-04-real.out`).
- Host suite: 1425 passed, 215 skipped. `uv run ruff check .` is clean.
- `git status --porcelain config/` is empty: the regenerated CSVs are committed, and nothing else under config/ changed.

## Decisions Made

- **Row 11:** (a), owner 2026-10-25. The CSV regeneration was done in 06-04, not 06-16, by orchestrator ruling, so main never carries a stale CSV.
- **Reachability set:** the row 11 rule looks only at targets in [table end, limit). A forward jump or case label at or past the limit belongs to another function and does not keep this one going.

## Deviations from Plan

### Orchestrator rulings applied

- **Orchestrator ruling F19 (06-04):** Task 3's real verify ran with REVERSEAPOC_ORIG, REVERSEAPOC_WATCOM_DIR and REVERSEAPOC_GHIDRA_EXPORT pointing at the main checkout. The `-rs` output was written to `build/06-04-real.out` and has no SKIPPED for tests/test_functions_real.py and tests/test_discover_real.py.
  - The harness refused inline env-var command prefixes and `$(git rev-parse ...)`, so the variables were set by a scratchpad wrapper (`run_real.py`). It runs `python -m pytest` with the literal main-checkout paths and writes the output file itself, which satisfies R-B (program's own write).
- **Orchestrator ruling (row 11 checkpoint, 2026-10-25):** owner option (a). The fix landed in f4e63a4, after the plan's checkpoint path had first reverted it and held the test as strict xfail (2114911).
- **Orchestrator ruling (2026-10-25), CSV regeneration moved into 06-04:** the plan prohibited changing functions.csv in this plan and handed regeneration to 06-16. The orchestrator instead had 06-04 regenerate both functions.csv files (47b633d), previewed first and limited to the 26 end cells, so main never carries a stale CSV between waves. boundaries.csv, units.csv and symbols.csv are untouched.
- **Orchestrator correction (2026-10-25):** no xfail, skip or expected-change marker was added to any real-file test.
- **Rules R-A / R-B:** no new skip was added. Everything under build/ was written by shell redirection or by the program's own writes.

### Auto-fixed Issues

**1. [Rule 3 - Blocking] tests/test_functions_real.py `_libraries` was also used by `test_symbols_resolve`**
- **Found during:** Task 3.
- **Issue:** removing the copied version rule left `test_symbols_resolve` needing the LIB386 for `runtime_entries`. cli has no public helper that returns libraries, and cli.py is read-only in this plan.
- **Fix:** `_libraries` now loads only RUNTIME_VERSION (10.6). The shared `_require_runtime_tree` asserts that every committed runtime.csv row lists 10.6, which is exactly the tree cli's rule loads. The runtime rows themselves come from `cli._seeded_runtime_rows`.
- **Verification:** the F19 real run passes, 24 tests.
- **Committed in:** f0dc6bf.

**2. [Extra pin] `test_case_label_after_the_table_stays_in_the_function`**
- **Found during:** Task 1.
- **Issue:** the plan names two tests. A third pin guards the common Watcom layout where case labels follow the table, so the new rule cannot cut a real function short.
- **Committed in:** 5cf5392.

**Total deviations:** 4 orchestrator rulings applied (plus the R-A/R-B rules honoured), 1 blocking fix, 1 extra pin.
**Impact on plan:** the CSV prohibition was lifted by the owner and the orchestrator. Everything else is as planned.

## Issues Encountered

- The first synthetic layout dropped the fixups argument, and the default 0x11 page fill stood in for the padding, so the tests did not exercise the case. Fixed before the RED commit.
- The Write/Edit tools and `Path.write_text` on Windows write CRLF. lint.py was rewritten with LF before its commit.

## Known Stubs

None.

## Handed to 06-16

- The container run of test_ghidra_real.py exercises the new ExportDrafts.java, which the host cannot compile.
- Nothing to regenerate: the functions.csv files are already regenerated and committed here. rulings.md's note to "re-measure these figures if 06-04 chose (a)" still applies to whatever 06-16 measures from functions.csv: 26 function ends are now 4 to 12 bytes shorter.

## User Setup Required

None.

## Next Phase Readiness

DI-19 rows 8, 11, 13b, 16a and 16b are closed by commits. The new real-file pins need the 06-16 container run (Ghidra drafts).

## Self-Check: PASSED

- Files exist: tools/reverseapoc/discover.py, lint.py, ghidra_scripts/ExportDrafts.java, tests/test_discover.py, test_lint.py, test_ghidra.py, test_units.py, test_functions_real.py, config/ufo2p/functions.csv, config/tacp/functions.csv.
- Commits on HEAD: 5cf5392, 2114911, f4e63a4, 47b633d, dbc3d42, 8078685, f0dc6bf (7, measured with `git rev-list --count 021a58b..HEAD`).

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
