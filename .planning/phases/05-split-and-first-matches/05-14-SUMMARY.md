---
phase: 05-split-and-first-matches
plan: 14
subsystem: build-graph
tags: [configure, ninja, objdiff, clangd, compile_commands, include-asm, d-12]

requires:
  - phase: 05-split-and-first-matches
    provides: "05-04 read_units_csv / read_functions_csv / FunctionRow.kind; 05-05 INCLUDE_ASM marker in include/common.h; 05-12 lint.CLANGD_FLAGS and the lint --stamp verb"
provides:
  - "configure.py writes build.ninja, objdiff.json and compile_commands.json, all encoded before any is written"
  - "rules cc, omf2elf, target, lint, asm, land, configure (generator = 1); phony objects, lint, asm; default check-orig objects; verify = rebuild + land"
  - "check_unit_source: the D-12 completeness check (game and thunk rows defined in C or marked INCLUDE_ASM, exactly once, order-independent)"
  - "refusals: incomplete unit file, unit name outside [a-z0-9_]+, a C file that names no unit, unsafe config/src/configure.py path in the regeneration command"
affects: [05-17 target and land verbs, 05-18 container ninja run, 05-20 phase gate, objdiff, clangd]

actuals:
  tokens: 14000
  tasks: 3
  commits: 6
plan_head_before: a6cbc0f0426b24b68ab6aa07e9067bc7bbdd87ee
plan_head_after: 8c04aa550b3454f086591457f09345bef270ae97

tech-stack:
  added: []
  patterns:
    - "Generated build files are encoded together before any is opened; a refusal writes nothing"
    - "Every path in a command goes through the _SAFE_ORIG check (unquoted for /bin/sh and CreateProcess); every path in a build line through ninja_path(); $builddir outputs are not escaped"
    - "D-12 detection: blank comments and literals, then a marker regex and a file-scope (brace depth 0) definition regex; counts, not order"

key-files:
  created: []
  modified:
    - configure.py
    - tests/test_configure.py
    - .gitignore

key-decisions:
  - "Unit membership for D-12 is the functions.csv unit column (rows with unit == the units.csv name); range consistency stays with check_unit_assignment (05-13), which configure does not call"
  - "cc implicit deps are the repository's config/cflags.txt, config/watcom.toml and include/*.h (what reverseapoc cc reads), not the --config dir"
  - "compile_commands.json uses the repository root as directory, because the lint flags name include/ relative to it; file is absolute"
  - "The regeneration edge also depends on every unit C file and each existing src/<exe> dir, so editing a unit file re-runs the D-12 check and a new unit file re-runs configure"
  - "configure.py falls back to tools/ on sys.path when reverseapoc is not importable, so plain `python configure.py` works outside the uv environment"

patterns-established:
  - "UnitBuild (one units.csv row) and Layout (repository files relative to the build.ninja dir) carry everything render, render_objdiff and render_compile_commands need"

requirements-completed: [SPL-06, SPL-04]

coverage:
  - id: D1
    description: "configure.py writes build.ninja, objdiff.json and compile_commands.json next to --output, creating its directory, encoding all three first"
    requirement: SPL-06
    verification:
      - kind: unit
        ref: "tests/test_configure.py#test_unit_with_source_gets_compile_edges"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_main_creates_the_output_directory"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_main_never_truncates_on_an_encoding_failure"
        status: pass
      - kind: other
        ref: "uv run python configure.py --output build/cfg-smoke/build.ninja"
        status: pass
    human_judgment: false
  - id: D2
    description: "build.ninja keeps the Phase 3 rules and edges and adds cc, omf2elf, target, lint, asm, land and configure rules, per-unit edges, objects/lint/asm phonies, verify = rebuild + land, default check-orig objects"
    requirement: SPL-06
    verification:
      - kind: unit
        ref: "tests/test_configure.py#test_land_joins_verify"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_lint_and_asm_edges"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_regeneration_rule"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_default_builds_objects"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_render_has_verify_edge"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_generated_rebuild_writes_into_builddir"
        status: pass
    human_judgment: false
  - id: D3
    description: "objdiff.json in the objdiff 3.8.2 schema and compile_commands.json with lint.CLANGD_FLAGS, both gitignored"
    requirement: SPL-06
    verification:
      - kind: unit
        ref: "tests/test_configure.py#test_unit_with_source_gets_compile_edges"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_gitignore_lists_generated_files"
        status: pass
      - kind: other
        ref: "git check-ignore -v objdiff.json compile_commands.json"
        status: pass
    human_judgment: false
  - id: D4
    description: "D-12 refusal: a game or thunk function neither defined nor marked, both, marked twice, or a marker/definition outside the unit; marker adjacency accepted; order independent"
    requirement: SPL-04
    verification:
      - kind: unit
        ref: "tests/test_configure.py -k 'unit_source or next_to or order or refuses' (45 selected)"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_main_refuses_an_incomplete_unit"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_main_refuses_a_stray_source"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_main_refuses_a_bad_unit_name"
        status: pass
    human_judgment: false
  - id: D5
    description: "The generated graph actually runs under ninja in the container (target and land verbs arrive in 05-17)"
    requirement: SPL-06
    verification: []
    human_judgment: true
    rationale: "No ninja on the host and the target/land verbs do not exist yet; the container ninja run belongs to plans 05-18 and 05-20 (plan's flagged assumption)"

duration: 10min
completed: 2026-10-24
status: complete
---

# Phase 5 Plan 14: configure.py matching build graph Summary

**configure.py now turns every units.csv row into cc -> omf2elf -> base object and a target object cut from the LE image, adds lint, asm, land and self-regeneration edges, writes objdiff.json (3.8.2 schema) and compile_commands.json (lint dialect), and refuses any unit file whose game or thunk functions are not each defined in C or marked INCLUDE_ASM exactly once.**

## Performance

- **Duration:** about 10 min (wall clock of this executor)
- **Started:** 2026-10-24T02:20:25Z
- **Completed:** 2026-10-24T02:30:00Z
- **Tasks:** 3 (tracer + 2, all TDD)
- **Files modified:** 3

## Accomplishments

- `--config` and `--src` options; `UnitBuild` per units.csv row of each manifest EXE that has `config/<exe>/units.csv`; `Layout` names the repository files relative to the build.ninja dir.
- Edges: `$builddir/<exe>/target/<unit>.o` (implicit: the EXE, functions.csv, units.csv, symbols.csv when present; `exe`/`unit` edge variables), and for units with C `obj/<unit>.obj` (cc, implicit cflags.txt, watcom.toml, include/*.h), `base/<unit>.o` (omf2elf), `lint/<unit>.stamp`. One always-run asm edge per EXE. `build $builddir/always/land: land | <every base object>` and `build verify: phony $builddir/always/verify $builddir/always/land`. `build objects: phony` over every base and target object; `default check-orig objects`. `build build.ninja: configure | configure.py, the CSVs, the unit files, src/<exe>` with `generator = 1`.
- `render_objdiff`: `$schema`, `min_version` 3.8.2, `custom_make` ninja, `build_target` false, `build_base` true, `watch_patterns`, one progress category per EXE with units, one unit per row; `base_path` and `metadata.source_path` only when the unit has C.
- `render_compile_commands`: one entry per unit file, `directory` the repository root, `arguments` = clang + `CLANGD_FLAGS` + `-c <file>`.
- `check_unit_source(text, unit_functions)`: comments and string/char literals blanked; `INCLUDE_ASM(func_X);` markers and file-scope `func_X(...) {` definitions counted (prototypes, calls and commented-out code are neither).
- Header and docstring describe the compile, convert, cut, lint, asm and land targets (`grep "arrive in Phase 5" configure.py` prints nothing).

## Task Commits

1. **Task 1 (tracer): unit compile, convert and cut edges plus objdiff and clangd metadata** - RED `8130e2f` (test), GREEN `52249f4` (feat)
2. **Task 2: D-12 completeness refusal and the unit-name and source checks** - RED `2a30ab5` (test), GREEN `bdee4d2` (feat)
3. **Task 3: lint, asm, land and regeneration edges, default objects, .gitignore** - RED `ced1dd5` (test), GREEN `8c04aa5` (feat)

## TDD Gate Compliance

Each task has a `test(05-14)` commit before its `feat(05-14)` commit. RED evidence (semantic assessment):
- Task 1: the tracer test failed on argparse rejecting `--config`/`--src` (the feature under test), 45 others passed.
- Task 2: 18 tests failed with `AttributeError: check_unit_source` or main returning 0 for an incomplete unit / stray file; `test_main_refuses_a_bad_unit_name` already passed because the 05-04 reader refuses `Bad-Unit` (kept as a regression pin).
- Task 3: 9 tests failed on a missing rule block (`list.index`), the missing land/objects edges, the old header wording and the .gitignore block lacking the two files.
- Tracer gate: interactive, `end-of-phase`, automated-only verify; re-ran `pytest tests/test_configure.py` and `ruff check .` green before expanding.

## Files Created/Modified

- `configure.py` - matching build graph, objdiff and clangd metadata, D-12 check
- `tests/test_configure.py` - 31 new tests, 2 rewritten wording tests, 1 widened monkeypatch lambda
- `.gitignore` - `objdiff.json`, `compile_commands.json` in the configure block

## Decisions Made

See `key-decisions` above. In short: D-12 membership by the functions.csv unit column; cc deps are the repository files the cc verb reads; compile_commands directory is the repository root; regeneration also watches the unit files and src/<exe>; plain-python fallback to tools/.

## Deviations from Plan

**Orchestrator ruling F5:** the D-12 check covers every `game` and `thunk` row of a unit; `runtime` and `data-in-code` rows are exempt (`_CHECKED_KINDS`). Test: `test_unit_source_covers_thunk_rows_and_exempts_runtime_and_data`. Commit `bdee4d2`.

**Orchestrator ruling F8:** the configure.py header/docstring rewrite and the rewrite of the two "Phase 5" wording tests (`test_render_has_phony_targets_and_compile_rules`, `test_no_stale_phase_wording`) happened together in Task 3, so Tasks 1 and 2 ended with the suite green. Commits `ced1dd5`, `8c04aa5`.

### Auto-fixed Issues

**1. [Rule 3 - Blocking] configure did not create the output directory**
- **Found during:** Task 1 (acceptance smoke `--output build/cfg-smoke/build.ninja`)
- **Issue:** `FileNotFoundError` for a not-yet-existing output dir (the Phase 3 configure never created it)
- **Fix:** `args.output.parent.mkdir(parents=True, exist_ok=True)` after all three files are encoded
- **Verification:** `test_main_creates_the_output_directory`; smoke exits 0 and writes all three files
- **Committed in:** `52249f4`

**2. [Rule 3 - Blocking] Phase 3 test's monkeypatched render signature**
- **Found during:** Task 1
- **Issue:** `test_main_never_truncates_on_an_encoding_failure` replaced `render` with `lambda exes, *, orig:`; main now also passes `units=` and `layout=`
- **Fix:** the lambda takes `**_units` too; the test's intent (bytes encoded before build.ninja is opened) is unchanged. This is a third touched Phase 3 test besides the two wording tests the plan names.
- **Committed in:** `52249f4`

**3. [Rule 2 - Missing critical, T-05-31] Paths in the regeneration command are checked like orig**
- **Found during:** Task 3
- **Issue:** the `configure` rule writes configure.py, --config and --src paths unquoted into a command
- **Fix:** `_check_command_path` (the `_SAFE_ORIG` rule plus `_refuse_option_like`) for those three; `_check_orig_dir` now uses it
- **Verification:** `test_regeneration_rule_refuses_an_unsafe_config_dir` (nothing written)
- **Committed in:** `8c04aa5`

**4. [Rule 3 - Blocking] plain `python configure.py` could not import reverseapoc**
- **Found during:** Task 1 (the plan's command is `python configure.py`; configure now imports reverseapoc)
- **Fix:** when `importlib.util.find_spec("reverseapoc")` is None, `tools/` goes on sys.path; ruff accepts it before the imports
- **Verification:** `python configure.py --output build/cfg-smoke2/build.ninja` exits 0 with the system Python 3.14
- **Committed in:** `52249f4`

**5. Interface shape differences from the plan text (no behaviour lost)**
- `render_objdiff(units)` takes no `base`: UnitBuild paths are already relative to the build.ninja dir, which is objdiff.json's dir. `render_compile_commands(units, base)` as planned.
- `render(..., layout=...)` and a `Layout` dataclass beside `units=`; `UnitBuild` has an extra `inputs` field (the CSVs the target edge depends on) and an `output()` helper.
- A definition's `{` may follow the parameter list after any whitespace (including blank lines), not only on the same or next line; string and character literals are blanked as well as comments.

---

**Total deviations:** 2 orchestrator rulings applied (F5, F8), 4 auto-fixed (3 Rule 3, 1 Rule 2), plus the interface notes in item 5.
**Impact on plan:** all needed for the plan's own acceptance commands or its threat model; no scope creep.

## Issues Encountered

- The real checkout has no `config/<exe>/units.csv` yet (05-13 drafts them), so on the real tree the unit sections are empty (`objects`, `lint`, `asm` phonies with no inputs, land with no deps). The unit edges are pinned by the tmp-tree tests.
- Known limits of the regex D-12 check (the `check` verb confirms definitions from compiled publics later): `#if 0` blocks are not understood, and K&R-style definitions are not recognised as definitions.

## Notes for later plans

- 05-17: build.ninja calls `uv run reverseapoc target <exe-stem> <unit> --orig <orig> -o <out>` and `uv run reverseapoc land --orig <orig>` from the build.ninja directory (its cwd); land must read `expected_sha1` from config/targets.toml itself. `asm` is called as `asm <exe-stem> --orig <orig>`, lint as `lint <src> --stamp <stamp>`.
- 05-18/05-20: `ninja verify` runs `rebuild` and `land` (both in the console pool, so serialized); land depends on every base object.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 05-17 (target and land verbs the edges call) and the container ninja run in 05-18/05-20.

Execution context nonce: ba396fd0c5bc0597

## Self-Check: PASSED

- FOUND: configure.py, tests/test_configure.py, .gitignore (modified), this SUMMARY
- FOUND commits: 8130e2f, 52249f4, 2a30ab5, bdee4d2, ced1dd5, 8c04aa5 (ancestors of HEAD)
- `uv run pytest -q` 1252 passed, 200 skipped; `uv run ruff check .` clean; `git check-ignore` lists both generated files; `grep -n "arrive in Phase 5" configure.py` prints nothing

## Review fixes (round 1)

Two Important findings in the D-12 completeness check, fixed test-first (RED `fed1fc3`, fix `1a8e891`).

**1. `//` line comments were not blanked.** wcc386 and clang gnu89 accept them, so `// INCLUDE_ASM(func_X);` or a `//`-commented definition counted as marked or defined. `_NOT_CODE` now also blanks `//[^\n]*`, in the same left-to-right alternation as block comments and string/char literals, so a `//` inside a string is not a comment. Comment blanking now keeps line breaks, so directive line numbers stay true.
Tests: `test_unit_source_ignores_line_comments[marker]` and `[definition]` (both refused as "neither"), `test_unit_source_line_comment_inside_a_string_is_not_a_comment`.

**2. `#if 0` blocks were not understood.** Orchestrator ruling (review round 1), implemented as follows:
- An `#if 0` block is dead up to its matching `#endif`, including any conditionals nested inside it.
- The `#else` branch of an `#if 0` is live code.
- Any other preprocessor conditional is refused, naming the file and line: `#if <expr>` (including `#if 1`), `#ifdef`, `#ifndef`, and `#elif` (also at the top level of an `#if 0`). So are an `#else` or `#endif` without a matching `#if 0` and an `#if 0` still open at end of file.
- Directive lines themselves never count as code, so a macro body is never read as a marker.

This lives in `_live_code` and `_directive_step`, and `check_unit_source` returns the refusal as its problem. Tests:
- `test_unit_source_if0_block_is_dead`: "neither"
- `test_unit_source_if0_else_branch_is_live`: defined; would read "both" if the dead branch counted
- `test_unit_source_refuses_conditionals_it_cannot_evaluate`: 8 cases (ifdef, ifndef, if-expr, if-1, elif, after-comment line numbering, stray-endif, second-else), each asserting the line and the directive
- `test_unit_source_refuses_an_unterminated_if0`
- `test_main_refuses_a_conditional_naming_the_line`: exit 1, message names `u_00010000.c`, `line 1` and `#ifdef`; nothing is written

K&R definitions still fail safe: they are refused as "neither", never a false pass. That limit is now stated in the module docstring and the `check_unit_source` docstring, and the "Issues Encountered" note about `#if 0` above is superseded.

Commands and output lines:
- `uv run pytest -q tests/test_configure.py` -> `90 passed, 3 skipped in 0.45s` (RED before the fix: `14 failed, 76 passed, 3 skipped`)
- `uv run pytest -q` -> `1267 passed, 200 skipped in 13.95s`
- `uv run ruff check .` -> `All checks passed!`

---
*Phase: 05-split-and-first-matches*
*Completed: 2026-10-24*
