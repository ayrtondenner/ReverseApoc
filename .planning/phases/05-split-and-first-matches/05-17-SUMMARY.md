---
phase: 05-split-and-first-matches
plan: 17
subsystem: tooling
tags: [check, objdiff, relocs, land, sweep, spl-11, spl-10, d-16, d-17]

requires:
  - phase: 05-split-and-first-matches
    provides: "05-06 omf2elf.convert (filler-trimmed public sizes); 05-08 build_target -> TargetResult(data, raw_fields, undecoded); 05-09 relocs.check_function with own_publics and land.land with expected_sha1; 05-13 units.csv and the INCLUDE_ASM scaffold; 05-14 the build.ninja target and land edges"
provides:
  - "tools/reverseapoc/check.py: EXIT_OK/EXIT_MISMATCH/EXIT_TOOL, CheckError, FunctionCheck, CheckResult (ok, exit_code, format, to_json), objdiff_percent, match_percent, default_objdiff_runner, check_source, check_unit, land_all -> list[ExeLand], write_target, sweep_cells, sweep -> SweepReport"
  - "reverseapoc check EXE/UNIT [--json] [--sweep FUNC], reverseapoc target EXE UNIT -o OUT, reverseapoc land [--out] [--json]: the verbs build.ninja calls"
  - "One land step for check and ninja verify (SPL-10 wiring): land_all over every EXE that has config/<exe>/units.csv (ruling F4)"
affects: [05-18, 05-19, 05-20, phase-06]

actuals:
  tokens: 16373
  tasks: 3
  commits: 7
plan_head_before: 2c027c27e11a7c267f17ba2cae9bffefc01cd151
plan_head_after: cfef46d355dda5927161e6a39698de3ae85480b3

tech-stack:
  added: []
  patterns:
    - "check's verdict is three independent agreements: objdiff 100.0 (a score), the relocation check, and every EXE's splice SHA-1 with no function refused"
    - "A tool or usage problem is CheckError -> exit 2, never a pass; the default objdiff runner fails before any compile on a host without objdiff-cli"
    - "The tools that need injection (compile_source, default_objdiff_runner) are looked up at call time, so tests monkeypatch them and the CLI runs unchanged"

key-files:
  created:
    - tools/reverseapoc/check.py
    - tests/test_check.py
  modified:
    - tools/reverseapoc/cli.py

key-decisions:
  - "land_all returns ExeLand(exe, LandResult, refused) per EXE, not bare LandResult: a defined function whose relocation check fails is named, not landed, and fails its EXE's splice (ok = SHA-1 matches and nothing refused)"
  - "check JSON is the must_haves shape plus splice[].refused, splice[].first_difference and a top-level target {raw_fields, undecoded} (05-08 note); va and first_va are 0x%08X strings"
  - "A unit whose object defines no function of the unit is CheckError (exit 2): check never reports a match it did not measure"
  - "objdiff match_percent that is absent, not a number, a bool, NaN or outside [0, 100] counts as 0.0 (T-05-37)"
  - "check, target, land and the sweep take --config, --src and --build roots (defaults: the repository's), so ninja's argv from 05-14 stays exactly `target <exe-stem> <unit> --orig <orig> -o <out>` and `land --orig <orig>`"
  - "Sweep cell flags are written as <cpu> <-o set> [-s] -fpi; cells the sweep cannot measure log `not installed`, `compile failed` or `not defined`; check --sweep exits 0 because the sweep is evidence for a D-18 rule, never a match"
  - "check's SymbolTable loads functions.csv, units.csv and symbols.csv but no runtime aliases (that needs LIB386): a fixup naming an alias that is not a row name is refused by the relocation check, never passed"

patterns-established:
  - "land writes build/land/<EXE>, separate from rebuild's build/<EXE>, so ninja verify may run them in either order (05-14 review note)"

requirements-completed: [SPL-11, SPL-10]

coverage:
  - id: D1
    description: "Tracer: a synthetic unit goes through fake compile, real omf2elf, target, relocs and land, fake objdiff, and check --json prints the must_haves keys with objdiff 100.0, reloc ok, one splice ok, exit 0; objdiff-cli argv is `diff -1 <target.o> -2 <base.o> -o - <symbol>`"
    requirement: SPL-11
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_check_passes_a_matching_unit"
        status: pass
    human_judgment: false
  - id: D2
    description: "Exit codes: reloc failure under objdiff 100 is exit 1 with the function line MISMATCH; absent or nonsense match_percent is 0.0 and exit 1; objdiff-cli missing, unknown EXE or unit, bad unit name, compile failure, missing source are exit 2"
    requirement: SPL-11
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_check.py -k \"reloc_failure or absent or missing or unknown or compile_failure or target_verb or land_verb\" (21 selected, 21 passed)"
        status: pass
      - kind: other
        ref: "uv run reverseapoc check ufo2p/nonexistent on the host: exit 2, names the docker compose command"
        status: pass
    human_judgment: false
  - id: D3
    description: "target and land verbs with the 05-14 ninja signatures; land lands built objects into build/land/<EXE>, refuses a failing function, says run ninja first; ruling F4: only EXEs with units.csv are landed and listed"
    requirement: SPL-10
    verification:
      - kind: unit
        ref: "tests/test_check.py (test_target_verb, test_target_verb_unknown_unit, test_land_verb_without_units, test_land_verb_with_a_matched_unit, test_land_verb_refuses_a_failing_function, test_land_verb_missing_object_says_run_ninja, test_land_all_lists_only_exes_with_units)"
        status: pass
    human_judgment: false
  - id: D4
    description: "D-17 sweep: the fixed 30/60-cell matrix, one log line per cell plus best: under build/logs/, temporary rules only under build/sweep/, config/cflags.txt untouched, not installed versions logged, never lands"
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_check.py -k sweep (8 selected, 8 passed)"
        status: pass
    human_judgment: false
  - id: D5
    description: "No game bytes or disassembly in check output or logs (names, addresses, percentages, counts, SHA-1s only)"
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_sweep_log_carries_no_bytes"
        status: pass
    human_judgment: true
    rationale: "The prohibition has verification: judgment in the plan; the test covers the sweep log only, a reviewer confirms check's text and JSON formats print no bytes"

duration: 21min
completed: 2026-10-24
status: complete
---

# Phase 5 Plan 17: the single-unit check, target and land verbs, and the D-17 sweep Summary

**`reverseapoc check EXE/UNIT` compiles the unit's C, converts it with omf2elf, cuts the unit's target ELF from the LE, scores every defined function with objdiff-cli, runs the relocation check with the unit's public-to-row map and the byte compare, then lands every compiled unit of every EXE with units.csv through land.py and compares each SHA-1 with config/targets.toml. It exits 0 only when all three agree, 1 on a mismatch and 2 on any tool or usage problem. `target` and `land` are the verbs build.ninja calls, and `check --sweep FUNC` runs and logs the fixed D-17 matrix.**

Execution context nonce: 6114660a28185e3f

## Performance

- **Duration:** about 21 min
- **Started:** 2026-10-24T02:55:00Z
- **Completed:** 2026-10-24T03:15:56Z
- **Tasks:** 3 (Task 1 tracer, Tasks 2 and 3 auto; all TDD)
- **Files modified:** 3 (2 new, cli.py extended)

## Accomplishments

- `check_unit(exe, unit, ...) -> CheckResult`:
  - fails early with exit 2 when objdiff-cli is not on PATH, naming `docker compose run --rm build uv run reverseapoc check <exe>/<unit>`;
  - writes build/<exe>/obj/<unit>.obj, build/<exe>/base/<unit>.o and build/<exe>/target/<unit>.o;
  - checks every code public of our object that names a row of the unit, sized by omf2elf.
- Each function gets `objdiff_percent`, `reloc {ok, problems}` and `bytes {ok, differing, first_va}`. `CheckResult.ok` requires every function at 100.0 with reloc and bytes ok, and every splice ok.
- `own_publics(module, segment, rows, symbols)`: each public of the unit's `_TEXT` that names a unit row, sized to the next public or the segment end, with its row start, passed to `relocs.check_function` for every checked function (05-09 note).
- `check_source(exe_inputs, unit, src, rows, ...)`: the lower-level step 05-18 can call on the cmain386 runtime pair.
- `land_all(manifest, *, orig_dir, config_root, src_root, build_dir, compile_fn=None, ...)`:
  - lands every defined function of every unit with C, in every EXE with units.csv (ruling F4);
  - with `compile_fn` it compiles each unit first; without it, it reads the objects ninja built and says `run ninja first` when one is missing;
  - functions whose check fails are refused and listed.
- `target EXE UNIT [--orig] [--manifest] [--config] -o OUT` writes `build_target(...).data` and prints the raw fields and undecoded sites. `land [--orig] [--manifest] [--config] [--src] [--build] [--out] [--json]` writes build/land/<EXE> and exits 0 only when every SHA-1 matches and nothing is refused.
- `check EXE/UNIT --sweep FUNC`:
  - runs `sweep_cells(chk=...)`: 30 cells, or 60 for a function that calls the runtime row `__CHK`;
  - each cell gets a one-rule cflags file under build/sweep/<exe>/<unit>/;
  - logs `cell NN  wcc386@<version>  <flags>  objdiff X%  reloc ok|FAILED  differing N` (or `not installed`) and a `best:` line to build/logs/sweep-<exe>-<unit>-<func>.log;
  - never lands.

## Task Commits

1. **Task 1 (tracer): the check pipeline on a synthetic unit:** RED `ddedceb`, GREEN `956d0a7`
2. **Task 2: exit codes, objdiff edge cases, target and land verbs:** RED `221f8f7`, GREEN `2279217`
3. **Task 3: the logged D-17 sweep:** RED `b578ccb`, GREEN `fb75147`
4. **Test strengthened after a surviving mutation:** `cfef46d`

Tracer gate: an interactive run with `human_verify_mode` end-of-phase and an automated-only verify. After the GREEN commit I re-ran both verify commands (tracer test passed, ruff clean) before starting the expansion.

## TDD notes

- **Task 1 RED:** failed at collection with `ImportError: cannot import name 'check'`, the expected first RED for a new module. The plan is `type: execute` and `workflow.tdd_mode` is off, so the tdd-red-evidence classifier does not apply.
- **Task 2 RED:** 12 tests failed on their planned assertions: the `target` and `land` verbs did not exist (argparse exit 2) and `match_percent` was not public. 11 passed at RED: Task 1's `check_unit` already raised CheckError for the unknown unit, compile failure and missing objdiff, and its `land_all` already refused failing functions and skipped EXEs without units.csv.
- **Task 3 RED:** 8 tests failed with `AttributeError` (no `SWEEP_VERSIONS` or `sweep`) or with argparse exit 2 (no `--sweep`).
- **Mutation probes after GREEN:**
  - Dropping `reloc.ok` from `FunctionCheck.ok` survived at first: the splice refusal still failed the result. `cfef46d` now asserts the function verdict itself, and the mutation then fails a test.
  - Dropping `refused` from `ExeLand.ok` fails 2 tests.
  - Accepting any `match_percent` value fails 3 tests.
  - All mutations were reverted with `git checkout -- tools/reverseapoc/check.py`.

## Files Created/Modified

- `tools/reverseapoc/check.py` (new). Line 1 is the Theme Hospital `tools/check.py` derivation header (GPLv3).
- `tools/reverseapoc/cli.py`: the `check`, `target` and `land` verbs and the shared `_add_unit_roots`. CheckError, TargetError, RelocError, LandError and SpliceError are added to `_ERRORS`. `check` returns 2 itself for every listed error.
- `tests/test_check.py` (new): 31 tests on synthetic LEs and OMF objects with made-up bytes (tests/relocpair.py, tests/omfimage.py). Only the compiler and objdiff-cli are faked.

## Decisions Made

See key-decisions in the frontmatter. The ones later plans depend on:
- 05-18/05-19/05-20 parse `splice` as a list of `{exe, sha1, expected, ok, landed, refused, first_difference}`, which holds exactly UFO2P.EXE and TACP.EXE once both have units.csv.
- `check` with a unit that defines no function is exit 2, not 0.

## Deviations from Plan

### Orchestrator rulings applied

**Orchestrator ruling F4: land_all iterates only targets that have config/<exe>/units.csv.** SMKP.EXE (no units.csv) never appears in `check`'s `splice` or in `land`'s output. I reworded `test_land_verb_without_units` to the F4 behaviour: the output is `[]`, nothing is written, exit 0. `test_land_all_lists_only_exes_with_units` covers three manifest targets with units.csv for two, and gives exactly those two splice entries.

### Notes from merged plans honoured (interface facts)

- 05-08: `build_target` returns `TargetResult`. `check` and `target` write `.data`. Both print `raw_fields` and `undecoded`: `check` in a top-level `target` JSON key and a text line, `target` in its output line.
- 05-09: `own_publics` is built for every checked function from our object's publics and the unit's functions.csv rows. Without it, a reference to another public of the unit is refused, and nothing bypasses that. `land` gets `expected_sha1` from config/targets.toml (`Target.sha1`).
- 05-14: build.ninja's argv works unchanged: `target <exe-stem> <unit> --orig <orig> -o <out>` and `land --orig <orig>`. `land` reads the manifest itself and writes only build/land/, never rebuild's output.

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] land_all names refused functions instead of returning bare LandResults**
- **Found during:** Task 1
- **Issue:** The plan's `land_all -> list[LandResult]` can only drop a function whose relocation check fails, or raise LandError. Dropping it silently would let the SHA-1 still match the original, a false pass. Raising would stop `check` from reporting the splice.
- **Fix:** `land_all -> list[ExeLand]`, where `ExeLand(exe, result: LandResult, refused)`. `ok` holds only when the SHA-1 matches and nothing was refused. `land` and `check` print each refused function with its problems.
- **Files modified:** tools/reverseapoc/check.py
- **Verification:** test_reloc_failure_beats_objdiff, test_land_verb_refuses_a_failing_function, and the `ExeLand.ok` mutation probe
- **Committed in:** 956d0a7

**2. [Rule 2 - Missing critical] No defined function is a tool error, and nonsense objdiff values are 0.0**
- **Found during:** Tasks 1-2
- **Issue:** A unit whose object defines none of its rows would otherwise exit 0 with nothing measured. An objdiff `match_percent` that is a bool, a string, NaN or out of range could otherwise read as a score.
- **Fix:** Such a unit raises CheckError (exit 2). Those `match_percent` values give 0.0 (T-05-37).
- **Files modified:** tools/reverseapoc/check.py
- **Verification:** test_absent_percent_or_nonsense_is_zero_not_a_match (5 cases)
- **Committed in:** 956d0a7, 2279217

**3. [Rule 3 - Blocking] Root options on check, land and the sweep**
- **Found during:** Task 1
- **Issue:** The plan's option lists have no way to point the verbs at a test tree.
- **Fix:** Added `--config`, `--src` and `--build` (all three verbs), and `--watcom-manifest`, `--cflags` and `--log` (check). Each defaults to the repository's own path, so ninja's argv does not change.
- **Files modified:** tools/reverseapoc/cli.py
- **Committed in:** 956d0a7, 2279217

**4. [Rule 1 - Bug] A test passed with the gate broken**
- **Found during:** mutation probe after Task 3
- **Issue:** see TDD notes.
- **Fix:** assert `fn.ok` false and the function line `MISMATCH`.
- **Files modified:** tests/test_check.py
- **Committed in:** cfef46d

---

**Total deviations:** 1 orchestrator ruling applied, 4 auto-fixed (2 missing critical, 1 blocking, 1 test bug)
**Impact on plan:** The `--json` shape keeps every must_haves key and adds `refused`, `first_difference` and `target`. Exit codes are as planned. No scope creep.

## Issues Encountered

- The harness refused compound shell commands that wrote under `.git/` (the plan ledger sentinel), so I kept the plan's base SHA (`2c027c2`) and start time in this SUMMARY instead of a ledger file.

## Known Stubs

None.

## User Setup Required

None. objdiff-cli is in the container image; on the host `check` exits 2 and names the container command.

## Next Phase Readiness

- 05-18 can call `check.load_exe` and `check.check_source` on the cmain386 pair, then `check_unit` once units exist. One caveat: `check` builds its SymbolTable without runtime aliases (that needs LIB386 loaded). A cmain386 fixup to a runtime public that is only an alias, not a functions.csv row name, is refused, not passed. If 05-18 hits that, pass aliases through `load_exe`; do not weaken the check.
- 05-18/05-19 should also skip candidates whose target lists `undecoded` sites or `raw_fields`. Both are in the check JSON under `target`.
- Real runs (objdiff-cli, wibo, the owner's orig/ and Watcom tree) happen in the container in 05-18..05-20.

## Self-Check: PASSED

- FOUND: tools/reverseapoc/check.py, tests/test_check.py, tools/reverseapoc/cli.py
- FOUND commits: ddedceb, 956d0a7, 221f8f7, 2279217, b578ccb, fb75147, cfef46d (all ancestors of HEAD)
- `uv run pytest -q`: 1336 passed, 200 skipped; `uv run ruff check .`: all checks passed
- Acceptance: Task 2 `-k` selection 21 passed (>= 8); `uv run reverseapoc check ufo2p/nonexistent` exit 2; `-k sweep` 8 passed

---
*Phase: 05-split-and-first-matches*
*Completed: 2026-10-24*
