---
phase: 04-compiler-identification
plan: 07
subsystem: tooling
tags: [libmatch, runtime-csv, drift-test, watcom, d-06, d-07, python]

requires:
  - phase: 04-compiler-identification
    provides: "04-05 libmatch.py (scan_exe, load_libraries, format_runtime_csv, read_runtime_csv, runtime_csv_path) with review fix round 1 (rule (b) keyed by public address over surviving ranges)"
provides:
  - "config/ufo2p/runtime.csv (121 ranges) and config/tacp/runtime.csv (132 ranges), written only by `libmatch --write` (D-06, D-16)"
  - "tests/test_libmatch_real.py: drift test (text equality with a fresh scan), _cstart_ at the LE entry, a version-discriminating row, no overlap, a named discriminating module in the summary"
  - "test_committed_runtime_csvs_are_names_and_addresses: CI check of both CSVs without orig/"
  - "LibMatchReport.summary_data() / summary(): D-05/D-07 evidence block; format() ends with it, to_json() has a \"summary\" key"
affects: [04-09 cppscan, 04-10 probe (excludes these ranges), 04-11 toolchain docs, phase-05 functions.csv seeding]

actuals:
  tokens: 11800
  tasks: 2
  commits: 4
plan_head_before: 7088b0f9524174b8cbf559a42c5eb5a999d7f155
plan_head_after: b6d909209c10688025ad714b2d35c919f1013169

tech-stack:
  added: []
  patterns:
    - "Real-file drift test: a module-scoped fixture loads the libraries once; a module-scoped parametrized fixture scans each EXE once; the committed text must equal format_runtime_csv(fresh scan)"
    - "Committed derived data gets a CI-side content test that runs without the private inputs"

key-files:
  created:
    - config/ufo2p/runtime.csv
    - config/tacp/runtime.csv
    - tests/test_libmatch_real.py
  modified:
    - tools/reverseapoc/libmatch.py
    - tests/test_libmatch.py

key-decisions:
  - "The runtime maps are committed exactly as `libmatch --write` produced them; MIN_UNMASKED and the disambiguation rules are untouched"
  - "Ambiguous rows stay visibly ambiguous: a row's publics are the union over its candidates (e.g. atol_ in the atoi row), but status=ambiguous and the alternatives column say so, and the summary lists every ambiguous module with its alternative"
  - "summary_data() is public next to summary(), so JSON consumers (docs plan 04-11) get the same numbers as the text block"
  - "Version sets in the summary print largest first, versions in SWEPT_VERSIONS order joined by +; modules are named only for sets smaller than all swept versions"

patterns-established:
  - "Real-file tests assert a committed file exists before reading it, so a missing file is an assertion failure that names the command to run"

requirements-completed: [CID-04]  # copied from the plan; REQUIREMENTS.md is not marked here: requirements.ready-ids blocks CID-04 until 04-12 (which also declares it) has a SUMMARY

coverage:
  - id: D1
    description: "config/ufo2p/runtime.csv and config/tacp/runtime.csv committed from `libmatch --write`, re-derived without drift, _cstart_ on each LE entry, a version-discriminating row, no overlap"
    requirement: CID-04
    verification:
      - kind: integration
        ref: "REVERSEAPOC_ORIG=<main>/orig REVERSEAPOC_WATCOM_DIR=<main>/third_party/watcom uv run pytest -q -rs tests/test_libmatch_real.py (10 passed, no SKIPPED)"
        status: pass
      - kind: other
        ref: "git ls-files --error-unmatch config/ufo2p/runtime.csv config/tacp/runtime.csv"
        status: pass
    human_judgment: false
  - id: D2
    description: "CI checks the committed CSVs without orig/: generated-by comment, exact header, 9 cells per row, 8-digit hex addresses, versions within SWEPT_VERSIONS, status unique/ambiguous, no 8+ hex-digit run in a name cell"
    requirement: CID-04
    verification:
      - kind: unit
        ref: "tests/test_libmatch.py#test_committed_runtime_csvs_are_names_and_addresses (UFO2P.EXE, TACP.EXE)"
        status: pass
    human_judgment: false
  - id: D3
    description: "libmatch report ends with the D-05/D-07 summary (coverage percent, rows per version set with discriminating modules, rows per library, ambiguous modules, skips by version and reason); to_json() has the same numbers"
    requirement: CID-04
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_libmatch.py -k summary (3 tests)"
        status: pass
      - kind: integration
        ref: "tests/test_libmatch_real.py#test_summary_names_discriminating_modules"
        status: pass
    human_judgment: false

duration: 13min
completed: 2026-10-21
status: complete
---

# Phase 4 Plan 07: Committed Runtime Maps and libmatch Summary

**`config/ufo2p/runtime.csv` (121 ranges, 5.60% of the code object) and `config/tacp/runtime.csv` (132 ranges, 5.79%) are committed straight from `libmatch --write`. A real drift test re-derives them byte for byte in 37 s and a CI test checks they hold names and addresses only. The libmatch report now ends with a summary of the D-05/D-07 evidence: the same 11 modules match only 10.6 in both EXEs, and no row lacks 10.6.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-10-21T17:28:05Z
- **Completed:** 2026-10-21T17:41:00Z
- **Tasks:** 2 (both TDD; Task 1 is the tracer)
- **Files modified:** 5 (3 created, 2 modified)

## Accomplishments

- Both runtime maps are committed. Each has the generated-by/do-not-edit comment, the nine-column header and a `_cstart_` row (module `cstrt386`, DOS/CLIB3R.LIB, 10.5;10.6) that starts at the LE entry (0x000C0784 in UFO2P, 0x000C28B0 in TACP).
- `tests/test_libmatch_real.py` runs 5 tests per EXE (10 in all): drift, `_cstart_` at entry, a discriminating row, no overlap, and named discriminating modules in the summary. With both overrides set, nothing skips.
- `test_committed_runtime_csvs_are_names_and_addresses` runs in CI. It parses each CSV with `csv.reader` and requires exactly 9 cells per row (`zip(strict=True)`), because `read_runtime_csv` accepts missing cells and drops extra ones.
- `LibMatchReport.summary()` / `summary_data()`: `format()` ends with the summary block and `to_json()["summary"]` holds the same numbers.

## Real runs (names, counts and addresses only)

Inputs: the main checkout's `orig/` and `third_party/watcom` (read-only, via `../../../orig` and `../../../third_party/watcom` from the worktree root), versions 10.5, 10.6 and 11.0, MIN_UNMASKED 16. These are my own runs. They reproduce the reviewed 04-05 numbers: 121/132 ranges, 43,958/46,055 bytes, rule (b) 1/2, 14/12 ambiguous, 1 dropped `fatalerr` each.

| | UFO2P | TACP |
|---|---:|---:|
| Ranges | 121 | 132 |
| Bytes covered | 43,958 of 785,117 (5.60%) | 46,055 of 795,983 (5.79%) |
| Rows 10.5+10.6+11.0 (uninformative) | 58 | 62 |
| Rows 10.5+10.6 | 51 | 57 |
| Rows 10.6+11.0 | 1 | 2 |
| Rows 10.6 only | 11 | 11 |
| Ambiguous rows | 14 | 12 |
| Dropped (contained) | 1, `fatalerr` at 0x000C6B0E | 1, `fatalerr` at 0x000C9518 |
| Resolved data / calls / C-before-C++ | 0 / 1 / 0 | 0 / 2 / 0 |
| Drift test runtime (whole real file) | 37.2 s (31.3 s library load + UFO2P scan) | 5.6 s scan |

### UFO2P summary block (`uv run reverseapoc libmatch UFO2P.EXE`, no `--write`)

```
summary UFO2P.EXE: 121 ranges, 43958 of 785117 code bytes (5.60%)
versions 10.5+10.6+11.0: 58 rows
versions 10.5+10.6: 51 rows: allocfp, atoi, chipbug, clock, cmain386, cstrt386, cvt, d_getvec, d_setvec, delay, dosret, emu387, exit, fclose, fgetc, flush, fopen, fpeinth, fputc, fputs, fread, fseek, fwrite, getenv, hook387, inirt386, initfile, ioalloc, iomode, isatt, itoa, lseek, ltoa, mktime, nan_inf, nfree, nmalloc, open, qsort, read, sbrk386, scale, set386, setenvp, seterrno, signl, sigsy, strnicmp, strtod, timeutil, tzset
versions 10.6+11.0: 1 row: cprintf
versions 10.6: 11 rows: chk8087, cinit, close, efgfmt, ftell, ftos, grownear, initargv, memalloc, prtf, sprintf
library DOS/CLIB3R.LIB: 106 rows
library DOS/CLIB3S.LIB: 16 rows
library DOS/EMU387.LIB: 1 row
library DOS/GRAPH.LIB: 1 row
library MATH387R.LIB: 15 rows
library MATH387S.LIB: 3 rows
library MATH3R.LIB: 1 row
library MATH3S.LIB: 1 row
library NETWARE/CLIB3S.LIB: 7 rows
library NT/CLIB3R.LIB: 40 rows
library NT/CLIB3S.LIB: 8 rows
library OS2/CLIB3R.LIB: 42 rows
library OS2/CLIB3S.LIB: 8 rows
library WIN/CLIB3R.LIB: 33 rows
library WIN/CLIB3S.LIB: 6 rows
ambiguous 14: cstart (cstrt386), _strcmp (cmp386), atoi (atol), stk (stk386), dosdrive (drive386), ddisk386 (dosdisk), dosfind (find386), int386xa (intxa386), ini87386 (init8087), mbscat (strcat), dosio (io386), chainint (chint386), amodf (amodf386), i64tos (i64ts386)
skipped 10.5: not OMF 41, short 1927
skipped 10.6: not OMF 51, short 1929
skipped 11.0: not OMF 68, short 6285
```

### TACP summary block (`uv run reverseapoc libmatch TACP.EXE`, no `--write`)

```
summary TACP.EXE: 132 ranges, 46055 of 795983 code bytes (5.79%)
versions 10.5+10.6+11.0: 62 rows
versions 10.5+10.6: 57 rows: allocfp, atoi, chipbug, clock, cmain386, cstrt386, cvt, d_getvec, d_setvec, delay, dir, dosret, emu387, exit, fclose, fgetc, flush, fopen, fpeinth, fprtf, fputc, fputs, fread, fseek, fwrite, getenv, hook387, inirt386, initfile, ioalloc, iomode, isatt, itoa, lseek, ltoa, math87e, mktime, nan_inf, nfree, nmalloc, open, pow87e, qsort, read, sbrk386, scale, set386, setenvp, seterrno, signl, sigsy, stricmp, strnicmp, strtod, timeutil, tzset, write
versions 10.6+11.0: 2 rows: cprintf, exp387
versions 10.6: 11 rows: chk8087, cinit, close, efgfmt, ftell, ftos, grownear, initargv, memalloc, prtf, sprintf
library DOS/CLIB3R.LIB: 113 rows
library DOS/CLIB3S.LIB: 16 rows
library DOS/EMU387.LIB: 1 row
library DOS/GRAPH.LIB: 1 row
library MATH387R.LIB: 19 rows
library MATH387S.LIB: 3 rows
library MATH3R.LIB: 1 row
library MATH3S.LIB: 1 row
library NETWARE/CLIB3S.LIB: 7 rows
library NT/CLIB3R.LIB: 45 rows
library NT/CLIB3S.LIB: 8 rows
library OS2/CLIB3R.LIB: 47 rows
library OS2/CLIB3S.LIB: 8 rows
library WIN/CLIB3R.LIB: 36 rows
library WIN/CLIB3S.LIB: 6 rows
ambiguous 12: cstart (cstrt386), _strcmp (cmp386), atoi (atol), stk (stk386), dosfind (find386), int386xa (intxa386), ini87386 (init8087), mbscat (strcat), dosio (io386), chainint (chint386), amodf (amodf386), i64tos (i64ts386)
skipped 10.5: not OMF 41, short 1927
skipped 10.6: not OMF 51, short 1929
skipped 11.0: not OMF 68, short 6285
```

Reading notes for the docs plan:
- A row counts once for each library it lists. That is why the library lines add up to more than the range count: one body that is identical in DOS/, NT/, OS2/ and WIN/ CLIB3R counts in all four.
- The ambiguous list is mostly 10.x/11.0 renames (cmp386 -> `_strcmp`, stk386 -> stk, ...), so the version union on those rows is real evidence. atoi/atol is the only true same-library twin.
- Skip totals per EXE are 160 not OMF and 10,141 short, the same as 04-05's totals.

### Judgement on the "union publics" Minor (ambiguous rows)

The atoi row lists `atoi_;atol_` as publics, and `atol_` comes from the alternative module. I kept it as generated. The plan forbids tuning the rules and hand-editing the CSV, and the row stays visibly ambiguous: `status=ambiguous`, the `alternatives` column names `atol@...` for each library, and the summary line says `atoi (atol)`. Nobody reading the row can take `atol_` as proven to be at that address. Phase 5 must treat every public of an ambiguous row as a candidate, not a placement.

## Task Commits

1. **Task 1: Tracer - commit both runtime.csv files and pin them with a drift test**: `aef256b` (test, RED), `b2679fa` (feat, GREEN: the two CSVs, 121 and 132 ranges). No test fix was needed after GREEN. Tracer gate: interactive run, `end-of-phase`, automated-only verify, so I re-ran it with no checkpoint. Results: 8 passed and no SKIPPED (real file), 2 passed (CI test), both files tracked, ruff clean.
2. **Task 2: The libmatch report summarises the D-05/D-07 evidence**: `c313ddb` (test, RED), `b6d9092` (feat, GREEN).

### RED evidence (semantic assessment)

- Task 1: `gsd-tools check tdd-red-evidence` returned RED_EVIDENCE_OK on pytest's JUnit XML for both runs: `test_committed_runtime_csvs_are_names_and_addresses[UFO2P.EXE]` (CI file) and `test_runtime_csv_has_no_drift[UFO2P.EXE]` (real file, overrides set). All 2 + 8 tests failed on the planned assertion, `config/<stem>/runtime.csv missing: run uv run reverseapoc libmatch <EXE> --write`. The real scans did run (44.8 s, no skip), so the failure is the missing file and not a load or fixture fault.
- Task 2: RED_EVIDENCE_OK on `test_summary_in_format_and_json`. It failed its first assertion: `format()` still ended with the old summary line. `test_summary_counts` and `test_summary_of_an_empty_report` failed with `AttributeError: 'LibMatchReport' object has no attribute 'summary'`, inside the test body: that is the planned missing method, not a collection error. On the real file, `test_summary_names_discriminating_modules` failed the same way for both EXEs while the other 8 passed.

## Files Created/Modified

- `config/ufo2p/runtime.csv`, `config/tacp/runtime.csv`: the runtime maps (generated, do not edit).
- `tests/test_libmatch_real.py`: drift test and real facts (10 tests with the overrides).
- `tests/test_libmatch.py`: `test_committed_runtime_csvs_are_names_and_addresses` (2), `test_summary_counts`, `test_summary_in_format_and_json`, `test_summary_of_an_empty_report`.
- `tools/reverseapoc/libmatch.py`: `summary_data()`, `summary()`, the `"summary"` key in `to_json()`, summary lines at the end of `format()`, and module-level helpers `_plural`, `_version_key`, `_version_sets`, `_library_rows`, `_alternative_modules`, `_skip_counts`, `_skip_lines`. No existing name or signature changed (04-09 imports this module).

## Decisions Made

See `key-decisions` in the frontmatter.

## Deviations from Plan

### Minor additions

**1. `LibMatchReport.summary_data()` alongside `summary()`**
- The plan names `summary()` and a "summary" key in `to_json()`. One public method computes the numbers and the other formats them, so the text and JSON cannot drift apart. It is an added method, with no signature change.

**2. `test_summary_of_an_empty_report`**
- An extra unit test pins the zero-code-size percent (no division by zero) and the `none` lines.

**3. The real-file count is 10 tests, not 8**
- Task 1's acceptance says 8 (4 per EXE). Task 2 adds `test_summary_names_discriminating_modules` to the same file, as planned, so the final count is 10. Task 1's run was 8 passed.

**4. The CI test is stricter than its behavior line**
- It also requires the exact comment line (`RUNTIME_CSV_COMMENT.format(name=...)`), 9 cells per row, `start < end` and a `_cstart_` row. The notes from earlier waves called out the missing/extra-cell leniency of `read_runtime_csv`.

---

**Total deviations:** 4 minor additions, no auto-fixes.
**Impact on plan:** None on the CSV content. Every planned artifact, test and behavior exists.

## Issues Encountered

- The worktree sandbox refuses `$(git rev-parse ...)` and main-checkout absolute paths in commands. As the notes allow, I ran the plan's real commands and tests with `../../../orig` and `../../../third_party/watcom` (read-only), and the `wrote` lines confirm both CSVs landed in the worktree's `config/`.
- I introduced CRLF while editing `tests/test_libmatch.py` with a Python one-off and normalized it to LF before staging. `.gitattributes` is `eol=lf`.

## User Setup Required

None.

## Next Phase Readiness

- 04-10 (probe) can exclude these ranges with `read_runtime_csv(runtime_csv_path(name))`.
- 04-11 (docs) has the per-EXE evidence in `libmatch` output and `to_json()["summary"]`.
- Verification: `uv run pytest -q` gives 715 passed, 79 skipped (no overrides) and `uv run ruff check .` is clean. The real file gives 10 passed and no skip with the overrides.
- CID-04 stays open in REQUIREMENTS.md until 04-12 finishes (`requirements.ready-ids` blocks it).

## Self-Check: PASSED

- Files: config/ufo2p/runtime.csv, config/tacp/runtime.csv, tests/test_libmatch_real.py, this SUMMARY: present. `head -n 1 config/ufo2p/runtime.csv` starts with `# generated by: uv run reverseapoc libmatch UFO2P.EXE --write`.
- Commits since 7088b0f: aef256b, b2679fa, c313ddb, b6d9092 (4). `git rev-list --count HEAD -- config/ufo2p/runtime.csv config/tacp/runtime.csv` gives 1.
- Acceptance: both CSVs tracked, each with a `_cstart_` row; `-k committed_runtime_csvs` 2 passed; `-k summary` 3 passed; the real file passed with no SKIPPED; ruff clean.

---
*Phase: 04-compiler-identification*
*Completed: 2026-10-21*
