---
phase: 04-compiler-identification
plan: 10
subsystem: tooling
tags: [watcom, codegen-probe, idioms, runtime-map, flag-evidence, cli, python]

requires:
  - phase: 04-compiler-identification (plan 04-07)
    provides: config/ufo2p/runtime.csv (121 ranges) and config/tacp/runtime.csv (132 ranges), read_runtime_csv, runtime_csv_path
  - phase: 04-compiler-identification (plan 04-08)
    provides: IDIOMS, count_idioms with the corrected counters (review fix rounds 1 and 2), Cell, Calibration, calibrate
  - phase: 04-compiler-identification (plan 04-05)
    provides: libmatch.target_view, SWEPT_VERSIONS, select_target/read_target/refuse_output/check_versions
provides:
  - "probe.ExeScan, scan_exe, chk_calls, flag_evidence, consistent_cells, DECISIVE_FAMILIES, runtime_rows, ProbeError, Calibration.from_json"
  - "`uv run reverseapoc probe calibrate` (table + JSON, default build/probe/calibration.json) and `uv run reverseapoc probe scan EXE [--runtime CSV] [--calibration JSON] [--json]`"
  - "Per-EXE non-library idiom counts, __CHK calls by 64 KiB block, one evidence line per observable flag, and the consistent calibration cells (recorded below for plan 04-11)"
affects: [04-11 toolchain docs, 04-12, phase-05 cflags rules]

actuals:
  tokens: 11075
  tasks: 3
  commits: 7
plan_head_before: 0d0698272a81c121ad2960096e5280a56b7c6f08
plan_head_after: 1c47087b3d02c95a597d5a00d2fafbce5e238f0f

tech-stack:
  added: []
  patterns:
    - "A scan of the game's code object always takes the committed runtime map; a missing map is refused with the `libmatch <EXE> --write` hint instead of counting the whole object"
    - "The verdict keeps every calibration cell the decisive idiom families allow; nothing is voted, and ties are computed among the consistent cells only"
    - "Real-file assertions pin the measured values with the research value named in a comment when they differ"

key-files:
  created: []
  modified:
    - tools/reverseapoc/probe.py
    - tools/reverseapoc/cli.py
    - tests/test_probe.py
    - tests/test_probe_real.py
    - tests/test_cli.py

key-decisions:
  - "scan_exe masks every LE fixup byte inside the code object (the production mask), so a relocated operand is never read as an idiom; the decisive counts still equal the research's for setcc and unrolled movsd"
  - "The research reading 'no 11.0, no -3r/-4r cell' does not hold with the corrected counters: rep_movsd_small finds 4 (UFO2P) and 2 (TACP) copies, so both versions' -4r cells stay consistent. Recorded as measured and asserted as measured, not forced; the rule and the counters are unchanged"
  - "A sixth evidence line, 'shapes (not decisive):', reports loop and switch counts with the switch counter's eax/al coverage limit; consistent_cells never reads them"
  - "Calibration.from_json refuses a calibration whose idiom list differs from IDIOMS, so a table from other counters is never compared with a scan"

patterns-established:
  - "probe scan output: a header line, one indented line per idiom (`  <name>  <count>`), then evidence lines at column 0, then with --calibration a `consistent:` section and a `ties:` line"

requirements-completed: [CID-03, CID-05]  # copied from the plan; REQUIREMENTS.md is not marked here: requirements.ready-ids blocks both until 04-11/04-12 (which also declare them) have SUMMARYs

coverage:
  - id: D1
    description: "probe scan counts every idiom in each EXE's non-library code with the committed runtime map, reports non-library and library bytes, and refuses a missing runtime map"
    requirement: CID-03
    verification:
      - kind: unit
        ref: "tests/test_probe.py#test_scan_excludes_runtime_rows, test_scan_touching_row_boundary, test_scan_masks_le_fixup_bytes, test_scan_format_and_json"
        status: pass
      - kind: unit
        ref: "tests/test_cli.py#test_probe_scan_missing_runtime_map, test_probe_scan_prints_counts, test_probe_scan_json"
        status: pass
      - kind: integration
        ref: "REVERSEAPOC_ORIG=../../../orig uv run pytest -q tests/test_probe_real.py -k exe_nonlibrary (2 passed, no skip)"
        status: pass
    human_judgment: false
  - id: D2
    description: "__CHK stack-check calls (push imm32; call into the row publishing __CHK) counted per EXE and grouped by 64 KiB block"
    requirement: CID-05
    verification:
      - kind: unit
        ref: "tests/test_probe.py#test_chk_calls, test_chk_calls_blocks_sorted, test_chk_calls_need_the_push_and_a_chk_row"
        status: pass
      - kind: integration
        ref: "tests/test_probe_real.py#test_exe_chk_calls (UFO2P.EXE, TACP.EXE)"
        status: pass
    human_judgment: false
  - id: D3
    description: "One evidence line per observable flag per EXE (calling convention, fpu, cpu, stack checks, memory model, plus non-decisive shapes), each naming its source and counts"
    requirement: CID-05
    verification:
      - kind: unit
        ref: "tests/test_probe.py#test_flag_evidence_lines, test_flag_evidence_without_rows, test_scan_exe_fills_stack_checks_and_evidence"
        status: pass
    human_judgment: true
    rationale: "Whether the wording of each evidence line is what plan 04-11 can cite in docs/toolchain.md is a reading judgment; the counts themselves are tested"
  - id: D4
    description: "consistent_cells over the decisive families and the measured consistent cells for both EXEs, with ties kept as ties"
    requirement: CID-05
    verification:
      - kind: unit
        ref: "tests/test_probe.py#test_consistent_cells, test_consistent_cells_family_without_exe_hits_removes_nothing, test_decisive_families"
        status: pass
      - kind: integration
        ref: "tests/test_probe_real.py#test_exe_consistent_cells (asserts the measured list)"
        status: pass
    human_judgment: true
    rationale: "The measured verdict departs from the research reading (11.0 -4r stays consistent); what that means for the version and flags is plan 04-11's call, with the struct-copy size finding below"
  - id: D5
    description: "probe calibrate writes the calibration JSON atomically; probe scan --calibration prints the consistent cells and their ties; malformed calibration JSON is refused naming the file"
    requirement: CID-05
    verification:
      - kind: unit
        ref: "tests/test_probe.py#test_calibration_json_round_trip, test_calibration_from_json_refuses_malformed_shapes (8 cases)"
        status: pass
      - kind: unit
        ref: "tests/test_cli.py#test_probe_calibrate_writes_json, test_probe_scan_with_calibration, test_probe_scan_with_calibration_json, test_probe_scan_bad_calibration_json (3 cases)"
        status: pass
      - kind: integration
        ref: "uv run reverseapoc probe calibrate --watcom-dir ../../../third_party/watcom --output build/probe/calibration.json && uv run reverseapoc probe scan TACP.EXE --orig ../../../orig --calibration build/probe/calibration.json (consistent: and stack checks: present)"
        status: pass
    human_judgment: false

duration: 17min
completed: 2026-10-21
status: complete
---

# Phase 4 Plan 10: Probe scan of the game's non-library code Summary

**`reverseapoc probe scan` counts the calibrated idioms in each EXE's non-library code using the committed runtime map, counts the `__CHK` stack checks by 64 KiB block, prints one evidence line per flag, and lists the calibration cells the code is consistent with. `probe calibrate` writes the table as JSON. The research's `__CHK` (40/32), setcc and unrolled movsd counts reproduce exactly. The corrected small rep movsd counter finds 4 and 2 copies where the research found 0, so both versions' `-4r` cells stay consistent. That is recorded as measured, for plan 04-11.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-10-21T18:49:29Z
- **Completed:** 2026-10-21T19:06:05Z (SUMMARY written shortly after)
- **Tasks:** 3 (all TDD; Task 1 is the tracer)
- **Files modified:** 5

## Accomplishments

- `probe.scan_exe(le, rows, *, exe)` gives an `ExeScan` with the counts in IDIOMS order. Every runtime row is excluded (a hit that touches a row by one byte is dropped) and every LE fixup byte is masked. It reports non-library and library byte totals, the `__CHK` calls and blocks, and the evidence lines.
- `chk_calls`: `68 imm32` then `E8 rel32` whose target lies in a row publishing `__CHK`. The site must lie outside every row. Sites are grouped by 64 KiB block.
- `flag_evidence`: calling convention, fpu, cpu, stack checks and memory model, plus `shapes (not decisive):`. Each line names its source and its counts, and a mix is reported as a mix.
- `consistent_cells` uses `DECISIVE_FAMILIES` (byte_compare, struct_copy) and never reads loop or switch counts. Nothing is voted.
- `Calibration.from_json` and `ProbeError`. The `probe` verb has `calibrate` and `scan` (`--runtime`, `--calibration`, `--json`). `probe.runtime_rows` holds the missing-map refusal.

## Real results (host, 2026-10-21; counts, addresses and names only)

Inputs: the main checkout's `orig/` and `third_party/watcom` (read-only, via `../../../orig` and `../../../third_party/watcom` from the worktree root), and the committed runtime maps. Calibration: 10.6 and 11.0 over the ten flag sets. 10.5 was skipped by its gate (damaged BINW compiler, until plan 04-11). The table equals probe/README.md's re-run table cell for cell.

### Counts, old vs new (CID-03)

"Research" is 04-RESEARCH Pattern 6 (old blind counters, prototype mask). "Measured" is this plan: corrected 04-08 counters, every LE fixup byte masked, and the committed runtime maps excluded.

| Idiom | Research UFO2P / TACP | Measured UFO2P / TACP | Note |
|---|---|---|---|
| setcc_and | 30 / 58 | 30 / 58 | same |
| setcc_movzx | 0 / 0 | 0 / 0 | same |
| movsd_unrolled | 75 / 35 | 75 / 35 | same (fix round 2's operand boundary did not change a game count) |
| rep_movsd_small | 0 / 0 (adjacent `B9 n 00 00 00 F3 A5`) | **4 / 2** | the corrected counter allows up to 4 register moves between `mov ecx` and `rep movsd` |
| `__CHK` calls | 40 / 32, blocks 0x10000 and 0xB0000 | 40 / 32: 0x00010000 37 + 0x000b0000 3 / 0x00010000 26 + 0x000b0000 6 | same totals and blocks |
| loop_rotated / loop_top_tested | 111/80, 99/105 (a structural matcher, not this counter) | 357/194, 262/223 | byte-level counters, not comparable with the research's matcher; not decisive |
| switch_ascending / switch_descending | not counted | 10/7, 12/10 | eax/al compares only; not decisive |
| code bytes non-library / runtime rows | n/a | 741,159 / 43,958; 749,928 / 46,055 | runtime bytes equal 04-07's coverage (5.60% / 5.79%) |

### UFO2P.EXE evidence lines (`uv run reverseapoc probe scan UFO2P.EXE --calibration build/probe/calibration.json`)

```
calling convention: 3R only 102 rows, 3S only 0 rows, both 18 rows (source: runtime rows); register (r) convention
fpu: EMU387 1 row, NOEMU387 0 rows; MATH387 15 rows, MATH3 1 row (0 only in MATH3) (source: runtime rows); an EMU387 row means some object requested emu387 (-fpi), and -fpi87 modules linked beside it would not show (research A3)
cpu: setcc_and 30, setcc_movzx 0, movsd_unrolled 75, rep_movsd_small 4 (source: idiom counts in non-library code); read against the calibration cells (probe calibrate)
stack checks: 40 __CHK calls (push imm32; call __CHK) in non-library code, by block 0x00010000 37, 0x000b0000 3 (source: idiom counts, __CHK from runtime row stk); each call is a function built without -s (research A6)
memory model: 2 objects, 2 with the 32-bit flag (source: LE object table); flat 32-bit layout (-mf)
shapes (not decisive): loop_rotated 357, loop_top_tested 194, switch_ascending 10, switch_descending 7 (source: idiom counts in non-library code; byte-level, research A7; switch compares cover eax/al only: cmp eax,imm8, cmp eax,imm32, cmp al,imm8)
consistent: 10 of 20 calibration cells
  10.6 -4r -s
  10.6 -5r -s
  10.6 -5r
  10.6 -4r -s -ox
  10.6 -5r -s -ox
  10.6 -5r -s -oneatx
  10.6 -5r -s -fpi87
  10.6 -5s -s
  11.0 -4r -s
  11.0 -4r -s -ox
ties: none
calibration skipped: 10.5
```

### TACP.EXE evidence lines (`uv run reverseapoc probe scan TACP.EXE --calibration build/probe/calibration.json`)

```
calling convention: 3R only 113 rows, 3S only 0 rows, both 18 rows (source: runtime rows); register (r) convention
fpu: EMU387 1 row, NOEMU387 0 rows; MATH387 19 rows, MATH3 1 row (0 only in MATH3) (source: runtime rows); an EMU387 row means some object requested emu387 (-fpi), and -fpi87 modules linked beside it would not show (research A3)
cpu: setcc_and 58, setcc_movzx 0, movsd_unrolled 35, rep_movsd_small 2 (source: idiom counts in non-library code); read against the calibration cells (probe calibrate)
stack checks: 32 __CHK calls (push imm32; call __CHK) in non-library code, by block 0x00010000 26, 0x000b0000 6 (source: idiom counts, __CHK from runtime row stk); each call is a function built without -s (research A6)
memory model: 2 objects, 2 with the 32-bit flag (source: LE object table); flat 32-bit layout (-mf)
shapes (not decisive): loop_rotated 262, loop_top_tested 223, switch_ascending 12, switch_descending 10 (source: idiom counts in non-library code; byte-level, research A7; switch compares cover eax/al only: cmp eax,imm8, cmp eax,imm32, cmp al,imm8)
consistent: 10 of 20 calibration cells
  (the same ten cells as UFO2P, in the same order)
ties: none
calibration skipped: 10.5
```

### Reading the verdict, and what plan 04-11 must look at

- **Research claims that hold** (asserted in `test_exe_consistent_cells`): no `-3r` cell is consistent (setcc;and with no movzx), no 11.0 `-5` cell is consistent (11.0 branches at `-5`), and 10.6 `-5r` cells are consistent.
- **Research claims that do not hold:** "no 11.0" and "no `-4r`". The rep movsd hits keep both versions' `-4r` cells, which emit setcc;and plus `mov ecx,5 .. rep movsd`. The decisive families cannot separate 10.6 `-4r` from 11.0 `-4r`. Ties: none, because no two consistent cells share flags with equal hashes. Per D-07/D-10 this stays a mix and is not voted apart. The loop shapes favour rotation (10.x) in both EXEs, but they are not decisive and the rule does not read them. The runtime-library evidence (11 modules match only 10.6, 04-07) is separate evidence for 04-11 to weigh.
- **Struct-copy size (throwaway experiment, nothing committed; counts only).** The probe calibrates only a 5-dword copy. I compiled 4, 6, 8 and 16-dword struct copies (`build/probe-exp/`, gitignored) with 10.6 and 11.0 at `-4r -s`, `-5r -s` and `-5r -s -ox`:
  - 4 dwords: movsd_unrolled 1, rep_movsd_small 0 in every cell.
  - 6, 8 and 16 dwords: movsd_unrolled 0, rep_movsd_small 1 in every cell.
  So only the 5-dword size separates `-4` (rep) from `-5` (unrolled). In the game, every unrolled run is 2 to 4 movsd long (UFO2P 48/13/14, TACP 26/8/1 runs of length 2/3/4), which `-4r` emits too. Of the rep hits, UFO2P's 4 all copy 6 to 16 dwords, consistent with `-4` and `-5` alike. TACP has 1 rep copy of 6 to 16 dwords and **1 of exactly 5 dwords**, the calibrated `-4`-style copy (at `-5` it would be unrolled). The research's "unrolled movsd = -5 struct copy" therefore does not follow from these counts. The struct-copy family decides little beyond the 5-dword size, and TACP's one 5-dword rep copy points to at least one `-4` (or `-3`) module. I did not change the counters, the rule or the calibration; this is for 04-11 (and possibly a sized struct-copy probe).
- **Calling convention:** no row matches only 3S libraries in either EXE. The 18 rows listing CLIB3S also list CLIB3R (the shared asm modules), so the line reads register convention.
- **FPU:** one EMU387 row and no NOEMU387 row, so some object requested emu387 (`-fpi`). The A3 caveat stays in the line.
- **Stack checks:** the 40/32 calls sit in the 0x10000 and 0xB0000 blocks, below `_cstart_` (research A6). Phase 5 maps them to translation units.

## Task Commits

1. **Task 1: Tracer - `probe scan` counts the idioms in non-library code**
   - RED `ea51e75` test(04-10): add failing tests for the probe scan of an EXE's non-library code
   - GREEN `805bf01` feat(04-10): count the probe idioms in an EXE's non-library code with probe scan
2. **Task 2: Stack-check calls, per-flag evidence lines, consistent cells**
   - RED `f94203c` test(04-10): add failing tests for stack-check calls, flag evidence and consistent cells
   - GREEN `4839bae` feat(04-10): stack-check calls by block, per-flag evidence lines and consistent cells
3. **Task 3: `probe calibrate` and `probe scan --calibration`**
   - RED `e586fac` test(04-10): add failing tests for probe calibrate and scan --calibration
   - GREEN `dfa813d` feat(04-10): probe calibrate and probe scan --calibration on the command line
   - REFACTOR `1c47087` refactor(04-10): move the runtime-map read and refusal into probe.runtime_rows

**Plan metadata:** committed with this SUMMARY (docs(04-10)).

## TDD record

- **RED evidence.** Each RED run wrote pytest JUnit XML under build/red/, and `gsd-tools check tdd-red-evidence` returned `RED_EVIDENCE_OK` (reason `target_test_failed`) for:
  - Task 1: `test_probe_scan_help_lists_options` (assertion: `'--orig' in ''`, the verb was missing) and `test_scan_excludes_runtime_rows`.
  - Task 2: `test_chk_calls` and `test_scan_exe_fills_stack_checks_and_evidence` (the latter failed its assertion: `chk_calls` was 0 because scan_exe did not count yet).
  - Task 3: `test_calibration_json_round_trip` and `test_probe_calibrate_help_lists_options` (assertion on the missing options).
- **Semantic assessment.** The unit tests reach the new names through the module (`probe.scan_exe`), so existing tests kept collecting. The new ones failed inside the test body: AttributeError on the missing function, or an assertion on missing behaviour. No collection, syntax or fixture fault. The real tests failed in their fixture or body on the missing `scan_exe` and `consistent_cells`, after the real EXE and the calibration had loaded.
- **GREEN.** Two real assertions failed on the first GREEN run and were changed to the measured values, under the orchestrator's binding ruling and the plan's "a different real result is recorded, not forced":
  - `rep_movsd_small == 0` failed: the measured value is 4 and 2.
  - The consistent-cells "no 11.0 / no -4r" assertions failed: the measured value is the ten-cell list.
  The counters, the rule and the runtime maps were not changed.
- **REFACTOR.** `1c47087` only moves code. It was pinned by the CLI tests that had failed in RED (missing map message, default path).
- **Tracer gate:** interactive run, `end-of-phase` mode, automated-only verify. The Task 1 verify was re-run after its GREEN commit and passed, so expansion continued.

## Files Created/Modified

- `tools/reverseapoc/probe.py` - ProbeError, runtime_rows, ExeScan, scan_exe, chk_calls, DECISIVE_FAMILIES, consistent_cells, flag_evidence, Calibration.from_json
- `tools/reverseapoc/cli.py` - `probe` verb with `calibrate` and `scan`, `_cmd_probe`, ProbeError in main()'s error tuple
- `tests/test_probe.py` - scan, chk, evidence, consistency and JSON tests (47 in the file)
- `tests/test_probe_real.py` - test_exe_nonlibrary_idioms, test_exe_chk_calls, test_exe_consistent_cells (both EXEs)
- `tests/test_cli.py` - probe scan and probe calibrate tests

## Decisions Made

See `key-decisions` in the frontmatter.

## Deviations from Plan

### Auto-fixed / minor additions

**1. [Rule 2 - Correctness] scan_exe masks LE fixup bytes**
- **Found during:** Task 1
- **Issue:** the plan's action names only `exclude`. Without a mask, relocated operand bytes could be read as idioms.
- **Fix:** the mask is every LE fixup byte inside the code object (the "production mask" the plan's context names), pinned by `test_scan_masks_le_fixup_bytes`.
- **Commit:** 805bf01

**2. ProbeError arrived in Task 1, not Task 3.** The Task 1 missing-runtime refusal needed an error class in main()'s tuple. Task 3 then used it for the calibration JSON.

**3. A sixth evidence line, `shapes (not decisive):`.** The orchestrator asked for the switch counter's eax/al coverage limit in the switch idiom's evidence line, and none of the five flag lines carries switch counts. The five planned lines come first and are unchanged.

**4. Extra tests and options beyond the behaviour list:**
- A boundary complement (a row one byte later still counts).
- scan `--json` and orig-mismatch refusal; a probe subcommand requirement; the probe and calibrate help.
- calibrate `--json` and `--versions` order.
- `probe calibrate` refuses an `--output` inside the Watcom tree (refuse_output, as libmatch does).
- `scan --json --calibration` adds `consistent`, `ties` and `calibration_skipped` keys.
- The text output adds a `calibration skipped:` line per skipped version.

**5. Refactor: `probe.runtime_rows`.** The plan's key link expects `read_runtime_csv(` in probe.py, so the read-and-refuse helper moved from cli.py into probe.py (1c47087, no behaviour change).

### Real assertions recorded as measured (not code deviations)

- `rep_movsd_small == 0` becomes `> 0` (4 / 2), and `test_exe_nonlibrary_idioms` pins the four decisive counts per EXE.
- "No consistent cell has 11.0, -3r or -4r" becomes the measured ten-cell list. The claims that hold stay asserted.

### Environment adaptations

- The sandbox refused the plan's `$(git rev-parse --path-format=absolute --git-common-dir)/../...` form, as in earlier waves. Every real test and command ran with `REVERSEAPOC_ORIG=../../../orig` and `REVERSEAPOC_WATCOM_DIR=../../../third_party/watcom` (or `--orig ../../../orig` / `--watcom-dir ../../../third_party/watcom`) from the worktree root, read-only. The gate log names the main checkout's 10.6 and 11.0 trees.
- I did not write the plan-commit ledger file. Commits are measured against the dispatch base: `git rev-list --count 0d06982..HEAD` = 7 before this SUMMARY.

---

**Total deviations:** 1 auto-fixed (Rule 2) and 4 minor additions; 2 real assertions recorded as measured.
**Impact on plan:** every planned artifact, test and command exists. The verdict differs from the research reading and is recorded, not forced.

## Issues Encountered

- `docker compose run --rm test` was not run in this worktree. The plan's verification is host-only. Host: `uv run pytest -q` gives 818 passed, 135 skipped; `uv run ruff check .` is clean.
- probe/README.md still says "the CLI verb arrives with plan 04-10" under "Running the calibration". The verb exists now. The README is not in this plan's files, so I left it for plan 04-11's docs pass.

## Known Stubs

None.

## User Setup Required

None.

## Next Phase Readiness

- Plan 04-11 can cite `uv run reverseapoc probe calibrate` and `uv run reverseapoc probe scan <EXE> --calibration build/probe/calibration.json` verbatim. Both outputs hold counts, block addresses and library or module names only.
- 04-11 must weigh the struct-copy size finding and the `-4r` mix above, together with the runtime-library evidence, before writing the version and flags into docs/toolchain.md. Once 10.5 is reinstalled, `probe calibrate` adds the 10.5 cells and the ties among the consistent ones.

## Self-Check: PASSED

- Files exist: tools/reverseapoc/probe.py, tools/reverseapoc/cli.py, tests/test_probe.py, tests/test_probe_real.py, tests/test_cli.py, config/ufo2p/runtime.csv, config/tacp/runtime.csv, and this SUMMARY.
- Commits ea51e75, 805bf01, f94203c, 4839bae, e586fac, dfa813d and 1c47087 are ancestors of HEAD. No plan commit deletes a file.
- Acceptance checks:
  - `uv run pytest -q tests/test_probe.py -k scan`: 4 passed. `-k "chk or flag_evidence or consistent"`: 8 passed.
  - `probe scan --help` lists --orig, --manifest, --runtime, --calibration and --json. `probe --help` lists calibrate and scan. `probe calibrate --help` lists --versions, --manifest, --watcom-dir, --output and --json (tested).
  - `grep -n "class ProbeError(ValueError)" tools/reverseapoc/probe.py` prints line 31.
  - build/probe/calibration.json exists, and build/probe/scan-tacp.out holds `consistent:` and `stack checks:`. build/probe/scan-ufo2p.out has a non-zero setcc_and line.
- Plan verification:
  - Real file (overrides set): 50 passed, 1 skipped. The only skip is "Watcom 10.5: gate refused"; there is no skip for 10.6, 11.0, the runner or orig.
  - `uv run pytest -q`: 818 passed, 135 skipped. `uv run ruff check .`: All checks passed!

---
*Phase: 04-compiler-identification*
*Completed: 2026-10-21*
