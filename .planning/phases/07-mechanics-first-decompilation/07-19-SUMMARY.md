---
phase: 07-mechanics-first-decompilation
plan: 19
subsystem: tooling
tags: [d-19, d-21, r5, proposals, naming-state, rename, headers]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-04: hooks.asm_problem(any_pragma=...), hooks.include_problem, the reserved-header list"
  - phase: 07-mechanics-first-decompilation
    provides: "07-09: unitdefs.C_KEYWORDS, c_name_of and the func/data `_` linker rule"
  - phase: 07-mechanics-first-decompilation
    provides: "07-16: symbols.csv C names (SymbolTable.c_name through unitdefs.c_name_of)"
provides:
  - "tools/reverseapoc/proposals.py: ProposalError, OPS, KINDS, EXES, EVIDENCE_KINDS, PLACEHOLDER, NAME_MAX, HEADER_TEXT_MAX, Rename, Header, parse_line, read_proposals, evidence_problem, name_problem, linker_name, rename_problem, header_problem"
  - "tests/test_proposals.py: the pinned proposals.jsonl format and its validators (105 tests)"
affects: [07-27, 07-34, 07-35, 07-36]

actuals:
  tokens: 6900
  tasks: 2
  commits: 4
plan_head_before: aaa81213cfcc46c1f9028bfa077e5ce67b41d9c3
plan_head_after: 375e8ab268243e92d3a8a4a2c1c8eaf7beca0f58

tech-stack:
  added: []
  patterns:
    - "Shape first, applicability second: parse_line/read_proposals check only the line format; name_problem/rename_problem/header_problem are asked by the driver against the naming state of that moment"
    - "Header proposals reuse the hooks' own scans (asm_problem with any_pragma=True, include_problem) and the hooks' reserved-header list, so the driver and the hooks refuse the same text"

key-files:
  created:
    - tools/reverseapoc/proposals.py
    - tests/test_proposals.py
  modified: []

key-decisions:
  - "Rename.address is an int (parsed from 0x%08X); exe is validated as ufo2p|tacp, the stems the driver's v2 rename records use"
  - "Strict JSON per line: duplicate keys and NaN/Infinity are refused; lines split on \\n only (U+2028 may sit inside a JSON string); whitespace-only lines are skipped"
  - "Evidence text is 1..200 printable ASCII characters on one line, not only spaces"
  - "A rename to the row's current C name is refused ('already the C name'), so the driver never makes an empty rename commit"
  - "Uniqueness compares C and linker spellings ({name, linker_name(name, kind)}) against each symbols.csv row's C and linker name, and against each runtime public read fail-closed as a func or a data name"
  - "A data rename must lie in no functions.csv row (code), and in a data object when data_ranges are given (the SymbolTable.build rule); data-in-code rows cannot be renamed through a proposal"
  - "Header paths must be lower-case bare include/<name>.h (the hooks' new-header shape), so no case variant of a reserved header passes on a case-insensitive file system"

patterns-established:
  - "07-34 builds src_names (file-scope name -> repo-relative path) and calls parse_line per line so one bad line becomes one REFUSED record (op null) without losing the good lines"

requirements-completed: [DEC-02, DEC-04]

coverage:
  - id: D1
    description: "The D-19 proposals.jsonl line format: rename and header lines parse into Rename/Header; every malformed line (non-JSON, non-object, extra/missing key, op delete, kind label, address 0xa3980, bad exe, non-string value, duplicate key, NaN, non-UTF-8) is a ProposalError naming its line; missing/empty file -> []"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_proposals.py#test_parse_rename_and_header, test_bad_lines_name_the_line, test_not_utf8_names_the_line, test_empty_file, test_missing_file"
        status: pass
    human_judgment: false
  - id: D2
    description: "D-21 evidence form <string|table|call|vocab>: <1..200 printable ASCII chars>"
    requirement: DEC-04
    verification:
      - kind: unit
        ref: "tests/test_proposals.py#test_evidence_kinds_accepted, test_evidence_kinds_refused, test_evidence_kinds_are_readlints"
        status: pass
    human_judgment: false
  - id: D3
    description: "name_problem: identifier, keyword, placeholder (R5 incl. LAB_/PTR_/UNK_) and 63-character rules"
    requirement: DEC-04
    verification:
      - kind: unit
        ref: "tests/test_proposals.py#test_name_problems, test_name_passes, test_placeholder_regex_is_readlints"
        status: pass
    human_judgment: false
  - id: D4
    description: "rename_problem: target kind (func -> game/thunk row start; data -> no code, in a data object) and uniqueness across symbols.csv, runtime publics and src/ file-scope names, naming where the name is used"
    requirement: DEC-04
    verification:
      - kind: unit
        ref: "tests/test_proposals.py#test_rename_unique, test_rename_target_kind, test_rename_passes, test_rename_to_its_current_name_is_refused, test_data_rename_without_data_ranges_checks_code_only"
        status: pass
    human_judgment: false
  - id: D5
    description: "header_problem: reserved/non-bare paths, inline asm, any #pragma, _Pragma, path includes, non-ASCII and > 64 KiB text refused; a plain struct header passes"
    requirement: DEC-04
    verification:
      - kind: unit
        ref: "tests/test_proposals.py#test_header_path_problems, test_header_problems, test_plain_header_passes, test_header_of_64_kib_passes"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 19: The D-19 naming-proposal format and its validators Summary

**`tools/reverseapoc/proposals.py` pins the machine-checked `proposals.jsonl` format: strict one-object-per-line JSON with exact key sets for `rename` (exe, kind, address `0x%08X`, name, evidence) and `header` (path, text, evidence), D-21 evidence `<string|table|call|vocab>: <text>`, and a ProposalError that names the line. Three validators decide whether the driver may apply a proposal: `name_problem` (C identifier, 63 characters, keywords, R5 placeholders), `rename_problem` (target row kind, uniqueness across symbols.csv, runtime publics and src/ file-scope names) and `header_problem` (bare non-reserved header, ASCII, 64 KiB, the hooks' asm/pragma/include scans).**

Execution context nonce: f557261d8877a5ab

## Performance

- **Duration:** about 10 min of execution (18:55:44Z to 19:05:59Z), after reading the context
- **Started:** 2026-10-27T18:55:44Z
- **Completed:** 2026-10-27T19:05:59Z
- **Tasks:** 2
- **Files modified:** 2 (both created)

## Accomplishments

- **Format (Task 1, tracer).**
  - `parse_line(text, lineno) -> Rename | Header`.
  - Strict JSON: no NaN or Infinity, and no repeated key, which `json` would otherwise let silently win.
  - Exact key sets per op, all values strings.
  - `exe` is one of `ufo2p`/`tacp`, `kind` one of `func`/`data`, and `address` matches `0x[0-9A-F]{8}` exactly.
  - `evidence_problem` checks the D-21 evidence form.
- **`read_proposals(path)`.**
  - Decodes strict UTF-8. A bad byte is reported with its line.
  - Splits on `\n` only. JSON allows U+2028 inside a string, and `str.splitlines` would cut there.
  - CRLF lines parse.
  - A missing, empty or whitespace-only file returns `[]` (DEC-02 edge).
- **Validators (Task 2).**
  - `PLACEHOLDER` is the plan's regex verbatim. It includes `LAB_`, `PTR_` and `UNK_` (R5, owner-confirmed).
  - `name_problem` checks the name.
  - `linker_name` turns a C name back into its linker name (`Foo` -> `Foo_`, `g_vol` -> `_g_vol`).
  - `rename_problem` checks the target row and uniqueness. It names the symbols.csv row (address and linker name), the runtime public, or the src/ file that already uses the name.
  - `header_problem` reuses `hooks.asm_problem(text, any_pragma=True)`, `hooks.include_problem` and `hooks._RESERVED_HEADERS`.

## Task Commits

1. **Task 1 (tracer, TDD): the proposal line format.** RED `e63ff65` (test), GREEN `253a1af` (feat).
2. **Task 2 (TDD): name, rename and header validation.** RED `479f1ee` (test), GREEN `375e8ab` (feat).

No REFACTOR commits were needed.

## TDD evidence

- **Task 1 RED (`e63ff65`).**
  - Target: `tests/test_proposals.py::test_parse_rename_and_header`. It failed on its assertion `[] == [Rename(...), Header(...)]`.
  - JUnit report: `build/red/07-19-t1.xml` (gitignored). Record: `build/red/07-19-t1.json`, with `runStartedAt` captured by `date` before the run.
  - Classifier: `RED_EVIDENCE_OK` / `target_test_failed` (42 tests: 37 failed, 5 passed).
  - Semantic assessment: the target ran and failed on the planned behaviour, not on an import, collection or fixture fault.
  - The RED commit holds an interface skeleton of `proposals.py`: the constants, the error class and the two dataclasses, plus `parse_line`/`read_proposals` stubs that return nothing. Without it, the new module's absence would fail collection with ModuleNotFoundError, which is INVALID_RED.
  - The 5 tests that passed in RED are edge characterizations the stub satisfies by accident: missing/empty file -> `[]` (4) and the constants test (1).
- **Tracer feedback gate.** The run was interactive, `human_verify_mode` was end-of-phase, and the verify step was automated only. After GREEN I re-ran `uv run pytest -q tests/test_proposals.py`: 42 passed. Then I expanded to Task 2.
- **Task 2 RED (`479f1ee`).**
  - Target: `tests/test_proposals.py::test_name_problems[while]`. It failed on its assertion: no problem was reported for a C keyword.
  - JUnit report: `build/red/07-19-t2.xml`. Record: `build/red/07-19-t2.json`.
  - Classifier: `RED_EVIDENCE_OK` / `target_test_failed` (105 tests: 53 failed, 52 passed).
  - The stubs `name_problem`, `rename_problem` and `header_problem` returned None.
  - Two failures were not on an assertion:
    - `test_placeholder_regex_is_readlints` hit AttributeError, because `PLACEHOLDER` does not exist yet.
    - `test_rename_carries_name_problems` hit TypeError (`"keyword" in None`).
  - The passing tests are the accept cases (`test_name_passes`, `test_rename_passes`, `test_plain_header_passes`, the 64 KiB pass) plus the Task 1 tests.

## Verification (done gate)

- `uv run pytest -q tests/test_proposals.py`: 105 passed, 0 skipped.
- `uv run pytest -q` (full host suite, worktree): **3212 passed, 246 skipped**. This plan adds no skip. The others are the existing owner-file, container and platform skips; the worktree has no `orig/` or `third_party/`.
- `uv run ruff check .`: All checks passed. `ruff format --check` is clean on both new files.
- Acceptance greps:
  - `EVIDENCE_KINDS = ("string", "table", "call", "vocab")` (proposals.py:36);
  - `def read_proposals(`, `def rename_problem(` and `def header_problem(` are present;
  - `asm_problem(` is called in `_header_text_problem`;
  - `ProposalError` appears in tests/test_proposals.py.

## Container steps deferred to the orchestrator

- `docker compose run --rm test` (the full container suite). Nothing in this plan is container-only.

## Files Created/Modified

- `tools/reverseapoc/proposals.py` (new): the format, the parser and the validators.
- `tests/test_proposals.py` (new): 105 tests. Every name, address and header in them is made up, and there are no game bytes.

## Decisions Made

See key-decisions in the frontmatter.

## Deviations from Plan

**Orchestrator rulings.** The plan has no section in rulings.md. "Rules for every plan" applied:
- R-A: no new skip.
- R-B: the container run is deferred.
- R-D: no subagents.

R5 (owner answer) is applied as researched: `LAB_`, `PTR_` and `UNK_` are placeholders.

**1. [Rule 2 - Correctness] Linker-spelling and cross-kind collisions.**
- The plan says the name must be unique among symbols.csv C names and runtime publics. A C name can still collide at link time:
  - a func `_Tick` links as `_Tick_`, which is the linker name of data `Tick_`;
  - a func `exit` links as `exit_`, the runtime public.
- `rename_problem` therefore compares the proposal's C and linker spellings with each symbols.csv row's C and linker name. It reads runtime publics fail-closed, as both func and data C names.
- Tests: `test_rename_unique[symbols-linker|symbols-cross-kind|runtime-*]`.
- Committed in `375e8ab`.

**2. [Rule 2 - Correctness] A rename to the row's current name is refused.**
- Without this, the driver could make a rename commit that changes nothing.
- Test: `test_rename_to_its_current_name_is_refused`.

**3. API addition (not in the plan text).**
- `rename_problem` takes an optional `data_ranges` keyword, the LE data objects. A data address outside them is refused, the same rule `SymbolTable.build` applies to symbols.csv data rows.
- Without it the plan's "data rename of a code address" can only be checked against functions.csv rows. That check stays when no ranges are given (`test_data_rename_without_data_ranges_checks_code_only`).
- Public helpers beyond the plan's list: `EXES`, `NAME_MAX`, `HEADER_TEXT_MAX`, `evidence_problem` and `linker_name`.

**4. RED skeletons.** Both RED commits include interface stubs in `proposals.py`, so the RED tests fail on assertions instead of at import (see TDD evidence).

**5. Header path rule is lower-case only.** The hooks' `_NEW_HEADER` shape is reused, so `include/Common.h` is refused. On Windows it would be the same file as `common.h`.

**Total deviations:** 2 auto-fixed (Rule 2), 3 documented design choices; rulings: Rules for every plan plus R5.
**Impact:** no scope creep. Every change narrows what the driver may apply.

## Threat Flags

None. The module only parses and validates; it writes nothing.
- T-07-55 is mitigated by `header_problem`: reserved headers, asm/pragma/include scans, ASCII and the 64 KiB cap.
- T-07-56 is mitigated by `rename_problem`'s uniqueness checks.

Not covered here: a header text that `#define`s or `#undef`s `INCLUDE_ASM`. It passes the hooks' scans; the driver's all-or-nothing gate catches the changed bytes.

## Issues Encountered

- The harness refused compound shell commands that combined `cd` with git, and a heredoc append to a tracked file. I split the commands, and used the Edit tool for the test file.

## User Setup Required

None.

## Next Phase Readiness

- **07-34 (rename apply step):**
  - Call `parse_line` per line. A ProposalError becomes a REFUSED v2 record with op null and the error as reason; `driver.validate_record` requires that reason.
  - Build `src_names` (file-scope name -> path) from the committed src/ units. A public file-scope scan helper in `unitdefs` would be the place for it; `_file_scope` is private (rulings note under 07-27).
  - Pass the EXE's `symbols`, `functions`, runtime names and aliases, and `data_ranges` to `rename_problem`.
  - Write the linker name with `linker_name(name, kind)`.
- **07-27 (readlint)** can import `PLACEHOLDER` and `EVIDENCE_KINDS` for RL01/RL03.
- **07-35/07-36 (skills)** can quote the format from the module docstring.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*

## Self-Check: PASSED

## Fix round 1

The findings came from the task review (I1, I2) and an automated security review (S1, S2). The orchestrator ruled on each, and also asked for three minors.

**Changes.**
- **I1.** `json.loads` raises `RecursionError` on a deeply nested line, which escaped `parse_line`. `parse_line` now also catches `RecursionError` and raises it as a ProposalError naming the line. Covered by `BAD_LINES["deep-nesting"]`.
- **I2.** `rename_problem`'s `data_ranges` is now a required keyword. An empty sequence means there is no data object, so every data rename is refused (fail closed, the `SymbolTable.build` rule).
  - Tests: `test_data_ranges_are_required` and `test_data_rename_with_no_data_object_is_refused`. They replace `test_data_rename_without_data_ranges_checks_code_only`, which pinned the old fail-open default.
- **S1 (header text).** `header_problem` runs its own preprocessor check on the text before the hooks' scans. The text is read the way configure reads it: trigraphs mapped, continuations spliced, comments and literals blanked. It refuses:
  - any `%:` digraph;
  - any `#` or `##` operator after a directive's own `#`;
  - a function-like macro;
  - a `#define` or `#undef` of a keyword (C89, prefixed Watcom or bare Watcom), of `_Pragma`, `__pragma`, `__emit` or `INCLUDE_ASM`, or of any macro the reserved headers define. `reserved_macros()` reads those names from include/common.h and include/watcom_compat.h at validation time; callers may pass `reserved=`;
  - an object-like body containing `{`, `}` or `;`.

  `test_header_allowed_forms_pass` pins what passes: include guards, typedef/struct/union/enum, prototypes, object-like constant `#define`s, and `##` inside a comment.
- **S1 (hooks).** `hooks._inline_asm` (the scan function) refuses a `#`, `##`, `%:` or `%:%:` operator after a directive's own `#`. This applies only in the strict mode (`any_pragma=True`), which the matching layer and `header_problem` use. Covered by `tests/test_hooks.py::test_matching_denies_preprocessor_operators` (8 spellings: plain, spaced, digraph, trigraph, across a continuation, stringize) and `test_matching_allows_hashes_outside_code`.
- **S2.** `name_problem` additionally refuses:
  - the bare Watcom keywords (`asm`, `cdecl`, `far`, `near`, `huge`, `interrupt`, `pascal`, `fortran`, and the rest of `WATCOM_BARE_KEYWORDS`);
  - `_Pragma`, `__pragma`, `__emit` and `INCLUDE_ASM`;
  - the reserved headers' macro names (`COMMON_H`, `WATCOM_COMPAT_H`, `__far`, ...);
  - every C89-reserved `_X` and `__x` name.
- **Minors.**
  - `PROPOSAL_LINE_MAX` is 196,608 bytes (192 KiB, 3 x `HEADER_TEXT_MAX`). The largest header line, 64 KiB of newlines escaped to 128 KiB, still parses.
  - `PROPOSALS_FILE_MAX` is 4 MiB per file.
  - Header text may hold no control character other than tab, LF and CR.
  - The DOS device stems `con`, `nul`, `aux`, `prn`, `com1`-`com9` and `lpt1`-`lpt9` are refused as header names.

**Deviations (fix round).**
- **Hooks edit outside files_modified.** `tools/reverseapoc/hooks.py` and `tests/test_hooks.py` are not in this plan's files_modified, but the ruling asked for the edit.
  - The change is local to the scan function: two constants, `_preprocessor_operator`, and one branch in `_inline_asm`.
  - 07-13, not yet merged, also edits hooks.py. The rule's regexes are named `_DIRECTIVE_HASH` and `_HASH_OPERATOR` and sit right above `_inline_asm`.
- **The hooks rule is tied to the strict scan, not to every scan.**
  - `include/common.h:19` itself uses `##`: `#define INCLUDE_ASM(name) extern int INCLUDE_ASM_##name`.
  - `tests/test_hooks.py::test_always_allows_the_committed_headers_and_units` (F16) requires the always layer to accept a write of that file.
  - So the always layer (`any_pragma=False`) is unchanged, and the matching layer (`any_pragma=True`, every matching and readability session) refuses the operators. Header proposals use the strict scan too.
- **Test fixture change.** The linker-collision case now uses data `_tick_` and func `_tick`. `_Tick` is C89-reserved after S2, so name_problem refused it before the collision check ran.
- **Keywords as macro names.** `#define`/`#undef` of any keyword or reserved identifier is refused, not only of the reserved headers' macros. This goes beyond the ruling, which named only INCLUDE_ASM and the reserved headers' macros; it keeps a header from redefining `while` or `_asm`.

**src/ grep (asked before adding the hooks rule).**
- `grep -rn "%:\|##" src include` finds one hit: `include/common.h:19`, the INCLUDE_ASM macro above.
- No committed src/ unit (`src/ufo2p/*.c`, `src/tacp/*.c`, 4 files) defines a macro with `#` or `##`.
- No src/ file uses `%:`, and no `#` follows a directive's own `#`. So every committed unit passes the new strict rule.

**RED evidence (`26107a8`).**
- Target: `tests/test_proposals.py::test_header_problems[paste]`. `header_problem` returned None for a header that pastes `__a##sm`.
- JUnit report: `build/red/07-19-fr1.xml`. Record: `build/red/07-19-fr1.json`.
- Classifier: `RED_EVIDENCE_OK` / `target_test_failed`. 481 tests ran and 57 failed: every new rule failed, and the deep-nesting case raised `RecursionError`, not a ProposalError.
- Characterization tests that passed before the fix: `test_largest_header_line_parses` and `test_matching_allows_hashes_outside_code`.
- `test_header_allowed_forms_pass` was added with the fix commit as a pass-case pin.

**Commits:** `26107a8` (test), `c7b466e` (fix: hooks), `ab9d04e` (fix: proposals).

**Commands and output after the fix.**
- `uv run pytest -q tests/test_proposals.py tests/test_hooks.py`: 480 passed, 2 skipped. The 2 skips are the existing "symlink creation needs privileges on this host"; none is new.
- `uv run pytest -q` (full host suite): **3272 passed, 246 skipped**. No new skip.
- `uv run ruff check .`: All checks passed. `ruff format --check` is clean on proposals.py and test_proposals.py.

**Container step deferred to the orchestrator:** `docker compose run --rm test`.

**Open for 07-34.** `src_names` should also carry the file-scope names of the shared headers under include/: the typedefs `s8`..`u32` in common.h, and the macros and types of the driver-written headers. A rename to `u8` or to another header's macro name is not refused here. The all-or-nothing gate would catch it at compile time.
