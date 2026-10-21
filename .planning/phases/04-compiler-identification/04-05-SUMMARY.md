---
phase: 04-compiler-identification
plan: 05
subsystem: tooling
tags: [libmatch, omf, le, watcom, runtime-csv, masked-match, python, stdlib]

requires:
  - phase: 04-compiler-identification
    provides: "04-02 omf.py (read_library, is_omf_library, Segment.data/mask/unmaskable, OMFFixup.segment_relative/target_kind/target_name/displacement)"
  - phase: 03-rebuild
    provides: "le.py LE.load_flat()/fixups(), splice._write_atomic, the rebuild verb's manifest-checked input pattern"
provides:
  - "tools/reverseapoc/libmatch.py: masked whole-segment library matcher over the EXE code object, with skip records, version/library merge, containment handling and disambiguation rules (a)-(d)"
  - "runtime.csv format (D-06): format_runtime_csv / write_runtime_csv / read_runtime_csv / runtime_csv_path"
  - "targets.config_dir(name) -> config/<lowercase stem> (D-16)"
  - "`uv run reverseapoc libmatch EXE [--write | --output PATH] [--json]`; OMFError and LibMatchError mapped in cli.main"
  - "tests/conftest.py build_le_image(patches=...) VA-keyed page overlay; tests/libtree.py synthetic LIB386 trees"
affects: [04-07 runtime map and drift test, 04-09 cppscan, phase-05 functions.csv seeding, phase-06 hooks]

actuals:
  tokens: 15800
  tasks: 3
  commits: 8
plan_head_before: 5f2d1866396e45929706467c19f53ad018b4e985
plan_head_after: a246bf482185164faa70621b65846fcb5bcb0cf4

tech-stack:
  added: []
  patterns:
    - "Identical segments (same bytes, mask and absolute sites) are searched once and the placements shared by every owner"
    - "Disambiguation narrows by module name, and only when at least one candidate passes the rule"
    - "Real-input smoke runs write only to build/libmatch-smoke/ (gitignored)"

key-files:
  created:
    - tools/reverseapoc/libmatch.py
    - tests/test_libmatch.py
    - tests/libtree.py
  modified:
    - tools/reverseapoc/targets.py
    - tools/reverseapoc/cli.py
    - tests/conftest.py
    - tests/test_targets.py
    - tests/test_cli.py

key-decisions:
  - "A row's libraries, versions and publics are the union over every candidate left after disambiguation; the module column names the chosen one and `alternatives` the rest (a module renamed between versions otherwise read as 11.0-only)"
  - "Disambiguation is decided per module name (a name passes a rule when any of its hits passes), so a row's version set does not depend on whether an unrelated twin was present"
  - "Rule (c) drops only the C++-library candidates when C and C++ ones are tied; other libraries stay"
  - "The libmatch verb refuses an --output inside --orig or --watcom-dir, refuses a version that is not a bare directory name, and refuses to run when no OMF library was loaded at all (no empty runtime.csv from a wrong --watcom-dir)"
  - "The orig file is read once, hashed against the manifest, then parsed (no check-then-reopen gap)"
  - "LibMatchReport gains `resolved` (per-rule counts) so the real numbers come from the tool, not a side script"

patterns-established:
  - "tests/libtree.py: made-up module bodies (counting sequences), planted copies carry 0xEE at masked sites"
  - "Report summary line: ranges, covered bytes, skipped by reason, dropped, resolved per rule, ambiguous count"

requirements-completed: []  # CID-04 is shared with 04-07 and 04-12; marked when the last of them finishes

coverage:
  - id: D1
    description: "libmatch places a planted synthetic module (both-side masks, LE fixup required at the absolute site, none at the rel32 site) and the real UFO2P/TACP runs place _cstart_ at the LE entry VA"
    requirement: CID-04
    verification:
      - kind: unit
        ref: "tests/test_libmatch.py#test_planted_module_is_found"
        status: pass
      - kind: unit
        ref: "uv run pytest -q tests/test_libmatch.py -k rejects"
        status: pass
      - kind: integration
        ref: "uv run reverseapoc libmatch UFO2P.EXE / TACP.EXE --orig <main>/orig --watcom-dir <main>/third_party/watcom --output build/libmatch-smoke/<exe>.csv (_cstart_ at 0x000C0784 / 0x000C28B0 = entry VA)"
        status: pass
    human_judgment: false
  - id: D2
    description: "runtime.csv (D-06): comment line, nine columns, 8-digit hex, ;-joined sets, sorted by (start, end), addresses and names only; round trip through read_runtime_csv; config_dir (D-16)"
    requirement: CID-04
    verification:
      - kind: unit
        ref: "tests/test_libmatch.py#test_runtime_csv_round_trip, test_runtime_csv_holds_addresses_and_names_only, test_equal_start_sorts_by_end, test_runtime_csv_path_is_in_the_exe_config_dir"
        status: pass
      - kind: unit
        ref: "tests/test_targets.py#test_config_dir"
        status: pass
    human_judgment: false
  - id: D3
    description: "Skip records (short, unmaskable, not OMF, parse error, no LIB386 directory), version and library merge order, touching ranges kept, contained ranges dropped and listed, partial overlap refused"
    requirement: CID-04
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_libmatch.py -k 'rejects or recorded or merge or touching or contained or overlap or empty_tree or equal_start or cover_every'"
        status: pass
    human_judgment: false
  - id: D4
    description: "Disambiguation (a) data check, (b) call graph, (c) C before C++, (d) ambiguous; never empties a group; no unique row for the C++ stubs undefmbr, undefed or fatalerr in the real runs"
    requirement: CID-04
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_libmatch.py -k 'data_check or call_graph or c_before_cpp or still_tied or never_drops'"
        status: pass
      - kind: integration
        ref: "real runs + `! grep -hE ',(undefmbr|undefed|fatalerr),[^,]*,[^,]*,[^,]*,unique,'` on both CSVs"
        status: pass
    human_judgment: false
  - id: D5
    description: "libmatch verb: manifest name or stem, --orig/--manifest/--watcom-dir/--versions, --write xor --output, --json; refuses unknown EXE, orig mismatch, missing orig, output inside orig, empty tree"
    requirement: CID-04
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_cli.py -k libmatch (11 tests; first written as 12, corrected in Review fix round 1)"
        status: pass
    human_judgment: false

duration: 21min
completed: 2026-10-21
status: complete
---

# Phase 4 Plan 05: Masked Library Matcher Summary

**`reverseapoc libmatch` places whole Watcom LIB386 CODE segments (10.5, 10.6 and 11.0) in each EXE's code object, masked on both sides. It merges matches per range into library and version sets, drops contained ranges, resolves identical bodies by data, call-graph and C-before-C++ evidence, and writes the D-06 runtime.csv. The real runs place 121 ranges in UFO2P and 132 in TACP, with `_cstart_` at the LE entry in both.**

## Performance

- **Duration:** 21 min
- **Started:** 2026-10-21T16:24:25Z
- **Completed:** 2026-10-21T16:45:09Z
- **Tasks:** 3 (all TDD; Task 1 is the tracer)
- **Files modified:** 8 (3 created, 5 modified)

## Accomplishments

- `tools/reverseapoc/libmatch.py` with the KKND-Decomp CC0 derivation header on line 1. It anchors each segment on its longest unmasked run, finds every occurrence in the code object and verifies each one in full (`verify_at`). Identical segments are searched once: one real run over all three LIB386 trees takes about 31 s.
- `runtime.csv` (D-06) writer, reader and path helper; `targets.config_dir` (D-16).
- The `libmatch` verb, with the orig file checked against the manifest before parsing. `OMFError` and `LibMatchError` are now mapped in `cli.main`.
- The `build_le_image(patches=...)` overlay in conftest, mapped through the object table and the page map.

## Real smoke runs (counts and names only)

> Review fix round 1 (2026-10-21, at the end of this file) changes TACP's rule (b) and ambiguous counts, and corrects the fprintf/sprintf sentence and the rule (b) observation below. This section is kept as first written.

Inputs: the main checkout's `orig/` and `third_party/watcom` (read-only), all three swept versions, MIN_UNMASKED 16. Output: `build/libmatch-smoke/` only.

| | UFO2P | TACP |
|---|---:|---:|
| Ranges | 121 | 132 |
| Bytes covered (of the code object) | 43,958 of 785,117 | 46,055 of 795,983 |
| `_cstart_` row (module `cstrt386`, DOS/CLIB3R.LIB, 10.5;10.6) | 0x000C0784 = entry VA | 0x000C28B0 = entry VA |
| Versions 10.5;10.6;11.0 (uninformative) | 58 | 62 |
| 10.5;10.6 | 51 | 57 |
| 10.6;11.0 | 1 | 2 |
| 10.6 only | 11 | 11 |
| Any row without 10.6 | 0 | 0 |
| Skipped: not OMF | 160 | 160 |
| Skipped: short (segment owners under 16 unmasked bytes) | 10,141 | 10,141 |
| Skipped: unmaskable / parse error / no LIB386 | 0 / 0 / 0 | 0 / 0 / 0 |
| Dropped (strictly contained) | 1 (`fatalerr` inside CLIB's fatal-error range) | 1 (`fatalerr`) |
| Partial overlaps | 0 | 0 |
| Resolved by rule (a) data / (b) calls / (c) C before C++ | 0 / 1 / 0 | 0 / 1 / 0 |
| Still ambiguous | 14 | 13 |

- 10.6-only modules in UFO2P: sprintf, ftell, memalloc, prtf, initargv, grownear, chk8087, cinit, efgfmt, close, ftos. TACP has the same eleven. This matches the research prototype's version pattern at threshold 16 (11 10.6-only, none without 10.6). The prototype's 122 UFO2P ranges are 121 here because `fatalerr` is now dropped as contained.
- Rule (b) resolved `puts` against NT/CLIB3R's `uputs` (in both EXEs).
- Rule (a) resolved nothing here: the Pitfall 4 18-byte stubs (`noefgfmt`, `nomem`, `undefmbr`, `undefed`) fall under 16 unmasked bytes and are recorded as `short`. `fatalerr` is dropped as contained. No unique row names undefmbr, undefed or fatalerr.
- Remaining ambiguous rows, by module (alternative): cstart (cstrt386), _strcmp (cmp386), atoi (atol), stk (stk386), dosdrive (drive386, UFO2P only), ddisk386 (dosdisk, UFO2P only), dosfind (find386), int386xa (intxa386), ini87386 (init8087), mbscat (strcat), dosio (io386), chainint (chint386), amodf (amodf386), i64tos (i64ts386), fprintf (sprintf, TACP only). Most of these are one module renamed between 10.x and 11.0, e.g. `cmp386` -> `_strcmp`. Their rows now carry every version that matched. `atoi`/`atol` and `fprintf`/`sprintf` are true identical bodies in one library.

### Rule (a) assumption check (flagged in the plan)

I ran a read-only probe that applies the data check to every real hit (all groups, before disambiguation). In UFO2P, 102 hits have at least one data reference, and all 102 pass. The addend rule (segment VA = LE target - OMF displacement - the u32 stored at the site) holds on the real libraries, so rule (a) does not fail true matches.

### Rule (b) observation

The same probe found the call-graph check flagging some true matches: `initfile` (single module, unaffected) and both `stk` and `stk386` in their two-module group. In each case an extern call lands on a range start whose publics do not carry that extern's name. When every candidate fails, all are kept, so no row changed. Still, rule (b) is evidence that can be wrong; it never decides a group alone against a passing alternative.

## Task Commits

1. **Task 1: Tracer - libmatch finds a planted module and writes runtime.csv** - `1cda9d4` (test, RED), `ab039e2` (feat, GREEN). Tracer gate: interactive, `end-of-phase`, automated-only verify. I re-ran it (257 passed, ruff clean, real UFO2P smoke exit 0 with `_cstart_` at the entry VA) and continued.
2. **Task 2: Rejection rules, skip records, merge and overlaps** - `3590650` (test, RED), `15df920` (feat, GREEN), then `1dfcaae` (test, RED) and `551aa0f` (fix, GREEN) for the version union.
3. **Task 3: Disambiguation** - `83b7d9b` (test, RED), `a246bf4` (feat, GREEN).

### RED evidence (semantic assessment)

- Task 1: `test_libmatch.py` and `test_targets.py` failed at collection (`cannot import name 'libmatch'`, `'config_dir'`): new module, new function. That is a load failure, not an assertion failure, so it is recorded here and not hidden. The 11 CLI tests failed on the planned behavior: `build_le_image()` got an unexpected `patches`, and `libmatch` is not a known subcommand.
- Task 2: 7 new tests failed on their planned assertions. No short or unmaskable skip was recorded, the merge order was wrong (`NT/PMATH.LIB` came before `PMATH.LIB`), the contained range was kept, a partial overlap gave `DID NOT RAISE`, there was no `no LIB386 directory` skip, and the CSV rows came out unsorted. Six passed on arrival because the plan builds those rules in Task 1 (`verify_at` rejections, not-OMF/parse-error skips) or they are inherent in Task 1's grouping (version merge, touching ranges). They pin existing behavior.
- Version union: `assert ('11.0',) == ('10.6', '11.0')`, the planned assertion.
- Task 3: 3 tests failed on their planned assertions (data check, call graph and C before C++ each gave `ambiguous`). `still_tied` and `never_drops` passed on arrival, because Task 1's interim rule already produced that row.

## Files Created/Modified

- `tools/reverseapoc/libmatch.py` - matcher, report, runtime.csv I/O, disambiguation, verb helpers (`select_target`, `read_target`, `check_versions`, `refuse_output`).
- `tools/reverseapoc/targets.py` - `config_dir(name)`.
- `tools/reverseapoc/cli.py` - `libmatch` subcommand, `_cmd_libmatch`, `LibMatchError`/`OMFError` in `_ERRORS`, docstring.
- `tests/conftest.py` - `build_le_image(patches=...)`, `_patch_offset`.
- `tests/libtree.py` - synthetic LIB386 tree, module, EXE and CLI workspace builders.
- `tests/test_libmatch.py` - 28 tests; `tests/test_targets.py` - `test_config_dir`; `tests/test_cli.py` - 12 libmatch tests.

## Decisions Made

See `key-decisions` in the frontmatter. The version union needs a reviewer's eye most, because it is what makes D-07 readable in ambiguous rows.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ambiguous rows listed only the chosen module's versions**
- **Found during:** Task 2 real smoke run
- **Issue:** Modules renamed between versions (cmp386 in 10.x, `_strcmp` in 11.0) form one group with two module names. The row showed only the alphabetically first name's version, so `_strcmp`, `cstart`, `stk` and others read as 11.0-only. That contradicts the plan's truth that a row's versions are "the sets of every library and version that matched".
- **Fix:** libraries, versions and publics are the union over every candidate left after disambiguation; module and alternatives are unchanged.
- **Files modified:** tools/reverseapoc/libmatch.py, tests/test_libmatch.py
- **Verification:** `test_row_versions_and_libraries_cover_every_candidate` went RED, then GREEN. Real runs: no row without 10.6.
- **Committed in:** `1dfcaae` (test), `551aa0f` (fix)

**2. [Rule 2 - Missing critical] Verb input and output guards**
- **Found during:** Task 1
- **Issue:** T-04-21 asks that output never lands in orig/ or third_party/. A wrong `--watcom-dir` would also have written an empty runtime.csv.
- **Fix:** `refuse_output` (inside `--orig` or `--watcom-dir`), `check_versions` (bare directory names), and a refusal when no OMF library loads. `read_target` reads the orig file once, hashes it and then parses those same bytes.
- **Committed in:** `ab039e2`

**3. [Minor] tests/libtree.py added**
- It holds the synthetic tree and EXE builders shared by `test_libmatch.py` and `test_cli.py` (the plan's file list named only the test files).

**4. [Minor] LibMatchReport.resolved and TargetView.image/fixup_targets**
- These are extra fields with defaults, needed by rules (a) and (b) and by the per-rule counts this SUMMARY reports.

---

**Total deviations:** 4 (1 bug, 1 missing critical, 2 minor additions)
**Impact on plan:** Every planned artifact, behavior and test exists. The version union changes how ambiguous rows read, not which ranges are found.

## Issues Encountered

- The worktree sandbox refuses `$(git rev-parse ...)` inside a command. I ran the plan's real commands with the resolved paths `C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/orig` and `.../third_party/watcom` (read-only).
- Open observation, not acted on: C++ runtime code in COMDAT blocks is not scanned. The plan matches CODE segments only. Plan 04-09 (cppscan) should decide whether `Module.comdats` needs the same matcher.
- Open observation: most ambiguous rows are cross-version renames, not identical bodies within one library. A later rule could call a group unique when no single version contributes two module names. That is beyond rules (a)-(d) as planned, so they stay visibly ambiguous for 04-07 to judge.

## User Setup Required

None.

## Next Phase Readiness

- 04-07 can run `uv run reverseapoc libmatch UFO2P.EXE --write` and `TACP.EXE --write` and commit `config/ufo2p/runtime.csv` and `config/tacp/runtime.csv` with a drift test (`read_runtime_csv`, `format_runtime_csv`).
- Verification: `uv run pytest -q` gives 664 passed, 56 skipped, and `uv run ruff check .` is clean.

## Self-Check: PASSED

- Files: tools/reverseapoc/libmatch.py, tests/test_libmatch.py, tests/libtree.py, this SUMMARY: present. `head -n 1 tools/reverseapoc/libmatch.py` starts with `# Derived from KKND-Decomp tools/lib_match.py (CC0 1.0)`. `grep -n "def config_dir" tools/reverseapoc/targets.py` prints a line.
- Commits on this branch since 5f2d186: 1cda9d4, ab039e2, 3590650, 15df920, 1dfcaae, 551aa0f, 83b7d9b, a246bf4 (8 task commits), plus this SUMMARY's docs commit.
- Acceptance: the plan's pytest selections for Tasks 1-3 exit 0; `libmatch --help` lists all seven options (`test_libmatch_help_lists_options`); both real runs exit 0 with `_cstart_` at the entry VA; no unique undefmbr/undefed/fatalerr row.

## Review fix round 1 (2026-10-21)

The plan review found one defect in rule (b) (Q1), two SUMMARY claims the evidence does not support (S1, S2) and a missing negative test that 04-07 relies on (M3). The sections above are kept as first written; only the D5 test count in the frontmatter is corrected in place, and it says so.

### Changes

- `c95e950` fix(04-05): rule (b) keyed each candidate's publics by range start only, and built that map from every group, including ranges later dropped as contained. Containment is now decided on the raw (start, end) groups first (`_split_contained`). The rule (b) map (`_public_addresses`) is built from the surviving groups, with each public at its range start plus its offset. New tests: `test_call_graph_target_is_a_public_inside_a_range` (on the old code the row stayed ambiguous) and `test_call_graph_ignores_a_contained_range` (on the old code the wrong module came out unique).
- `cc5f52c` test(04-05): `read_runtime_csv` refuses a wrong header and a start cell that is not hex (bad digit, empty, `h` suffix). Both tests fail when the header check or the ValueError wrap is removed.

### Corrections

- **fprintf/sprintf (S1).** "`fprintf`/`sprintf` are true identical bodies in one library" is wrong. TACP's group at 0x000C3665..0x000C3686 was fprintf (10.5, 10.6, 11.0) against **11.0's** sprintf. Their masked extern calls differ: fprintf calls `__fprtf_`, 11.0's sprintf calls `vsprintf_`. Both calls land at 0x000C99BC, where `__fprtf_` is the public, 0x11 bytes into the fprtf range at 0x000C99AB. The 10.6 sprintf has its own row at 0x000C32B2. With the fix, rule (b) resolves the group to fprintf. The atoi/atol half of the sentence stands: both rows' candidates share every library and version.
- **Rule (b) observation (S1).** The false flags on stk, stk386 and initfile came from the evidence-map defect, not from the rule. Their call to `__fatal_runtime_error_` (xmsg + 5: 0x000C6B0E in UFO2P, 0x000C9518 in TACP) hit the start of the dropped C++ `fatalerr` range. After the fix, a read-only probe that applies rule (b) to every real hit flags only `uputs` (the NT alternative that `puts` beats), 11.0's `sprintf` at TACP 0x000C3665, and `fatalerr` in its dropped range.
- **CLI test count (S2).** `tests/test_cli.py -k libmatch` collects 11 tests, not 12. `tests/test_libmatch.py` now holds 34 (the 28 above, 2 call-graph tests and 4 CSV refusal cases).

### Re-run

Same command lines and inputs as above, output in `build/libmatch-smoke/` only.

| | UFO2P | TACP |
|---|---:|---:|
| Ranges | 121 (unchanged) | 132 (unchanged) |
| Bytes covered (of the code object) | 43,958 of 785,117 | 46,055 of 795,983 |
| Skipped: not OMF / short | 160 / 10,141 | 160 / 10,141 |
| Dropped (strictly contained) | 1 (`fatalerr` at 0x000C6B0E) | 1 (`fatalerr` at 0x000C9518) |
| Resolved by rule (a) data / (b) calls / (c) C before C++ | 0 / 1 / 0 | 0 / 2 / 0 |
| Still ambiguous | 14 | 12 |

- UFO2P's CSV is identical to the first run. TACP's differs in one row: 0x000C3665 is now `fprintf`, `unique`, publics `fprintf_`, no alternatives. Before, it was `ambiguous` with publics `fprintf_;sprintf_` and three `sprintf@.../CLIB3R.LIB` alternatives. This reproduces the reviewer's in-memory what-if.
- Version tallies are unchanged in both EXEs. `_cstart_` is still at the entry VA, and no unique row names undefmbr, undefed or fatalerr.
- Remaining ambiguous rows: the list in "Real smoke runs" names 15 modules across both EXEs. UFO2P's 14 are all of them except fprintf. TACP's 12 also lack dosdrive and ddisk386.
- Verification: `uv run pytest -q` gives 772 passed, 7 skipped, and `uv run ruff check .` is clean.

---
*Phase: 04-compiler-identification*
*Completed: 2026-10-21*
