---
phase: 03-byte-identical-round-trip
plan: 04
subsystem: tooling
tags: [le, rebuild, cli, json, trailer, pytest, mutation-testing]

requires:
  - phase: 03-byte-identical-round-trip
    provides: "plan 03-01: rebuild verb, RebuildResult/RebuildReport, LE.pages_end, SYNTHETIC_TRAILER fixture; plan 03-03: splice(), first_diff/first_diff_region/first_diff_va/diff_bytes/masked_fields on RebuildResult"
provides:
  - "RebuildResult.to_json() and RebuildReport.to_json(): name, status, output, sha1, expected_sha1, first_diff ({offset, region, va} or null), diff_bytes, masked_fields"
  - "rebuild(..., exe=NAME): case-insensitive selection of one manifest target; unknown names raise ManifestError listing the known targets before any write"
  - "`uv run reverseapoc rebuild --exe NAME --json`"
  - "LE.summary()['trailer'] = {offset, length, sha1} (length clamped at 0) and a `trailer` row in format_summary(), so parse-le reports the bytes after the last page without printing them"
affects: [03-05, phase-5-landing, phase-6-driver]

actuals:
  tokens: 3650
  tasks: 3
  commits: 6
plan_head_before: 87f917720a897e76bf4926bdf1392cbb20e1668d
plan_head_after: 039e741

tech-stack:
  added: []
  patterns:
    - "to_json() next to format(): the JSON and the text line come from the same result object"
    - "Selection by name only (next(..., None) over Target.name.casefold()); the user string never forms a path"
    - "Leak tests check both the hex and the text of the synthetic trailer in text and JSON output"

key-files:
  created: []
  modified:
    - tools/reverseapoc/splice.py
    - tools/reverseapoc/cli.py
    - tools/reverseapoc/le.py
    - tests/test_cli.py
    - tests/test_le.py

key-decisions:
  - "rebuild() still checks every manifest target name is a bare file name before selecting with --exe, so a bad manifest entry is refused even when another target is selected"
  - "The unknown --exe error names the resolved manifest path (default config/targets.toml) and the known targets comma-separated, raised as ManifestError so main() prints it and exits 1"
  - "The trailer report lives in a private LE._trailer() helper called from summary(); format_summary() adds the row right after the pages row"

patterns-established:
  - "Pin tests for behaviour an earlier plan already shipped are proven by uncommitted mutants applied and restored by a scratch script, with git diff --exit-code checked afterwards"

requirements-completed: [RT-03, RT-05]

coverage:
  - id: D1
    description: "`rebuild --json` prints one object per EXE with name, status, output, sha1, expected_sha1, first_diff, diff_bytes and masked_fields; missing inputs give status missing with null output and sha1"
    requirement: RT-03
    verification:
      - kind: integration
        ref: "tests/test_cli.py#test_rebuild_json_output"
        status: pass
      - kind: integration
        ref: "tests/test_cli.py#test_rebuild_json_missing"
        status: pass
      - kind: other
        ref: "uv run reverseapoc rebuild --orig <main checkout>/orig --json (3 ok objects, exit 0)"
        status: pass
    human_judgment: false
  - id: D2
    description: "`rebuild --exe NAME` rebuilds one target matched case-insensitively; an unknown name exits 1 naming the known targets and writes nothing"
    requirement: RT-03
    verification:
      - kind: integration
        ref: "tests/test_cli.py#test_rebuild_exe_filter_case_insensitive"
        status: pass
      - kind: integration
        ref: "tests/test_cli.py#test_rebuild_unknown_exe_lists_known_names"
        status: pass
      - kind: other
        ref: "uv run reverseapoc rebuild --orig <main checkout>/orig --exe smkp.exe (one OK line for SMKP.EXE); rebuild --exe NOPE.EXE (exit 1, stderr names UFO2P.EXE, TACP.EXE, SMKP.EXE)"
        status: pass
    human_judgment: false
  - id: D3
    description: "At the CLI a mismatch exits 1 and both the text line and the JSON object name the first differing offset, region, VA and differing-byte count; rebuild defaults are orig/, config/targets.toml, build/"
    requirement: RT-03
    verification:
      - kind: integration
        ref: "tests/test_cli.py#test_rebuild_mismatch_line_and_json"
        status: pass
      - kind: unit
        ref: "tests/test_cli.py#test_rebuild_default_options"
        status: pass
    human_judgment: false
  - id: D4
    description: "parse-le reports the trailer as offset, length and SHA-1 in text and JSON (length 0 and the empty-input SHA-1 when absent or truncated) and never prints its bytes"
    requirement: RT-05
    verification:
      - kind: unit
        ref: "tests/test_le.py#test_summary_reports_trailer"
        status: pass
      - kind: unit
        ref: "tests/test_le.py#test_summary_trailer_absent_is_zero_length"
        status: pass
      - kind: unit
        ref: "tests/test_le.py#test_summary_trailer_clamped_on_truncated_file"
        status: pass
      - kind: unit
        ref: "tests/test_le.py#test_format_summary_trailer_row"
        status: pass
      - kind: integration
        ref: "tests/test_cli.py#test_parse_le_reports_trailer_without_bytes"
        status: pass
      - kind: other
        ref: "uv run reverseapoc parse-le on the real files: UFO2P 27 bytes at 0x001a0723, TACP 27 bytes at 0x00303ddf, SMKP length 0"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-10-20
status: complete
---

# Phase 3 Plan 04: rebuild --exe/--json and the parse-le trailer report Summary

**`reverseapoc rebuild` now takes `--exe NAME` (case-insensitive, unknown names refused with the known list before any write) and `--json` (one object per EXE carrying status, SHA-1s, first difference and counts), and `parse-le` reports the bytes after the last page as offset, length and SHA-1 in text and JSON without ever printing them.**

## Performance

- **Duration:** about 6 min (2026-10-20T21:28:34Z to 21:33:58Z)
- **Tasks:** 3 of 3
- **Files modified:** 5

## Accomplishments

- `RebuildResult.to_json()` / `RebuildReport.to_json()` in `tools/reverseapoc/splice.py`, printed by `rebuild --json` as a JSON list; exit code unchanged (0 only when every target is ok).
- `rebuild(..., exe=)` and `rebuild --exe NAME`: picks the manifest target by `Target.name.casefold()`, raises `ManifestError` naming the name, the manifest and the known targets otherwise. The name never becomes a path.
- The CLI mismatch path is pinned end to end: a byte spliced at VA 0x10800 shows up as `first difference at <offset> (page 1 of object 1, VA 0x00010800), 1 bytes differ` and as `first_diff {offset, region, va}`, `diff_bytes 1` in JSON.
- `LE.summary()["trailer"]` and a `trailer` row in `format_summary()`. On the real files: UFO2P 27 bytes at 0x001a0723, TACP 27 bytes at 0x00303ddf, SMKP length 0 with the SHA-1 of empty input, matching the spike facts.

## Task Commits

1. **Task 1 (tracer): `rebuild --json`**
   - RED `548edf7` test(03-04): add failing tests for rebuild --json
   - GREEN `1ae5fdf` feat(03-04): print rebuild results as JSON with --json
2. **Task 2: `--exe NAME`, the CLI mismatch path and the defaults**
   - RED `8af3cc0` test(03-04): add failing tests for rebuild --exe, the CLI mismatch path and defaults
   - GREEN `8ea8759` feat(03-04): rebuild only one manifest target with --exe NAME
3. **Task 3: parse-le trailer report (D-11)**
   - RED `a0310b1` test(03-04): add failing tests for the parse-le trailer report
   - GREEN `039e741` feat(03-04): report the trailer in parse-le as offset, length and SHA-1

## TDD record

- **Task 1 RED:** both tests failed with argparse `unrecognized arguments: --json` (SystemExit 2), the planned missing flag. Tracer gate (interactive, end-of-phase, automated-only verify): after GREEN the rebuild tests, ruff and the real `rebuild --json` (three ok objects, exit 0) were re-run and passed before Task 2.
- **Task 2 RED:** the two `--exe` tests failed with SystemExit 2 and `test_rebuild_default_options` with `AttributeError: 'Namespace' object has no attribute 'exe'`. `test_rebuild_mismatch_line_and_json` passed at RED: it pins the 03-03 report and the Task 1 JSON, so its RED evidence is the mutant table below.
- **Task 3 RED:** four tests failed with `KeyError: 'trailer'` or no trailer row, the CLI test with no trailer row to unpack: the planned missing field.
- `gsd_run check tdd-red-evidence` was not run: pytest's default report is not one of its formats and this plan is `type: execute` with task-level `tdd="true"`.

## Mutants

Each mutant was applied to one source file by a scratch script (outside the repo), the listed tests were run, and the original bytes were written back; `git diff --exit-code` was clean after each set. None was committed.

| Mutant | File | Change | Failing tests |
|---|---|---|---|
| M1 | splice.py | `to_json` first_diff `va` always None | `test_rebuild_mismatch_line_and_json` |
| M2 | splice.py | MISMATCH line drops the byte count | `test_rebuild_mismatch_line_and_json` |
| M3 | splice.py | exact instead of case-insensitive match | `test_rebuild_exe_filter_case_insensitive` |
| M4 | splice.py | `--exe` found but all targets rebuilt | `test_rebuild_exe_filter_case_insensitive` |
| M5 | splice.py | unknown `--exe` returns no targets instead of raising | `test_rebuild_unknown_exe_lists_known_names` |
| M6 | splice.py | JSON `sha1` taken from the manifest | `test_rebuild_json_missing` |
| T1 | le.py | trailer length not clamped | `test_summary_trailer_clamped_on_truncated_file` |
| T2 | le.py | SHA-1 of the whole file | all 5 trailer tests |
| T3 | le.py | trailer hex inside the trailer field | `test_summary_reports_trailer`, `test_summary_trailer_absent_is_zero_length`, `test_parse_le_reports_trailer_without_bytes` |
| T4 | le.py | trailer row without the offset | `test_format_summary_trailer_row`, `test_parse_le_reports_trailer_without_bytes` |
| T5 | le.py | trailer hex in a separate top-level JSON field | `test_parse_le_reports_trailer_without_bytes` (the no-bytes assertion itself) |
| T6 | le.py | trailer text in a separate top-level JSON field | `test_parse_le_reports_trailer_without_bytes` (the no-bytes assertion itself) |

## Files Created/Modified

- `tools/reverseapoc/splice.py` - `to_json` on `RebuildResult` and `RebuildReport`, `_select`, keyword `exe` on `rebuild()`
- `tools/reverseapoc/cli.py` - `rebuild --exe NAME` and `rebuild --json`, help text mentions `--exe`
- `tools/reverseapoc/le.py` - `"trailer"` in `summary()` via `_trailer()`, `trailer` row in `format_summary()`
- `tests/test_cli.py` - 7 new tests (json output/missing, exe filter/unknown, mismatch line and JSON, defaults, parse-le trailer without bytes)
- `tests/test_le.py` - 4 new trailer tests

## Decisions Made

- Every manifest target name is still checked as a bare file name before `--exe` selects one, so "refuse before writing" covers the whole manifest.
- The unknown-name error is a `ManifestError`, which `main()` already reports, so no CLI change was needed for the exit code.

## Deviations from Plan

None in scope or behaviour. Mechanical notes:
- The plan's real-file commands use `"$(git rev-parse --path-format=absolute --git-common-dir)/../orig"`. The worktree sandbox refuses git inside a command substitution, so they ran with the literal `C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/orig` (read only; `rebuild` wrote to this worktree's build/).
- The plan-head ledger was not written under `.git/worktrees/`; the base SHA comes from the dispatch (`87f9177`) and the commit count was measured with `git rev-list --count 87f9177..HEAD` = 6.
- Mutants were driven by a scratch Python script that restores the file's original bytes, because the sandbox refused the compound shell form with `git checkout`; `git diff --exit-code` was run separately after each set.

**Total deviations:** 0 auto-fixed. **Impact:** none.

## Verification

- `REVERSEAPOC_ORIG=C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/orig uv run pytest -q -rs`: 296 passed, 9 skipped (3 container-only hygiene, 6 absent Watcom media; none for a missing orig/ file).
- `uv run pytest -q` (no override): 284 passed, 21 skipped.
- `uv run ruff check .`: All checks passed.
- `-k json`: 3 passed (both new tests plus parse-le JSON); `-k "exe or mismatch or default"`: 5 passed; `-k trailer` over test_le.py and test_cli.py: 5 passed.
- `rebuild --orig <main checkout>/orig --json`: exit 0, objects for UFO2P.EXE, TACP.EXE, SMKP.EXE, all `ok` with `sha1 == expected_sha1`.
- `rebuild --orig <main checkout>/orig --exe smkp.exe`: one OK line for SMKP.EXE, exit 0. `rebuild --exe NOPE.EXE`: exit 1, stderr lists UFO2P.EXE, TACP.EXE, SMKP.EXE. `rebuild --help` lists `--exe NAME` and `--json`.
- `parse-le` on UFO2P.EXE and TACP.EXE prints a `trailer` row with length, offset and a 40-hex-digit SHA-1; `parse-le SMKP.EXE --json` has `trailer.length` 0.
- The container gate was not run from this worktree, as instructed.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03-05 (real-file round-trip tests, docs) can use `rebuild --exe` / `--json` and the parse-le trailer field; the docs note that page data "runs exactly to EOF" can now point at the `trailer` row.
- The Phase 6 driver can consume `rebuild --json` directly.

## Self-Check: PASSED

All 5 modified files exist; all 6 commits (548edf7, 1ae5fdf, 8af3cc0, 8ea8759, a0310b1, 039e741) are ancestors of HEAD; `git rev-list --count 87f9177..HEAD` = 6 before this SUMMARY commit.

---
*Phase: 03-byte-identical-round-trip*
*Completed: 2026-10-20*
