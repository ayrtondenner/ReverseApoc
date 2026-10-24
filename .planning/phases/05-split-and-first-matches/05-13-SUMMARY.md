---
phase: 05-split-and-first-matches
plan: 13
subsystem: tooling
tags: [reconcile, boundaries, units, include-asm, capstone, ghidra, cli]

requires:
  - phase: 05-04
    provides: functions.csv/boundaries.csv/units.csv schemas, seed_runtime_rows, check_unit_assignment
  - phase: 05-07
    provides: discover (starts, evidence, jump tables) and the D-07 ends rule
  - phase: 05-10
    provides: read_ghidra_export / GhidraFunction
  - phase: 05-12
    provides: the real Ghidra exports (build/ghidra/<exe>/functions.raw.csv) used for the smoke runs
provides:
  - functions.reconcile (D-07 rule, D-08 verdict merge, EVIDENCE_ORDER tie-break, Reconciled)
  - tools/reverseapoc/units.py (draft_units, assign_units, chk_callers, scaffold_unit, write_unit_source)
  - verbs discover, functions, units (with --write-src)
affects: [05-14, 05-16, 05-17, 05-18, 05-19]

actuals:
  tokens: 19214
  tasks: 3
  commits: 6
plan_head_before: a6cbc0f0426b24b68ab6aa07e9067bc7bbdd87ee
plan_head_after: 5c07c04d2c9b358c5a8211c894db042866dd2dc8

tech-stack:
  added: []
  patterns:
    - "reconcile decides by LE evidence; Ghidra bodies are used only to confirm a thunk and to close an alignment gap"
    - "tool-owned boundaries columns are regenerated; a hand verdict survives only where the rule does not decide"
    - "functions.py stays capstone-free at import: discover/x86 are imported inside reconcile"

key-files:
  created:
    - tools/reverseapoc/units.py
    - tests/test_units.py
  modified:
    - tools/reverseapoc/functions.py
    - tools/reverseapoc/cli.py
    - tests/test_functions.py

key-decisions:
  - "reconcile takes the runtime.csv rows as `modules=`: an address inside a runtime row or module (not a runtime row start) is decided `rule` with reason `runtime (inside <name>)` and gets no row; the bytes before a module's first public become a data-in-code row D_<module start> with evidence runtime (05-04 note)"
  - "A case label (a jump-table target) whose only LE evidence is fixup is decided `rule`, reason `case label of the table at 0x...`, and is not a start; a jump table no row covers (a leading table) becomes a data-in-code row with evidence fixup"
  - "Ghidra entries outside every code object are dropped and counted (Reconciled.dropped_ghidra, printed by the verb): 1 per EXE in the real exports (05-12 note)"
  - "Alignment-gap merge (05-07 note): when capstone ends a function early and Ghidra's function at that start spans the gap, the end extends to min(next start, Ghidra body_max + 1, next jump table)"
  - "An undecided disagreement (empty verdict) places no start; the verb exits 0 and reports the open verdicts, the D-08 check fails on them"
  - "data-order cuts on string literals only (module-private data): a function whose lowest referenced string lies below every string its unit referenced so far starts a new unit; shared globals would cut almost every function"
  - "scaffold_unit refuses a unit with no game or thunk row (a runtime unit has nothing to scaffold)"

patterns-established:
  - "Leading jump tables travel with the function they touch when units are cut"
  - "--write never replaces a hand-edited file without an explicit flag (--redraft); --write-src never overwrites"

requirements-completed: [SPL-02, SPL-03, SPL-04]

coverage:
  - id: D1
    description: "functions.reconcile applies the D-07 rule with automatic rule verdicts and preserved hand verdicts (D-08)"
    requirement: SPL-02
    verification:
      - kind: unit
        ref: "tests/test_functions.py -k 'case_label or runtime_public or hand_verdict or thunk or agreement or touching or no_disagreements or no_starts or sorted or tie_break or gap_merged or outside_code'"
        status: pass
    human_judgment: false
  - id: D2
    description: "`reverseapoc functions EXE --ghidra-export PATH (--write | --output DIR)` writes functions.csv and boundaries.csv and prints counts per kind and per verdict class"
    requirement: SPL-02
    verification:
      - kind: integration
        ref: "tests/test_functions.py#test_functions_verb_writes_both_csvs"
        status: pass
      - kind: integration
        ref: "tests/test_functions.py#test_functions_verb_keeps_units"
        status: pass
    human_judgment: false
  - id: D3
    description: "units.draft_units cuts the code object into address-range units with a reason per cut; every function in exactly one unit"
    requirement: SPL-03
    verification:
      - kind: unit
        ref: "tests/test_units.py (runtime, chk-cluster, source-string, data-order, alignment-gap, unique names, every function in one unit)"
        status: pass
    human_judgment: false
  - id: D4
    description: "`units EXE --write-src UNIT` scaffolds src/<exe>/<unit>.c with INCLUDE_ASM markers for game and thunk rows and never overwrites"
    requirement: SPL-04
    verification:
      - kind: integration
        ref: "tests/test_units.py#test_units_verb, #test_write_src_runs_on_its_own, #test_scaffold, #test_write_unit_source_refuses_an_existing_file"
        status: pass
    human_judgment: false
  - id: D5
    description: "The drafted unit cuts are plausible module boundaries on the real EXEs"
    verification: []
    human_judgment: true
    rationale: "Only a person (05-16, 05-18/05-19 re-cuts) can judge whether a drafted unit is a real translation unit; the tests only pin the rules"

duration: 17min
completed: 2026-10-24
status: complete
---

# Phase 5 Plan 13: Reconcile, units draft and INCLUDE_ASM scaffold Summary

**The D-07 reconcile rule turns the Ghidra export and the capstone pass into functions.csv and boundaries.csv with automatic `rule` verdicts. On the real exports it decides 589 of 591 UFO2P and 492 of 497 TACP disagreements. Hand verdicts survive regeneration. The D-11 unit draft and the D-12 INCLUDE_ASM scaffold sit behind the new `discover`, `functions` and `units` verbs.**

## Performance

- **Duration:** about 17 min
- **Started:** 2026-10-24T02:21:50Z
- **Completed:** 2026-10-24T02:38:24Z
- **Tasks:** 3 (one tracer, two TDD tasks)
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- `functions.reconcile(le, ghidra, discovery, runtime_rows, *, existing, modules)`. An address both tools report becomes one row. An address only one tool reports becomes one boundaries.csv row. The rule decides it, in this order: a runtime row start, a start inside a runtime row or module, a case label, then call/entry/fixup evidence. The reason names the evidence. Anything else keeps the hand verdict of the previous boundaries.csv (`ghidra`, `capstone` or `data-in-code`, applied), or stays empty for a person.
- Ends come from `discover.ends` over the final starts. Thunks are Ghidra thunks whose body is one `jmp rel32`. Alignment gaps that Ghidra spans are merged back. Leading jump tables and the bytes before a module's first public become data-in-code rows. An overlap is refused, never written.
- Real smoke runs (output to the scratchpad only; plan 05-16 commits the real CSVs):
  - UFO2P: 1,891 rows (1,548 game, 259 runtime, 4 thunk, 80 data-in-code). 591 disagreements: 589 rule, 2 open. 1 Ghidra data-object entry dropped.
  - TACP: 1,870 rows (1,515 game, 278 runtime, 7 thunk, 70 data-in-code). 497 disagreements: 492 rule, 5 open. 1 Ghidra data-object entry dropped.
  - The UFO2P reasons were: 330 fixup, 110 runtime, 140 inside a runtime row or module, and 9 call.
- `units.py` (KKND gen_units.py derivation header on line 1):
  - `draft_units` cuts at runtime modules (`rt_<module>`), source-file/assert strings (the stem names the unit), `__CHK` cluster edges, data-order breaks and alignment gaps. Each cut carries its reason, and repeated names get `_2`, `_3`.
  - The real UFO2P draft has 408 units: 239 alignment-gap, 142 runtime, 20 data-order, 4 chk-cluster and 3 source-string. `check_unit_assignment` finds no problem.
- `scaffold_unit` / `write_unit_source` write `#include "common.h"` plus one `INCLUDE_ASM(func_X);` per game and thunk row, in address order, with `/* */` comments only. An existing file is never overwritten.
- New verbs:
  - `discover EXE [--json]`.
  - `functions EXE --ghidra-export PATH (--write | --output DIR) [--runtime] [--watcom-dir] [--json]`. It fills the unit column from an existing units.csv.
  - `units EXE [--functions] [--runtime] [--units] [--write | --output DIR] [--redraft] [--write-src UNIT] [--src-root]`.
- `DiscoverError` and `UnitsError` are registered in the CLI error list.

## Task Commits

1. **Task 1: Tracer, the functions verb**: `9c03823` (test, RED), `5319c6b` (feat, GREEN). Tracer gate: the interactive end-of-phase mode with an automated-only verify, so the verify was re-run and passed before expanding.
2. **Task 2: Full D-07/D-08 rules and the SPL-02 edges**: `930edcb` (test, RED), `93d598c` (feat, GREEN)
3. **Task 3: Units draft, assignment, scaffold and the units verb**: `14b27b9` (test, RED), `5c07c04` (feat, GREEN)

## TDD Gate Compliance

- RED before GREEN for all three tasks. Each RED run failed on the missing behaviour:
  - Task 1: the verb did not exist.
  - Task 2: 8 tests failed on their planned assertions; the 2 module tests failed on the missing `modules` input.
  - Task 3: `reverseapoc.units` did not exist, and `test_functions_verb_keeps_units` failed on its assertion.
- Semantic assessment: several Task 2 edge pins already passed against the tracer slice: agreement, touching rows, no disagreements, no starts, ordering and tie-break. They pin behaviour the tracer had already built, which is expected for edge tests and is not an unexpected GREEN of a planned feature.
- The Task 3 RED commit had one transient ruff import-grouping finding (I001), because ruff only recognises `reverseapoc.units` as first-party once the module exists. It cleared at GREEN.

## Files Created/Modified

- `tools/reverseapoc/functions.py`: the reconcile section (EVIDENCE_ORDER, Reconciled, reconcile, `_candidate_starts`, `_disagreements`, `_auto_verdict`, `_apply_verdicts`, `_data_in_code_rows`, `_kind`, `_evidence`, `_merged_end`, `_module_lead_rows`) and a docstring paragraph about it.
- `tools/reverseapoc/units.py`: new. UnitsError, draft_units, assign_units, chk_callers, scaffold_unit, write_unit_source, unit_name.
- `tools/reverseapoc/cli.py`: the verbs discover, functions and units, and the two errors. The verbs of 05-02, 05-11 and 05-12 are untouched.
- `tests/test_functions.py`: 1 tracer test, 1 unit-fill verb test and 16 reconcile tests.
- `tests/test_units.py`: new, 15 tests.

## Decisions Made

See key-decisions in the frontmatter. The main ones:
- runtime.csv rows feed reconcile as `modules`.
- Case labels are decided by the rule.
- Out-of-code Ghidra entries are counted and dropped.
- Ghidra's body is used only for the thunk check and the gap merge.
- data-order cuts read string literals only.

## Deviations from Plan

### Orchestrator rulings applied

- **Orchestrator ruling F2:** `units EXE --write-src UNIT` runs on its own. The `--write`/`--output` group is optional. Without it, the verb reads the committed config/<exe>/units.csv and functions.csv (or `--units` / `--functions`) and writes only src/<exe>/<unit>.c, never overwriting it. With none of the three options it refuses. Tests: `test_write_src_runs_on_its_own` (only the unit source is created, a second run and an unknown unit exit 1) and `test_units_verb_needs_an_action`.
- **Orchestrator ruling F5:** the scaffold marks every `game` AND `thunk` row of the unit; `runtime` and `data-in-code` rows are exempt. Test: `test_scaffold` (a thunk row gets a marker; the runtime and data-in-code rows of the unit do not).

### Notes from merged plans applied (05-04, 05-07, 05-12)

- **[Rule 2 - Missing critical] Bytes before a module's first public (05-04 note).** These bytes become a data-in-code row of the module (evidence runtime). A disagreement inside them, or inside any runtime row, is decided `rule` with reason `runtime (inside <name>)`. This needed the runtime.csv rows as a new keyword `modules=` of reconcile (the plan's signature is otherwise unchanged). Tests: `test_runtime_public_inside_a_module` and `test_runtime_public_start_inside_a_runtime_row`. Commits 930edcb, 93d598c.
- **[Rule 2 - Missing critical] Alignment gaps after a jmp (05-07 note).** A gap that Ghidra's function spans is merged back into the function. Test: `test_gap_merged_into_ghidra_function`. Commits 930edcb, 93d598c.
- **[Rule 2 - Missing critical] Ghidra data-object entry (05-12 note).** Entries outside every code object are dropped, counted in `Reconciled.dropped_ghidra`, and printed by the verb. Tests: `test_ghidra_entry_outside_code_is_dropped` and `test_no_starts`. Commits 930edcb, 93d598c.

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `--runtime CSV` option on functions and units**
- **Found during:** Task 1
- **Issue:** the synthetic EXE has no committed config/syn/runtime.csv, and a missing runtime.csv must not silently mean "no runtime rows" for the real EXEs.
- **Fix:** both verbs take `--runtime CSV` (default: the committed file) and refuse a missing file with the libmatch hint, as `cppscan` does.
- **Commit:** 5319c6b

**2. [Rule 2 - Missing critical] `--units CSV` on the units verb**
- **Found during:** Task 3
- **Issue:** ruling F2's on-its-own mode had to be testable without writing into the repo's config/.
- **Fix:** `--units CSV` overrides the committed units.csv. `test_units_write_keeps_a_hand_recut` monkeypatches `cli.config_dir` to a tmp tree.
- **Commit:** 5c07c04

**Total deviations:** 2 orchestrator rulings, 3 notes applied, 2 auto-fixed (1 blocking, 1 missing critical). **Impact:** all are additive keyword or option inputs; the plan's verbs and signatures are otherwise as written.

## Issues Encountered

- The host has no clang, so the scaffolded file's lint gate (`reverseapoc lint`, container only) was not run here. The text is `#include "common.h"`, `/* */` comments and `INCLUDE_ASM(...)` lines only, and `test_scaffold` asserts exactly that. 05-14/05-17 run the lint in the container.
- Writing the first RED test with a Python heredoc produced CRLF line endings and a literal NUL byte. I restored the file and redid every later edit with the Edit tool or byte-preserving writes; every committed file is LF ASCII.

## Known Stubs

None. The open verdicts (2 UFO2P, 5 TACP on the real exports) are left on purpose for plan 05-16, per the plan's prohibition on inventing reasons.

## Threat Flags

None. No new network, auth or trust-boundary surface. T-05-29: `rule` is written only with an evidence reason, and open rows stay empty. T-05-30: `write_unit_source` opens with `xb`.

## User Setup Required

None.

## Next Phase Readiness

- 05-14 reads units.csv and the scaffolded unit files: its D-12/F5 completeness check matches `scaffold_unit`'s rule (game and thunk rows).
- 05-16 runs `functions --write` with the real exports (`--ghidra-export C:/.../build/ghidra/<exe>/functions.raw.csv`, `--watcom-dir` pointing at the installed trees) and writes the 7 open verdicts by hand. It then runs `units --write`.
- The draft over-cuts on alignment gaps (239 of the 408 UFO2P units). The first-match units may need a hand re-cut (reason `hand`) in 05-18/05-19.

Execution context nonce: a6e90a49d73f316c

## Self-Check: PASSED

- FOUND: tools/reverseapoc/units.py, tests/test_units.py, tools/reverseapoc/functions.py, tools/reverseapoc/cli.py, tests/test_functions.py
- FOUND commits: 9c03823, 5319c6b, 930edcb, 93d598c, 14b27b9, 5c07c04
- Acceptance:
  - the tracer test passes with exactly two boundaries rows;
  - `functions --help` lists `--ghidra-export`, `--write` and `--output`;
  - the Task 2 `-k` selection gives 15 passed;
  - `tests/test_units.py` gives 15 passed;
  - `units --help` lists `--write-src`;
  - `uv run pytest -q` gives 1254 passed, 200 skipped;
  - `uv run ruff check .` is clean.

*Phase: 05-split-and-first-matches*
*Completed: 2026-10-24*

## Review fixes (round 1)

**Important: hand verdicts lost silently.** Before this fix, a hand verdict from the previous boundaries.csv disappeared without a message in two cases: when the LE rule decided its address, and when its address was no longer a disagreement. `test_hand_verdict_kept` pinned that behaviour.

The orchestrator ruled: the rule still wins where it decides (D-07), but nothing is lost silently. A hand verdict where the rule does not decide is kept, as before.

- `Reconciled` gains two fields:
  - `replaced: tuple[(address, old verdict), ...]`: the hand verdicts (`ghidra`, `capstone`, `data-in-code`) that the rule replaced with `rule`.
  - `dropped_hand: tuple[address, ...]`: the hand rows dropped because the address is no longer a disagreement.
  - Open rows and earlier `rule` rows are not hand verdicts and are not reported. A new helper, `_lost_hand_verdicts`, computes both fields. `HAND_VERDICTS` names the hand verdict words.
- The `functions` verb prints `N hand verdict(s) replaced by the rule: 0x... <old> -> rule` and `N hand row(s) no longer a disagreement, dropped: 0x...` when either count is non-zero. The `--json` output gains `replaced` (address and verdict) and `dropped_hand` (addresses). Both hold addresses and verdict words only.
- Tests:
  - `test_hand_verdict_kept` is narrowed to the case where the rule does not decide; it also asserts that nothing is reported.
  - New: `test_hand_verdict_replaced_by_the_rule_is_reported`, `test_hand_row_no_longer_a_disagreement_is_reported` and `test_functions_verb_reports_replaced_and_dropped_hand_verdicts` (text and JSON).

**Minor: `--units` was ignored when drafting.** `units` now refuses `--units` together with `--write` or `--output`. The error names `--units`, and nothing is written. Test: `test_units_option_refused_when_drafting`.

Commits: `ef62903` (test, RED: 5 failed, 77 passed), `e89eea1` (fix).

Commands and output:
- `uv run pytest -q tests/test_functions.py tests/test_units.py`: `82 passed in 0.75s`
- `uv run pytest -q`: `1258 passed, 200 skipped in 14.33s`
- `uv run ruff check .`: `All checks passed!`
