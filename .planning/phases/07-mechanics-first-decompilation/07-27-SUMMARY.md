---
phase: 07-mechanics-first-decompilation
plan: 27
subsystem: tooling
tags: [dec-04, d-20, d-21, d-30, readlint, backlog-999.2, tdd]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-09 unitdefs (c_names, the depth-0 definition scan); 07-10 mechanics (read_committed, members); 07-16 symbols C names; 07-19 proposals (PLACEHOLDER, EVIDENCE_KINDS, evidence_problem, RESERVED_HEADERS, EXES)"
provides:
  - "tools/reverseapoc/readlint.py: ReadlintError, Token, tokenize, Violation, FloatLiteral, Skipped, ReadlintResult (exit_code, format, to_json, per_file, rule_counts), PLACEHOLDER (= proposals.PLACEHOLDER), WAIVER, ALLOWLIST, read_allowlist, run_readlint; rules RL01-RL06"
  - "`uv run reverseapoc readlint [PATHS] [--units EXE/UNIT,...] [--tier N] [--report] [--src DIR] [--config DIR] [--json]`: exit 0 clean, 1 violations, 2 tool error"
  - "config/readlint-allow.csv: header only (comment line plus exe,name,reason)"
  - "unitdefs.file_scope_definitions(code): the public depth-0 definition scan (ruling note under 07-27)"
affects: [07-31, 07-35, 07-36, 07-38, 07-40]

actuals:
  tokens: 18192
  tasks: 3
  commits: 6
plan_head_before: 5d3d5845003feb67bdf06520403f2f3772c33bfb
plan_head_after: f9aa4d6ecae07370a8e3f2a94e68629ade516b74

tech-stack:
  added: []
  patterns:
    - "readlint reads units through configure's normalize_source/code_text and _directive_step (one reading of #if 0 and lone CR for D-12 and readlint)"
    - "Definitions come from unitdefs.file_scope_definitions and are paired in order with their tokens; a definition readlint cannot place is exit 2 (fail closed)"
    - "RL03 maps a definition's name to its row start with unitdefs.c_names over functions.csv + symbols.csv"

key-files:
  created:
    - tools/reverseapoc/readlint.py
    - tests/test_readlint.py
    - config/readlint-allow.csv
  modified:
    - tools/reverseapoc/cli.py
    - tools/reverseapoc/unitdefs.py
    - tests/test_unitdefs.py

key-decisions:
  - "Exit 2 is returned by _cmd_readlint itself (ReadlintError caught there); cli._ERRORS is untouched, so the verb's tool error is 2 while every other verb keeps 1"
  - "A definition the allowlist can never exempt is a function definition or a declarator of a file-scope declaration without extern/typedef; prototypes, externs (any scope), calls and uses are references"
  - "Headers get RL01 (no allowlist) and RL04 only, read once per run; conditionals in headers are not evaluated (include guards), a lone CR or bad UTF-8 is still exit 2"
  - "Files outside the --units/--tier selection are reported as skipped ('not selected by --units/--tier'); a --units entry with no file under PATHS, a malformed selector or an unknown tier is exit 2"
  - "RL04 field pattern: unk|unknown|field|pad|padding|gap|filler|undefined + optional `_`/`0x`/hex + optional `_word`, case-insensitive; `paddle`, `gaps2`, `fieldOfView` pass"

patterns-established:
  - "A readability check that can fail: the phase gate is strict `readlint src/` exit 0; `--report` is for nights and stats"

requirements-completed: [DEC-04]

coverage:
  - id: D1
    description: "RL01 placeholder rule (999.2, R5): every pattern as definition, prototype, extern and use with file:line; exempt in stubs, comments, strings and dead #if 0; case-exact func_ hex; across a splice; in a directive"
    requirement: DEC-04
    verification:
      - kind: unit
        ref: "tests/test_readlint.py#test_rl01_each_pattern, test_rl01_exempt_contexts, test_rl01_case_exact, test_rl01_across_a_splice, test_rl01_in_a_directive"
        status: pass
    human_judgment: false
  - id: D2
    description: "Verb and scope: matched units only (others skipped), exit 0/1/2, --json keys, --help options, tool errors (#ifdef, lone CR, invalid UTF-8) exit 2 naming the file"
    requirement: DEC-04
    verification:
      - kind: unit
        ref: "tests/test_readlint.py#test_cli_exit_codes, test_help_lists_options, test_tool_errors, test_unmatched_unit_skipped, test_file_outside_exe_dirs_skipped"
        status: pass
    human_judgment: false
  - id: D3
    description: "RL02-RL06 with negative and exempt cases; the RL06 table one parametrized case each; tagged waiver counted; floats only in --report"
    requirement: DEC-04
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_readlint.py -k \"rl02 or rl03 or rl04 or rl05 or rl06 or floats\" (56 passed)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Allowlist for references only (D-30), --units/--tier selectors, included-header scan, report mode, committed-tree pin, empty and stub-only units clean"
    requirement: DEC-04
    verification:
      - kind: unit
        ref: "tests/test_readlint.py#test_allowlist_references_only, test_allowlist_never_a_data_definition, test_units_and_tier_selectors, test_included_header_scanned, test_report_mode_exit_0, test_committed_tree_report, test_empty_unit"
        status: pass
      - kind: other
        ref: "uv run reverseapoc readlint --report src/ (exit 0); uv run reverseapoc readlint src/ (exit 1, 37 violations)"
        status: pass
    human_judgment: false

duration: 22min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 27: readlint, the readability linter for matched units Summary

**`uv run reverseapoc readlint` is a stdlib, host-only linter that reads matched units through configure's translation phases and fails on placeholder names (RL01, backlog 999.2), missing or malformed D-21 header comments (RL02/RL03), unnamed struct fields (RL04), raw pointer-offset casts (RL05) and magic integer literals (RL06). It has a counted reference-only allowlist (D-30), a counted `/* lit: */` waiver, `--units`/`--tier` selectors, included-header scanning and a `--report` mode. Today strict mode exits 1 on the 4 matched units (37 violations) and `--report` exits 0.**

Execution context nonce: 5b0f71ccd80b9afa

## Performance

- **Duration:** 22 min
- **Started:** 2026-10-27T20:00:27Z
- **Completed:** 2026-10-27T20:22:14Z
- **Tasks:** 3 (Task 1 a tracer; all three TDD)
- **Files modified:** 6 (3 created, 3 modified)

## Accomplishments

- **Reading.**
  - Strict UTF-8 through `check.read_source`, then `configure.normalize_source` and `code_text`. Any conditional but `#if 0`, or a lone CR, is exit 2.
  - A tokenizer with 1-based physical lines that reads splices as the compiler does.
  - Dead `#if 0` branches are dropped with configure's own `_directive_step`.
  - `INCLUDE_ASM(name);` stubs are exempt from every rule.
- **Rules.**
  - RL01 placeholders: `proposals.PLACEHOLDER` itself, in code and in directives.
  - RL02 header comment: the last comment between the previous depth-0 boundary and the declaration.
  - RL03 header form: `<name>: <3+ word purpose>`, exactly one `Address: <EXE> 0x%08X` equal to the row start from `unitdefs.c_names`, and one or more `Evidence:` lines checked by `proposals.evidence_problem`.
  - RL04 unnamed fields: struct and union bodies at any depth.
  - RL05 raw offsets: a pointer cast over an additive operand that holds a non-zero literal.
  - RL06 magic literals: judged by context, as the truth states.
- **Allowlist (D-30).** `read_allowlist` reads the file strictly. Allowlisted references are counted per file. A function definition or a file-scope data definition is never exempted.
- **Selectors.**
  - `--units EXE/UNIT,...`.
  - `--tier N`: the mechanics `member` rows of the tier's items, mapped to units through functions.csv.
  - `--src` and `--config` name other roots, so plan 07-31 can lint a view.
- **Headers and report mode.**
  - Included project headers (common.h and watcom_compat.h excepted) are scanned once per run for RL01 and RL04.
  - `--report` exits 0 and prints per-file counts and floats. JSON adds `per_file`, `headers_checked` and `floats`.
- **Committed tree.**
  - `readlint --report src/` exits 0 and lists all 4 matched units.
  - Strict `readlint src/` exits 1: RL01 24, RL02 1, RL03 10, RL06 2.
  - This matches research Q5's table: RL03 on u_000a34f0, u_00054f20 and u_00089980 (twice); RL02 on u_0006ee30; RL06 on the bare `3` and `4` call arguments.

## Task Commits

1. **Task 1: Tracer - tokenizer, structure and RL01 through the verb**
   - `161104b` (test, RED; tests plus an API skeleton so the tests fail on assertions)
   - `bd63f26` (feat)
2. **Task 2: RL02-RL06, the tagged waiver and floats in report mode**
   - `9d0d605` (test)
   - `ad256be` (feat)
3. **Task 3: Allowlist, selectors, headers, report mode and the committed-tree pin**
   - `d30f39a` (test)
   - `f9aa4d6` (feat)

No REFACTOR commits: the cleanups (ruff line lengths, `yield from`) were folded into each GREEN commit before it was made.

## TDD Gate Compliance

Each task has a `test(07-27)` commit before its `feat(07-27)` commit. RED evidence came from a pytest JUnit report and was classified with `gsd-tools check tdd-red-evidence`. The records are in build/red/, which is gitignored.

| Task | Target test | Verdict | Run | Semantic assessment |
|------|-------------|---------|-----|---------------------|
| 1 | `test_rl01_each_pattern[func_0001ABCD-use]` | RED_EVIDENCE_OK / target_test_failed | 51 tests, 42 failed (`07-27-t1.xml`) | Failed on `assert [] == [3]`: the skeleton reported no RL01. Not a load fault: the first run without a skeleton was an ImportError at collection, which is INVALID_RED, so a skeleton was added to the RED commit. |
| 2 | `test_rl06_table[x = 36;]` | RED_EVIDENCE_OK / target_test_failed | 57 selected, 33 failed (`07-27-t2.xml`) | Failed on `0 == 1`: RL06 was not implemented yet. |
| 3 | `test_allowlist_references_only` | RED_EVIDENCE_OK / target_test_failed | 130 tests, 15 failed (`07-27-t3.xml`) | Failed on the RL01 assertion: the allowlisted call was still reported. |

Vacuous passes in RED, as expected:
- Exempt-context and zero-count cases passed before their rule existed: `test_rl01_exempt_contexts`, the RL06 cases expecting 0, `test_empty_unit` and `test_allowlist_is_per_exe`.
- `test_bad_selector_is_a_tool_error` passed because the Task 1 code refused any selector with ReadlintError.

## Files Created/Modified

- `tools/reverseapoc/readlint.py`: the linter (new).
- `tests/test_readlint.py`: 130 tests: negative and exempt cases for every rule, the verb, selectors, headers, the allowlist and the committed-tree pin (new).
- `config/readlint-allow.csv`: the comment line and the `exe,name,reason` header (new).
- `tools/reverseapoc/cli.py`:
  - `_cmd_readlint` and `_add_readlint_command`, right after `_add_lint_command`;
  - registered right after `_add_lint_command(sub)`;
  - one import line after `.lint`.
- `tools/reverseapoc/unitdefs.py`: public `file_scope_definitions(code)`, wrapping the private `_file_scope` with `DEFINITION_ANY`.
- `tests/test_unitdefs.py`: one test for that helper.

## Decisions Made

See key-decisions in the frontmatter. Two more points:
- Violation lines are `path:line: RLnn message`, with paths relative to the directory that holds the src root (`src/ufo2p/u_x.c`, `include/snd.h`).
- RL02 and RL03 apply to every definition in a matched unit, helpers included. A helper whose name maps to no game or thunk row gets RL03 "names no game or thunk row".

## Deviations from Plan

**1. Orchestrator ruling F7: cli.py placement.**
- `_cmd_readlint` and `_add_readlint_command` sit right after `_add_lint_command`, and `_add_readlint_command(sub)` is registered right after `_add_lint_command(sub)`.
- The import goes on its own line after `from .lint import ...`.
- Nothing else in cli.py moved. `_ERRORS` and the module docstring's verb list are untouched, to keep the W5 merge (07-21, then 07-24, then 07-27) conflict-free.

**2. Orchestrator ruling R5 (F23, owner-confirmed): applied as researched.**
- Floats are collected and printed only in `--report` mode.
- `LAB_`, `PTR_` and `UNK_` fall under RL01, through `proposals.PLACEHOLDER`.

**3. Ruling note under 07-27 (07-09 as built): a public unitdefs helper.**
- `unitdefs.file_scope_definitions` was added rather than copying the scan.
- This edits `tools/reverseapoc/unitdefs.py` and `tests/test_unitdefs.py`, both outside files_modified.

**4. [Rule 3 - Blocking] The Task 1 RED commit includes an API skeleton of readlint.py.**
- Without it, test collection failed with ImportError. The classifier reads that as INVALID_RED (a load failure), not as a valid RED.
- The skeleton holds the dataclasses and a `run_readlint` that returns nothing, so the tests fail on their assertions.

**5. [Rule 2 - Missing critical] The allowlist file is validated strictly.**
- A wrong header, an unknown exe, a name that is not a placeholder, an empty reason, a wrong cell count, a repeated row or invalid UTF-8 each give exit 2.
- Reason: a malformed allowlist must never silently allow anything (threat T-07-79).

**6. Scope additions, each with a test.**
- An RL01 identifier spliced across lines is still found.
- A placeholder inside a directive counts as RL01.
- A file outside `src/<exe>/` is skipped.
- Headers included from headers are scanned too.

---

**Total deviations:** 3 orchestrator rulings applied, 2 auto-fixes (1 blocking, 1 missing critical), 1 set of scope additions. **Impact:** none on the plan's interfaces; every addition fails closed.

## Issues Encountered

None.

## Verification

- `uv run pytest -q tests/test_readlint.py`: **130 passed**.
- `uv run pytest -q tests/test_readlint.py -k "rl02 or rl03 or rl04 or rl05 or rl06 or floats"`: 56 passed.
- `uv run reverseapoc readlint --report src/`: exit 0, 4 files checked.
- `uv run reverseapoc readlint src/`: exit 1, 37 violations. This is the acceptance "exits 1 today".
- `uv run reverseapoc readlint --help` lists `--units`, `--tier`, `--report`, `--src`, `--config` and `--json`.
- `uv run pytest -q` (full host suite, worktree): **3510 passed, 247 skipped**.
  - The skip count equals the last recorded baseline (07-19 fix round 2: 247).
  - The readlint tests skip nothing, so there is no new skip reason.
- `uv run ruff check .`: All checks passed.
- Container step deferred to the orchestrator: `docker compose build && docker compose run --rm test`.

## Known Stubs

None. config/readlint-allow.csv is header-only by design: the plan says "header only at first", and 07-40 fills it after the owner's review (F5).

## Threat Flags

None. readlint only reads local files under the given roots, and it adds no network, write or auth surface.

## User Setup Required

None.

## Next Phase Readiness

- **07-31** can lint a view with `readlint --src <view>/src --config <config>`. Headers resolve from `<view>/include`, beside the src root.
- **07-35 and 07-36 (skills)** can quote the module docstring for the rule set and the RL03 header form:

  ```
  <name>: <purpose>
  Address: <EXE> 0x%08X
  Evidence: <kind>: <text>
  ```

- **07-38** lands with strict `readlint` exit 0.
- **07-40** fills config/readlint-allow.csv: references only, each with a reason.
- `--tier N` needs config/mechanics.toml and config/mechanics-members.csv. A missing file is exit 2.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*

## Self-Check: PASSED
