---
phase: 03-byte-identical-round-trip
plan: 08
subsystem: tooling
tags: [python, tomllib, ntpath, pathlib, le, splice, rebuild, manifest]
gap_closure: true
gap_ids: [G-03-6]

requires:
  - phase: 03-byte-identical-round-trip
    provides: "03-06: splice.py rebuild path, RebuildResult/RebuildReport, the 8-key --json contract, the 03-03 refusal reasons"
provides:
  - "load_manifest reports invalid TOML, non-UTF-8 bytes and a wrong `targets` shape as ManifestError naming the manifest (IN-06)"
  - "targets.check_bare_name: a target name must be a bare file name on Windows and POSIX alike (IN-07); splice._check_bare_name delegates to it"
  - "Region.describe counts pages within the object: `page K of object M (logical page L), VA ...` (IN-01)"
  - "_unwritable_reason names the page: short-page hole vs page data past vsize (IN-02)"
  - "Corrected layout() docstring (IN-03)"
  - "RebuildResult.source and RebuildReport.manifest named by the MISSING and REFUSED lines, kept out of to_json (VN-01)"
affects: [03-10, phase-5-landing, phase-6-driver]

actuals:
  tokens: 5843
  tasks: 2
  commits: 4
plan_head_before: 0269b2ae4057c5a94e96266de82d24e510915def
plan_head_after: 09781cf53980dde5df05ffecf162f927cd29afac

tech-stack:
  added: []
  patterns:
    - "Manifest problems of every kind end as ManifestError, which cli.main already turns into one `reverseapoc <verb>: error:` line"
    - "Host-independent name checks through ntpath and the Pure path classes, never the host Path"
    - "Page labels count within the object; the logical and physical numbers appear only when they differ"

key-files:
  created: []
  modified:
    - tools/reverseapoc/targets.py
    - tools/reverseapoc/splice.py
    - tests/test_targets.py
    - tests/test_splice.py
    - tests/test_cli.py

key-decisions:
  - "check_bare_name lives in targets.py and runs in _parse_target, so check-orig, ingest and rebuild are all protected; rebuild_target keeps a guard for a hand-built Target, now raising ManifestError instead of SpliceError"
  - "check_bare_name also refuses an empty name, keeping the old splice guard's `not name` case for hand-built Targets"
  - "The page lookup in _unwritable_reason is a small _page_slot helper (next(..., None) over _object_pages); the caller has already established base <= addr < the page-backed end, so it always finds a page"
  - "A result formatted without a report (a direct rebuild_target caller) says `the manifest` in REFUSED instead of guessing the default path; a hand-built result with no source names the bare target name"

patterns-established:
  - "New report fields that are for people (paths) stay out of to_json, so the --json contract only changes on purpose"

requirements-completed: [RT-02, RT-03, RT-04]

coverage:
  - id: D1
    description: "IN-06: invalid TOML, non-UTF-8 bytes and four wrong `targets` shapes raise ManifestError naming the manifest; check-orig, rebuild and rebuild --json print one error line and exit 1"
    requirement: RT-04
    verification:
      - kind: unit
        ref: "tests/test_targets.py#test_malformed_manifest_raises_manifest_error"
        status: pass
      - kind: integration
        ref: "tests/test_cli.py#test_malformed_manifest_is_an_error_line"
        status: pass
    human_judgment: false
  - id: D2
    description: "IN-07: load_manifest refuses 14 names that are not bare on Windows and POSIX alike (directory, drive, . and .., reserved devices, wildcard, trailing dot or space); rebuild_target refuses a hand-built Target with ManifestError; the real manifest still loads"
    requirement: RT-04
    verification:
      - kind: unit
        ref: "tests/test_targets.py#test_manifest_refuses_a_non_bare_target_name"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_rebuild_target_refuses_a_non_bare_name"
        status: pass
      - kind: unit
        ref: "tests/test_targets.py#test_default_manifest_lists_the_three_targets"
        status: pass
    human_judgment: false
  - id: D3
    description: "IN-01: page labels count within the object (`page 1 of object 2 (logical page 3), VA 0x00020010`), object-1 labels unchanged, mismatch report and --json carry the new label"
    requirement: RT-03
    verification:
      - kind: unit
        ref: "tests/test_splice.py#test_region_labels_count_pages_within_the_object"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_mismatch_label_in_a_later_object"
        status: pass
      - kind: integration
        ref: "REVERSEAPOC_ORIG=<main>/orig uv run pytest -q -rs tests/test_splice_real.py tests/test_le_real.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "IN-02: refusal reasons name the page (short-page hole is not BSS; page data past vsize names its own page); the 03-03 substrings stay"
    requirement: RT-02
    verification:
      - kind: unit
        ref: "tests/test_splice.py#test_unwritable_reason_names_the_page"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_refuse_past_vsize_tail"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_refuse_bss_past_short_page"
        status: pass
    human_judgment: false
  - id: D5
    description: "IN-03: the layout() docstring says zero-length fixed regions are dropped while every page keeps its region (docstring only)"
    verification:
      - kind: other
        ref: "! grep -n 'Zero-length regions are left out' tools/reverseapoc/splice.py"
        status: pass
    human_judgment: true
    rationale: "A docstring rewording: no test can assert that the prose reads correctly; a reviewer confirms the sentence matches _page_regions and layout()"
  - id: D6
    description: "VN-01: MISSING and REFUSED name the input file rebuild checked and REFUSED the manifest it used; the 8 --json keys are unchanged"
    requirement: RT-04
    verification:
      - kind: unit
        ref: "tests/test_splice.py#test_rebuild_result_names_the_input_path"
        status: pass
      - kind: integration
        ref: "tests/test_cli.py#test_rebuild_refused_names_the_input_and_manifest"
        status: pass
      - kind: integration
        ref: "tests/test_cli.py#test_rebuild_missing_names_the_input"
        status: pass
      - kind: integration
        ref: "tests/test_cli.py#test_rebuild_json_refused_keeps_the_eight_keys"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-10-21
status: complete
---

# Phase 3 Plan 08: Manifest errors, bare names, page labels and real paths (G-03-6) Summary

**A malformed manifest or a non-bare target name is now one `reverseapoc <verb>: error:` line, with the name check the same on every host (ntpath.isreserved plus both Pure path classes). Mismatch labels and refusal reasons count pages within their object. REFUSED and MISSING name the file and manifest rebuild actually used. The 8-key --json contract is unchanged.**

## Performance

- **Duration:** about 9 min
- **Started:** 2026-10-21T02:28:28Z
- **Completed:** 2026-10-21T02:37:54Z
- **Tasks:** 2 (Task 1 tracer, Task 2 auto; both TDD)
- **Files modified:** 5

## Accomplishments

- IN-06: `load_manifest` re-raises `tomllib.TOMLDecodeError` and `UnicodeDecodeError` as `ManifestError(f"{path}: {exc}")`. It also refuses a `targets` value that is not an array of tables, so check-orig, rebuild (with and without --json) and ingest no longer print a traceback. A missing file stays an OSError. No JSON error status was added (WR-04 stays in Phase 6).
- IN-07: the public `targets.check_bare_name(name)` refuses an empty name, `.`, `..`, any name whose `PurePosixPath(...).name` or `PureWindowsPath(...).name` differs from the name itself, and any name `ntpath.isreserved` flags. `_parse_target` calls it and adds its `targets[i] (...)` prefix in one place. `splice._check_bare_name` delegates to it, so a hand-built Target is refused with ManifestError too. Both call sites stay.
- IN-01: the new `_page_label(obj, page)` helper gives `page K of object M`, followed by ` (logical page L)` when L != K. `Region.describe` uses it ahead of the existing `, VA 0x........` and ` (physical page P)` parts. Every object-1 label is unchanged.
- IN-02: `_unwritable_reason` keeps the "not in any object" and BSS reasons. Inside the page-backed range it now says `past the page data of page K of object M (0x... bytes)` for a short-page hole, and `past the end of object M (vsize V) in page K of object M` for page data past vsize. The pinned 03-03 substrings still match.
- IN-03: the layout() docstring now says that zero-length fixed regions are dropped and that every page keeps its region. Behaviour is unchanged.
- VN-01: `RebuildResult.source` (set by rebuild_target for every status) and `RebuildReport.manifest` (set by rebuild()) are named by the MISSING and REFUSED lines through `format(width, manifest=None)`. Neither field reaches `to_json`.

## Task Commits

1. **Task 1 RED: failing tests for malformed manifests and non-bare names** - `284b321` (test)
2. **Task 1 GREEN: IN-06 and IN-07** - `51a6efc` (fix)
3. **Task 2 RED: failing tests for within-object labels and real input paths** - `e1b02ca` (test)
4. **Task 2 GREEN: IN-01, IN-02, IN-03 and VN-01** - `09781cf` (fix)

GREEN hashes for 03-REVIEW-DISPOSITION.md (plan 03-10): IN-06 and IN-07 -> `51a6efc`; IN-01, IN-02, IN-03 and VN-01 -> `09781cf`.

**Plan metadata:** recorded in the docs(03-08) commit that adds this SUMMARY.

## RED evidence

### Task 1 (run at 0269b2a with the new tests, then committed as 284b321): 26 failed, 118 passed

| Test (ids) | Failure at HEAD |
|---|---|
| test_malformed_manifest_raises_manifest_error[invalid-toml] | `tomllib.TOMLDecodeError: Expected ']]' at the end of an array declaration` |
| ...[not-utf8] | `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 20` |
| ...[targets-int] | `TypeError: 'int' object is not iterable` (targets.py:101, enumerate) |
| ...[targets-str] | `AttributeError: 'str' object has no attribute 'get'` (targets.py:76) |
| ...[targets-array-of-ints] | `AttributeError: 'int' object has no attribute 'get'` |
| ...[targets-table] | `AttributeError: 'str' object has no attribute 'get'` (iterating the table's keys) |
| test_manifest_refuses_a_non_bare_target_name, all 14 ids | `Failed: DID NOT RAISE ManifestError` (every name loaded) |
| test_malformed_manifest_is_an_error_line[check-orig, rebuild, rebuild-json] | `tomllib.TOMLDecodeError` raised out of main() |
| test_rebuild_target_refuses_a_non_bare_name[NUL] | `DID NOT RAISE ManifestError` (rebuild_target returned a missing result) |
| ...[SUB/X.EXE] | `SpliceError: target name 'SUB/X.EXE' is not a bare file name` |
| ...[A:B] | `SpliceError: target name 'A:B' is not a bare file name` (this Windows host) |

Semantic assessment: each target test ran and failed on the planned behaviour (the wrong exception type, no exception, or a raise out of main()). None failed through a collection, import or fixture error.

### Task 2 (run at 51a6efc with the new tests, then committed as e1b02ca): 9 failed, 115 passed

| Test (ids) | Failure at HEAD |
|---|---|
| test_region_labels_count_pages_within_the_object | `'page 3 of object 2, VA 0x00020010' == 'page 1 of object 2 (logical page 3), ...'` |
| test_mismatch_label_in_a_later_object | the same object-2 label mismatch |
| test_unwritable_reason_names_the_page[short-page-hole] | got `0x10400 is in the BSS of object 1 (past its page data)` |
| ...[past-vsize-page-1] | got `0x10800 is past the end of object 1 (vsize 0x800) in its last page` |
| ...[past-vsize-page-2] | got `0x11000 ... in its last page` |
| ...[later-object] | got `0x21100 is past the end of object 2 (vsize 0x1100) in its last page` |
| test_rebuild_result_names_the_input_path | `AttributeError: 'RebuildResult' object has no attribute 'source'` |
| test_rebuild_refused_names_the_input_and_manifest | the line read `REFUSED   SYNTH.EXE  orig/SYNTH.EXE does not match config/targets.toml; ...` |
| test_rebuild_missing_names_the_input | the line read `MISSING   SYNTH.EXE  (orig/SYNTH.EXE not found; ...)` |

**JSON control:** test_rebuild_json_refused_keeps_the_eight_keys passed at 51a6efc (before VN-01) and still passes after it. The refused --json object has exactly JSON_KEYS and status "refused".

Semantic assessment: every failure is the planned assertion on the label, reason or line text. The one AttributeError is the planned "RebuildResult has no source field".

## Mutants (all applied one at a time after the GREEN commit, run, reverted; none committed)

| # | Mutant | Tests that failed |
|---|---|---|
| T1-1 | drop the `ntpath.isreserved` condition | test_manifest_refuses_a_non_bare_target_name[NUL, CON, nul.exe, COM1, LPT1.EXE, CONIN$, A., A , A*B]; test_rebuild_target_refuses_a_non_bare_name[NUL] (10 failed) |
| T1-2 | drop the `PureWindowsPath` comparison | test_manifest_refuses_a_non_bare_target_name[SUB\\X.EXE, A:B]; test_rebuild_target_refuses_a_non_bare_name[A:B] (3 failed) |
| T1-3 | drop the decode and parse wrap (`except ()`) | test_malformed_manifest_raises_manifest_error[invalid-toml, not-utf8]; test_malformed_manifest_is_an_error_line[check-orig, rebuild, rebuild-json] (5 failed) |
| T1-4 | drop the `targets` shape check | test_malformed_manifest_raises_manifest_error[targets-int, targets-str, targets-array-of-ints, targets-table] (4 failed) |
| T1-5 | put `splice._check_bare_name` back to its host-Path SpliceError form | test_rebuild_target_refuses_a_non_bare_name[NUL, SUB/X.EXE, A:B] (3 failed) |
| T2-1 | describe prints `page.logical` as the page number | test_region_labels_count_pages_within_the_object; test_mismatch_label_in_a_later_object (2 failed) |
| T2-2 | the page label never appends the logical page | test_region_labels_count_pages_within_the_object; test_mismatch_label_in_a_later_object; test_unwritable_reason_names_the_page[later-object] (3 failed) |
| T2-3 | the short-page case returns the BSS reason | test_unwritable_reason_names_the_page[short-page-hole] (1 failed) |
| T2-4 | MISSING and REFUSED go back to the fixed `orig/` and `config/targets.toml` text | test_rebuild_result_names_the_input_path; test_rebuild_refused_names_the_input_and_manifest; test_rebuild_missing_names_the_input (3 failed) |
| T2-5 | REFUSED ignores the report's manifest and always says "the manifest" | test_rebuild_result_names_the_input_path (the rebuild() assertion); test_rebuild_refused_names_the_input_and_manifest (2 failed) |

After each revert, `git diff --exit-code -- tools/reverseapoc/targets.py tools/reverseapoc/splice.py` exited 0.

## Real-file runs (D-20)

- After Task 1 GREEN: `REVERSEAPOC_ORIG="$(git rev-parse --path-format=absolute --git-common-dir)/../orig" uv run pytest -q -rs tests/test_splice_real.py tests/test_le_real.py` -> `33 passed`, no SKIPPED line.
- After Task 2 GREEN: the same command -> `33 passed`, no SKIPPED line. The object-1 control label in tests/test_splice_real.py still passes.
- Final full suite with the same REVERSEAPOC_ORIG: `379 passed, 11 skipped`. The skips are 2 x test_configure.py:196 (Windows file names cannot hold | or LF), 3 x test_hygiene.py:180 (container only) and 6 x test_watcom_real.py (third_party/watcom-media not present). None of them is a missing orig/ file. `uv run ruff check .`: All checks passed.
- The sandbox accepted the `$(...)` substitution, so the literal-path fallback was not needed.

## Files Created/Modified

- `tools/reverseapoc/targets.py`: decode and parse wrap, `targets` shape check, public `check_bare_name`, and its call in `_parse_target` with the `where` prefix.
- `tools/reverseapoc/splice.py`: `_page_label`, `Region.describe`, `_page_slot`, the rewritten `_unwritable_reason`, the layout() docstring, `RebuildResult.source` and `format(width, manifest=None)`, `RebuildReport.manifest`, rebuild_target and rebuild() filling both, and `_check_bare_name` delegating to targets.
- `tests/test_targets.py`: test_malformed_manifest_raises_manifest_error and test_manifest_refuses_a_non_bare_target_name (with the `_one_target` helper, which writes the name as a TOML literal string and computes digests from b"x").
- `tests/test_splice.py`: test_rebuild_target_refuses_a_non_bare_name, test_region_labels_count_pages_within_the_object, test_mismatch_label_in_a_later_object, test_unwritable_reason_names_the_page and test_rebuild_result_names_the_input_path. The only changed existing line is the import of ManifestError and Target.
- `tests/test_cli.py`: test_malformed_manifest_is_an_error_line, test_rebuild_refused_names_the_input_and_manifest, test_rebuild_missing_names_the_input and test_rebuild_json_refused_keeps_the_eight_keys (with the `_elsewhere_setup` helper).

## Decisions Made

- `check_bare_name` also refuses an empty name. The old splice guard did this for hand-built Targets; manifest names are already non-empty through `_text`.
- `_page_slot` is a separate helper for the `next(..., None)` lookup over `_object_pages` (D-17). `_unwritable_reason` unpacks its result only after establishing base <= addr < the page-backed end, so a page always covers the address.
- The short-page reason adds the page's byte count in hex, e.g. `(0x200 bytes)`, as the plan asked.
- In rebuild_target, `masked_fields` and `source` travel in one `common` dict for the ok and mismatch results, so the two constructors stay on one line each.

## Deviations from Plan

None. The plan was executed as written. Both tasks were TDD, with RED committed before GREEN and five reverted mutants each. The `$(...)` form of the real-file command worked, so no sandbox fallback was needed.

## TDD Gate Compliance

Each task has a `test(03-08)` commit before its `fix(03-08)` commit: 284b321 then 51a6efc, and e1b02ca then 09781cf. The plan specified `fix(...)` rather than `feat(...)` as the GREEN commit type. No refactor commit was needed.

## Issues Encountered

`uv run ruff format --check` reports 7 files that would be reformatted. Most of those diffs, including the one in targets.py's `CheckReport.format`, were already there at the base commit. Formatting is not part of the done gate (`ruff check` is), and this plan did not reformat unrelated code.

## Boundaries kept

- Not touched: WR-01 (no shared-page or overlapping-object refusal), WR-03 (rebuild write path) and WR-04 (no JSON error status).
- `git diff --exit-code main -- tools/reverseapoc/le.py tools/reverseapoc/watcom.py tools/reverseapoc/cli.py tests/test_splice_real.py tests/test_configure.py` exits 0.
- JSON_KEYS still holds the same 8 names. The new fields stay out of both to_json methods.
- No manifest hash or 8-hex prefix in any new test line, no game bytes, no unknown-marker word, no zero-numbered phase.
- STATE.md, ROADMAP.md and REQUIREMENTS.md were not edited. The orchestrator owns those writes after the wave merges.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- Ready for 03-10, the phase gate after 03-07, 03-08 and 03-09 merge. 03-10 cites `51a6efc` (IN-06, IN-07) and `09781cf` (IN-01, IN-02, IN-03, VN-01).
- 03-09 edits tests/test_splice_real.py in parallel. Its object-1 label expectation holds before and after IN-01, as the plan predicted.

---
*Phase: 03-byte-identical-round-trip*
*Completed: 2026-10-21*

## Self-Check: PASSED

- FOUND: tools/reverseapoc/targets.py, tools/reverseapoc/splice.py, tests/test_targets.py, tests/test_splice.py, tests/test_cli.py
- FOUND commits on this branch: 284b321, 51a6efc, e1b02ca, 09781cf
- Acceptance re-run: test-diff check OK (only an import line removed), `isreserved` and `TOMLDecodeError` in targets.py, `(logical page ` in splice.py, the old texts gone, the untouched files unchanged, the tree clean, the full suite and ruff green
