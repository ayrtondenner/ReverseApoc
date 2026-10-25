---
phase: 06-reporting-and-agent-pilot
plan: 11
subsystem: oracle
tags: [gate, status-table, cross-check, d-20, d-21, d-24, agt-06, rpt-01, python]

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "06-02 fileio.write_atomic; 06-06 the functions.csv helpers; 06-08 RelocResult bound to its row; 06-09 CompileOptions.src_root/config_root (check-custom) and the provenance stamp"
provides:
  - "tools/reverseapoc/status.py: StatusRow, STATUS_COLUMNS (D-20), STATUS_COMMENT, strict read_status naming the file line, write_status through fileio.write_atomic, status_path, lf_sha256"
  - "tools/reverseapoc/gate.py: gate_unit/gate_units (several targets, one combined cross-check, all or nothing), cross_check (D-24), gate_all (check_source per matched unit + one land_all), gate_partial (check-custom), GateRoots, GateResult"
  - "`reverseapoc gate EXE/UNIT [EXE/UNIT ...] [--attempts N] [--json]`, `gate --all`, `gate EXE/UNIT --partial --src FILE`; exit 0/1/2; StatusError in _ERRORS"
affects: [06-12 hooks deny agent edits of status.csv, 06-16 seeding (one gate run of both Phase 5 units) and the D-22 drift test, 06-18 gate writes decomphub.progress.json, 06-23/06-25 the driver's gate and partial-gate calls]

actuals:
  tokens: 23000  # chars/4 over git diff 325c606..4f3beb7 (79,794 chars) plus this SUMMARY
  tasks: 3
  commits: 7  # MEASURED: git rev-list --count 325c606..4f3beb7, before this SUMMARY commit
plan_head_before: 325c6066b67916ec70c794d79ebfabfcea2178c1
plan_head_after: 4f3beb75475bcdd932ee6017207e7d62b0459d61

tech-stack:
  added: []
  patterns:
    - "A table writer that formats and validates every touched table before writing any, so one refused row writes nothing"
    - "Collaborators (check_unit, check_source, land_all, load_exe, compile_source) resolved at call time (`fn or check_unit`), so tests inject or monkeypatch fakes"

key-files:
  created:
    - tools/reverseapoc/status.py
    - tools/reverseapoc/gate.py
    - tests/test_status.py
    - tests/test_gate.py
  modified:
    - tools/reverseapoc/cli.py

key-decisions:
  - "The cross-check also compares each matched row's unit and name with functions.csv (owners), so a moved function is refused even when the gated unit is a third one"
  - "A missing status.csv reads as no rows (D-20 sparse); a header-only file is a valid, empty table"
  - "The reader is strict: comment line first, exact header, LF only, no blank or comment line inside, sorted unique starts, 0x%08X, NNN.NN percent (matched = 100.00), decimal attempts, 64 lower-case hex, real ISO date; each refusal names the file line"
  - "gate hashes the unit file before and after check; a file edited while check ran is a tool error (exit 2)"
  - "gate --partial exits 0 when an unmatched function scored above 0% (its row is merged: best percent wins, ties keep the earlier row, attempts take the larger count), 1 when none did"
  - "gate --partial refuses a saved file whose directory would route the compile to ninja's paths (defence in depth on top of 06-09's object_root)"

patterns-established:
  - "tests/test_gate.py FakeCheck/FakeAll/FakePartial: a tmp tree of unit files, each defining some functions, landed the way check's land step lands every compiled unit"

requirements-completed: [RPT-01, AGT-06]

coverage:
  - id: D1
    description: "status.csv model (D-20): exact columns and comment, 0x%08X starts, two-decimal percent, sorted LF rows written atomically; wrong header, duplicate or unsorted start, unknown status, bad sha, bad date, CRLF, blank line refused naming the line; writer refuses what the reader would"
    requirement: "RPT-01"
    verification:
      - kind: unit
        ref: "tests/test_status.py#test_status_round_trip, test_header_only_table_is_valid_and_empty, test_missing_table_has_no_rows, test_status_refuses_bad_tables (15), test_status_refuses_unsorted_rows, test_write_refuses_a_duplicate_start_and_writes_nothing, test_write_refuses_a_row_the_reader_would_refuse (7), test_lf_sha256_ignores_crlf, test_only_gate_writes_the_table"
        status: pass
    human_judgment: false
  - id: D2
    description: "gate EXE/UNIT writes matched rows (100.00, LF sha of the unit file, --attempts, UTC date) only on check exit 0 and a passing cross-check; nothing on a mismatch or tool error; CLI exit 0/1/2"
    requirement: "RPT-01"
    verification:
      - kind: unit
        ref: "tests/test_gate.py#test_gate_writes_matched_rows_on_pass, test_gate_writes_nothing_on_mismatch, test_gate_writes_nothing_on_a_tool_error, test_gate_refuses_negative_attempts, test_gate_cli_exit_codes (3), test_gate_cli_refuses_a_bad_target (4), test_gate_cli_text_output"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-24 cross-check: reverted match, extra landed function, moved function (gated or third unit), adjacency both ways, matched rows of an EXE that did not land; several targets all or nothing (F1); re-gating keeps attempts and date (F29); order independence"
    requirement: "AGT-06"
    verification:
      - kind: unit
        ref: "tests/test_gate.py#test_crosscheck_refuses_a_reverted_match, test_crosscheck_refuses_an_extra_landed_function, test_crosscheck_refuses_a_moved_function (2), test_crosscheck_adjacency, test_crosscheck_refuses_matched_rows_of_an_exe_that_did_not_land, test_crosscheck_reads_the_exeland_exe_field, test_gate_two_targets_writes_both_rows, test_gate_targets_are_all_or_nothing, test_gate_refuses_a_target_named_twice, test_regating_keeps_attempts_and_date, test_a_match_replaces_a_partial_row, test_merge_is_order_independent"
        status: pass
    human_judgment: false
  - id: D4
    description: "gate --all: check_source per matched unit, one land_all, never check_unit; empty table exits 0 landing nothing; objdiff regression, revert, extra landed start, SHA-1 mismatch and a matched unit without C exit 1; writes nothing"
    requirement: "AGT-06"
    verification:
      - kind: unit
        ref: "tests/test_gate.py#test_gate_all_passes_and_writes_nothing, test_gate_all_runs_one_land, test_gate_all_with_empty_status, test_gate_all_refuses_a_regression (4), test_gate_all_refuses_a_matched_unit_without_c, test_gate_cli_all, test_gate_cli_target_usage (3)"
        status: pass
    human_judgment: false
  - id: D5
    description: "gate --partial --src FILE: best-percent partial rows with the saved file's sha, compiled under build/check-custom with ninja's object untouched (F7), matched rows never touched, higher percent kept, no progress exits 1; usage errors exit 2"
    requirement: "RPT-01"
    verification:
      - kind: unit
        ref: "tests/test_gate.py#test_partial_writes_best_percent, test_partial_never_downgrades_a_matched_row, test_partial_keeps_the_higher_percent, test_partial_takes_a_higher_percent, test_partial_with_no_progress_writes_nothing, test_partial_cli, test_partial_cli_usage (6)"
        status: pass
    human_judgment: false
  - id: D6
    description: "The gate against the real check in the container (seeding both Phase 5 units in one run)"
    requirement: "AGT-06"
    verification: []
    human_judgment: true
    rationale: "Needs the container and the real orig/ and Watcom tree; plan 06-16 seeds status.csv on the main checkout. Here gate is proven on fakes only, as the plan says."

duration: 16min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 11: The gate-written status table and the zero-regression gate Summary

**`reverseapoc gate EXE/UNIT [EXE/UNIT ...]` is now the only writer of the sparse `config/<exe>/status.csv` (D-20, D-21): it writes matched rows only after every check exits 0 and the D-24 cross-check (landed starts == matched starts + newly defined functions, moved functions refused) passes; `gate --all` re-proves every matched function with one land and writes nothing; `gate --partial --src FILE` records the best percent of a saved attempt under build/check-custom without touching a match.**

Execution context nonce: 4cd196affae39523

## Performance

- **Duration:** 16 min
- **Started:** 2026-10-25T04:11:24Z
- **Completed:** 2026-10-25T04:27:22Z
- **Tasks:** 3 (each a RED test commit, then its GREEN commit), plus one guard test
- **Files modified:** 5 (4 created, 1 modified)

## Accomplishments

- status.py: the D-20 table. `STATUS_COLUMNS = ("start", "name", "unit", "status", "best_percent", "attempts", "source_sha256", "date")`, first line `# written by: uv run reverseapoc gate EXE/UNIT; do not edit`. It reuses functions.py's `_format_csv`, `_read_records`, `_address` and `_parse_address`. `read_status` refuses a bad table with a StatusError that names the file line. `write_status` validates every row the same way and writes nothing when one is refused.
- gate_units: checks each target, hashing the unit file before and after. With every check at exit 0, it builds the newly-defined map (start -> gated unit) as the union over the targets and runs one combined cross-check against each check's splices. Only then does it merge and write all touched tables. All or nothing.
- cross_check (pure): per EXE, it compares `ExeLand.exe`'s landed starts with status.csv's matched starts plus the defined map. The problems it names:
  - "not landed (reverted to INCLUDE_ASM, or its unit file is gone)";
  - "landed but is neither matched ... nor defined by a gated unit";
  - a matched row now defined by another unit, or that functions.csv puts in another unit or under another name;
  - matched rows of an EXE that did not land.
- gate_all: for every EXE with units.csv, check_source on each unit with matched rows. Then one land_all, with those units in `fresh`, then the cross-check and `ExeLand.ok`. It writes nothing. A matched function that is no longer defined, or no longer 100.0 with reloc and bytes ok, is a problem. So is a matched unit whose C file is gone.
- gate_partial: passes `CompileOptions(src_root=<saved file's parent>)`, so the compile lands under build/check-custom. It merges partial rows by best percent for unmatched functions only.
- cli: `gate` with `targets nargs="*"`, `--all`, `--partial`, `--attempts N` and `--json`, plus the check verb's roots and tool options. `_cmd_gate` maps CheckError, StatusError and `_ERRORS` to exit 2. The module docstring's verb list gains target, land and gate.

## Task Commits

1. **Task 1 (tracer): gate writes one matched row through status.py.** RED `1401e62` (test), GREEN `4808d0a` (feat). Tracer gate: interactive run, `end-of-phase`, verify automated-only. I re-ran `uv run pytest -q tests/test_status.py tests/test_gate.py` (41 passed), then expanded.
2. **Task 2: the cross-check and `gate --all`.** RED `1da0ee2` (test), GREEN `8a554d1` (feat).
3. **Task 3: `gate --partial`.** RED `873997a` (test), GREEN `309f360` (feat).
4. Guard: `4f3beb7` (test), only gate.py calls write_status.

**Plan metadata:** this SUMMARY commit (docs).

## RED evidence (semantic assessment)

`workflow.tdd_mode` is off, and pytest's console report is not a format `check tdd-red-evidence` reads. I judged RED from the failing assertions, as 06-02, 06-08 and 06-09 did.

- Task 1 (`1401e62`): both files failed at collection. `reverseapoc.status` and `reverseapoc.gate` did not exist yet (ImportError). This is the new-module case 06-02 recorded.
- Task 2 (`1da0ee2`): 21 targets failed, all on the planned behaviour.
  - The gate tests failed on assertions. The cross-check cases returned exit 0 where 1 was expected (`assert 0 == 1`). Re-gating had attempts 1 where 3 was kept.
  - `cross_check` and `gate_all` did not exist yet (AttributeError on the module).
  - The CLI usage cases hit argparse's `SystemExit: 2` where `main` should return 2.
  - `test_merge_is_order_independent` first failed on a test-helper bug (the tmp root did not exist). I fixed that before the RED commit. It then passed on Task 1's code, as a pin.
- Task 3 (`873997a`): 12 targets failed.
  - 5 failed because `gate_partial` did not exist (AttributeError).
  - 7 CLI cases hit `SystemExit: 2`: `--partial` was not an option yet.

## Files Created/Modified

- `tools/reverseapoc/status.py` (new): the status table model, reader, writer and `lf_sha256`.
- `tools/reverseapoc/gate.py` (new): `GateRoots`, `Written`, `GateResult`, `cross_check`, `merge_matched`, `gate_units`/`gate_unit`, `gate_all`, `gate_partial`, `source_sha256`.
- `tools/reverseapoc/cli.py`: the `gate` verb (`_gate`, `_gate_partial`, `_run_gate`, `_cmd_gate`, `_add_gate_command`, registered after `_add_land_command`), StatusError in `_ERRORS`, and the docstring.
- `tests/test_status.py`, `tests/test_gate.py` (new).

## Decisions Made

See key-decisions in the frontmatter. Two points on interfaces later plans call:

- `GateResult.to_json()` has the top-level keys `mode`, `targets`, `ok`, `exit_code`, `checks`, `problems` and `written`. 06-16's seed verify reads `['ok']`.
- The gate verb takes the check verb's options. These are `--orig`, `--manifest`, `--config`, `--src` and `--build`, plus `--watcom-dir`, `--watcom-manifest`, `--cflags` and `--log`.

## Deviations from Plan

- **Orchestrator ruling F1: gate several targets in one run.**
  - `gate` takes one or more EXE/UNIT targets.
  - Each target is checked first. Then one cross-check runs, with the union of the targets' defined functions. Then all rows are written, or none.
  - The ruling says `nargs="+"`. argparse cannot put a `+` positional in a mutually exclusive group with `--all`. So the positional is `nargs="*"`, and `_gate` enforces "targets or `--all`, not both, not neither" with exit 2 (`test_gate_cli_target_usage`).
  - Tests: `test_gate_two_targets_writes_both_rows` (empty tables, a unit of each EXE: `gate A B` writes both rows, `gate A` alone fails on B's landed function), `test_gate_targets_are_all_or_nothing`, `test_gate_refuses_a_target_named_twice`.
- **Orchestrator ruling F7: what `--src` means with `--partial`.**
  - With `--partial`, `--src` must name an existing `.c` file. A directory, a non-`.c` path, a missing file or the default src root exits 2 with a usage message.
  - `gate_partial` passes `CompileOptions(src_root=<that file's parent>)`.
  - `test_partial_writes_best_percent` stands the tmp tree in for the committed roots. It proves that the compile goes under `build/check-custom/` and that a pre-existing ninja `build/ufo2p/obj/<unit>.obj` keeps its bytes.
  - Without `--partial`, `--src` keeps its src-root meaning.
- **Orchestrator ruling F29: re-gating a unit.** A gated unit's functions that already have `matched` rows keep their `attempts` and `date`, and only `source_sha256` is rewritten (`merge_matched`, `test_regating_keeps_attempts_and_date`). The cross-check reads `ExeLand.exe` (`test_crosscheck_reads_the_exeland_exe_field`).

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] The cross-check compares matched rows with functions.csv**
- **Found during:** Task 2
- **Issue:** "a matched row whose function moved to another unit is refused" only held when the gated unit was the new owner. When a third unit was gated, the landed set still equalled the expected set, and the move went unseen.
- **Fix:** `cross_check(..., owners=)` takes the functions.csv rows. A matched row whose start has no row, or whose row names another unit or name, is a problem. `gate_units` reads functions.csv. `gate_all` uses `ExeInputs.rows`.
- **Files modified:** tools/reverseapoc/gate.py, tests/test_gate.py (`test_crosscheck_refuses_a_moved_function[a-third-unit]`)
- **Commit:** `1da0ee2`, `8a554d1`

**2. [Rule 2 - Missing critical] The unit file is hashed before and after the check**
- **Found during:** Task 1
- **Issue:** a hash taken only after check could record a file other than the one check proved.
- **Fix:** gate hashes before and after. A difference is a CheckError (exit 2), and nothing is written. The same applies to the saved file in `--partial`.
- **Files modified:** tools/reverseapoc/gate.py
- **Commit:** `4808d0a`, `309f360`

**3. [Rule 2 - Missing critical] A scan test that only gate.py calls write_status**
- **Found during:** final review against the D-21 prohibition
- **Fix:** `test_only_gate_writes_the_table` scans tools/reverseapoc/*.py and configure.py.
- **Commit:** `4f3beb7`

**4. [Rule 1 - Test bug] Binary writes where the LF rule is under test**
- **Found during:** Task 1 GREEN
- **Issue:** `write_text` translates `\n` to CRLF on Windows, so `test_status_refuses_unsorted_rows` saw the CR refusal first.
- **Fix:** the test writes bytes.
- **Commit:** `4808d0a`

**5. [Rule 3 - Blocking] Test fakes pass an objdiff runner**
- **Found during:** Task 2 GREEN
- **Issue:** `default_objdiff_runner` refuses at construction when objdiff-cli is not on PATH (correct in production), and the host has no objdiff-cli.
- **Fix:** the gate --all and --partial tests pass a fake runner or monkeypatch `gate.default_objdiff_runner`. No production change.
- **Commit:** `8a554d1`

---

**Total deviations:** 3 orchestrator rulings applied (F1, F7, F29); 5 auto-fixed (3 missing critical, 1 test bug, 1 blocking).
**Impact on plan:** the rulings are applied as plan text, and the auto-fixes tighten D-21/D-24. No scope creep. Seeding is left to 06-16.

## Issues Encountered

- The worktree harness refused heredoc and chained shell commands as "too complex to verify". Edits went through the Edit tool and scratchpad scripts instead.
- Host suite: 1676 passed, 217 skipped. The skips are the usual real-file skips in a worktree with no orig/, Watcom or media. None is in the new tests. Ruff is green.

## Known limits

- The writes are atomic per file, not across the two EXEs' tables. Every touched table is merged and validated before any is written, so only an OS error between the two `os.replace` calls could leave one table written. That is an exit 2 the driver reports.
- `write_status` is a public library function. D-21's "no other writer" is enforced by the CLI (only `gate` reaches it), by the scan test, and later by the 06-12 hooks and the 06-16 drift test.
- Fix round 1: deliberately un-matching a function, or moving a matched start to another unit, has no gate path. Only gate writes status.csv, and gate never removes a matched row: it refuses the cross-check. Removing such a row is an owner action outside this plan. A moved start cannot happen for matched code; a rename can, and it is re-gateable.
- Fix round 1 (M6, a note for 06-23 and 06-25): `gate --partial` compiles the saved file, and `compiler.source_rule` picks the cflags rule by that file's own repo-relative path (`build/driver/.../best/<unit>.c`), not by `src/<exe>/<unit>.c`. That is harmless while config/cflags.txt has only the `*` rule. Once a D-18 per-glob rule exists, partial percents would be scored with the wrong flags. 06-23 must pick the rule by the unit path, for example by saving the best C under a tree that mirrors `src/<exe>/<unit>.c`, or by passing the unit path to the rule lookup.

## User Setup Required

None.

## Next Phase Readiness

- 06-16 can seed both Phase 5 units in one container run: `uv run reverseapoc gate ufo2p/u_000a34f0 tacp/u_00054f20 --json`. Its verify reads the top-level `ok`.
- 06-18 adds the decomphub feed write to the gate (F8: `config_root.parent / "decomphub.progress.json"`). The natural place is `_write_tables` in gate.py, after the status tables are written.
- 06-23/06-25 call `gate EXE/UNIT --partial --src <repo-relative .c> --attempts N --json`.

## Fix round 1

Fix base `ae38da9`. The review approved, with one Important finding (it fails closed) and nine minors. RED `a22f512` (test), GREEN `1230849` (fix).

| Finding | What changed | Test (tests/test_gate.py unless named) |
|---|---|---|
| Important 1: a fully reverted matched unit made `gate --all` (and gating it) exit 2 | `_reverted` reads the unit file with configure's D-12 parser (`source_marks`) before check. If its C defines none of the unit's functions, every matched row of the unit is a mismatch (exit 1). check is not run, and gate --all leaves the unit out of `fresh`. The fakes now raise "defines no function of unit" as check_unit/check_source do. | `test_gate_all_exits_1_on_a_fully_reverted_unit`, `test_gating_a_fully_reverted_matched_unit_exits_1` |
| Ruling on minor 3: renames | Matched rows are keyed by (EXE, start). `_owners` names each start by its symbols.csv function name, else its functions.csv name. A passing re-gate writes that name and the new sha, and keeps attempts and date (F29). The cross-check compares by start. A matched row that is not re-gated and whose start now has another name is refused. A change of unit is still refused. | `test_regating_a_renamed_function_updates_its_name`, `test_a_stale_name_is_refused` |
| M2: half-write message | An OSError on a later table raises CheckError naming the tables already written ("restore config/ before committing"). `_cmd_gate`'s docstring describes this case. | `test_a_failed_second_write_names_the_written_table`, `test_cmd_gate_docstring_names_the_half_write` |
| M4: non-default `--src` | `gate` and `gate --all` refuse a src root other than the committed one (`check.DEFAULT_SRC`, read at call time), exit 2. `--src` is for `--partial` only. The tree fixture now stands in for the committed src/ and config/. | `test_gate_refuses_a_non_default_src`, `test_gate_cli_refuses_src_without_partial` (2) |
| M5: partial with account problems | `gate_partial` writes nothing and exits 1 when `source.problems` is non-empty, naming them. | `test_partial_with_source_problems_writes_nothing` |
| M6: cflags rule of a saved file | Not changed here. Recorded under Known limits as a note for 06-23/06-25. | n/a |
| M7: hash window | Each unit file is hashed again just before the write. If it differs from the hash taken around its own check, gate raises CheckError (exit 2) and writes nothing. | `test_a_unit_file_changed_before_the_write_is_refused` |
| M8: exact bytes | `read_status` requires a final LF and requires the file to equal `format_status(rows)` byte for byte. A quoted or re-spelled cell is refused, naming its line. | tests/test_status.py `test_status_refuses_bad_tables[quoted-cell, no-final-lf, header-no-final-lf]` |
| M9: `--all` and source_sha256 | `recheck` compares each matched row's `source_sha256` with the unit file and reports a difference (exit 1). | `test_gate_all_refuses_a_stale_source_sha` |
| M10: `--all` output | `--all` ends with `ok` or `MISMATCH`, never "status.csv not written". `checks` holds one `{exe, unit, functions}` entry per matched unit. The land's per-EXE results go under the new top-level `splice` key. | `test_gate_all_output_shape` |

RED (`a22f512`): 16 new targets failed on their assertions. The full-revert cases raised CheckError, or wrongly exited 0. The rename kept the old name; the stale name passed; the half-write raised a bare OSError; the non-default src passed. The partial with problems wrote a row, the edited file passed, and the stale sha passed. The `--all` text ended "status.csv not written". The three status tables were read without error. Existing tests stayed green; seeded_tree now seeds the real file hashes.

After the fix: `uv run pytest -q tests/test_gate.py tests/test_status.py` gives 95 passed. `uv run pytest -q` gives 1693 passed and 217 skipped (the worktree's real-file skips). `uv run ruff check .` is clean.

## Self-Check: PASSED

- FOUND: tools/reverseapoc/status.py, tools/reverseapoc/gate.py, tests/test_status.py, tests/test_gate.py
- FOUND commits: 1401e62, 4808d0a, 1da0ee2, 8a554d1, 873997a, 309f360, 4f3beb7 (all ancestors of HEAD)
- Acceptance: STATUS_COLUMNS line present; `gate --help` lists `--attempts`, `--json`, `--partial`, `--all`; gate.py has `def cross_check(` and `def gate_all(`; tests/test_gate.py has `test_partial_never_downgrades_a_matched_row`
- Verify: `uv run pytest -q tests/test_status.py tests/test_gate.py` (79 passed); `-k "crosscheck or gate_all or order_independent"` (16 passed); `-k partial` (13 passed); `uv run pytest -q` (1676 passed, 217 skipped); `uv run ruff check .` (all checks passed)

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
