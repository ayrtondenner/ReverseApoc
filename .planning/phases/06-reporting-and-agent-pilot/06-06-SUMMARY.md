---
phase: 06-reporting-and-agent-pilot
plan: 06
subsystem: tooling
tags: [python, asm, score, capstone, listings, DI-01, DI-19]

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "06-02: fileio.write_atomic (the listing writer) and SymbolTable.build's CSV-only path (ruling F6)"
provides:
  - "asm.file_name: one listing per functions.csv row; a name in SymbolTable.ambiguous falls back to <kind>_<start>.s (DI-01, backlog 999.3)"
  - "a uniqueness test over the committed ufo2p/tacp CSVs, compared with str.casefold, that needs no orig/"
  - "score: page size from the LE header (row 9a); --top refused only by ScoreReport.build (9b); __CHK prologue needs push <immediate> (9d)"
  - "asm._substitute names the operand that capstone's disp_offset/imm_offset places the fixup field in (9c)"
  - "x86.Insn.disp_offset / imm_offset"
affects: [06-context-pack, 06-driver, 06-25, 06-15]

actuals:
  tokens: 4481  # chars/4 over the realized diff (17923 bytes, 6 files, +221/-24)
  tasks: 2
  commits: 4
plan_head_before: a9e13ed54f72aafb7389d1415f1707e516d1581d
plan_head_after: ec55400151655b6dbfcfa7d801183b728818ae7d

tech-stack:
  added: []
  patterns:
    - "A fixup field's operand is found by capstone's field offsets (disp_offset, imm_offset), never by matching its value in op_str"

key-files:
  created: []
  modified:
    - tools/reverseapoc/asm.py
    - tools/reverseapoc/score.py
    - tools/reverseapoc/cli.py
    - tools/reverseapoc/x86.py
    - tests/test_asm.py
    - tests/test_score.py

key-decisions:
  - "Ambiguous runtime names (today only _Alphabet, in rt_itoa and rt_ltoa of both EXEs) use the <kind>_<start>.s fallback; no other case-only collision exists in the committed CSVs"
  - "x86.Insn carries capstone's disp_offset and imm_offset so asm.py can name a fixup operand by position (x86.py was not in the plan's file list)"
  - "A field at neither offset (e.g. the ptr16:32 of a far jump) keeps the existing `; <kind> -> <name>` note"

patterns-established:
  - "Listing file names are unique per EXE under str.casefold, pinned by tests/test_asm.py::test_committed_listing_names_are_unique"

requirements-completed: [AGT-07, AGT-08]

coverage:
  - id: D1
    description: "Every functions.csv row gets its own listing; ambiguous runtime names write runtime_<start>.s; committed names are unique under casefold"
    requirement: AGT-08
    verification:
      - kind: unit
        ref: "tests/test_asm.py#test_ambiguous_name_gets_one_listing_per_row"
        status: pass
      - kind: unit
        ref: "tests/test_asm.py#test_committed_listing_names_are_unique[ufo2p|tacp]"
        status: pass
      - kind: other
        ref: "uv run reverseapoc asm ufo2p|tacp --orig <main>/orig --out <scratch>: 1892 and 1874 files written, one per row"
        status: pass
    human_judgment: false
  - id: D2
    description: "score uses the LE header's page size (9a), checks --top once (9b), and counts only push <immediate>; call __CHK (9d)"
    requirement: AGT-07
    verification:
      - kind: unit
        ref: "tests/test_score.py#test_score_takes_the_page_size_from_the_le"
        status: pass
      - kind: unit
        ref: "tests/test_score.py#test_top_is_checked_once"
        status: pass
      - kind: unit
        ref: "tests/test_score.py#test_has_chk_needs_a_chk_call"
        status: pass
    human_judgment: false
  - id: D3
    description: "asm._substitute renames only the operand holding the fixup field (9c)"
    requirement: AGT-08
    verification:
      - kind: unit
        ref: "tests/test_asm.py#test_substitute_leaves_an_equal_displacement_alone"
        status: pass
      - kind: other
        ref: "diff -r of all 3766 real listings before/after the fix: identical"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 06: One listing per row and the scorer minors Summary

**`asm` writes `runtime_<start>.s` for an ambiguous runtime name such as `_Alphabet`, so each functions.csv row has its own listing. The scorer reads the page size from the LE header, refuses `--top` in one place and counts a stack-check prologue only for `push <imm>; call __CHK`. Listings now name a fixup operand by its position in the instruction (from capstone's offsets), not by matching its value.**

Execution context nonce: 19e7f704b16d5182

## Performance

- **Duration:** about 12 min
- **Started:** 2026-10-25T02:31:47Z
- **Completed:** 2026-10-25T02:43:42Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- DI-01 (backlog 999.3) closed. In both EXEs, `_Alphabet` (rt_itoa and rt_ltoa) wrote the same `_Alphabet.s`; it now writes two `runtime_<start>.s` files (UFO2P 0x000C06FA / 0x000C92CD, TACP 0x000C2826 / 0x000CD0AF). The uniqueness test over the committed CSVs found no other case-only collision. A real run wrote 1892 UFO2P and 1874 TACP listings, one per row.
- 05-REVIEW row 9a: `_cmd_score` passes `inputs.le.page_size` (LE header field 0x28). `LE_PAGE_SIZE` is now only assess's default, and its comment names the header field.
- Row 9b: the duplicate `--top` check in `cli._cmd_score` is gone; `ScoreReport.build` is the only check.
- Row 9c: `_substitute` finds the operand from capstone's `disp_offset` / `imm_offset`. It renames the displacement (the last number inside `[...]`) or the immediate (the last operand), and nothing else.
- Row 9d: `_has_chk` requires the push to carry an immediate (`imm_offset != 0`), as ruling F23 says.

## Score before and after (`--orig <main checkout>/orig`, ruling F23)

`uv run reverseapoc score ufo2p --top 5 --orig C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/orig`, before and after, identical:

```
UFO2P.EXE: 612 of 1892 functions pass the P16 filter (rejected: call target is not a nameable functions.csv start 109, data target not at an exact address 17, jump table 237, no absolute fixup 465, no call rel32 741, non-off32 fixup 9, not game code 84, runtime 262, straddling fixup 14, string reference 241)
  0x000A3980  func_000A3980  size 13  score 155  (size 13; 1 call; 1 D_ reference; no push ebp frame)
  0x0008A0E0  func_0008A0E0  size 27  score 169  (size 27; 1 call; 1 D_ reference; no push ebp frame)
  0x0008A100  func_0008A100  size 27  score 169  (size 27; 1 call; 1 D_ reference; no push ebp frame)
  0x0008A120  func_0008A120  size 27  score 169  (size 27; 1 call; 1 D_ reference; no push ebp frame)
  0x0008A140  func_0008A140  size 27  score 169  (size 27; 1 call; 1 D_ reference; no push ebp frame)
```

The full JSON reports (`--top 2000`) of both EXEs are byte-identical before and after (`cmp`). No real function opens with a non-immediate push before `call __CHK` (9d), and both EXEs have 0x1000 pages (9a). The asm listings of both EXEs (3766 files) are also identical before and after the 9c change (`diff -r`). On the real data, positional naming picks the same operand that value matching did, so no listing regressed.

## Task Commits

1. **Task 1 (tracer): one listing per row, unique case-insensitively (DI-01)**
   - RED `a56080d` (test): `test_ambiguous_name_gets_one_listing_per_row`, `test_committed_listing_names_are_unique[ufo2p|tacp]`
   - GREEN `6d535c1` (fix): `file_name` falls back for names in `symbols.ambiguous`
2. **Task 2: scorer and listing minors (rows 9a-9d)**
   - RED `940b974` (test): the four tests
   - GREEN `ec55400` (fix): score.py, cli.py, asm.py, x86.py

## TDD evidence

- Task 1 RED: all three new tests failed on their assertions. The synthetic run wrote only `_Alphabet.s` instead of two `runtime_<start>.s` files. The committed-CSV test reported `0x000C06FA and 0x000C92CD -> _alphabet.s` (UFO2P) and `0x000C2826 and 0x000CD0AF -> _alphabet.s` (TACP), and nothing else. Semantic assessment: the target tests ran and failed for the planned reason (the DI-01 collision). GREEN: 11 passed.
- Task 2 RED: all four tests failed on their assertions. 9a: `rejected` had no `straddling fixup`. 9b: `ScoreReport.build` was never called, because cli refused first. 9c: the line read `mov dword ptr [eax*D_00020004 + 4], 4`, so the scale had been renamed. 9d: `chk=True` for `push eax; call __CHK`. Semantic assessment: each target ran and failed on the planned defect; this was not a setup failure. One first-run setup error in the 9a test, a functions.csv row-order error, was fixed before the RED commit. GREEN: 133 passed in test_score/test_asm/test_cli.

## Verification

- `uv run pytest -q tests/test_asm.py`: 12 passed (tracer verify, re-run after GREEN).
- `uv run pytest -q tests/test_score.py tests/test_asm.py tests/test_cli.py`: 133 passed.
- `uv run pytest -q`: 1521 passed, 216 skipped. `uv run ruff check .`: all checks passed.
- With `REVERSEAPOC_ORIG` and `REVERSEAPOC_WATCOM_DIR` pointing at the main checkout, tests/test_discover_real.py, test_functions_real.py, test_le_real.py, test_x86.py, test_asm.py and test_score.py gave 84 passed, 6 skipped.

## Files Created/Modified

- `tools/reverseapoc/asm.py`: `file_name` falls back for ambiguous names. Positional `_field_operand` / `_substitute`, and the module docstring now describes them.
- `tools/reverseapoc/score.py`: comment on `LE_PAGE_SIZE`; `_has_chk` requires `push <imm>`.
- `tools/reverseapoc/cli.py`: `_cmd_score` passes `page_size=inputs.le.page_size`; the duplicate `--top` check is gone.
- `tools/reverseapoc/x86.py`: `Insn.disp_offset`, `Insn.imm_offset` from capstone.
- `tests/test_asm.py`, `tests/test_score.py`: the six tests the plan names.

## Decisions Made

- No case-only collision other than `_Alphabet` exists, so the fallback covers only `symbols.ambiguous` and unsafe names.
- A fixup field at neither capstone offset keeps the existing comment note. Before, the code would have fallen back to matching by value.

## Deviations from Plan

### Orchestrator rulings applied

- **Orchestrator ruling F23: 9d and the score run.** The 9d RED test is `push eax; call __CHK` (a register push), and it must not count. GREEN requires the push to carry an immediate (`Insn.imm_offset`), as `target in chk_targets` already did for the call. The before/after `score` listing used `--orig "<main checkout>/orig"`, because the CLI does not read REVERSEAPOC_ORIG.
- **Ruling note F6 (06-02):** `test_committed_listing_names_are_unique` builds `SymbolTable` from the committed CSVs with no data ranges and no LE. No code change was needed.
- **"For 06-06, 06-15 and 06-25":** no positional `EXE` or other split-input argument was added. Only `_cmd_score`'s body changed.
- **R-A / R-B:** no new skip; nothing was written under build/.

### Auto-fixed Issues

**1. [Rule 3 - Blocking] x86.py exposes the field offsets**
- **Found during:** Task 2 (9c)
- **Issue:** Substituting "by the fixup field's operand position" needs to know where the displacement and immediate fields sit in the instruction. `Insn` did not carry that, and x86.py is not in the plan's file list.
- **Fix:** Added `disp_offset` and `imm_offset` to `Insn`, both taken from capstone's detail (defaults of 0 mean none). The module docstring names them.
- **Files modified:** tools/reverseapoc/x86.py
- **Verification:** test_x86.py and the full suite pass, and all real listings are unchanged.
- **Committed in:** ec55400

**2. [Test setup] a 0x800-page synthetic LE for 9a**
- **Found during:** Task 2 RED
- **Issue:** conftest's LE builder always writes 0x1000 pages.
- **Fix:** The 9a test monkeypatches `conftest.PAGE_SIZE` to 0x800, so the header, page layout and patch mapping all agree. It cuts its own fixup records and code patches at 0x800 and asserts `LE(data).page_size == 0x800`. Nothing in conftest itself changed.
- **Committed in:** 940b974

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 test setup), plus 1 orchestrator ruling applied (F23).
**Impact on plan:** None in scope. Committed scorer output and listings are unchanged.

## Issues Encountered

- The tests/test_functions_real.py `test_symbols_resolve` tests need Watcom 10.6. With `REVERSEAPOC_WATCOM_DIR` unset they fail in the worktree, because `third_party/` is not copied there. They pass with the main checkout's install. This is the environment, not this plan.
- `ruff format --check` would reformat some lines in cli.py, score.py and x86.py that this plan did not touch. They are left alone: `ruff check` is the gate, and they are out of scope.

## Next Phase Readiness

- Main-checkout `asm/` listings written before this fix still include the old `_Alphabet.s` until the driver preflight regenerates them (plan 06-25). Listings are gitignored.
- The context pack (D-13) can rely on one `asm/<exe>/<file_name>.s` per row. A consumer should get the name from `asm.file_name(symbols, row)`, not from the C name.

## Self-Check: PASSED

- FOUND: tools/reverseapoc/asm.py, tools/reverseapoc/score.py, tools/reverseapoc/cli.py, tools/reverseapoc/x86.py, tests/test_asm.py, tests/test_score.py
- FOUND commits on HEAD: a56080d, 6d535c1, 940b974, ec55400
- RED commits precede GREEN for both tdd tasks: test(06-06) a56080d < fix(06-06) 6d535c1; test(06-06) 940b974 < fix(06-06) ec55400

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
