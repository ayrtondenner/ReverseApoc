---
phase: 05-split-and-first-matches
plan: 04
subsystem: tooling
tags: [functions.csv, boundaries.csv, units.csv, symbols.csv, lib386, watcom, naming, objdiff]

requires:
  - phase: 04-compiler-identification
    provides: config/<exe>/runtime.csv (04 D-06), libmatch.load_libraries/_code_segments/_Owner
  - phase: 05-split-and-first-matches
    provides: spike 005 verdict (objdiff pairs on exact linker names, plan 05-01)
provides:
  - functions.py: FunctionRow/BoundaryRow/UnitRow/SymbolRow, validated read/format/write for functions.csv (D-10), boundaries.csv (D-08), units.csv (D-11), symbols.csv (D-19)
  - seed_runtime_rows / runtime_entries / runtime_aliases: runtime rows at runtime.csv start + LIB386 public offset
  - check_unit_assignment, missing_verdicts, game_name/data_name placeholders
  - symbols.py: SymbolTable (build, linker_name, c_name, address_of, function_at, containing), SymbolError
affects: [05-08 target writer, 05-09 relocation check, 05-11 asm/score, 05-13 reconcile/units, 05-14 configure, phase 6 progress]

actuals:
  tokens: 14969
  tasks: 3
  commits: 6
plan_head_before: 6463d471f6040396d790fc8b1d9243901a6200e3
plan_head_after: 770d70a1ca4b577ab9b729d7eb6e5b511cfc16fe

tech-stack:
  added: []
  patterns:
    - "One generic _load(path, columns, parse, follows) reader: exact header, per-row parse checks, cross-row checks, FunctionsError naming file and data row"
    - "Placeholder names and regexes built from named constants (GAME_PREFIX, DATA_PREFIX, ADDRESS_DIGITS, FUNCTION_LINK_SUFFIX, DATA_LINK_PREFIX)"

key-files:
  created:
    - tools/reverseapoc/functions.py
    - tools/reverseapoc/symbols.py
    - tests/test_functions.py
    - tests/test_symbols.py
    - tests/test_functions_lib_real.py
  modified: []

key-decisions:
  - "A runtime.csv row resolves to every code segment of the chosen version whose (module, library) is the row's module in a listed library or one of its alternatives, and whose length equals the row's span. runtime.csv may name a module after another version's THEADR (10.6 calls _strcmp cmp386), so libraries[0] plus row.module does not work"
  - "Aliases come from the union of the publics of every matching segment at each offset. One row per distinct offset, named by F12's rule"
  - "A public at or past the segment end (___GETDSEnd_) is an end label and starts no row. Bytes before a module's first public (cstart +3, stk +8, emu387 +888) belong to no seeded row"
  - "SymbolTable.build takes aliases=functions.runtime_aliases(entries). A runtime name at two addresses (_Alphabet heads both itoa and ltoa) is recorded in table.ambiguous and address_of refuses it. A symbols.csv name that clashes with anything is still refused at build time"
  - "address_of accepts linker names only (func_X_, _D_X, publics, symbols.csv names), never C names. _D_X must lie in a caller-given data range or start a data-in-code row"

patterns-established:
  - "Every committed config CSV goes through functions.py readers; a bad file is refused, never half-read"
  - "symbols.SymbolTable is the only place that maps addresses to names"

requirements-completed: [SPL-01, SPL-03]

coverage:
  - id: D1
    description: "functions.csv (D-10) round-trips with the generated-by comment and exact header; the reader refuses unsorted, overlapping, empty-range, misnamed, bad-kind, bad-evidence and bad-unit rows with file and data row; empty unit accepted (F1); touching rows stay separate"
    requirement: SPL-01
    verification:
      - kind: unit
        ref: "tests/test_functions.py#test_functions_csv_round_trip, test_functions_reader_refusals, test_functions_reader_accepts_an_empty_unit, test_touching_rows_stay_separate"
        status: pass
    human_judgment: false
  - id: D2
    description: "Runtime rows seeded from runtime.csv plus 10.6 LIB386: __CMain at 0x000C5C9C, exit_ at 0x000C01E1, every row inside its runtime.csv row, one row per offset (F12), UFO2P and TACP"
    requirement: SPL-01
    verification:
      - kind: integration
        ref: "REVERSEAPOC_WATCOM_DIR=<main>/third_party/watcom uv run pytest -q -rs tests/test_functions_lib_real.py (7 passed, 0 skipped)"
        status: pass
      - kind: unit
        ref: "tests/test_functions.py#test_seed_*"
        status: pass
    human_judgment: false
  - id: D3
    description: "boundaries.csv (D-08), units.csv (D-11) and symbols.csv (D-19) schemas with validation, missing_verdicts and check_unit_assignment"
    requirement: SPL-03
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_functions.py -k \"touching or boundaries or units or symbols or refus\" (33 selected, passed)"
        status: pass
    human_judgment: false
  - id: D4
    description: "symbols.py SymbolTable: the one address <-> linker-name mapping (P8), symbols.csv override, unknown-symbol refusal, F12 alias resolution"
    requirement: SPL-03
    verification:
      - kind: unit
        ref: "tests/test_symbols.py (19 passed)"
        status: pass
      - kind: integration
        ref: "tests/test_functions_lib_real.py#test_runtime_names_and_aliases_build_one_symbol_table"
        status: pass
    human_judgment: false

duration: 24min
completed: 2026-10-24
status: complete
---

# Phase 5 Plan 04: functions.csv, config schemas and symbols.py Summary

**Validated readers and writers for functions.csv (D-10), boundaries.csv (D-08), units.csv (D-11) and symbols.csv (D-19). Runtime rows are seeded at runtime.csv start plus the 10.6 LIB386 public offset (`__CMain` 0x000C5C9C, `exit_` 0x000C01E1). `symbols.SymbolTable` is the one mapping from addresses to linker names (`func_X_`, `_D_X`, publics verbatim, F12 aliases).**

Execution context nonce: e8c3b25a8b359a4a

## Performance

- **Duration:** about 24 min (two API 529 interruptions in between)
- **Started:** 2026-10-24T00:13:15Z
- **Completed:** 2026-10-24T00:37:16Z
- **Tasks:** 3 (Task 1 tracer, Tasks 2-3 auto, all TDD)
- **Files modified:** 5 (all new)

## Accomplishments

- functions.py defines the four column tuples exactly as the plan wrote them, plus the enums, the comments, the frozen row types and atomic writers. A shared `_load` reader rejects a bad file with `FunctionsError: <path>: data row N: ...`.
- Runtime seeding works on real data. Every UFO2P (121) and TACP (132) runtime.csv row resolves against the 10.6 libraries: 260 and 279 rows. Seeded rows round-trip through the validating reader.
- SymbolTable maps both ways. `address_of` parses placeholders with regexes built from named constants. A func_ placeholder must name a game/thunk row start. `_D_` must lie in a data range or start a data-in-code row. Anything unknown raises SymbolError naming the symbol.

## Task Commits

1. **Task 1 (tracer): runtime.csv + LIB386 -> runtime rows of a functions.csv that round-trips.** RED `a89eb35`, GREEN `1d34f86`
2. **Task 2: validation rules and the boundaries, units, symbols schemas.** RED `58dc9f2`, GREEN `9adfc3e`
3. **Task 3: symbols.py.** RED `0470238`, GREEN `770d70a`

Tracer gate (Task 1): interactive, `human_verify_mode` end-of-phase, automated-only verify. Both verify commands were re-run and passed (real test unskipped), then expansion went ahead.

## TDD notes

Each RED commit failed at import: the new module or names did not exist yet. That is the normal first RED for a brand-new Python module. The plan is `type: execute` and `workflow.tdd_mode` is off, so the tdd-red-evidence classifier gate does not apply. Two RED steps inside GREEN failed on their assertions: the end-label test in Task 1 and the ambiguous-name test in Task 3.

## Files Created/Modified

- `tools/reverseapoc/functions.py`: schemas, readers/writers, `check_unit_assignment`, `missing_verdicts`, `seed_runtime_rows`, `runtime_entries`, `runtime_aliases`, `game_name`, `data_name`
- `tools/reverseapoc/symbols.py`: `SymbolTable`, `SymbolError`
- `tests/test_functions.py`: 44 synthetic tests (tests/libtree.py libraries, made-up names)
- `tests/test_symbols.py`: 19 synthetic tests
- `tests/test_functions_lib_real.py`: 7 real tests against the owner's 10.6 LIB386 (skip without it)

## Decisions Made

See key-decisions in the frontmatter. In short: a runtime.csv row resolves through its module plus alternatives, matched on segment length. End labels and leading bytes before the first public give no row. Ambiguous runtime names stay row names but cannot be resolved by name.

## Deviations from Plan

**Orchestrator ruling F1: the functions.csv reader accepts an empty unit column** as well as `[a-z0-9_]+`. Checking that every function is in exactly one unit stays the job of `check_unit_assignment`. Tests: `test_functions_reader_accepts_an_empty_unit` and the `refused-unit-name` case (`Bad-Name`). Commit `9adfc3e`.

**Orchestrator ruling F12: one seeded row per distinct offset, never zero-length**, named by the alias without a leading underscore, else the first in sorted order. Every alias still resolves: `runtime_entries` records each entry's aliases, `runtime_aliases(entries)` maps them to the row start, and `SymbolTable.build(..., aliases=...)` feeds `address_of`. Tests: `test_seed_aliases_at_one_offset_give_one_row`, `test_runtime_aliases_resolve_to_their_row`, `test_an_alias_must_name_a_runtime_row_start`, and the real `test_every_alias_shares_its_rows_start` and `test_runtime_names_and_aliases_build_one_symbol_table`. Commits `1d34f86` and `770d70a`.

### Auto-fixed Issues

**1. [Rule 1 - Bug] Module resolution rule in the plan did not fit runtime.csv**
- **Found during:** Task 1 (probe of the real rows before writing code)
- **Issue:** The plan said "library = row.libraries[0], module whose stem equals row.module". In practice 10 UFO2P and 9 TACP rows had no such module in 10.6. `row.libraries` is the union over all hits, and `row.module` can be another version's THEADR name: `_strcmp` vs 10.6 `cmp386`, `dosdrive`, `stk`, `amodf`. The mbscat row is really `strcat`-shaped.
- **Fix:** Take every 10.6 code segment whose (module, library) is the row's module in any listed library or one of its alternatives, and whose length equals the row span. Publics are unioned over those segments, per offset. A row with no match raises FunctionsError naming the row.
- **Files modified:** tools/reverseapoc/functions.py
- **Verification:** `test_seed_finds_a_module_named_by_another_version`, `test_seed_refuses_a_module_whose_segment_length_differs`; the real tests resolve every row of both EXEs
- **Committed in:** `1d34f86`

**2. [Rule 1 - Bug] End labels made zero-length rows**
- **Found during:** Task 1 (real test)
- **Issue:** `___GETDSEnd_` sits at offset == segment length and produced a zero-length row.
- **Fix:** A public at or past the segment end starts no row.
- **Files modified:** tools/reverseapoc/functions.py
- **Verification:** `test_seed_ignores_a_public_at_the_segment_end`; real test
- **Committed in:** `1d34f86`

**3. [Rule 1 - Bug] `_Alphabet` named two addresses and broke SymbolTable.build on real data**
- **Found during:** Task 3 (added real test)
- **Issue:** `_Alphabet` sits at offset 0 of both the itoa and ltoa modules, so two runtime rows carry that name. It is almost certainly an LPUBDEF (module-local) table, but omf.py reads LPUBDEF like PUBDEF. Changing omf.py is outside this plan's files, and other wave plans edit omf.py.
- **Fix:** Runtime names and aliases at more than one address go to `SymbolTable.ambiguous`. `address_of` refuses them with "ambiguous" and lists every address. `linker_name` of each row is still the name. A symbols.csv name that clashes with a runtime or other name is still a build error.
- **Files modified:** tools/reverseapoc/symbols.py, tests/test_symbols.py, tests/test_functions_lib_real.py
- **Verification:** `test_a_runtime_name_at_two_addresses_is_ambiguous`; the real test pins `set(table.ambiguous) == {"_Alphabet"}` for both EXEs
- **Committed in:** `770d70a`

**4. [Rule 2 - Missing critical] Extra reader hardening (T-05-08)**
- Rows with more fields than the header are refused. Runtime and symbols.csv names must match a linker-name pattern. An unparsable address gets an error naming its column.
- **Committed in:** `9adfc3e`

---

**Total deviations:** 2 orchestrator rulings applied (F1, F12) and 4 auto-fixed (3 Rule 1, 1 Rule 2).
**Impact on plan:** All changes are needed for the seeding to work on the real runtime.csv. Public API names and the four column tuples are exactly as planned. Additions: `runtime_entries`, `runtime_aliases`, `RuntimeEntry`, `game_name`, `data_name`, `SymbolTable.ambiguous` and the `aliases=` keyword of `SymbolTable.build`.

## Issues Encountered

- The harness refused `$(git rev-parse ...)` inside the verify command. The real test ran with `REVERSEAPOC_WATCOM_DIR` set to the resolved main-checkout path `C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/third_party/watcom`, which is the same value. Result: exit 0, 7 passed, 0 SKIPPED.
- Two API 529 interruptions during Task 3. Work resumed from the uncommitted state with nothing lost.

## Flagged for later plans

- **05-13 (reconcile/units):** bytes before a module's first public are in no seeded row: cstart [0x10000, 0x10003), stk +8, emu387 +888 (a table). runtime.csv still covers them, so reconcile must decide their kind.
- **Consumers that need aliases** (05-09 relocation check, 05-11 scorer) must build the table with `aliases=runtime_aliases(runtime_entries(...))`, which needs LIB386 at run time. Without it only F12 row names resolve.
- **omf.py** does not mark LPUBDEF publics as local. If it ever does, `_Alphabet` stops being ambiguous; the real test then fails on `{"_Alphabet"}` and should be updated.
- For ambiguous rows, aliases come from alternative modules too (for example `atol_` with `atoi_`, `strcat_` with `_mbscat_`), because the bytes are identical.

## Verification

- `uv run pytest -q tests/test_functions.py tests/test_symbols.py`: 63 passed
- Real: `tests/test_functions_lib_real.py`: 7 passed, 0 skipped (owner's 10.6 tree)
- `uv run pytest -q`: 943 passed, 172 skipped (the real files skip in the worktree without the env var). `uv run ruff check .`: clean
- No commit of this plan touches `config/` (runtime.csv untouched), STATE.md or ROADMAP.md

## User Setup Required

None.

## Next Phase Readiness

Wave 3 plans (05-08, 05-09, 05-11, 05-13, 05-14) can import functions.py and symbols.py.

## Self-Check: PASSED

- Files exist: tools/reverseapoc/functions.py, tools/reverseapoc/symbols.py, tests/test_functions.py, tests/test_symbols.py, tests/test_functions_lib_real.py
- Commits on this branch: a89eb35, 1d34f86, 58dc9f2, 9adfc3e, 0470238, 770d70a
