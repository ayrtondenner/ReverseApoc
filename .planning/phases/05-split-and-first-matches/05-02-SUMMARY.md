---
phase: 05-split-and-first-matches
plan: 02
subsystem: tooling
tags: [omf, elf, omf2elf, objdiff, watcom, spl-07]

requires:
  - phase: 05-split-and-first-matches
    provides: "05-01 spike 005: the ELF shape objdiff 3.8.2 accepts (`_TEXT` names, REL implicit addends, TH addend rule)"
  - phase: 04-compiler-identification
    provides: "omf.read_object (segments, publics, externs, fixups with THREAD state), compile_source under the `*` rule, splice._write_atomic"
provides:
  - "tools/reverseapoc/elf.py: ELF32 ET_REL EM_386 writer (ElfSection/ElfSymbol/ElfReloc/ElfObject, write_elf, ElfError, named field constants)"
  - "tools/reverseapoc/omf2elf.py: convert(Module) -> ElfObject, convert_file(src, dst) -> ConvertResult, Omf2ElfError"
  - "`reverseapoc omf2elf SRC -o OUT [--json]` verb for ninja (D-13 base side)"
  - "tests/elfread.py: test-only ELF32 reader, sections addressable by index or unique name (ruling F10)"
affects: [05-06, 05-08, 05-09, 05-14, 05-17]

actuals:
  tokens: 11700
  tasks: 3
  commits: 5
plan_head_before: 6463d471f6040396d790fc8b1d9243901a6200e3
plan_head_after: a6537e7c3c6a5a28209cfb84d26f4a7583d57d3e

tech-stack:
  added: []
  patterns:
    - "write_elf emits one LOCAL STT_SECTION symbol per data section itself; a relocation names a symbol by name or a section by index (ElfReloc.target_section)"
    - "omf2elf rewrites each fixup field to its REL addend (TH rule) before the section is frozen"

key-files:
  created:
    - tools/reverseapoc/elf.py
    - tools/reverseapoc/omf2elf.py
    - tests/elfread.py
    - tests/test_elf.py
    - tests/test_omf2elf.py
    - tests/test_omf2elf_real.py
  modified:
    - tools/reverseapoc/cli.py

key-decisions:
  - "ElfReloc targets a symbol by name OR a section's STT_SECTION symbol by index (target_section): section symbols have no unique name once two `_TEXT` sections exist"
  - "write_elf refuses a relocation naming an unknown symbol (no implicit extern); callers list undefined symbols explicitly"
  - "Section kinds by class: CODE -> PROGBITS exec, class ending BSS -> NOBITS, DEB* dropped, any other -> PROGBITS write"
  - "Every extern is emitted as an undefined GLOBAL, referenced or not; an extern named like a local public resolves to the defined symbol"

patterns-established:
  - "omf2elf refusals name the segment and offset (`segment _TEXT offset 0x2: ...`); convert_file prefixes the source path"

requirements-completed: [SPL-07]

coverage:
  - id: D1
    description: "ELF32 writer: header fields, section order null/data/.rel/.symtab/.strtab/.shstrtab, rel links, locals-first symtab, two same-named `_TEXT` sections, refusals"
    requirement: SPL-07
    verification:
      - kind: unit
        ref: "tests/test_elf.py (9 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "omf2elf core rules on synthetic Watcom-shaped modules: segment classes, debug drop, STT_FUNC/STT_OBJECT, public sizing, PC32/R_386_32 addends, THREAD fixups, refusals"
    requirement: SPL-07
    verification:
      - kind: unit
        ref: "tests/test_omf2elf.py (17 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "`reverseapoc omf2elf` verb: OK line or JSON, exit 1 with `reverseapoc omf2elf: error:` on a refused input"
    requirement: SPL-07
    verification:
      - kind: integration
        ref: "tests/test_omf2elf.py#test_cli_converts_a_synthetic_module, #test_cli_refuses_a_non_omf_input"
        status: pass
    human_judgment: false
  - id: D4
    description: "A real Watcom 10.6 compile of probe/cg_basic.c converts with every segment, public and fixup accounted for, through the API and the CLI"
    requirement: SPL-07
    verification:
      - kind: integration
        ref: "REVERSEAPOC_WATCOM_DIR=<main checkout>/third_party/watcom uv run pytest -q -rs tests/test_omf2elf_real.py (2 passed, 0 SKIPPED)"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-10-24
status: complete
---

# Phase 5 Plan 02: omf2elf core Summary

**A stdlib ELF32 REL writer (`elf.py`) and the Watcom OMF -> ELF converter (`omf2elf.py`) on top of `omf.read_object`, exposed as `reverseapoc omf2elf SRC -o OUT [--json]`. Code/data/BSS segments keep their SEGDEF names, debug classes are dropped, and every location-9 fixup becomes one REL relocation by the Theme Hospital addend rule. A real Watcom 10.6 object converts with every public and fixup accounted for.**

Execution context nonce: bc0cd06d8adb00ce

## Performance

- **Duration:** about 8 min
- **Started:** 2026-10-24T00:09:49Z
- **Completed:** 2026-10-24T00:18:18Z
- **Tasks:** 3
- **Files modified:** 7 (6 created, 1 modified)

## Accomplishments

- `elf.py`: frozen `ElfSection`/`ElfSymbol`/`ElfReloc`/`ElfObject` and `write_elf`, with the layout objdiff accepted in spike 005. Every ELF field and size is a named constant (`R_386_32 = 1`, `R_386_PC32 = 2`, `NULL_ENTRIES`, `EI_*`, `SHT_*`, `SHF_*`, `STB_*`, `STT_*`, struct sizes). `ElfError` covers a duplicate global, an unknown or ambiguous symbol, a field outside its section, and a relocation on NOBITS.
- `omf2elf.py` (Theme Hospital derivation header on line 1): `convert` handles CODE -> PROGBITS exec, `*BSS` -> NOBITS, other classes -> PROGBITS write, and drops `DEB*`. Publics become STT_FUNC or STT_OBJECT, sized to the next public or the segment end. Externs become undefined GLOBALs. Fixups become R_386_PC32 (field = stored + disp - 4) or R_386_32 (field = stored + disp), against an extern symbol or a section symbol. `convert_file` writes atomically and refuses its own input and non-OMF data.
- `reverseapoc omf2elf` verb. `Omf2ElfError` and `ElfError` exit 1 with the standard error line.
- `tests/elfread.py`: an independent reader for sections (with index), symbols (with section index) and relocations (with the implicit addend read from the field), addressable by section index or unique name.
- Real test: `probe/cg_basic.c` compiled by wcc386 10.6 (`-4r -s -fpi`, cc.log exit 0) gives an Easy OMF object with 5 SEGDEFs, 7 publics, 4 externs and 2 fixups. All of them are accounted for in the ELF, and the CLI's `--json` reports 2 relocations.

## Task Commits

1. **Task 1: Tracer, synthetic module through `reverseapoc omf2elf`**: `ddbe2c5` (test, RED), `2f764ed` (feat, GREEN)
2. **Task 2: Writer shape and full core rules**: `e116ec6` (test, RED), `9b67c47` (feat, GREEN)
3. **Task 3: Real Watcom 10.6 object**: `a6537e7` (test)

## TDD Gate Compliance

- Task 1 RED (`ddbe2c5`): both tracer tests failed on the planned behaviour, because argparse rejected `omf2elf` as an invalid choice (the verb did not exist). GREEN `2f764ed`: both pass.
- Task 2 RED (`e116ec6`): 4 tests failed on their planned assertions: data/BSS sections absent, a data public missing, a segment target refused as "not supported", and no refusal for iterated data. The writer tests in test_elf.py, plus the extern-addend, THREAD, location, group and convert_file tests, already passed at RED, because Task 1's action specified the writer's full shape and the extern/location handling. They pin existing behaviour. The first RED run also crashed in a Task 1 helper (deviation 3); I fixed that before recording RED, so the recorded failures are the planned assertions. GREEN `9b67c47`: all pass.
- Task 3 (`a6537e7`): a test-only task. As the plan expected ("the core is already built"), it passed on its first run. No feat commit was needed.

## Files Created/Modified

- `tools/reverseapoc/elf.py`: ELF32 relocatable writer and constants
- `tools/reverseapoc/omf2elf.py`: OMF Module -> ElfObject conversion, convert_file, ConvertResult
- `tools/reverseapoc/cli.py`: `omf2elf` verb, docstring verb list, `_ERRORS`
- `tests/elfread.py`: test-only ELF32 reader
- `tests/test_elf.py`: writer layout and refusals
- `tests/test_omf2elf.py`: tracer CLI tests and the core conversion rules
- `tests/test_omf2elf_real.py`: the real 10.6 compile -> convert test

## Decisions Made

- `ElfReloc` keeps the plan's `(section, offset, type, symbol name)` and adds an optional `target_section`. The converter needs a relocation against a section's STT_SECTION symbol (switch tables, string literals), and with several `_TEXT` sections a name cannot identify it. `write_elf` creates the section symbols itself, so callers never list them.
- `write_elf` does not invent undefined symbols: a relocation naming an unknown symbol is an `ElfError`. 05-08 must list its `_D_*`/`func_*_` externs as `ElfSymbol(name, None)`.
- Data sections (including CONST) carry SHF_WRITE, as the plan states. Alignment is fixed: 16 for code, 4 for data and BSS. `omf.Segment` does not keep the SEGDEF alignment.

## Deviations from Plan

### Orchestrator rulings applied

**Orchestrator ruling F9: tracer module without a filler byte.** The Task 1 tracer's SEGDEF32 `_TEXT` holds exactly the 6 code bytes `e8 00000000 c3`, and the test asserts `func_00010000_` is sized 6 by the next-public-or-segment-end rule. Filler trimming stays with 05-06. Test: `tests/test_omf2elf.py#test_cli_converts_a_synthetic_module`. Committed in `ddbe2c5`.

**Orchestrator ruling F10: index-based section access in tests/elfread.py.** `SectionView.index` is the section header number. `ElfView.section(key)` and `ElfView.relocs(key)` accept a section index or a name, and the name form raises `KeyError("2 sections named '_TEXT'; address it by index")` when the name is ambiguous. `SymbolView.section_index` and `RelocView.symbol_section_index` report the section index alongside the name. Test: `tests/test_elf.py#test_two_sections_with_one_name_stay_two_sections` writes two `_TEXT` sections, reads the second one's relocations and its symbol by index, and checks that the name form refuses. Committed in `ddbe2c5` (reader) and `e116ec6` (test).

### Auto-fixed Issues

**3. [Rule 1 - Bug] Crash sizing publics in a segment without publics**
- **Found during:** Task 2 (first RED run)
- **Issue:** the Task 1 sizing helper zipped the public offsets against `[*offsets[1:], length]` with `strict=True`. For a code segment with no publics that is `[]` against `[length]`, which raises `ValueError`.
- **Fix:** `strict=False`; the empty case yields no symbols.
- **Files modified:** tools/reverseapoc/omf2elf.py
- **Verification:** the Task 2 tests that build a `_TEXT` with no public now reach their assertions and pass.
- **Committed in:** `9b67c47`

**4. [Rule 2 - Missing critical] Refusals beyond the plan's list (threat T-05-04)**
- **Found during:** Task 2
- **Issue:** without them, an absolute public, initialised bytes in a BSS segment, or a fixup targeting a dropped debug segment would produce a wrong ELF silently or crash with KeyError. A relocation naming an unknown symbol is a related case in the writer.
- **Fix:** `Omf2ElfError` for the first three and `ElfError` for the unknown symbol, each with a test (`test_absolute_public_is_refused`, `test_initialised_bytes_in_bss_are_refused`, `test_fixup_to_a_dropped_debug_segment_is_refused`, `test_relocation_naming_an_unknown_symbol_is_refused`). `convert_file` also refuses non-OMF data up front (first record not THEADR) and prefixes `OMFError`/`Omf2ElfError` with the source path.
- **Files modified:** tools/reverseapoc/omf2elf.py, tools/reverseapoc/elf.py, tests/test_omf2elf.py, tests/test_elf.py
- **Committed in:** `2f764ed`, `e116ec6`, `9b67c47`

**5. [Rule 3 - Blocking] Task 3 verify command split for the worktree sandbox**
- **Found during:** Task 3
- **Issue:** the agent sandbox refused the verify one-liner as written ("names git in a form too complex"), because of the embedded `$(git rev-parse --path-format=absolute --git-common-dir)`.
- **Fix:** I resolved that expression in a separate call (`C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/.git/../third_party/watcom`) and ran the same steps with the normalized literal path, one per line: `REVERSEAPOC_WATCOM_DIR=... uv run pytest -q -rs tests/test_omf2elf_real.py > build/omf2elf-real.out 2>&1` (exit 0), then `cat` and `grep -c SKIPPED` (0). The semantics are unchanged: the main checkout's tree is read-only and nothing is copied into the worktree.
- **Files modified:** none

---

**Total deviations:** 2 orchestrator rulings applied (F9, F10) and 3 auto-fixed (1 bug, 1 missing critical, 1 blocking command form).
**Impact on plan:** the rulings and auto-fixes are correctness or tooling issues. The one API addition (`ElfReloc.target_section`) is noted under Decisions for 05-06 and 05-08.

## Issues Encountered

- `pathlib.Path.write_text` on Windows turned `cli.py` into CRLF during an edit. I normalized it back to LF before committing, and all touched files are LF.
- The real probe object exercises only self-relative extern fixups (2 calls). Its data segments are empty, so on a real object the segment-relative/R_386_32 path is covered by spike 005 (cmain386, 5 segment-relative fixups at 100.0 in objdiff), not by this plan's real test. The synthetic tests pin that path.

## Verification

- `uv run pytest -q tests/test_omf2elf.py` and `uv run ruff check .` passed (Task 1 and tracer gate).
- `uv run pytest -q tests/test_elf.py tests/test_omf2elf.py -k "addend or thread or nobits or location"`: 9 selected, 9 passed (at least 4 required).
- With REVERSEAPOC_WATCOM_DIR on the main checkout's tree, `uv run pytest -q -rs tests/test_elf.py tests/test_omf2elf.py tests/test_omf2elf_real.py` gave 28 passed and 0 skipped.
- `uv run pytest -q` gave 906 passed and 167 skipped (the real-file tests without the env var). `uv run ruff check .` gave "All checks passed!".
- `uv run reverseapoc omf2elf --help` exits 0 and lists `-o, --output OUTPUT`.
- `git status --porcelain` showed nothing under build/ and no `.obj` or `.o` files.

## User Setup Required

None. No external service configuration required.

## Next Phase Readiness

- 05-06 can add COMDAT (0xC2/0xC3), NBKPAT, LPUBDEF -> LOCAL, filler trimming and the remaining refusals on `convert`, using `STB_WEAK`/`STB_LOCAL` in `ElfSymbol`.
- 05-08 can write target objects with `write_elf`, listing externs as `ElfSymbol(name, None)`, and read the second `_TEXT` with `elfread` by index.
- No blockers.

## Self-Check: PASSED

- All 6 created files exist on disk, and cli.py is modified.
- Commits `ddbe2c5`, `2f764ed`, `e116ec6`, `9b67c47` and `a6537e7` are ancestors of HEAD (`git rev-list --count 6463d47..HEAD` = 5 before this SUMMARY commit).

---
*Phase: 05-split-and-first-matches*
*Completed: 2026-10-24*
