---
phase: 04-compiler-identification
plan: 08
subsystem: tooling
tags: [watcom, wcc386, codegen-probe, idioms, omf, calibration]

requires:
  - phase: 04-compiler-identification (plan 04-04)
    provides: compile_rule with object_sha1/normalized_sha1, the cc_root/_require_compiler real-test pattern
  - phase: 04-compiler-identification (plan 04-05)
    provides: libmatch.SWEPT_VERSIONS
  - phase: 04-compiler-identification (plan 04-02)
    provides: omf.read_object (CODE segments, fixup masks, externs, default libraries)
provides:
  - probe/cg_basic.c, a clean-room C89 codegen probe (pr_eq5, pr_sum, pr_switch, pr_copy, pr_div10, pr_fexpr, pr_call)
  - tools/reverseapoc/probe.py with IDIOMS, FLAG_SETS, count_idioms(code, *, base, exclude, mask), object_code, chk_sites, Cell, Calibration (ties, cell, format, to_json), calibrate
  - the measured idiom table for 10.6 and 11.0 over ten flag sets (probe/README.md)
affects: [04-10, 04-11, 04-12]

actuals:
  tokens: 12764
  tasks: 2
  commits: 4
plan_head_before: 7088b0f9524174b8cbf559a42c5eb5a999d7f155
plan_head_after: a491fa17792028c37ad0bf1cd4fe2abb1f8b12e6

tech-stack:
  added: []
  patterns:
    - "An idiom counter yields the pieces of code each hit reads; a hit is dropped when a piece touches a masked offset or the hit's hull overlaps an excluded VA range"
    - "Jumps are decoded at every byte offset (byte-level, research A7); loop and switch shapes are built from those jumps"
    - "Calibration cells are ordered SWEPT_VERSIONS then flag-set order; a version the gate refuses is recorded as skipped, a failed compile raises CompilerError naming the cell"

key-files:
  created:
    - probe/cg_basic.c
    - probe/README.md
    - tools/reverseapoc/probe.py
    - tests/test_probe.py
    - tests/test_probe_real.py
  modified: []

key-decisions:
  - "Masks apply to the instructions a hit reads, not to the bytes between them: a loop whose body holds a call fixup is still counted, but a masked jump or compare drops the hit"
  - "Two research rows did not reproduce and were recorded as measured, not forced: rep_movsd_small counts 0 at -4r (mov ecx,5 sits 9 bytes before rep movsd), and -5s requests math387s but no clib3s"
  - "calibrate() sorts the requested versions into SWEPT_VERSIONS order and keeps the given flag-set order; with several probe sources a cell's hash is a SHA-1 over the per-source normalized hashes"

patterns-established:
  - "Real probe tests write under build/test-probe/<test>/ and run calibrate once per module through a module-scoped fixture"
  - "A research row that does not reproduce stays in the test with its measured value and an id ending in -measured-..."

requirements-completed: [CID-03]

coverage:
  - id: D1
    description: "Clean-room C89 probe with the seven constructs and a README that says what each discriminates"
    requirement: CID-03
    verification:
      - kind: other
        ref: "grep -c \"//\" probe/cg_basic.c (prints 0)"
        status: pass
      - kind: integration
        ref: "tests/test_probe_real.py#test_byte_compare_calibration"
        status: pass
    human_judgment: true
    rationale: "That the probe is clean-room (nothing copied from mosura) is a judgment call no test can make"
  - id: D2
    description: "Idiom counters (setcc forms, movsd runs, small rep movsd, loop shapes, switch order) with mask/exclude adjacency and empty-input edges"
    requirement: CID-03
    verification:
      - kind: unit
        ref: "tests/test_probe.py (19 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "calibrate(), Cell and Calibration with ties, skipped versions, format and to_json"
    requirement: CID-03
    verification:
      - kind: unit
        ref: "tests/test_probe.py#test_ties, test_calibration_format_and_json, test_calibrate_cells_order_and_skips, test_calibrate_failed_compile_names_the_cell"
        status: pass
    human_judgment: false
  - id: D4
    description: "Real calibration of 10.6 and 11.0 over every flag set, one assertion block per research row"
    requirement: CID-03
    verification:
      - kind: integration
        ref: "REVERSEAPOC_WATCOM_DIR=... uv run pytest -q -rs tests/test_probe_real.py (22 passed, 10.5 skipped by its gate)"
        status: pass
    human_judgment: false

duration: 13min
completed: 2026-10-21
status: complete
---

# Phase 4 Plan 08: Codegen probe and idiom calibration Summary

**Clean-room C89 probe plus byte-level idiom counters, calibrated on the real 10.6 and 11.0 compilers over ten flag sets: the two versions never tie, 10.6 rotates loops and 11.0 top-tests them, and two research rows are recorded as measured instead of forced.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-10-21T17:28:54Z
- **Completed:** 2026-10-21T17:41:35Z
- **Tasks:** 2
- **Files modified:** 5 (all new)

## Accomplishments

- `probe/cg_basic.c`: clean-room C89, seven functions (byte compare, counted loop, sparse switch, five-dword struct copy, division by 10, x87 expression, a caller). `probe/README.md` has the construct table, the clean-room note and the measured table.
- `tools/reverseapoc/probe.py`: the eight counters in IDIOMS order behind one mask/exclude filter, `object_code`, `chk_sites`, `Cell`, `Calibration` and `calibrate`.
- Real calibration on the host: 10.6 and 11.0 x 10 flag sets, 20 cells, no ties. 10.5 is skipped by its gate (reason starts "Watcom 10.5:") until plan 04-11.
- Every hit in the real objects falls in the function the construct lives in, with one exception, a switch_descending hit in 11.0 `-5r -s -ox` that starts in pr_eq5 (byte-level noise, research A7). Checked with a throwaway script that reported only names and offsets.

## Measured calibration table (host, 2026-10-21; counts only)

`and` = setcc_and, `movzx` = setcc_movzx, `movsd` = movsd_unrolled, `rep` = rep_movsd_small, `rot`/`top` = loop_rotated/loop_top_tested, `up`/`down` = switch_ascending/descending.

| version | flags | and | movzx | movsd | rep | rot | top | up | down | `__CHK` | default libraries |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 10.6 | `-3r -s` | 0 | 1 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-4r -s` | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r -s` | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r` | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 7 | math387r, emu387 |
| 10.6 | `-4r -s -ox` | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r -s -ox` | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r -s -oneatx` | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r -s -os` | 0 | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, emu387 |
| 10.6 | `-5r -s -fpi87` | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | math387r, noemu387 |
| 10.6 | `-5s -s` | 1 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | math387s, emu387 |
| 11.0 | `-3r -s` | 0 | 1 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | math387r, emu387 |
| 11.0 | `-4r -s` | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | math387r, emu387 |
| 11.0 | `-5r -s` | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | math387r, emu387 |
| 11.0 | `-5r` | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 | 7 | math387r, emu387 |
| 11.0 | `-4r -s -ox` | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | math387r, emu387 |
| 11.0 | `-5r -s -ox` | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 1 | 0 | math387r, emu387 |
| 11.0 | `-5r -s -oneatx` | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | math387r, emu387 |
| 11.0 | `-5r -s -os` | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | math387r, emu387 |
| 11.0 | `-5r -s -fpi87` | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | math387r, noemu387 |
| 11.0 | `-5s -s` | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 | 0 | math387s, emu387 |

Ties: none (no two versions produce the same normalized object for any flag set). Skipped: 10.5 (gate refused, damaged BINW compiler).

## Deviations from 04-RESEARCH.md (for plan 04-11)

| Row | Research expectation | Measured |
|---|---|---|
| 10.6 `-4r -s` struct copy | `mov ecx,5; rep movsd`, counted as `B9 <1..16> 00 00 00 F3 A5` (rep_movsd_small >= 1) | rep_movsd_small = 0 in every cell. Both instructions are there at `-3r` and `-4r` for both versions, but `mov ecx,5` sits 9 bytes before `rep movsd`, with other moves between. The test asserts the measured 0, plus movsd_unrolled = 0 at `-4r`, which keeps the -4/-5 split visible. Consequence for 04-10: a game-code count of 0 for the adjacent encoding does not rule out `-4`. |
| `-5s -s` default libraries | clib3s and math387s | math387s and emu387; no CLIB library is requested under any flag set (clib3r is absent too). The test asserts math387s present, math387r absent and clib3s absent (measured). |

Every other research row reproduced: `movzx` at 10.6 `-3r`; `and`, unrolled movsd and no small rep movsd at 10.6 `-5r`; `and` at 11.0 `-4r`; neither setcc form at 11.0 `-5r`; rotated loops for 10.6 and top-tested for 11.0 at `-5r -s`; `__CHK` calls without `-s` (7, one per function) and none with `-s`; emu387 with `-fpi` and noemu387 with `-fpi87`, on both versions.

Not a research row, but relevant to 04-10: 10.6 at `-5r -s -os` emits `movzx`, so a movzx hit alone does not prove `-3`. Under `-oneatx` neither loop shape is found for either version, as the research noted.

## Task Commits

1. **Task 1: Tracer - the probe through omf and the byte-compare counter**
   - RED `cb8891f` test(04-08): add failing tests for the byte-compare idiom counter and probe tracer
   - GREEN `8e9bec2` feat(04-08): add the clean-room probe and the byte-compare idiom counters
2. **Task 2: All idiom counters, stack checks, default libraries, the calibration matrix with ties**
   - RED `5f2ee36` test(04-08): add failing tests for every idiom counter and the calibration matrix
   - GREEN `a491fa1` feat(04-08): count every probe idiom and calibrate 10.6 and 11.0 per flag set

**Plan metadata:** committed with this SUMMARY (docs(04-08)).

## TDD record

- **RED (Task 1):** tests/test_probe.py and tests/test_probe_real.py were committed before `reverseapoc.probe` existed. The run stopped at collection with `ModuleNotFoundError: No module named 'reverseapoc.probe'`. Semantic assessment: this fails for the intended reason (the feature is missing) and matches earlier RED commits in this phase (e.g. 1cda9d4 for libmatch), but under the strict GSD classifier it is a load failure, not an assertion failure. `gsd_run check tdd-red-evidence` was not run.
- **RED (Task 2):** the new tests imported names that did not exist yet (`FLAG_SETS`, `Calibration`, `Cell`, `calibrate`, `chk_sites`): `ImportError` at collection, the same classification as above.
- **GREEN:** 19 unit tests pass. Real: 22 passed, 1 skipped (10.5). The first real run failed three assertions: the two research rows above, with 10.6 and 11.0 each asserting clib3s. Those assertions were changed to the measured values. The probe and the counters were not changed.
- **REFACTOR:** none as a separate commit. The compare opcodes got names and the calibrate loop was split into `_compile_probe` before the GREEN commit.
- **Tracer gate:** interactive run, `end-of-phase` mode, automated-only verify. The Task 1 verify was re-run after its commit and passed, so expansion continued.

## Files Created/Modified

- `probe/cg_basic.c` - clean-room C89 codegen probe
- `probe/README.md` - construct table, clean-room note, measured calibration table and reading
- `tools/reverseapoc/probe.py` - counters, object_code, chk_sites, Cell, Calibration, calibrate
- `tests/test_probe.py` - counters on hand-written encodings, Calibration bookkeeping, calibrate on fake trees
- `tests/test_probe_real.py` - byte-compare tracer, research rows, default libraries, flag-set coverage, 10.5 tie check

## Decisions Made

- Masks apply to the instructions a hit reads (pieces), and exclusions to the hit's hull. A call fixup in a loop body therefore does not hide the loop, but a masked jump does (`test_loop_mask_reads_only_the_jumps`).
- `calibrate()` puts the requested versions in SWEPT_VERSIONS order, so cell order does not depend on the caller (the CID-03 ordering edge). Flag sets keep the order given (FLAG_SETS by default).
- `Calibration.cell()` raises `KeyError` for a missing cell, so a typo in a test fails instead of skipping.
- `tests/test_probe.py` also runs `calibrate()` against fake trees with the existing FakeCompiler (watcomtree.py) and a synthetic OMF object (omfimage.py). That covers skip, ordering and failure paths without real compilers.

## Deviations from Plan

### Auto-fixed Issues

None. The two research rows that did not reproduce were handled as the plan says (assert the measured value, record it above); they are not code deviations.

### Environment adaptations

- The sandbox refused the plan's `REVERSEAPOC_WATCOM_DIR="$(git rev-parse --path-format=absolute --git-common-dir)/../third_party/watcom"` form. The real tests ran with the relative `REVERSEAPOC_WATCOM_DIR=../../../third_party/watcom` from the worktree root, as the orchestrator allowed. The gate resolves it to the main checkout's tree; the log shows the 10.6 and 11.0 gate SHA-1s.
- The plan-commit ledger file could not be written into the worktree's git dir (the sandbox refused). The base 7088b0f is the dispatch base from the branch check, and the commit count above is measured with `git rev-list --count 7088b0f..HEAD`.

**Total deviations:** 0 auto-fixed. **Impact:** none on scope.

## Issues Encountered

- clang is not installed on the host, so the C89 lint gate (`clang -fsyntax-only -std=gnu89 -Werror=declaration-after-statement`) was not run on probe/cg_basic.c. That gate covers `src/**`, and the probe is outside it. The probe compiles cleanly under both wcc386 versions and has no `//` comments.

## Known Stubs

None.

## User Setup Required

None.

## Next Phase Readiness

- Plan 04-10 can call `count_idioms(code, base=..., exclude=runtime_ranges, mask=...)` on the game's code objects and compare against `calibrate()` cells. It should read the two deviations first: rep_movsd_small cannot show `-4`, and movzx appears under 10.6 `-os`.
- Plan 04-11: once 10.5 is reinstalled, `test_calibration_with_10_5` runs all three versions and checks that `ties()` agrees with the cells' hashes. The expected result is "10.6 (10.5 byte-identical on the probe)".

## Self-Check: PASSED

- All six files exist: probe/cg_basic.c, probe/README.md, tools/reverseapoc/probe.py, tests/test_probe.py, tests/test_probe_real.py, and this SUMMARY.
- Commits cb8891f, 8e9bec2, 5f2ee36 and a491fa1 are on this branch (`git log 7088b0f..HEAD`). No file was deleted (`git diff --diff-filter=D 7088b0f HEAD` is empty), and the working tree is clean.
- Acceptance checks:
  - `uv run pytest -q`: 729 passed, 92 skipped. `uv run ruff check .`: clean.
  - `grep -c "//" probe/cg_basic.c` prints 0, and `grep -c "Calibration (host" probe/README.md` prints 1.
  - `grep -n "def count_idioms"` finds it.
  - `pytest -k "movsd or rep_movsd or loop or switch or calibration_format or ties"`: 10 passed.
  - Real verify (relative watcom dir): 22 passed, 1 skipped. The only skip is "Watcom 10.5: gate refused".

---
*Phase: 04-compiler-identification*
*Completed: 2026-10-21*
