---
phase: 05-split-and-first-matches
plan: 08
subsystem: tooling
tags: [elf, objdiff, target, le, fixups, capstone, spl-08, d-13]

requires:
  - phase: 05-split-and-first-matches
    provides: "05-02 elf.write_elf and tests/elfread.py with index-based sections (F10); 05-03 x86.decode with data_sites and rel32_field; 05-04 FunctionRow and SymbolTable.linker_name/containing/function_at"
provides:
  - "tools/reverseapoc/target.py: build_target(le, rows, symbols, *, flat, fixups) -> TargetResult(data, raw_fields), branch_fields(row, flat, fixup_sites), TargetError, RawField"
  - "Per-unit target ELF cut from load_flat(relocate=False): one _TEXT section per row, GLOBAL STT_FUNC per function, LOCAL STT_OBJECT per data-in-code row, R_386_32 from LE off32 fixups, synthesized R_386_PC32 for calls and function-leaving rel32 jumps"
affects: [05-17, 05-18, 05-11]

actuals:
  tokens: 6240
  tasks: 2
  commits: 4
plan_head_before: 532a74582239727dd92c0ee200d1d3e8d81b87cf
plan_head_after: 8ad11737d23c0a07a83bfaa84d265336c8d96c02

tech-stack:
  added: []
  patterns:
    - "Every target name comes from SymbolTable.linker_name; a reference into the code object names its containing row plus the offset"
    - "Decoding skips an LE fixup site at an instruction start by its field size and resumes after it; an undecodable byte is skipped by one byte"

key-files:
  created:
    - tools/reverseapoc/target.py
    - tests/test_target.py
  modified: []

key-decisions:
  - "build_target returns TargetResult(data, raw_fields) rather than bytes, so the non-off32 sites of ruling F11 are reported in its result. 05-17 writes result.data and can print raw_fields"
  - "A data-in-code row's LOCAL STT_OBJECT is named by SymbolTable.linker_name (_D_<start>), not D_<start> as the plan's behavior line wrote, so the plan's own key_link (every name from linker_name) holds and the R_386_32 into the table resolves by the same name"
  - "branch_fields takes (row, flat, fixup_sites) with fixup_sites a {field VA: size} map; the plan's unused `le` parameter was dropped"
  - "A rel32 field that is itself an LE fixup site belongs to that fixup and gets no PC32"
  - "The code object is the first executable LE object, as libmatch picks it"

patterns-established:
  - "TargetError messages name the VA as 0x%08x (row start, branch field and destination, fixup field)"

requirements-completed: [SPL-08]

coverage:
  - id: D1
    description: "Tracer: a synthetic function with an off32 data fixup and a call rel32 becomes two _TEXT sections, R_386_32 against _D_00020100 (field 0) and R_386_PC32 against func_00010010_ (field -4), every other byte equal to load_flat(relocate=False)"
    requirement: SPL-08
    verification:
      - kind: unit
        ref: "tests/test_target.py#test_function_with_data_fixup_and_call"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every Pattern 5 rule: in-function targets, function pointers, symbols.csv and runtime names, rel32 jumps leaving the function, rel8 and intra-function jumps, page straddler (one relocation, rewritten across the page), inline data, data-in-code rows"
    requirement: SPL-08
    verification:
      - kind: unit
        ref: "tests/test_target.py (test_target_inside_a_function, test_obj1_target_at_a_start, test_symbols_csv_name, test_runtime_target, test_jumps, test_straddler, test_inline_data, test_data_in_code_row)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Ruling F11: sel16, ptr16:32 and rel32 LE fixup fields stay raw with no relocation and are listed in TargetResult.raw_fields"
    requirement: SPL-08
    verification:
      - kind: unit
        ref: "tests/test_target.py#test_non_off32_field_stays_raw, #test_rel32_field_with_an_le_fixup_gets_no_pc32"
        status: pass
    human_judgment: false
  - id: D4
    description: "Refusals naming the VA: call to no row, row outside the code object, off32 target in no row, field split by a row boundary"
    requirement: SPL-08
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_target.py -k \"straddler or inline or jumps or refus or data_in_code\" (9 selected, 9 passed)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Target objects only under build/ and no target bytes in tests (synthetic LEs only)"
    verification: []
    human_judgment: true
    rationale: "The prohibition has verification: judgment in the plan. target.py writes no file at all (it returns bytes; the verb that writes to build/ is 05-17), and the tests use made-up bytes; a reviewer confirms"

duration: 10min
completed: 2026-10-24
status: complete
---

# Phase 5 Plan 08: target ELF writer Summary

**`target.build_target` cuts one ELF32 object per unit straight from the LE with no assembler (D-13). Each row gets its own `_TEXT` section from `load_flat(relocate=False)`. LE off32 fixups become R_386_32 against the row at or around the target, or against `_D_<addr>` / a symbols.csv name. Calls and rel32 jumps that leave the function become R_386_PC32 with the field rewritten to -4 plus the offset. Non-off32 fixups stay raw and are reported (ruling F11). Every name comes from `SymbolTable.linker_name`.**

Execution context nonce: 404087e15cf95fdb

## Performance

- **Duration:** about 10 min
- **Started:** 2026-10-24T00:52:34Z
- **Completed:** 2026-10-24T01:02:23Z
- **Tasks:** 2 (Task 1 tracer, Task 2 auto, both TDD)
- **Files modified:** 2 (both new)

## Accomplishments

- `build_target(le, rows, symbols, *, flat=None, fixups=None) -> TargetResult`. `flat` and `fixups` default to `le.load_flat(relocate=False)` and `le.fixups()`, so a caller cutting many units passes them once.
- **Relocations from LE fixups:** each off32 fixup whose field starts in the row becomes one R_386_32 and its field is rewritten to the REL addend:
  - target at a row start: that row's symbol, addend 0;
  - target inside a row: that row's symbol plus the offset;
  - target outside the code object: `linker_name(va, data=True)`.
  - A page-straddling field is one relocation, rewritten across the boundary (P3).
- **Synthesized PC32:** for every `call rel32` and every rel32 jump out of the function, field `-4 + offset`. Intra-function jumps and rel8 branches get none. `branch_fields` decodes through `x86.decode`. An LE fixup site at an instruction start is skipped by its field size and decoding resumes after it (P8). Data-in-code rows are never decoded.
- **Data-in-code rows:** each gets its own `_TEXT` section with a LOCAL STT_OBJECT, so jump-table entries resolve against the containing function plus the case-label offset.
- **Undefined symbols:** referenced names the unit does not define are written as undefined GLOBAL STT_NOTYPE symbols. `write_elf` invents none.
- **Refusals:** TargetError, naming the VA, for a row outside the code object, a reference into the code object in no row, and an LE fixup field split by a row boundary.

## Task Commits

1. **Task 1 (tracer): one function with a data fixup and a call:** RED `a964c65`, GREEN `b468c3f`
2. **Task 2: every target rule, F11, refusals:** RED `d14c7a2`, GREEN `8ad1173`

Tracer gate: interactive run, `human_verify_mode` end-of-phase, automated-only verify. I re-ran both verify commands after the GREEN commit (1 passed, ruff clean) and then started the expansion.

## TDD notes

- Task 1 RED failed at collection with `ModuleNotFoundError: reverseapoc.target`, the expected first RED for a new module. The plan is `type: execute` and `workflow.tdd_mode` is off, so the tdd-red-evidence classifier does not apply.
- Task 2 RED had 9 tests failing on their planned assertions:
  - in-function targets refused as "no row starts there";
  - the jmp rel32 out of the function missing;
  - inline data stopping decoding before the call after the table;
  - data-in-code, both F11 cases, the row-outside refusal, and both split-field cases.
- At RED, `test_refuses_a_call_to_no_row` and `test_refuses_an_off32_target_in_no_row` already passed, because Task 1's `_target_symbol` refuses a reference to no row start.
- I added two pins after GREEN and proved each one by mutation: removing the fixup-site guard and stopping at an undecodable byte each fail exactly one of them. Both mutations were reverted before the commit.

## Files Created/Modified

- `tools/reverseapoc/target.py`: `build_target`, `branch_fields`, `TargetError`, `RawField`, `TargetResult`, helpers `_covered`, `_fixup_relocs`, `_branch_relocs`, `_instructions`, `_rewrite`, `_undefined`, `_row_symbol`, `_cut_row`. Line 1 is the Theme Hospital derivation header.
- `tests/test_target.py`: 18 tests on synthetic LEs with made-up bytes. Sections are read by index through `tests/elfread.py` (F10).

## Decisions Made

See key-decisions in the frontmatter. The two that affect later plans:
- 05-17 gets a `TargetResult` and must write `.data`; it can print `.raw_fields`.
- The data-in-code symbol is `_D_<start>`, its linker name.

## Deviations from Plan

### Orchestrator rulings applied

**Orchestrator ruling F11: non-off32 LE fixups are not refused.** `build_target` writes the field's raw bytes, adds no relocation, and lists the site in `TargetResult.raw_fields` as `RawField(va, kind_name)`. This replaces the plan's "a sel16 or ptr16:32 LE fixup inside a function raises TargetError". It applies to every non-off32 kind, a rel32 LE fixup included. A field that is an LE fixup site is also never given a synthesized PC32. Tests:
- `test_non_off32_field_stays_raw[sel16]`
- `test_non_off32_field_stays_raw[ptr16:32]`
- `test_rel32_field_with_an_le_fixup_gets_no_pc32`

Commits `d14c7a2`, `8ad1173`.

**Orchestrator ruling F10 (consumer side):** the tests read the second and later `_TEXT` sections through `view.section(symbol.section_index)` and `view.relocs(section_index)` (`_section_of`, `_relocs` in tests/test_target.py). Commits `a964c65`, `d14c7a2`.

### Auto-fixed Issues

**1. [Rule 1 - Interface] `build_target` returns `TargetResult`, not `bytes`**
- **Found during:** Task 1
- **Issue:** ruling F11 needs the raw sites in the result, but the plan's signature returned bytes.
- **Fix:** `TargetResult(data: bytes, raw_fields: tuple[RawField, ...])`.
- **Files modified:** tools/reverseapoc/target.py
- **Committed in:** `b468c3f`

**2. [Rule 1 - Naming] Data-in-code symbol named by `linker_name` (`_D_<start>`)**
- **Found during:** Task 2
- **Issue:** the behavior line wrote `D_<start>`, while the plan's key_link and acceptance criterion require every name to come from SymbolTable, which gives `_D_<start>` for a data-in-code row.
- **Fix:** used `linker_name`, so the table's own R_386_32 resolves by that name.
- **Committed in:** `8ad1173`

**3. [Rule 2 - Missing critical] Refusal of an LE fixup field split by a row boundary**
- **Found during:** Task 2
- **Issue:** a field that starts in one row and ends in the next would either break `write_elf` (field outside its section) or be left half-relocated in the other unit, silently.
- **Fix:** TargetError naming the field VA, from either side.
- **Tests:** `test_refuses_a_field_split_by_a_row_boundary[a]`, `[b]`.
- **Committed in:** `8ad1173`

**4. [Rule 2 - Missing critical] Decoding resumes after an undecodable byte**
- **Found during:** Task 2
- **Issue:** `x86.decode` stops at an undecodable byte, so every branch after it would be silently missed.
- **Fix:** `_instructions` skips one byte and resumes.
- **Test:** `test_decoding_resumes_after_an_undecodable_byte`.
- **Committed in:** `8ad1173`

**5. [Rule 3 - Signature] `branch_fields(row, flat, fixup_sites)` without `le`**
- The plan's `le` parameter had no use, so it was dropped. `fixup_sites` is a `{field VA: size}` map, because skipping inline data needs the field size.
- **Committed in:** `b468c3f`

---

**Total deviations:** 2 orchestrator rulings applied (F11, F10 consumer side) and 5 auto-fixed (2 interface/naming, 2 missing critical, 1 signature).
**Impact on plan:** none on scope. The public names `build_target`, `branch_fields`, `TargetError` and the helper set are as planned, plus `RawField`/`TargetResult`.

## Issues Encountered

- The worktree sandbox refused compound shell commands containing `$(git ...)` or heredocs. The plan ledger base came from the dispatch prompt (532a745). File edits went through the Write/Edit tools.
- `ruff format --check .` reports 33 pre-existing files in the repo that would be reformatted. Formatting is not part of the done gate; I formatted only the new test file.

## Threat Flags

None. target.py writes no file and reads only the LE; no new trust boundary.

## Verification

- `uv run pytest -q tests/test_target.py`: 18 passed
- `uv run pytest -q tests/test_target.py -k "straddler or inline or jumps or refus or data_in_code"`: 9 selected, 9 passed (at least 5 required)
- `uv run pytest -q`: 1018 passed, 177 skipped. `uv run ruff check .`: All checks passed!
- `grep -n "relocate=True" tools/reverseapoc/target.py`: no output
- No f-string builds a `func_` or `_D_` name in target.py; `linker_name(` appears 3 times.

## User Setup Required

None.

## Next Phase Readiness

- 05-17 can wire the `target` verb. Write `build_target(...).data` to build/ and pass `flat`/`fixups` once per EXE.
- 05-11's F11 filter can use `TargetResult.raw_fields`, or `le.fixups()` directly, to exclude functions with non-off32 sites.
- Research A4 (pairing many same-named `_TEXT` sections in objdiff) is still verified for two functions only. 05-17's `check` will show any gap.

## Self-Check: PASSED

- FOUND: tools/reverseapoc/target.py, tests/test_target.py
- FOUND on this branch: a964c65, b468c3f, d14c7a2, 8ad1173 (`git rev-list --count 532a745..HEAD` = 4 before this SUMMARY commit)

---
*Phase: 05-split-and-first-matches*
*Completed: 2026-10-24*
