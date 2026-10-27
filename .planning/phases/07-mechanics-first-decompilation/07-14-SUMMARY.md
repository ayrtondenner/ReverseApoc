---
phase: 07-mechanics-first-decompilation
plan: 14
subsystem: tooling
tags: [d-15, sweep, cflags, attempt-wrapper, zm-spike]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-09: check.account_unit / defined_functions pair rows by start with the EXE's C names; 07-11: check.sweep passes its src root so view sweeps compile against the view's include/"
provides:
  - "check.SWEEP2_VERSION, SWEEP2_LETTERS, SWEEP2_KKND, SWEEP2_PACK, SWEEP2_ZM, SWEEP2_SEGMENT, SWEEP2_FP, SWEEP2_FLOOR"
  - "check.sweep2_cells(best) -> list[(version, flags)]: at most 24 D-15 cells (O1 9, O2 <= 8, Z 4, M 1, F 2), all 10.6"
  - "check.sweep2_trigger(cells) -> SweepCell | None: the stage-1 cell stage 2 varies, or None"
  - "SweepReport.stage2 / stage2_best (default None, ruling F11), stage2_from, to_json()['stage2'] = null | {from, cells, best}, stage-2 log lines"
  - "attempt._sweep_line: sweep_hit is stage 1's first hit, else stage 2's; the summary prints the stage-2 best cell"
  - "docs/toolchain.md 'Fallbacks and candidates': the second-stage sweep paragraph and the -zm result"
affects: [07-16, 07-17, 07-24, 07-29]

actuals:
  tokens: 6583
  tasks: 3
  commits: 6
plan_head_before: 8a8f98e5278614aa181fd6101c5ecb58ef29bead
plan_head_after: 4e3906378db82ab6c567826da0cdd0ec7a1a45f3

tech-stack:
  added: []
  patterns:
    - "A diagnostic second stage reuses the first stage's _measure (temporary one-rule cflags file, T-05-38 refusal) and numbers its cells on from stage 1"
    - "New dataclass fields on a report that tests construct positionally get defaults after the last field (ruling F11)"

key-files:
  created: []
  modified:
    - tools/reverseapoc/check.py
    - tools/reverseapoc/attempt.py
    - tests/test_check.py
    - tests/test_attempt_wrapper.py
    - docs/toolchain.md

key-decisions:
  - "Stage 2 varies the first best stage-1 cell (lowest cell number among equal ranks), so the cell list is deterministic"
  - "Z, M and F flags are appended after the best cell's flags; O1 puts the replacing -o set right after the CPU flag, O2 the added letter after the existing -o set; a cell equal to the best cell or to an earlier one is dropped"
  - "Stage-2 cells are numbered on from stage 1 (31.., or 61.. for a __CHK caller), so their objects and rule files never overwrite stage 1's"
  - "-zm is included (SWEEP2_ZM = True): a synthetic one-segment-per-function object passes defined_functions and account_unit"
  - "The sweep line's best_percent / reloc_ok / bytes_ok keep describing stage 1; only sweep_hit looks at stage 2 (then only when stage 1 has no hit)"

patterns-established:
  - "sweep2_trigger is the one answer to 'does stage 2 run, and from which cell'"

requirements-completed: [DEC-03]

coverage:
  - id: D1
    description: "A near miss (stage-1 best 92.0, reloc ok) runs stage 2; its -4r -of+ -s -fpi cell measures 100.0 and is stage2_best; to_json()['stage2'] and the log carry it; a perfect stage-1 cell leaves stage2 null with 30 compiles"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_stage2_runs_on_a_near_miss"
        status: pass
      - kind: unit
        ref: "tests/test_check.py#test_stage2_skipped_when_stage1_hits"
        status: pass
    human_judgment: false
  - id: D2
    description: "The attempt wrapper reports a stage-2 hit as sweep_hit when stage 1 has none, a stage-1 hit first, and none when stage2 is null; no new ATTEMPT_FORMS entry"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_wrapper_reports_stage2_hit"
        status: pass
      - kind: unit
        ref: "tests/test_attempt_wrapper.py#test_forms_unchanged"
        status: pass
    human_judgment: false
  - id: D3
    description: "Stage-2 composition: 24 cells from -ot (O1 9, O2 8, Z 4, M 1, F 2), no O2 without an -o set, all 10.6, CPU/stack/-fpi kept"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_sweep2_cells_from_ot"
        status: pass
      - kind: unit
        ref: "tests/test_check.py#test_sweep2_cells_from_no_o"
        status: pass
    human_judgment: false
  - id: D4
    description: "Trigger edges: 90.0 reloc ok runs, 89.99 not, 95.0 reloc failed not, a 100.0 cell with 1 differing byte is not perfect and does not stop stage 2"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_trigger_edges"
        status: pass
      - kind: unit
        ref: "tests/test_check.py#test_trigger_edges_perfect_needs_zero_differing"
        status: pass
    human_judgment: false
  - id: D5
    description: "Every stage-2 cell rule (from the best of any of the 60 stage-1 cells) passes parse_cflags with no wrapper-owned flag"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_every_cell_rule_parses"
        status: pass
    human_judgment: false
  - id: D6
    description: "-zm spike: a synthetic -zm object passes defined_functions and account_unit (SWEEP2_ZM = True); a call into a sibling's segment fails the relocation check (pinned); docs/toolchain.md records both with the test name"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_zm_object_accounting"
        status: pass
      - kind: other
        ref: "grep -q 'second-stage sweep' docs/toolchain.md && grep -q test_zm_object_accounting docs/toolchain.md"
        status: pass
    human_judgment: false
  - id: D7
    description: "A real -zm compile (Watcom's actual segment names and how it references a sibling function) matches the synthetic layout"
    verification: []
    human_judgment: true
    rationale: "Research A14 is settled on a synthetic object only, as the plan's flagged assumption says; no real compile was attempted and no Watcom tree is in the worktree"

duration: 17min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 14: D-15 second-stage sweep Summary

**When the 30-cell sweep misses but its best cell reaches 90% with relocations passing, `check --sweep` now runs up to 24 more cells under 10.6: single `-o` letters, KKND's `-of+ -omiler`, letters added to the best `-o` set, `-zp1/2/4/8`, `-zm` and `-fp3`/`-fp5`. The cells come from the best cell, go through the same temporary one-rule cflags file, and appear in `to_json()["stage2"]` and the log. `attempt check --sweep` reports a stage-2 hit as `sweep_hit` when stage 1 has none. A synthetic `-zm` object passes unit accounting, so `-zm` is one of the cells.**

## Performance

- **Duration:** about 17 min
- **Started:** 2026-10-27T17:44:22Z
- **Completed:** 2026-10-27T18:01Z
- **Tasks:** 3 (all TDD: RED commit, then GREEN commit)
- **Files modified:** 5

## Accomplishments

- **`check.sweep2_cells(best)`:** returns the D-15 cells for the best stage-1 cell. Each one keeps that cell's CPU, stack and `-fpi` flags under 10.6:
  - O1 replaces the `-o` set with each of the 8 letters and with KKND's set (9 cells).
  - O2 adds each letter to an existing `-o` set (8 cells, none without an `-o` set).
  - Z adds `-zp1/2/4/8` (4), M adds `-zm` (1), F adds `-fp3`/`-fp5` (2).
  - Duplicates are dropped. From `-ot` this gives exactly 24 cells.
- **`check.sweep2_trigger(cells)`:** stage 2 runs only when no stage-1 cell is perfect (100.0, relocation check passing, 0 differing) and the first best cell reaches `SWEEP2_FLOOR = 90.0` with its relocation check passing.
- **`sweep`:** measures stage 2 through the same `_measure`, numbering its cells on from stage 1.
  - `SweepReport` gains `stage2`/`stage2_best`, which default to None (ruling F11), plus `stage2_from`.
  - `to_json()["stage2"]` is null, or `{from, cells, best}`.
  - The log adds `stage 2 from cell NN`, one line per cell and `stage 2 best: ...`.
- **`attempt._sweep_line`:** takes a stage-1 hit first, then a stage-2 hit. The run summary prints the stage-2 best cell. `ATTEMPT_FORMS` is unchanged, so agents still never choose flags (T-07-41).
- **`-zm` spike (research A14):** a synthetic object with one code segment per function passes `defined_functions` and `account_unit` (`SWEEP2_ZM = True`).
  - The same test pins a limit: a call into a sibling function's own segment is refused by the relocation check ("local segment reference").
  - docs/toolchain.md records the second-stage sweep, the `-zm` result and that limit.

## Task Commits

1. **Task 1 (tracer, TDD): a near miss runs stage 2 and the wrapper reports its hit.** RED `c853ab8` (test), GREEN `70c6be4` (feat).
   - Tracer feedback gate: the run is interactive with `human_verify_mode` end-of-phase, and the verify is automated only. I re-ran `uv run pytest -q tests/test_check.py tests/test_attempt_wrapper.py -k "sweep or stage2"` on the committed GREEN (16 passed), then continued.
2. **Task 2 (TDD): composition, trigger edges, flag safety.** RED `90ff858` (test), GREEN `0e8b6d5` (feat).
3. **Task 3 (TDD, ruling F28): the `-zm` spike and the docs note.** RED `cc298ee` (test), GREEN `4e39063` (feat).

## TDD evidence (RED)

Each RED run wrote a pytest JUnit report (`build/red/07-14-t{1,2,3}.xml`, gitignored). `gsd-tools check tdd-red-evidence` returned `RED_EVIDENCE_OK` / `target_test_failed` for each.

- **Task 1 (`c853ab8`):** 3 failed, 0 passed. Target: `test_stage2_runs_on_a_near_miss`.
  - The near-miss and skip tests failed because `to_json()` had no `stage2` key (`assert None is not None`, `assert 'stage2' in doc`).
  - The wrapper test failed with `sweep_hit` None instead of the stage-2 spec.
  - Semantic assessment: every target ran and failed on its planned assertion. There was no import or collection fault.
- **Task 2 (`90ff858`):** 4 failed, 3 passed. Target: `test_sweep2_cells_from_ot`.
  - The two composition tests failed because the O2/Z/F slices were empty (assertion).
  - `test_trigger_edges[reloc-failed-not]` failed because stage 2 still ran from a reloc-failed 95.0 cell (assertion).
  - `test_trigger_edges_perfect_needs_zero_differing` failed with AttributeError: `sweep2_trigger` was not public yet.
  - The 3 passes were characterization of the tracer's behaviour: 90.0 runs, 89.99 does not, every cell rule parses.
- **Task 3 (`cc298ee`):** 3 failed, 7 passed. Target: `test_zm_object_accounting`.
  - Per ruling F28, the core failure is the missing M cell and `SWEEP2_ZM`: the `-zm` cell was absent from `sweep2_cells` (assertion). The two composition tests failed on the missing `-zm` slot.
  - The accounting and relocation parts of `test_zm_object_accounting` are characterization of existing check behaviour. They passed in the exploration run before the constant existed.
- Record note: I first entered `runStartedAt` by hand as estimates, and two of them were later than the real reports. I rebuilt all three records with the plan's start time (17:44:22Z), a true lower bound for every run, and re-classified them: all `RED_EVIDENCE_OK`. The records are in gitignored `build/red/`.

## Verification

- `uv run pytest -q tests/test_check.py tests/test_attempt_wrapper.py -k "sweep or stage2"`: 18 passed.
- `uv run pytest -q tests/test_check.py -k "sweep2 or trigger or cell_rule"`: 7 passed.
- `uv run pytest -q tests/test_check.py -k zm`: 1 passed. `grep -q "second-stage sweep" docs/toolchain.md`: found.
- `uv run pytest -q tests/test_hygiene.py`: 75 passed, 3 skipped (pre-existing). `tests/test_skill.py` passes unchanged: ruling F11 keeps the 7-argument `SweepReport` construction working.
- `uv run pytest -q` (host, worktree): **3012 passed, 236 skipped**.
  - Every skip has a pre-existing reason: orig/ absent, Watcom/watcom-media not installed, clang/objdiff-cli "run in the container", POSIX-only.
  - No new test skips, and there is no new skip reason.
- `uv run ruff check .`: All checks passed. (`ruff format` is not a repo gate: untouched files such as driver.py also fail it.)
- Acceptance:
  - check.py has `def sweep2_cells(`, `SWEEP2_FLOOR = 90.0` and `SWEEP2_ZM =`.
  - `test_sweep2_cells_from_ot` asserts `len(cells) <= 24`.
  - docs/toolchain.md names `test_zm_object_accounting`.
  - attempt.py reads `stage2`.
- **Container step deferred to the orchestrator:** `docker compose build && docker compose run --rm test`.

## Files Created/Modified

- `tools/reverseapoc/check.py`:
  - module docstring;
  - the stage-2 constants, `sweep2_cells`, `_perfect`, `sweep2_trigger`;
  - `SweepReport.stage2/stage2_best/stage2_from`, its lines and `to_json`, and `_cell_list`;
  - `sweep` runs stage 2.
- `tools/reverseapoc/attempt.py`: `_stage2`, `_sweep_line` (looks for a hit in stage 1, then stage 2), `_best_text`, and the stage-2 line in `_sweep_summary`.
- `tests/test_check.py`: `RuleObjdiff`, `run_near_miss`, the tracer, composition, trigger, flag-safety and `-zm` tests, and `zm_object`.
- `tests/test_attempt_wrapper.py`: `test_wrapper_reports_stage2_hit`.
- `docs/toolchain.md`: the second-stage sweep paragraph in "Fallbacks and candidates".

## Decisions Made

See `key-decisions` in the frontmatter. None of them lets a cell land, write config/cflags.txt or count as a match: stage 2 goes through `_compile_cell`, whose T-05-38 refusal guards the committed table (T-07-40).

## Deviations from Plan

**1. Orchestrator ruling F11: `stage2` and `stage2_best` default to None, after `log_path`.**
- The ruling keeps `tests/test_skill.py:224`'s 7-argument positional `SweepReport` construction working, and that file is unchanged.
- I added `stage2_from` as a property derived from `best[0]` rather than as a field, so the field list is exactly what the ruling names.
- Commit: `70c6be4`.

**2. Orchestrator ruling F28: Task 3's RED holds the failing core test (the missing `-zm` cell / `SWEEP2_ZM`).**
- The rest of `test_zm_object_accounting` (accounting and relocation) is characterization, as stated in the TDD evidence above.
- Commits: `cc298ee` (RED), `4e39063` (GREEN).

**3. [Plan clarification] The "100.0 with one differing byte" trigger edge is tested at the cell level.**
- **Found during:** Task 2.
- **Issue:** check's relocation check compares bytes too. A compiled object with one differing byte therefore fails its relocation check, so the edge cannot be built end to end through `sweep`.
- **Fix:** The trigger became a public function, `check.sweep2_trigger(cells)`. `test_trigger_edges_perfect_needs_zero_differing` tests it on `SweepCell`s, including empty and unmeasured stage-1 input. The other three edges stay end to end in `test_trigger_edges`.
- **Commits:** `90ff858`, `0e8b6d5`.

**4. [Rule 2 - Missing critical] Stage-2 cells are numbered on from stage 1.**
- **Issue:** Numbering stage 2 from 1 would overwrite stage 1's `cell-NN.cflags`, `.obj` and `.elf` in the work directory and make the log ambiguous.
- **Fix:** Stage-2 cells are numbered on from stage 1. The tracer test asserts numbers 31.. for a non-`__CHK` function.
- **Commit:** `70c6be4`.

**5. [Finding, recorded, no code change] `-zm` and calls into the same unit.**
- In the synthetic `-zm` layout, a call from one function into another function's own segment is a fixup to a module-local segment. relocs refuses it as a "local segment reference". A `-zm` cell of a function that calls a sibling in its own unit therefore always fails its relocation check: it fails safe and is never a hit.
- The plan scopes A14 to unit accounting (which passes), so `-zm` is in. relocs is not changed, matching the plan's "do not change account_unit".
- The limit is pinned in the test and stated in docs/toolchain.md. Whether a real `-zm` compile references a sibling this way is unverified (D7).

**Total deviations:** 2 orchestrator rulings applied, 1 clarification, 1 Rule-2 addition, 1 recorded finding.
**Impact on plan:** every must-have truth holds as written, and there is no scope creep.

## Issues Encountered

- The worktree harness refused some heredoc `cat >>` appends to test files. I made those edits with the Edit tool instead.
- omf2elf sizes a public without its trailing `nop` filler. The first `-zm` fixture used `ret; nop; nop` and measured 6 bytes. The fixture is now all code (8 bytes). This is existing behaviour, not a `-zm` effect.

## Known Stubs

None.

## User Setup Required

None.

## Next Phase Readiness

- 07-17's proposal queue can read stage-2 hits. They come through the same `sweep_hit` field of checks.jsonl, and in full in check's JSON under `stage2`.
- The watcom-decomp skill does not mention stage 2. Its JSON-field test still passes, because `stage2` exists in `to_json`. If the skill should describe stage 2, that update goes through writing-skills (07-35's scope).
- The real `-zm` behaviour is open (D7) until a real 10.6 `-zm` compile is checked in the container.

Execution context nonce: 02135080c6292877

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
