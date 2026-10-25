---
phase: 06-reporting-and-agent-pilot
plan: 02
subsystem: tooling
tags: [python, fileio, atomic-write, symbols, refactor]

requires: []
provides:
  - "public fileio.write_atomic, the one atomic writer of tools/reverseapoc (DI-18, D-41)"
  - "splice._write_atomic as a one-release alias of fileio.write_atomic"
  - "SymbolTable refuses out-of-range symbols.csv data rows (when given data ranges) and renamed-address placeholders"
  - "SYMBOL_KIND_FUNC / SYMBOL_KIND_DATA derived from functions.SYMBOL_KINDS"
  - "set-based uniqueness checks in read_units_csv / read_symbols_csv"
affects: [06-status-table, 06-gate, 06-progress, 06-driver, 06-06, 06-16]

actuals:
  tokens: 7575
  tasks: 3
  commits: 6
plan_head_before: 021a58ba7441665b1eb5486caef92c91f23ad9c2
plan_head_after: bc84d084ac966b3e82639d31434c3a50450ba792

tech-stack:
  added: []
  patterns:
    - "Every file write goes through fileio.write_atomic (temp next to the target, os.replace, temp removed on failure)"
    - "Row checks passed to functions._load that need state are built once per read (a factory returning the follows callable)"

key-files:
  created:
    - tools/reverseapoc/fileio.py
    - tests/test_fileio.py
  modified:
    - tools/reverseapoc/splice.py
    - tools/reverseapoc/compiler.py
    - tools/reverseapoc/asm.py
    - tools/reverseapoc/check.py
    - tools/reverseapoc/cli.py
    - tools/reverseapoc/functions.py
    - tools/reverseapoc/land.py
    - tools/reverseapoc/libmatch.py
    - tools/reverseapoc/omf2elf.py
    - tools/reverseapoc/symbols.py
    - tests/test_compiler.py
    - tests/test_symbols.py
    - tests/test_functions.py

key-decisions:
  - "fileio.py carries only a module docstring: write_atomic is project-original (d4de0d8, WR-03), and no project-original neighbour carries a license header line"
  - "The symbols.csv data-range check runs only when SymbolTable.build is given data ranges (ruling F6); production callers always pass data_ranges(le)"
  - "address_of refuses both the func_ and the D_ placeholder of a renamed address, with the symbols.csv name in the message"

patterns-established:
  - "fileio.write_atomic is the import for any new writer; splice._write_atomic is removed after one release (D-41)"

requirements-completed: [RPT-01, AGT-06]

coverage:
  - id: D1
    description: "fileio.write_atomic replaces/creates files, keeps the old file on failure, replaces a link, and splice._write_atomic is the same object"
    requirement: RPT-01
    verification:
      - kind: unit
        ref: "tests/test_fileio.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "Only splice.py names _write_atomic; eight modules import write_atomic from .fileio"
    requirement: AGT-06
    verification:
      - kind: unit
        ref: "tests/test_fileio.py#test_no_module_imports_the_private_alias"
        status: pass
      - kind: other
        ref: "grep -l _write_atomic tools/reverseapoc/*.py -> tools/reverseapoc/splice.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "SymbolTable refuses out-of-range data rows (rows 3, 7b) and renamed-address placeholders (7a); SYMBOL_KIND_FUNC derived (7c); linear follows checks (7d)"
    verification:
      - kind: unit
        ref: "tests/test_symbols.py, tests/test_functions.py#test_unit_and_symbol_follow_checks_keep_their_verdicts"
        status: pass
      - kind: integration
        ref: "REVERSEAPOC_ORIG=<main>/orig uv run pytest tests/test_functions_real.py tests/test_check_real.py (43 passed, 4 tool skips)"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 02: fileio.write_atomic and the symbols minors Summary

**`write_atomic` moved out of splice into a public `fileio.write_atomic` that all eight writer modules import (splice keeps `_write_atomic` as an alias for one release). The symbol table now refuses symbols.csv data rows outside the LE data objects and the func_/D_ placeholders of addresses symbols.csv renames. `SYMBOL_KIND_FUNC` is now derived from `SYMBOL_KINDS`, and the CSV uniqueness checks use set lookups.**

Execution context nonce: 23c816a0c70e2f32

## Performance

- **Duration:** about 12 min
- **Started:** 2026-10-25T01:08:33Z
- **Completed:** 2026-10-25T01:20:13Z
- **Tasks:** 3
- **Files modified:** 15 (2 created, 13 modified)

## Accomplishments

- DI-18 / D-41: `tools/reverseapoc/fileio.py` holds `write_atomic`, moved verbatim with its docstring. splice re-exports it as `_write_atomic` for one release. asm, check, cli, compiler, functions, land, libmatch and omf2elf import it from `.fileio`.
- DI-19 rows 3 and 7b: a symbols.csv `data` row outside every data range raises SymbolError naming the address as `0x%08X`. The check runs whenever data ranges are given (ruling F6).
- DI-19 row 7a: `address_of("func_00010010_")` raises SymbolError naming `main_` when symbols.csv renames 0x00010010. The `_D_` placeholder of a renamed data address is refused the same way.
- DI-19 row 7c: `SYMBOL_KIND_FUNC = SYMBOL_KINDS[0]` (plus `SYMBOL_KIND_DATA = SYMBOL_KINDS[1]`). symbols.py no longer contains a `"func"` literal.
- DI-19 row 7d: `_unit_follows` and `_symbol_follows` are now built once per read and keep seen names and addresses in sets, so each row is one lookup instead of an `any()` scan.
- Host suite went from 1416 passed / 215 skipped to 1430 passed / 216 skipped. The one new skip is the symlink test on this Windows host. ruff is clean.

## Task Commits

| DI row | Task | RED | GREEN |
|--------|------|-----|-------|
| DI-18 (fileio + splice alias + compiler) | 1 (tracer) | `1681fdc` test | `cfb84d4` refactor |
| DI-18 (seven remaining importers) | 2 | `f90097f` test | `732a537` refactor |
| DI-19 rows 3, 7a, 7b, 7c, 7d | 3 | `863114d` test | `bc84d08` fix |

Tracer gate (Task 1): interactive mode with end-of-phase verification, and the verify is automated only. I re-ran `uv run pytest -q tests/test_fileio.py tests/test_compiler.py tests/test_splice.py`: 179 passed, 1 skipped (symlink). Then I continued to Task 2.

## Files Created/Modified

- `tools/reverseapoc/fileio.py` (new): `write_atomic(path, data)`.
- `tests/test_fileio.py` (new): replace, create-missing, keep-old-on-failure, link-replaced, the alias identity, and the `_write_atomic` scan of the package.
- `tools/reverseapoc/splice.py`: definition replaced by `from .fileio import write_atomic as _write_atomic` with a one-release comment (D-41). The now-unused `import secrets` is gone.
- `tools/reverseapoc/{asm,check,cli,compiler,functions,land,libmatch,omf2elf}.py`: import from `.fileio`, call sites renamed.
- `tests/test_compiler.py`: three references renamed (`real = compiler.write_atomic`, two monkeypatches).
- `tools/reverseapoc/symbols.py`: derived kind constants, `_check_symbol` (data-range check), `_refuse_renamed` in `address_of`, shared `_in_data_range`, F6 note in `SymbolTable.build`'s docstring.
- `tools/reverseapoc/functions.py`: `_unit_follows()` / `_symbol_follows()` factories with per-read sets.
- `tests/test_symbols.py`, `tests/test_functions.py`: the minors' tests.

## Decisions Made

- fileio.py has a module docstring and no provenance or license line. `_write_atomic` was written in this project (`d4de0d8`, WR-03), not taken from KKND-Decomp. No project-original module carries a header line.
- The `follows` checks became factories, so `_load`'s `follows(rows, row)` contract is unchanged and no other reader is affected.

## Deviations from Plan

### Orchestrator rulings applied

- **Orchestrator ruling F6: when the data-range check applies.** symbols.csv `data` rows are checked against `data_ranges` only when the table gets non-empty ranges, and `SymbolTable.build`'s docstring says so. Tests cover both sides: `test_data_symbol_is_not_range_checked_without_data_ranges` (loads with `data_ranges=()`) and `test_data_symbol_outside_every_data_range_is_refused[past|at-end|before]` (raises naming the address when ranges are given). Commits `863114d`, `bc84d08`.
- **Orchestrator ruling F22: alias sites and the 7a spelling.** compiler.py's stamp comment now names `fileio.write_atomic` instead of `splice._write_atomic`. All three test_compiler.py sites were renamed (:437, :443, :458). The 7a test uses the linker spelling `address_of("func_00010010_")` and expects `main_` in the error. Commits `cfb84d4`, `863114d`.
- **Orchestrator ruling F2 / R-A: the symlink skip.** `test_write_atomic_replaces_a_link` skips only when `symlink_to` raises OSError, with exactly the reason `symlink creation needs privileges on this host`. It skips on this Windows host and runs in the container. Commit `1681fdc`.

### Auto-fixed / minor deviations

**1. [Rule 2 - Missing test] Extra coverage beyond the plan's behaviour list**
- **Found during:** Tasks 1 and 3
- **Issue:** Each behaviour change needs a test (rulings preamble). The plan's list did not cover writing a new file, the D_ side of 7a, or the in-range boundary.
- **Fix:** Added `test_write_atomic_creates_a_missing_file`, `test_address_of_refuses_the_data_placeholder_of_a_renamed_address` and `test_data_symbol_inside_a_data_range_loads` (first and last byte of the range).
- **Committed in:** `1681fdc`, `863114d`

**2. [Plan text] The 7c test was RED, not a passing pin**
- **Found during:** Task 3 RED
- **Issue:** The plan expected `test_symbol_kind_func_is_one_of_symbol_kinds` to pass before the change. Its "no second literal" assertion fails while symbols.py still says `SYMBOL_KIND_FUNC = "func"`.
- **Fix:** None needed. It failed on that assertion at RED and passes after GREEN. The 7d pin did pass before and after the change. I also proved it fails when any one of the three scans is hand-broken to `rows[-1:]`, then restored the file with `git checkout -- tools/reverseapoc/functions.py`.

**3. [Plan text] Task 1 RED is a collection error**
- **Issue:** As the plan says, RED fails because `reverseapoc.fileio` does not exist (ImportError at collection). `workflow.tdd_mode` is off, so the strict RED-evidence classifier does not apply. The Task 2 and Task 3 REDs fail on assertions.

**4. [Rule 3 - Tooling] Plan ledger not written to the git dir**
- **Issue:** The worktree sandbox refused writes to `.git/worktrees/<id>/gsd-plan-head-before-06-02`.
- **Fix:** `commits:` was measured directly as `git rev-list --count 021a58ba..HEAD` = 6, starting from the dispatch base.

---

**Total deviations:** 3 orchestrator rulings applied (F6, F22, F2), 1 rule-2 test addition, 3 notes on plan text and tooling.
**Impact on plan:** No scope creep. Behaviour of every committed CSV and generated file is unchanged (the existing suite and the real-LE tests stay green).

## Issues Encountered

- While checking Task 2's grep scan I mistakenly redirected its output to `C:/Users/Ayrton/Documents/Gitprojects/scan.tmp`, outside both checkouts. It held only the scan text (`tools/reverseapoc/splice.py `). I deleted it right away.
- `uv run ruff format --check tools tests` reports 31 files that would be reformatted. That was already true before this plan and is outside the done gate (`ruff check`). All files this plan created or changed are formatted.
- Real-file check on the host: I ran `REVERSEAPOC_ORIG/REVERSEAPOC_WATCOM_DIR/REVERSEAPOC_GHIDRA_EXPORT=<main checkout>` with `uv run pytest tests/test_functions_real.py tests/test_check_real.py tests/test_symbols.py`: 43 passed, 4 skipped (objdiff-cli or ninja not on PATH). The committed symbols.csv files load under the stricter table built from the real LE's data ranges. The container suite in 06-16 re-proves this.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Later plans (status table, gate, progress feed, driver) can import `from .fileio import write_atomic`.
- Remove `splice._write_atomic` one release after this plan (D-41). `tests/test_splice.py:1041/1047` and `test_splice_alias_is_the_same_object` are its only remaining users.

## Self-Check: PASSED

- FOUND: tools/reverseapoc/fileio.py, tests/test_fileio.py
- FOUND commits: 1681fdc, cfb84d4, f90097f, 732a537, 863114d, bc84d08 (all ancestors of HEAD)
- Acceptance: `def write_atomic(path: Path, data: bytes) -> None:` in fileio.py; `from .fileio import write_atomic as _write_atomic` in splice.py; `"write_atomic"` monkeypatched twice in test_compiler.py; eight modules import write_atomic from .fileio; both named test_symbols tests exist; `SYMBOL_KIND_FUNC = SYMBOL_KINDS[0]`.
- Plan verification: `uv run pytest -q` 1430 passed / 216 skipped, `uv run ruff check .` clean, only splice.py names `_write_atomic`.

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
