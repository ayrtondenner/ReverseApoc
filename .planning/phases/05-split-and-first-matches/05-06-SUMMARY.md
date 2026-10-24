---
phase: 05-split-and-first-matches
plan: 06
subsystem: tooling
tags: [omf, elf, omf2elf, comdat, nbkpat, capstone, watcom, spl-07]

requires:
  - phase: 05-split-and-first-matches
    provides: "05-02 omf2elf core (convert, convert_file, Omf2ElfError, elf.py writer, tests/elfread.py)"
  - phase: 05-split-and-first-matches
    provides: "05-03 x86.py (decode with data_sites, is_filler, Insn.is_terminal)"
provides:
  - "omf.py: REC_COMDAT 0xC2 read by _comdat; NBKPAT/NBKPAT32 applied to the named COMDAT; Public.local; Comdat.attributes/selection/allocation/backpatched/iterated_at; Segment/Comdat.unmaskable_at"
  - "omf2elf.py: COMDAT sections with WEAK/GLOBAL symbols, LOCAL LPUBDEF, filler-trimmed code sizes (_code_end, _sized_publics), Easy OMF location 5 as offset32, _refuse_* checks before any section is built"
  - "tests/omfimage.py: comdat16, nbkpat, nbkpat32, lpubdef32, lextdef builders; fixup() takes a u16 frame-number datum"
  - "tests/elfread.py: a relocation against symbol 0 raises"
affects: [05-08, 05-09, 05-14, 05-17]

actuals:
  tokens: 14800
  tasks: 3
  commits: 6
plan_head_before: 532a74582239727dd92c0ee200d1d3e8d81b87cf
plan_head_after: 2d49bbdc46f7d30b4a58d215ed1ddea39e128f98

tech-stack:
  added: []
  patterns:
    - "omf2elf works on _Part views (a segment or a COMDAT); a refusal pass over all parts runs before _sections/_symbols build anything"
    - "Code symbol sizes come from x86.decode over the span, stopping at fixup sites; filler is trimmed only after a terminal instruction"

key-files:
  created: []
  modified:
    - tools/reverseapoc/omf.py
    - tools/reverseapoc/omf2elf.py
    - tests/omfimage.py
    - tests/test_omf.py
    - tests/test_omf2elf.py
    - tests/elfread.py
    - tests/test_elf.py

key-decisions:
  - "A COMDAT's symbol is WEAK for selection pick any / same size / exact match and GLOBAL for no match; a COMDAT without a segment is code when allocated as far code (1) or code32 (3)"
  - "NBKPAT bytes join Comdat.mask through Comdat.backpatched, like BAKPAT bytes join Segment.mask"
  - "An addend that leaves int32 is refused, not wrapped mod 2^32 (05-02 review minor); Watcom 10.6 always writes displacement 0"
  - "A public in a dropped debug segment is refused rather than silently omitted"
  - "Filler trimming keeps the whole span unless it decodes to its last byte, ends in filler, and the last non-filler instruction is terminal"

patterns-established:
  - "omf2elf refusal messages: `<segment NAME|COMDAT 'name'> offset 0xN: <RECORD> ...` or `<PUBDEF|LPUBDEF> public 'name' offset 0xN ...`"

requirements-completed: [SPL-07]

coverage:
  - id: D1
    description: "omf.py reads 0xC2 COMDATs like COMDAT32, applies NBKPAT/NBKPAT32 into the named COMDAT (bounds-checked, unknown name refused, record still counted), marks LPUBDEF publics local"
    requirement: SPL-07
    verification:
      - kind: unit
        ref: "tests/test_omf.py#test_comdat16_reads_like_comdat32, #test_nbkpat_patches_the_comdat, #test_nbkpat_naming_an_unknown_comdat_raises, #test_nbkpat_past_the_comdat_raises, #test_lpubdef_is_local"
        status: pass
      - kind: integration
        ref: "REVERSEAPOC_WATCOM_DIR=<main checkout>/third_party/watcom uv run pytest -q -rs tests/test_omf_real.py (9 passed, 0 SKIPPED)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every SPL-07 record kind converts: COMDAT (both widths, WEAK/GLOBAL), LIDATA, BAKPAT, NBKPAT, CEXTDEF, THREAD fixups, LPUBDEF as LOCAL, in one Easy OMF kitchen-sink module read back section by section"
    requirement: SPL-07
    verification:
      - kind: unit
        ref: "tests/test_omf2elf.py#test_comdat16_converts_to_a_weak_section, #test_lidata_converts, #test_bakpat_bytes_are_kept, #test_cextdef_extern, #test_lpubdef_is_local_in_elf, #test_kitchen_sink_module"
        status: pass
    human_judgment: false
  - id: D3
    description: "Code publics sized to the next public with trailing Watcom filler trimmed after a terminal instruction, decoded with x86.py; fall-through, non-filler tails, filler-only spans, data publics and inline jump tables keep the full span"
    requirement: SPL-07
    verification:
      - kind: unit
        ref: "tests/test_omf2elf.py#test_filler_trimmed (5 cases), #test_filler_not_trimmed_in_data, #test_filler_after_a_jump_table_keeps_the_span"
        status: pass
    human_judgment: false
  - id: D4
    description: "Unsupported OMF is refused with a named Omf2ElfError before any output; the CLI exits 1 with `reverseapoc omf2elf: error:` and writes no file; location 5 converts as offset32 only under Easy OMF"
    requirement: SPL-07
    verification:
      - kind: unit
        ref: "tests/test_omf2elf.py#test_refusal_names_the_record_and_writes_nothing (16 cases), #test_location_5_under_easy_omf_converts_as_offset32, #test_refusal_comes_before_any_output_when_a_good_segment_comes_first"
        status: pass
    human_judgment: false
  - id: D5
    description: "The 05-02 real Watcom 10.6 conversion and the libmatch real sweep still pass after the omf.py changes"
    requirement: SPL-07
    verification:
      - kind: integration
        ref: "REVERSEAPOC_WATCOM_DIR=... REVERSEAPOC_ORIG=<main checkout>/orig uv run pytest -q -rs tests/test_omf_real.py tests/test_omf2elf_real.py tests/test_libmatch_real.py (21 passed)"
        status: pass
    human_judgment: false

duration: 18min
completed: 2026-10-24
status: complete
---

# Phase 5 Plan 06: omf2elf complete for SPL-07 Summary

**omf.py now reads 16-bit COMDATs (0xC2) through the COMDAT32 handler, applies NBKPAT patches to the named COMDAT's bytes, and marks LPUBDEF publics local. omf2elf turns each COMDAT into its own section with a WEAK or GLOBAL symbol, emits LPUBDEF publics as LOCAL, and sizes code publics with Theme Hospital's filler trimming (decoded with x86.py). Everything Phase 5 does not convert is refused with a named error before any section is built: iterated COMDAT data, fixups into LIDATA, frame-number and group targets, pointer/selector locations, and location 5 outside Easy OMF.**

Execution context nonce: 806793b9c9dab08d

## Performance

- **Duration:** about 18 min
- **Started:** 2026-10-24T00:51:28Z
- **Completed:** 2026-10-24T01:09:03Z
- **Tasks:** 3
- **Files modified:** 7 (0 created)

## Accomplishments

- `omf.py`: `REC_COMDAT = 0xC2` is registered on `_comdat`, and the field width comes from `m.wide` (odd record or Easy OMF). `_nbkpat` parses the location type, the LNAMES index of the COMDAT and the offset/value pairs. Each value is added into the COMDAT through the same `_add_patches` helper that BAKPAT uses (`check_range` before every write, `OMFError` for an unknown name), and `nbkpat_records += 1` stays. `Public.local` is set for LPUBDEF/LPUBDEF32. `Comdat` keeps its `attributes` (properties `selection` and `allocation`) and its NBKPAT `backpatched` offsets, which are part of `mask`.
- `omf2elf.py`: works on `_Part` views (segments in SEGDEF order, then COMDATs, debug classes dropped). Each COMDAT becomes a section named after its segment, or after the COMDAT when it has none. Its symbol is WEAK unless the selection is "no match". Code publics and code COMDATs get `_code_end` sizes. LPUBDEF publics are STB_LOCAL.
- `_refuse(module, parts)` runs `_refuse_publics`, `_refuse_unmaskable`, `_refuse_iterated_comdats` and `_refuse_fixups` (location, target, field range, int32 addend) before `_sections`/`_symbols`. Every message names the record kind, the segment or COMDAT, and the offset.
- One Easy OMF kitchen-sink module holds THEADR, COMENT 0xAA, LNAMES, SEGDEF32, GRPDEF FLAT, PUBDEF32, LPUBDEF32, EXTDEF, LEXTDEF, CEXTDEF, COMDAT32, COMDAT 0xC2, LEDATA32, LIDATA32, FIXUPP32 with THREADs, BAKPAT32, NBKPAT and MODEND. It converts, and read_elf finds the 4 expected sections, 7 symbols and 4 relocations.

## Task Commits

1. **Task 1 (tracer): 0xC2 COMDAT + NBKPAT -> WEAK section**: `39284b5` (test, RED), `a8c0a3e` (feat, GREEN). Tracer gate: interactive run, `end-of-phase`, automated-only verify. I re-ran it: test_omf + test_omf2elf 90 passed, LIB386 sweep 9 passed with 0 SKIPPED lines, full suite 1006 passed / 177 skipped. Then I expanded to the other tasks.
2. **Task 2: remaining record kinds, LOCAL, filler-trimmed sizes**: `2ce1461` (test, RED), `5a54037` (feat, GREEN)
3. **Task 3: refusals**: `c1bab34` (test, RED), `2d49bbd` (feat, GREEN)

**Plan metadata:** this SUMMARY commit (docs).

## TDD notes (RED evidence, semantic assessment)

- Task 1 RED (`39284b5`): 6 failed on the planned behaviour. 0xC2 was skipped as an unknown record, so the following FIXUPP had no data record. NBKPAT left the bytes unpatched. The unknown-name and past-end NBKPAT cases did not raise. `Public` had no `local`. The ELF had no COMDAT symbol.
- Task 2 RED (`2ce1461`): 4 failed on their assertions. LPUBDEF was bound GLOBAL, the two trimming cases kept the filler, and the kitchen sink had the wrong sizes and binding. Its sections, bytes and relocations were already correct. LIDATA, BAKPAT, CEXTDEF, the non-trimming cases and the jump-table stop passed at RED by design: omf.py already provides those, and the tests pin it.
- Task 2 GREEN needed one correction to a RED test: `test_lpubdef_is_local_in_elf` compared list positions with `symtab_info`, but elfread leaves out the null symbol, so the positions were off by one. The fixed assertion still fails on the RED code, where LPUBDEF was GLOBAL.
- Task 3 RED (`c1bab34`): 19 failed. 3 did not raise (public past the end, public in a debug segment, iterated COMDAT). 10 raised with the wrong message. The overflow case raised `struct.error`. Easy OMF location 5 was refused. The new omf.py fields did not exist. elfread wrapped symbol 0 to the last symbol.

## Files Created/Modified

- `tools/reverseapoc/omf.py`: 0xC2 COMDAT, applied NBKPAT, `Public.local`, COMDAT attributes/backpatched/iterated_at, `unmaskable_at`, docstring
- `tools/reverseapoc/omf2elf.py`: `_Part`, COMDAT sections, LOCAL, `_code_end`/`_sized_publics`, `_refuse_*`, Easy OMF location 5, docstring
- `tests/omfimage.py`: `comdat16`, `nbkpat`, `nbkpat32`, `lpubdef32`, `lextdef`, shared `_comdat_body`/`_pubdef32_body`, u16 frame-number datum in `fixup`
- `tests/test_omf.py`: 7 new tests, plus 2 extended assertions on `unmaskable_at`/`iterated_at`
- `tests/test_omf2elf.py`: COMDAT, record-kind, filler, kitchen-sink and 18 refusal tests
- `tests/elfread.py`: symbol-0 guard
- `tests/test_elf.py`: test for that guard

## Decisions Made

See key-decisions in the frontmatter. The one that matters downstream: COMDAT sections can share the name `_TEXT` with a SEGDEF section, so consumers must address them by index (05-02 F10 API).

## Deviations from Plan

### Orchestrator notes applied (rulings.md "For 05-06", 05-02 review minors)

No ruling amends 05-06. I applied each of the four review minors and tested it:
- **`_relocation` struct.error**: a 32-bit field past the data and an addend outside int32 now raise `Omf2ElfError` naming the segment or COMDAT and the offset (`_refuse_field`). Tests: `REFUSALS["location-5-field-past-the-data"]`, `REFUSALS["addend-overflows-int32"]`. In `2d49bbd`.
- **public offset past the segment end**: refused (`REFUSALS["public-past-the-segment-end"]`). A public at exactly the end (size 0) is allowed. In `2d49bbd`.
- **publics in dropped debug segments**: refused rather than omitted (`REFUSALS["public-in-a-debug-segment"]`). In `2d49bbd`.
- **tests/elfread.py symbol-0 wrap**: my tests read every converted object through elfread, so I fixed it as the dispatch allowed. `_entries` raises `ValueError` for symbol index 0 or past the table (`tests/test_elf.py#test_reader_refuses_a_relocation_against_symbol_0`). tests/elfread.py and tests/test_elf.py are outside the plan's files_modified. In `c1bab34`, `2d49bbd`.

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Refusal messages need an offset that omf.py did not keep**
- **Found during:** Task 3
- **Issue:** `Segment.unmaskable`/`Comdat.unmaskable` are booleans, and an iterated COMDAT left no flag at all. The plan requires the refusal to name the offset.
- **Fix:** I added `unmaskable_at` (data offset of the first LIDATA a FIXUPP addressed) to Segment and Comdat, and `iterated_at` to Comdat, all defaulting to None. The `unmaskable` refusal runs before the iterated-COMDAT one, so both can be reached from real bytes.
- **Files modified:** tools/reverseapoc/omf.py, tests/test_omf.py
- **Committed in:** `c1bab34`, `2d49bbd`

**2. [Rule 2 - Missing critical] NBKPAT bytes in the COMDAT mask**
- **Found during:** Task 1
- **Issue:** after linking, the bytes NBKPAT patches differ, just as BAKPAT bytes do (which `Segment.mask` already covers). `Comdat.mask` covered only fixups.
- **Fix:** `Comdat.backpatched`, now part of `mask`. `test_nbkpat_patches_the_comdat` asserts the mask. The libmatch real sweep still passes.
- **Committed in:** `a8c0a3e`

**3. [Rule 3 - Blocking] Test builders the plan's module needed**
- `lextdef` (the kitchen sink lists LEXTDEF), `nbkpat32` (the plan names "its 32-bit sibling"), an `offset32` option on `comdat16`/`nbkpat` (Easy OMF widens both), and a u16 datum for a frame-number target in `fixup()`, which the frame-target refusal needs. Committed in `39284b5`, `2ce1461`, `c1bab34`.

**4. [Rule 3 - Blocking] Verify commands split for the worktree sandbox**
- The sandbox refused the `$(git rev-parse ...)` form, as it did in 05-02. I ran the same steps with the resolved main-checkout path `C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/third_party/watcom`: `tests/test_omf_real.py` exit 0, 9 passed, 0 SKIPPED lines. I copied nothing into the worktree.

---

**Total deviations:** the 4 review minors applied, and 4 auto-fixed (2 missing critical, 2 blocking).
**Impact on plan:** each change serves correctness or the plan's named-error rule. omf.py gained only defaulted fields, so every existing constructor and test still holds.

## Issues Encountered

- The worktree sandbox refused heredoc and `cd`-prefixed shell commands. I made edits with the Edit tool and with small patch scripts in the session scratchpad. All touched files are LF.
- The plan-head ledger file would live in the shared git dir, outside the worktree, so I did not write it. The base `532a745` comes from the dispatch prompt, and `git rev-list --count 532a745..HEAD` = 6 before this SUMMARY commit.

## Verification

- `uv run pytest -q tests/test_omf.py tests/test_omf2elf.py`: green (Task 1).
- `uv run pytest -q tests/test_omf2elf.py -k "lidata or bakpat or cextdef or local or filler or kitchen"`: 12 selected, 12 passed (at least 6 required).
- `uv run pytest -q tests/test_omf2elf.py -k "refus or location or easy"`: 26 selected, 26 passed.
- `uv run pytest -q`: 1038 passed, 177 skipped. `uv run ruff check .`: All checks passed.
- With the owner's tree: `tests/test_omf_real.py tests/test_omf2elf_real.py tests/test_libmatch_real.py`: 21 passed.
- `grep -n "nbkpat_records += 1" tools/reverseapoc/omf.py` prints line 846, inside `_nbkpat`, which now also calls `_add_patches` on the COMDAT.

## User Setup Required

None. No external service configuration required.

## Next Phase Readiness

- 05-08/05-09 can convert our compiled objects with COMDATs, LOCAL statics and trimmed sizes. A refused object stops with a message that names the construct.
- No blockers.

## Self-Check: PASSED

- All 7 modified files exist and are in the commits above.
- `39284b5`, `a8c0a3e`, `2ce1461`, `5a54037`, `c1bab34` and `2d49bbd` are ancestors of HEAD.
