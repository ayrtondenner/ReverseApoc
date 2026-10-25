---
phase: 06-reporting-and-agent-pilot
plan: 18
subsystem: reporting
tags: [progress, objdiff-report, decomphub, shields, gate, drift]

requires:
  - phase: 06-reporting-and-agent-pilot (06-16)
    provides: gate-written config/ufo2p/status.csv and config/tacp/status.csv (one matched row each), 06-04's regenerated functions.csv
  - phase: 06-reporting-and-agent-pilot (06-11)
    provides: gate.py (gate_units writes status.csv after exit 0 and the cross-check)
provides:
  - tools/progress.py (stdlib, python -I): derive, Progress, build_progress, build_shield, build_report, build_decomphub, write_* and the CLI --config --out --report --decomphub --commit
  - decomphub.progress.json at the repo root (progress-v1)
  - gate rewrites decomphub.progress.json at config_root.parent after it writes status.csv
  - D-22 point 3 drift test for the committed feed
affects: [06-24 treemap and Pages workflow, 06-23 driver snapshot (the feed is a gate-written file), 06-27 phase gate]

actuals:
  tokens: 16870
  tasks: 3
  commits: 9
plan_head_before: 5d391a95fc7e771f05cab9d5985e9a315bc99097
plan_head_after: f3bfdfc0a8a92f1aea7b229b25f9e211de88c54c

tech-stack:
  added: []
  patterns:
    - "A root stdlib script loaded by path with functools.cache (gate._progress mirrors check._configure)"
    - "Every published output is render(build_*(derive(config))): one derivation, byte-stable JSON (indent 2, ASCII, LF, trailing newline), temp file + os.replace"

key-files:
  created:
    - tools/progress.py
    - decomphub.progress.json
    - tests/test_progress.py
    - tests/test_report_shape.py
  modified:
    - tools/reverseapoc/gate.py
    - tests/test_gate.py
    - tests/test_drift.py

key-decisions:
  - "Shield message is the combined percent as progress.json holds it (4 decimals, trailing zeros dropped): today's 0.0016% would read 0.00% with two decimals"
  - "The <exe>/uncovered report unit is a bucket, never complete (even when empty), and carries auto_generated: true"
  - "Report units are listed in address order (first game/thunk row); hand-named units such as grafix exist, so name order is not address order"
  - "gate rewrites the feed only after a passing gate EXE/UNIT; --partial and --all leave it (partial rows do not enter the feed's figures)"
  - "gate loads progress.py before it writes any status.csv, so a checkout without it writes nothing"
  - "A status.csv row whose start is no game/thunk functions.csv row is a ProgressError (fail closed)"

patterns-established:
  - "progress.py's minimal CSV reader is pinned to reverseapoc's readers by test_reader_agrees_with_reverseapoc"

requirements-completed: [RPT-02, RPT-04, RPT-05]

coverage:
  - id: D1
    description: "progress.py derives progress.json and the shield from the committed CSVs (stdlib, Python 3.12 syntax, python -I), uncovered bytes in the denominator"
    requirement: RPT-02
    verification:
      - kind: unit
        ref: "tests/test_progress.py (20 tests)"
        status: pass
      - kind: other
        ref: "uv run python -I tools/progress.py --out build/progress-check"
        status: pass
    human_judgment: false
  - id: D2
    description: "report.json in objdiff's report.proto shape, every Measures field, u64 as strings, combined percent equal to progress.json"
    requirement: RPT-04
    verification:
      - kind: unit
        ref: "tests/test_report_shape.py (8 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "DecompHub progress-v1 feed committed, rewritten by gate, guarded by the drift test"
    requirement: RPT-05
    verification:
      - kind: unit
        ref: "tests/test_progress.py#test_decomphub_feed_follows_progress_v1"
        status: pass
      - kind: unit
        ref: "tests/test_gate.py#test_gate_rewrites_the_decomphub_feed"
        status: pass
      - kind: unit
        ref: "tests/test_drift.py#test_committed_feed_is_derived"
        status: pass
    human_judgment: false
  - id: D4
    description: "recomp.fyi actually ingesting report.json"
    verification: []
    human_judgment: true
    rationale: "recomp.fyi's ingestion is private (D-49); the shape is pinned to report.proto names only"

duration: 25min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 18: progress.py, report shape and the DecompHub feed Summary

**One stdlib script, `tools/progress.py`, turns config/<exe>/{functions,units,status}.csv into
progress.json, the shields endpoint, an objdiff-shaped report.json and the DecompHub progress-v1
feed; gate rewrites the committed feed after every status.csv write, and the drift test keeps it
equal to the derivation.**

Execution context nonce: 5384026ff95d1b82

## Performance

- **Duration:** about 25 min
- **Started:** 2026-10-25T14:10Z (first commit 14:20Z)
- **Completed:** 2026-10-25T14:34Z
- **Tasks:** 3 (Task 1 tracer, verified end-to-end before expanding)
- **Files modified:** 7

## Current figures (committed CSVs, base 5d391a9)

| | UFO2P | TACP | combined |
|---|---|---|---|
| game+thunk bytes | 712,389 | 711,759 | 1,424,148 |
| matched bytes | 13 | 11 | 24 |
| partial bytes | 0 | 0 | 0 |
| uncovered bytes (D-50) | 25,787 | 35,349 | 61,136 |
| denominator | 738,176 | 747,108 | 1,485,284 |
| percent | 0.0018 | 0.0015 | 0.0016 |
| library bytes / functions | 43,059 / 259 | 45,156 / 278 | 88,215 / 537 |
| data-in-code bytes (excluded) | 3,879 | 3,719 | 7,598 |
| functions matched / total | 1 / 1,553 | 1 / 1,526 | 2 / 3,079 |

Shield: `0.0016%`, red. report.json: 590 units (288 UFO2P, 302 TACP, each count including the
`<exe>/uncovered` unit), complete_units 0, matched_functions_percent 0.065.

The uncovered figures were measured independently before pinning: set arithmetic over
reverseapoc's own readers (every byte of every units.csv span minus every byte of every
functions.csv row) gave 25,787 and 35,349, the same as the 06-16 note. test_uncovered_on_committed_csvs
pins the literals and recomputes the sets in the test.

## Accomplishments

- `derive()` per EXE and combined: game+thunk code, matched/partial/unmatched, uncovered bytes
  inside unit spans in no row (counted in the denominator), library and data-in-code outside the
  percent; notes on filler and the 3-byte UFO2P tail past 0x000CFADA (not counted).
- report.json: `measures`, `units`, `version` 2, `categories` ufo2p/tacp; all 16 Measures at
  every level; u64 as decimal strings; zero totals 100.0; fuzzy weighted by size; one unit per
  unit with game/thunk rows plus `<exe>/uncovered`.
- decomphub.progress.json: format const, the D-29 repository and four tracks, no revision, no
  timestamp.
- gate writes the feed at `config_root.parent` (F8) after status.csv; a feed failure names the
  written table; a missing progress.py fails before any write.

## Task Commits

1. Task 1 (tracer): `985cdd8` test RED, `ecdc340` test (shield message), `a08043b` feat GREEN
2. Task 2: `596cf36` test RED, `a8eba2d` feat GREEN
3. Task 3: `609e4f5` test RED, `e6d4cbe` feat GREEN (gate + committed feed), `5a43a97` test RED
   (load order), `f3bfdfc` fix GREEN

## TDD Gate Compliance

Each RED run was classified with `gsd-tools check tdd-red-evidence` on pytest JUnit XML:

- Task 1: RED_EVIDENCE_OK, target `test_derive_counts_on_synthetic_csvs`, 11/11 failing on
  `AssertionError: tools/progress.py does not exist`. Semantic assessment: the target ran and
  failed because the feature was missing, no collection or fixture fault (the loader assert sits
  in the test body for this reason).
- Task 2: RED_EVIDENCE_OK, target `test_report_counts_on_synthetic_csvs`, failing on
  `progress.py has no build_report`; the 16 Task 1 tests stayed green. Five committed-file shape
  tests errored in their module fixture for the same missing builder.
- Task 3: RED_EVIDENCE_OK, target `test_gate_rewrites_the_decomphub_feed`, failing on the stale
  feed bytes (gate did not write it); 4 failing, 78 passing.
- Load-order follow-up: `test_gate_without_progress_py_writes_no_table` failed on the written
  status.csv before `f3bfdfc`.

## Files Created/Modified

- `tools/progress.py`: the derivation and every output writer, CLI.
- `decomphub.progress.json`: generated by `uv run python -I tools/progress.py --decomphub decomphub.progress.json`.
- `tools/reverseapoc/gate.py`: `_progress()` loader, `feed_path`, `write_feed`, call in `gate_units`.
- `tests/test_progress.py`, `tests/test_report_shape.py`: new.
- `tests/test_gate.py`: five feed tests; `tests/test_drift.py`: committed-feed drift and a planted case.

## Decisions Made

See key-decisions above. The shield shows the 4-decimal percent because the two-decimal form
would publish 0.00% today.

## Deviations from Plan

### Orchestrator rulings applied

- **Orchestrator ruling F8: gate writes the feed to `config_root.parent / "decomphub.progress.json"`**
  instead of a separate repo-root parameter. Tests: `test_gate_rewrites_the_decomphub_feed`
  (feed under the tmp root) and `test_gate_with_a_tmp_config_root_leaves_the_repo_feed` (the
  repo's feed byte-identical, or still absent, after a tmp-config gate). Commit `e6d4cbe`.
- **Orchestrator ruling F17: `main()` creates the parent directory of every output** (`--out`,
  `--report`, `--decomphub`). Tests: `test_main_creates_every_output_parent`,
  `test_main_writes_report_and_feed`, `test_script_runs_isolated`. 06-24 adds its own
  `test_main_creates_output_dirs`; mine has a different name, so the two do not collide.
  Commits `a08043b`, `a8eba2d`.
- **06-16 notes: uncovered figures re-measured** independently (25,787 / 35,349, not the plan's
  25,691 / 35,241, which predate 06-04's 26 shorter rows) and pinned. Commit `985cdd8`.

### Auto-fixed issues

**1. [Rule 1 - Bug] Shield message would read 0.00%**
- Found during: Task 1, running the second verify on the real CSVs.
- Issue: a two-decimal message turns the combined 0.0016% into "0.00%".
- Fix: `shield_message` prints the 4-decimal percent with trailing zeros dropped; test first (`ecdc340`).

**2. [Rule 1 - Bug] My Task 2 RED test assumed name order equals address order for units**
- Found during: Task 2 GREEN. Hand-named units (`grafix`) sort before `u_...`.
- Fix: the test expects address order (first game/thunk row), which the report uses. Commit `a8eba2d`.

**3. [Rule 2 - Missing critical] A gate that cannot load progress.py wrote status.csv first**
- Found during: Task 3 self-review.
- Fix: gate calls `_progress()` before `_write_tables`; RED `5a43a97`, GREEN `f3bfdfc`.

**Total deviations:** 3 rulings applied, 3 auto-fixed (2 bugs, 1 missing-critical). **Impact:**
no scope change; files stayed within files_modified.

## Issues Encountered

- The harness refused commands with `$(...)` or `$'\r'`; I re-ran them with literal values.
- A Python `write_text` on Windows left the working copy of tests/test_progress.py with CRLF once.
  Git stored LF (`.gitattributes eol=lf`), and I normalised the working copy.

## Verification (fresh, host)

- `uv run pytest -q tests/test_progress.py`: 20 passed.
- `uv run python -I tools/progress.py --out build/progress-check` and both `test -s`: exit 0.
- `uv run pytest -q tests/test_report_shape.py tests/test_progress.py`: 28 passed.
- `uv run pytest -q tests/test_gate.py tests/test_drift.py`: 83 passed.
- Full host suite: 2119 passed, 224 skipped (baseline at 5d391a9: 2083 passed, 224 skipped). The
  skip count is unchanged, and none of the skips is in a file this plan touched. They are the
  existing real-file skips: orig/ is not in the worktree, and the real tests ran without the
  REVERSEAPOC_* variables.
- `uv run ruff check .`: All checks passed.
- No container run (worktree rule). Untested assumption: the Pages runner's python3 is 3.12 or
  newer. The `feature_version=(3, 12)` parse test guards syntax only, and no 3.12 interpreter is
  installed on this host.

## Known Stubs

None. The `"commit": null` in progress.json is the documented value when `--commit` is not
given; 06-24's Pages job passes it.

## Threat Flags

None. The only new write path is decomphub.progress.json next to the config root. It goes
through fileio.write_atomic and holds addresses-free counts and percents only.

## User Setup Required

None.

## Next Phase Readiness

06-24 can build the treemap from `derive()` (per-function status, per-unit uncovered bytes in
`ExeProgress.uncovered`) and run `python -I tools/progress.py --out _site --report <path>` in Pages.
The tick rate (OpenApoc #997) was not touched by this plan.

## Fix round 1 (FIX_BASE 6f9c066, review-06-18.md: approved, minors only)

| # | Minor | Change | Test | Commits |
|---|---|---|---|---|
| 1 | Pre-write guard only loaded progress.py | `progress.derive(config, status_texts=...)` reads status.csv text in memory. gate's `_write_tables` derives the merged tables before any write, so a table progress.py refuses exits 2 with nothing written | `test_gate_refuses_tables_progress_cannot_derive` (RED: status.csv was written first; RED_EVIDENCE_OK) | `8188945` RED, `5364ffa` GREEN |
| 2 | gate.py docstring claimed "writes nothing" on every tool error | Docstring now gives the real contract: exit 2 writes nothing, except an OS error after a table was written (a second status.csv, or the feed), whose message names every written table | docstring only | `5364ffa` |
| 3 | Feed rewrite not reported | `GateResult.feed`; text line `wrote decomphub.progress.json -> <path> (commit it with status.csv)`; `--json` key `feed` (null when nothing was written) | `test_gate_output_names_the_rewritten_feed`, `test_gate_output_has_no_feed_when_nothing_was_written` | `8188945` RED, `5364ffa` GREEN |
| 4 | Sole-writer scan missed tools/progress.py | `test_only_gate_writes_the_table` also scans tools/progress.py | test-only, passes (progress.py has no write_status) | `b96b761` |
| 5 | Five dead docstrings in tests/test_progress.py | Docstrings moved above `load_progress()` | test-only | `b96b761` |
| 6 | UNASSIGNED_UNIT branch untested | Synthetic row with an empty unit cell lands in `tacp/unassigned`, bytes in the totals | `test_report_puts_rows_without_a_unit_in_an_unassigned_unit` (coverage of an existing branch, passes) | `b96b761` |
| 7 | Report item `address` semantics | Comment in `_item`: linear address, not objdiff's section-relative offset | comment only | `5364ffa` |
| 8 | Hooks do not cover the feed | Recorded only, as a known limit (below) | none | this commit |

Files outside the plan's files_modified: `tests/test_status.py` (minor 4, at the coordinator's request).

**Known limit (minor 8).** The always-on hook layer protects orig/, asm/, build/, the two TOML
manifests and *.sha1 (hooks.py `_PROTECTED_DIRS` / `_PROTECTED_FILES`). It protects neither
decomphub.progress.json nor status.csv. In a matching session, `hooks.matching_write_allowed`
(hooks.py:546) allows only `src/<exe>/<unit>.c`, a new untracked `include/<name>.h` and the
attempt's notes.md, so an agent cannot write the feed there; I read the function to confirm
this. A hand edit outside a matching session is caught only by
`tests/test_drift.py::test_committed_feed_is_derived` in CI, and the 06-23 driver commits gate's
copy. A follow-up in 06-23 or later could add the feed to the always layer.

**Fix round 1 verification (host):**
- Targeted run (`test_gate`, `test_drift`, `test_progress`, `test_report_shape`, `test_status`): 148 passed.
- Full suite: 2123 passed, 224 skipped. The skips are the same pre-existing real-file skips.
- `uv run ruff check .`: All checks passed.
- The committed feed is unchanged (the drift test passes).

## Self-Check: PASSED

- Files: tools/progress.py, decomphub.progress.json, tests/test_progress.py, tests/test_report_shape.py exist.
- Commits 985cdd8, ecdc340, a08043b, 596cf36, a8eba2d, 609e4f5, e6d4cbe, 5a43a97, f3bfdfc are ancestors of HEAD.
