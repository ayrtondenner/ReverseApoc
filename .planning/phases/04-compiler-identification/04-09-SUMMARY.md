---
phase: 04-compiler-identification
plan: 09
subsystem: tooling
tags: [cppscan, cid-06, xi-yi, inirt386, libmatch, omf, le, watcom, python, stdlib]

requires:
  - phase: 04-compiler-identification
    provides: "04-05 libmatch (scan_exe, load_libraries, read_runtime_csv, runtime_csv_path, MatchRange, CPP_LIBRARY_PREFIXES, STATUS_UNIQUE, check_versions, select_target, read_target)"
  - phase: 04-compiler-identification
    provides: "04-02 omf.read_library (Segment.fixups with segment_relative/target_kind/target_name)"
provides:
  - "tools/reverseapoc/cppscan.py: XI/YI init tables located through the matched inirt386 module, priority classification, C++-only runtime rows, __wcpp_/W? string counts, vtable-shaped candidate runs, one verdict per EXE"
  - "`uv run reverseapoc cppscan EXE [--orig] [--manifest] [--watcom-dir] [--runtime CSV] [--json]`; CppScanError mapped in cli.main"
  - "tests/cpptree.py: synthetic inirt386 module and EXE with XI/YI tables"
  - "Real CID-06 result: UFO2P and TACP both C (wcc386)"
affects: [04-11 toolchain.md CID-06 write-up, phase-05 per-file compiler choice]

actuals:
  tokens: 8600
  tasks: 2
  commits: 4
plan_head_before: 7088b0f9524174b8cbf559a42c5eb5a999d7f155
plan_head_after: a6cb965f46cb647caa42cb2e2fc81d55d620c88f

tech-stack:
  added: []
  patterns:
    - "Table bounds come from the LE fixups at a matched library module's own segment-relative fixup sites (the address the runtime code itself uses)"
    - "Each signal is computed on its own; only XI 64, YI 40, unique C++-only rows and __wcpp_/W? strings decide; vtable-shaped runs are listed"
    - "The report states what a signal does not cover (COMDAT code) next to its count"

key-files:
  created:
    - tools/reverseapoc/cppscan.py
    - tests/cpptree.py
    - tests/test_cppscan.py
    - tests/test_cppscan_real.py
  modified:
    - tools/reverseapoc/cli.py
    - tests/test_cli.py

key-decisions:
  - "The C++-only-module signal covers CODE segments only, like libmatch; COMDAT code is not matched. The report and JSON say so (`CODE segments only; COMDAT code is not matched`). Probe: in 10.5/10.6 PLIB3R about 13% of code bytes (5.5k of 42k) sit in COMDATs and 320 of 336 modules have a CODE segment, so the signal covers most of the C++ runtime but not all of it"
  - "The table bounds are the LE fixup targets at the inirt386 sites (what __InitRtns iterates), with no displacement or addend correction; every site for one bound must agree, else CppScanError"
  - "The inirt386 module is re-read from the row's first library and version; the library path must stay inside <watcom>/<version>/LIB386"
  - "CppScanReport gains a `bounds` field (table -> start, end) so format() and to_json() show the table addresses even for an empty table"
  - "cppscan exits 0 for either verdict; a missing runtime map is an error naming `uv run reverseapoc libmatch <NAME> --write`"

patterns-established:
  - "tests/cpptree.py: made-up inirt386 body planted with 0xEE at its four bound sites; entries are (type 0, priority, pointer) with an LE off32 fixup at each pointer"

requirements-completed: [CID-06]

coverage:
  - id: D1
    description: "init_tables finds XI and YI through the inirt386 row's segment-relative fixups and the LE fixups at the same sites, and reads 6-byte entries relocated; bad length, table outside the data object, missing inirt386, missing LE fixup and a library path leaving the tree raise CppScanError"
    requirement: CID-06
    verification:
      - kind: unit
        ref: "tests/test_cppscan.py#test_init_tables_through_inirt386, test_bad_table_length, test_table_outside_the_data_object, test_missing_inirt386, test_missing_le_fixup_at_a_bound_site, test_library_path_must_stay_in_the_tree"
        status: pass
    human_judgment: false
  - id: D2
    description: "Verdict: C (wcc386) with the counts behind it, or C++ evidence naming the signals and the modules needing wpp386; vtable-shaped runs never decide; empty tables give C with zero counts"
    requirement: CID-06
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_cppscan.py -k 'verdict or priority or cpp_only or string_counts or vtable or empty_tables or format' (all 18 tests in the file pass)"
        status: pass
    human_judgment: false
  - id: D3
    description: "cppscan verb: --orig, --manifest, --watcom-dir, --runtime, --json; refuses a missing runtime map naming the libmatch command, refuses an orig mismatch, exits 0 for a C++ verdict"
    requirement: CID-06
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_cli.py -k cppscan (6 tests)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Real: UFO2P and TACP both report C (wcc386): no XI priority 64, no YI priority 40, no C++-only runtime row, no __wcpp_ or W? strings"
    requirement: CID-06
    verification:
      - kind: integration
        ref: "REVERSEAPOC_ORIG=<main>/orig REVERSEAPOC_WATCOM_DIR=<main>/third_party/watcom uv run pytest -q -rs tests/test_cppscan_real.py (4 passed, no skip)"
        status: pass
      - kind: integration
        ref: "uv run reverseapoc libmatch UFO2P.EXE --output build/cppscan/ufo2p.csv, then cppscan UFO2P.EXE --runtime build/cppscan/ufo2p.csv (and TACP): both print C (wcc386)"
        status: pass
    human_judgment: false

duration: 11min
completed: 2026-10-21
status: complete
---

# Phase 4 Plan 09: C vs C++ Scan Summary

**`reverseapoc cppscan` finds the XI and YI tables through the matched `inirt386` module and sorts their entries by priority. It also counts C++-only runtime rows, `__wcpp_`/`W?` strings and vtable-shaped pointer runs, then gives one verdict per EXE. UFO2P and TACP both come out `C (wcc386)`, which settles CID-06.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-10-21T17:31:39Z
- **Completed:** 2026-10-21T17:42:36Z
- **Tasks:** 2 (both TDD; Task 1 is the tracer)
- **Files modified:** 6 (4 created, 2 modified)

## Accomplishments

- `tools/reverseapoc/cppscan.py`. `table_bounds` finds the `inirt386` row and re-reads that module's CODE segment from the row's first library and version. It follows each segment-relative fixup to XIB/XIE/YIB/YIE through the LE fixup at `row.start + offset`. Each table must be a whole number of 6-byte entries inside a non-executable object. `init_tables` reads the entries (type, priority, routine) from `load_flat(relocate=True)` and flags routines that fall inside a runtime-map range.
- The other signals: `cpp_only_modules`, `string_counts` (counts only) and `vtable_candidates`. `verdict` decides on XI 64, YI 40, unique C++-only rows and `__wcpp_`/`W?` strings. Vtable-shaped runs only appear as a count.
- The `cppscan` verb sits next to `libmatch` in cli.py. `CppScanError` is mapped in `main()`.

## Real results (counts, priorities and addresses only)

> Review fix round 1 (2026-10-21, at the end of this file) adds a second verdict form for a scan whose C++-only module signal could not be computed. Both real EXEs still print the full form below. This section is kept as first written.

Inputs: the main checkout's `orig/` and `third_party/watcom` (10.5, 10.6, 11.0), read-only. The runtime map was computed live in the real test, and for the CLI check it went to `build/cppscan/<exe>.csv` (gitignored).

| | UFO2P | TACP |
|---|---|---|
| Verdict | C (wcc386) | C (wcc386) |
| XI table | 0x0013E11C..0x0013E158, 10 entries | 0x002B63D6..0x002B6412, 10 entries |
| XI priorities | 1 (thread) x1, 2 (fpu) x1, 3 x1, 32 (library) x7 | same |
| XI routines inside the runtime map | 8 of 10 | 8 of 10 |
| YI table | 0x0013E158..0x0013E164, 2 entries | 0x002B6412..0x002B641E, 2 entries |
| YI priorities | 1 (thread) x1, 32 (library) x1 | same |
| YI routines inside the runtime map | 1 of 2 | 1 of 2 |
| XI priority 64 / YI priority 40 | 0 / 0 | 0 / 0 |
| C++-only runtime rows (CODE segments only) | none | none |
| `__wcpp_` strings / `W?` strings | 0 / 0 | 0 / 0 |
| Vtable-shaped candidate runs | 5 | 3 |

Verdict lines as printed:

- `UFO2P.EXE: C (wcc386): no XI priority 64, no YI priority 40, no C++-only runtime module, no __wcpp_ or W? strings; 5 vtable-shaped candidate runs (C dispatch tables look the same)`
- `TACP.EXE: C (wcc386): no XI priority 64, no YI priority 40, no C++-only runtime module, no __wcpp_ or W? strings; 3 vtable-shaped candidate runs (C dispatch tables look the same)`

The table addresses and priority profiles match the research prototype (04-RESEARCH.md Pattern 7). Priority 3 matches no rtprior.h constant, so the scan reports it as the number 3 (assumption A4: unknown values are reported, not mapped). In each table, one or two routines point outside the runtime map. The research identified one of them as the thread-init routine just past the runtime, probably a short CLIB module that libmatch did not place.

## Task Commits

1. **Task 1: Tracer - cppscan reads the XI/YI tables through inirt386 and prints a verdict:** `87c528d` (test, RED), `a046803` (feat, GREEN). Tracer gate: the run is interactive, the mode is `end-of-phase` and the verify is automated-only. I re-ran it: 75 synthetic tests passed, the 2 real tests passed with no skip, and the real CLI check printed `C (wcc386)` for both EXEs. Then I continued to Task 2.
2. **Task 2: C++-only runtime rows, mangled strings and vtable-shaped candidates:** `a0808ad` (test, RED), `a6cb965` (feat, GREEN).

### RED evidence (semantic assessment)

- Task 1: `test_cppscan.py` and `test_cppscan_real.py` failed at collection with `No module named 'reverseapoc.cppscan'`, because the module is new. That is a load failure, not an assertion failure, and I record it as one. The 6 CLI tests failed on the planned behavior: `cppscan` was not a subcommand (argparse exit 2), and `--help` printed nothing. The other 59 CLI tests stayed green.
- Task 2: 7 of the 18 tests failed. `cpp_only_modules`, `string_counts` and `vtable_candidates` failed with AttributeError (the functions were missing; I referenced them through the module so the Task 1 tests kept running). Four verdict and format tests failed on their planned assertions. `test_empty_tables` passed on arrival because Task 1 already reads empty tables and the counts default to zero, so it pins existing behavior. The real `test_no_cpp_signals` also passed on arrival, because Task 1's `scan` left those fields at their defaults. It only became a real check with the GREEN commit, and it passed after that.
- I did not run the GSD RED classifier (`check tdd-red-evidence`): pytest's text report is not one of its formats. The assessments above come from the actual runs.

## Files Created/Modified

- `tools/reverseapoc/cppscan.py`: the scan, report, signals and verdict.
- `tools/reverseapoc/cli.py`: the `cppscan` subcommand, `_cmd_cppscan`, `CppScanError` in `_ERRORS`, and the docstring.
- `tests/cpptree.py`: the synthetic inirt386 library and EXE builders.
- `tests/test_cppscan.py`: 18 tests. `tests/test_cppscan_real.py`: 2 tests x 2 EXEs. `tests/test_cli.py`: 6 cppscan tests.

## Decisions Made

See `key-decisions` in the frontmatter. The COMDAT decision is the one to read with the verdict: "no C++-only runtime module" means no CODE-segment match. It says nothing about C++ runtime code that only exists in COMDATs. The XI/YI and string signals do not depend on the runtime map, and all of them are zero.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Library path guard and per-site consistency**
- **Found during:** Task 1
- **Issue:** The runtime CSV names the library and version that cppscan opens. A tampered row could point outside the Watcom tree. Two sites for the same bound could also disagree without anyone noticing.
- **Fix:** The version must be a bare name (`check_versions`) and the resolved library path must stay under `<watcom>/<version>/LIB386`. Bound sites that disagree raise CppScanError. Tests: `test_library_path_must_stay_in_the_tree`, `test_missing_le_fixup_at_a_bound_site`.
- **Committed in:** `a046803`

**2. [Minor] tests/cpptree.py added, and a `bounds` field on CppScanReport**
- The plan's file list names only the test files. The builders live in their own helper (not libtree.py), so they do not conflict with other wave-3 plans and test_cli.py can share them.
- `bounds` (with a default) lets the report show table addresses even when a table is empty. `table_bounds` is public, and `init_tables` composes it with the entry reader.

**3. [Minor] Extra tests beyond the plan's list**
- `test_destructor_priority_is_cpp_evidence`, `test_table_outside_the_data_object` (T-04-32), `test_cpp_verdict_without_modules_says_so`, `test_format_lists_every_signal_count`, `test_report_holds_counts_addresses_and_names_only`. In the CLI: default runtime path, verdict output, a C++ verdict still exiting 0, orig refusal, and help.

---

**Total deviations:** 3 (1 missing critical, 2 minor additions)
**Impact on plan:** Every planned artifact, behavior and test exists. The additions are guards and tests.

## Issues Encountered

- The worktree sandbox refuses `$(git rev-parse ...)` in commands and writes into the shared `.git` directory. I ran the plan's real commands with `../../../orig` and `../../../third_party/watcom` (read-only), and took the plan base (7088b0f) from the dispatch rather than from an on-disk ledger.
- My first scripted edit of cli.py wrote CRLF line endings (Python text mode on Windows). I normalized it to LF before the commit.

## User Setup Required

None.

## Next Phase Readiness

- 04-11 can write CID-06 into docs/toolchain.md "C, not C++" from the verdict lines and the table above. Both EXEs are C (wcc386), and no module needs wpp386.
- Open: C++ runtime code that lives only in COMDATs is not matched (see Decisions). If phase 5 ever has reason to doubt the C verdict for one file, matching `Module.comdats` the way libmatch matches segments would close that gap.
- Verification: `uv run pytest -q` gives 734 passed, 73 skipped, and `uv run ruff check .` is clean.

## Self-Check: PASSED

- Files present: tools/reverseapoc/cppscan.py, tests/cpptree.py, tests/test_cppscan.py, tests/test_cppscan_real.py, this SUMMARY. `grep -n "class CppScanError(ValueError)" tools/reverseapoc/cppscan.py` prints line 30.
- The task commits 87c528d, a046803, a0808ad and a6cb965 are all ancestors of HEAD (`git rev-list --count 7088b0f..a6cb965` = 4). No commit deletes a file. The working tree is clean.
- Acceptance: `uv run pytest -q tests/test_cppscan.py` gives 18 passed. The `-k "cpp_only or string_counts or vtable or cpp_verdict or empty_tables"` selection gives 7 passed. The real tests give 4 passed with no SKIPPED line. `cppscan --help` lists `--orig`, `--manifest`, `--watcom-dir`, `--runtime` and `--json`. `uv run pytest -q && uv run ruff check .` gives 734 passed, 73 skipped, and ruff is clean.


## Review fix round 1 (2026-10-21)

The plan review found one Important defect: the C++-only-module signal read only the runtime map, and nothing recorded whether the sweep that built the map held any C++ library. A map built from a tree without PLIB/PLBX/CPLX, or with those libraries skipped as unreadable, still gave `C (wcc386)` for a signal that was never computed. The real verdict was sound (52 C++ libraries loaded, none skipped), but 04-11 writes this verdict into toolchain.md. Two minors were folded in. The sections above are kept as first written.

### Changes

- `9c81fa7` fix(04-09), one commit with its tests:
  - **Important (signal not computed).** `scan` now calls `cpp_only_gap(rows, watcom_dir)`. For every Watcom version the runtime map names, `<watcom>/<version>/LIB386` must hold C++ libraries (file name starting PLIB, PLBX or CPLX) and each must parse completely: not an OMF library, a parse error and any unparsed module (what `libmatch.load_libraries` would record as skipped) all count as a gap. A version name that is not a bare directory name raises CppScanError, as before. The reason is stored in `CppScanReport.cpp_only_gap` (empty when the signal was computed) and shown in the text report (`C++-only runtime rows: not computed (...)`) and the JSON (`cpp_only_modules_computed`, `cpp_only_modules_gap`).
  - **Minor 1 (W? end to end).** `test_mangled_names_alone_are_cpp_evidence`: an EXE whose only signal is one `W?abc$` string gets a `C++ evidence:` verdict naming `W? strings x1`. With the `W? strings` entry deleted from `_signals` it fails.
  - **Minor 2 (library/version pairing).** `_init_segment` no longer pairs `row.libraries[0]` with `row.versions[0]`. It tries the (version, library) pairs in row order, versions outermost, keeps the pairs whose library file exists in that version's LIB386, and takes the first one that holds the module's CODE segment. It refuses when no pair exists ("... not found in Watcom ...") or no existing pair holds the segment ("no inirt386 CODE segment ... in <pairs tried>").

### Verdict wording

| Situation | Verdict |
|---|---|
| Every signal computed, none fired | `C (wcc386): no XI priority 64, no YI priority 40, no C++-only runtime module, no __wcpp_ or W? strings; N vtable-shaped candidate runs (...)` |
| C++-only module signal not computed, nothing else fired | `C (wcc386) on partial evidence: the C++-only runtime module signal was not computed (<gap>); no XI priority 64, no YI priority 40, no __wcpp_ or W? strings; N vtable-shaped candidate runs (...)` |
| Any signal fired | `C++ evidence: ...; modules needing wpp386: <names, or "not located (no C++-only runtime rows)", or "not located (C++-only runtime module signal not computed)">` |

The XI/YI tables and the strings are always computed (a failure raises), so the verdict is never left undetermined and "undetermined" is not a verdict form. Only the first form is a full C verdict: plan 04-11 should cite it, and treat anything starting `C (wcc386) on partial evidence` as unconfirmed. The real tests now match `C (wcc386): ` with the colon, so the partial form cannot pass them.

### Covering tests

- `tests/test_cppscan.py` (18 -> 32 tests): no C++ library, an unreadable one (not OMF), one with an unparsed module, a second version named by the map that holds none, a version without a LIB386 tree, a C++ verdict with the gap (modules "not located (... not computed)"), a version name leaving the Watcom dir, a map naming no version; the `W?`-only verdict; five pairing tests (first version lacks the library, first library missing, library present but another module in 10.5, no pair exists, no pair holds the module). The shared `watcom` fixture now also holds a readable C++ library (`tests/cpptree.py: write_cpp_lib`), and the C verdict tests match `C (wcc386): `.
- `tests/test_cli.py`: `test_cppscan_without_cpp_libraries_does_not_report_a_full_c_verdict` (text and JSON); the other cppscan CLI tests use a workspace with a C++ library.
- `tests/test_cppscan_real.py` (4 -> 5 tests): `test_cpp_libraries_were_swept_and_none_was_skipped` asserts that every swept version loaded at least one PLIB/PLBX/CPLX library and that no C++ library is in the skip list; `test_verdict_is_c` also asserts `cpp_only_gap == ""`.
- On the old code, 13 tests failed (12 new ones and `test_c_verdict`, which now also reads `cpp_only_gap`). The failures were the intended ones: a full C verdict with no C++ library, and "not found" for an absent first pairing. Removing `W? strings` from `_signals` fails the W? test, and making `scan` pass `cpp_only_gap=""` fails 8 tests (7 synthetic, 1 CLI).

### Re-run

Real inputs read-only (the main checkout's `orig/` and `third_party/watcom`); the runtime maps went to `build/cppscan/`.

- `uv run pytest -q -rs tests/test_cppscan_real.py` gives 5 passed, no SKIPPED line.
- Both verdict lines are unchanged and still the full form:
  - `UFO2P.EXE: C (wcc386): no XI priority 64, no YI priority 40, no C++-only runtime module, no __wcpp_ or W? strings; 5 vtable-shaped candidate runs (C dispatch tables look the same)`
  - `TACP.EXE: C (wcc386): no XI priority 64, no YI priority 40, no C++-only runtime module, no __wcpp_ or W? strings; 3 vtable-shaped candidate runs (C dispatch tables look the same)`
- The UFO2P map names versions 10.5, 10.6 and 11.0; each LIB386 holds C++ libraries and none is unreadable, so `cpp_only_modules_computed` is true. Pointing `--watcom-dir` at a scratch tree with only `DOS/CLIB3R.LIB` per version (scratchpad, outside the repo) gives `C (wcc386) on partial evidence: the C++-only runtime module signal was not computed (10.5: no C++ library ...; 10.6: ...; 11.0: ...)`.
- Cost: the check parses the 52 C++ libraries again, about 2.7 s per `cppscan` run on this host.
- Verification: `uv run pytest -q` gives 900 passed, 8 skipped, and `uv run ruff check .` is clean.

Not changed (out of scope for this round): review Minors 3 to 7, including the stale line-30 self-check above.

---
*Phase: 04-compiler-identification*
*Completed: 2026-10-21*
