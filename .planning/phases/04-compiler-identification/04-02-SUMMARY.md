---
phase: 04-compiler-identification
plan: 02
subsystem: tooling
tags: [omf, watcom, lib, easy-omf, comdat, fixupp, python, stdlib]

requires:
  - phase: 03-watcom-media
    provides: installed Watcom 10.5, 10.6 and 11.0 trees under third_party/watcom/<version>/ (read-only)
provides:
  - "tools/reverseapoc/omf.py: stdlib OMF object and LIB reader (segments with zero-filled data, fixups with masks, publics, externs, COMDAT32, Easy OMF, BAKPAT, module metadata)"
  - "normalized_object_sha1 for comparing host and wibo compiles (D-03)"
  - "tests/conftest.py: WATCOM_DIR (REVERSEAPOC_WATCOM_DIR), requires_version, requires_runner"
  - "tests/omfimage.py: synthetic OMF record, module and LIB builders"
  - "real proof: every LIB386 library of 10.5, 10.6 and 11.0 parses or is reported non-OMF, with zero module failures"
affects: [04-05 libmatch, 04-07 runtime map, 04-08 probe, 04-09 cppscan, phase 5 omf2elf]

actuals:
  tokens: 17100
  tasks: 3
  commits: 8
plan_head_before: e24d37a624e84c4cc601e0eff8abc7681673f327
plan_head_after: 01a2100b293c6d6bc58d5cee9efdea3a58fe1de4

tech-stack:
  added: []
  patterns:
    - "Record handlers as small functions in a dispatch dict; error context (record name, file offset) added once in _ModuleReader.feed"
    - "Builders (_SegmentBuilder, _ComdatBuilder) share check_range/check_write so LEDATA, LIDATA, COMDAT and FIXUPP use one bounds path"
    - "Real-file tests call requires_version(v) first and read through REVERSEAPOC_WATCOM_DIR from a worktree"

key-files:
  created:
    - tools/reverseapoc/omf.py
    - tests/omfimage.py
    - tests/test_omf.py
    - tests/test_omf_real.py
  modified:
    - tests/conftest.py

key-decisions:
  - "Easy OMF widens the data offset of LIDATA 0xA2 but keeps 16-bit repeat counts: the only real Easy OMF LIDATA records (GRAPH.LIB) parse to the last byte only that way"
  - "COMDAT32 reads a public base only for explicit allocation (attributes low nibble 0), per TIS OMF 1.1"
  - "Fixups after LIDATA or an iterated COMDAT are decoded (threads stay in sync) but not attached; the target is marked unmaskable"
  - "Zero-filled segment and COMDAT buffers are capped at MAX_SEGMENT_LENGTH (16 MiB); a 32-bit SEGDEF with the B bit (4 GiB) raises"
  - "A module whose records cannot be framed ends the library walk with that failure recorded; a module that frames but fails to parse is recorded and the walk resumes at the next page"
  - "Written from the TIS OMF 1.1 spec; no KKND-Decomp or Open Watcom code, so no derivation header"

patterns-established:
  - "omfimage.py builders carry their own literals; tests never embed library bytes"
  - "Sweep failures are reported as library path, module index, file offset and parser message only"

requirements-completed: []  # CID-04 is shared with 04-05, 04-07 and 04-12; marked when the last of them finishes

coverage:
  - id: D1
    description: "read_library walks a LIB from the 0xF0 header through page-aligned modules to 0xF1, returning segments, publics and externs; failing modules are recorded, not dropped"
    requirement: CID-04
    verification:
      - kind: unit
        ref: "tests/test_omf.py#test_read_library_walks_page_aligned_modules, test_bad_module_is_recorded_not_dropped, test_library_end_record_stops_walk, test_truncated_record_raises"
        status: pass
      - kind: integration
        ref: "tests/test_omf_real.py#test_clib3r_module_counts (544/549/970)"
        status: pass
    human_judgment: false
  - id: D2
    description: "FIXUPP with THREAD state, location sizes, segment-relative offsets, target kinds and names; LIDATA expansion with depth and size caps; Easy OMF; BAKPAT; COMENT 0x9B/0x9F"
    requirement: CID-04
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_omf.py -k 'fixup or thread or location or lidata or easy_omf or bakpat or coment or grpdef'"
        status: pass
    human_judgment: false
  - id: D3
    description: "COMDAT32 blocks and normalized_object_sha1 (THEADR and COMENT 0xE9 excluded, stops at MODEND)"
    requirement: CID-04
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_omf.py -k 'comdat or normalized'"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every LIB386 library of 10.5, 10.6 and 11.0 parsed or reported non-OMF (41/51/68, all under NT/), zero module failures; 10.6 EMU387 Easy OMF module; 11.0 EMU387 page 512; 10.6 PLIB3R COMDAT code"
    requirement: CID-04
    verification:
      - kind: integration
        ref: "REVERSEAPOC_WATCOM_DIR=<main checkout>/third_party/watcom uv run pytest -q -rs tests/test_omf_real.py (9 passed, no SKIPPED)"
        status: pass
    human_judgment: false
  - id: D5
    description: "conftest WATCOM_DIR / requires_version / requires_runner skip helpers"
    verification:
      - kind: integration
        ref: "tests/test_omf_real.py (each test calls requires_version first); full suite 498 passed, 54 skipped without overrides"
        status: pass
    human_judgment: false

duration: 22min
completed: 2026-10-21
status: complete
---

# Phase 4 Plan 02: OMF/LIB Reader Summary

**A stdlib OMF object and LIB reader (`omf.py`) that gives each library module's segment bytes, fixup masks, publics, externs and COMDAT code, handles Easy OMF, LIDATA, BAKPAT and threads, and parses every LIB386 library of Watcom 10.5, 10.6 and 11.0 with zero module failures.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-10-21T15:20:34Z
- **Completed:** 2026-10-21T15:43:05Z
- **Tasks:** 3 (all TDD: RED commit, then GREEN commit)
- **Files modified:** 5 (4 created, 1 modified)

## Accomplishments

- `read_library` / `read_object` / `iter_records` / `is_omf_library` / `normalized_object_sha1` in `tools/reverseapoc/omf.py`, with frozen `Record`, `OMFFixup`, `Segment` (`is_code`, `mask`), `Public`, `Comdat` (`mask`), `Module`, `ModuleFailure`, `Library`.
- FIXUPP decoding with frame/target threads that persist across records, the P bit as bit 2 of the target method, location sizes from `LOC_SIZES`, and segment-relative offsets (data-record offset + 10-bit locat offset). Externals are numbered across EXTDEF, LEXTDEF, COMDEF/LCOMDEF and CEXTDEF.
- Bounded LIDATA expansion: size computed before anything is expanded, checked against the SEGDEF length, nesting capped at `LIDATA_MAX_DEPTH = 8` (T-04-07).
- `tests/conftest.py` gains `WATCOM_DIR`, `requires_version(version)` and `requires_runner()`, which later Phase 4 plans share.

## Real LIB386 sweep (counts and names only)

| Version | `.LIB` files | Parsed (OMF) | Non-OMF (all under `NT/`) | Modules | COMDATs | Easy OMF modules | Page sizes | Module failures |
|---|---:|---:|---:|---:|---:|---:|---|---|
| 10.5 | 135 | 94 | 41 | 61104 | 33604 | 12973 | 16 x78, 128 x16 | none |
| 10.6 | 179 | 128 | 51 | 62405 | 35440 | 13059 | 16 x88, 128 x40 | none |
| 11.0 | 187 | 119 | 68 | 99413 | 43248 | 13335 | 16 x69, 512 x50 | none |

- `DOS/GRAPH.LIB`: the research prototype failed one module here. The production reader first failed it too (10.6 module 77 at 0x18380: an Easy OMF LIDATA record). Its two LIDATA records fit to the last byte only as "32-bit data offset, 16-bit repeat counts". With that format rule the module parses: 10.6 GRAPH.LIB has 258 modules and 0 failures, and 10.5 has 0 failures as well. The test still tolerates failures in GRAPH.LIB, as planned.
- CLIB3R: 544 / 549 / 970 modules, no failures. 10.6 CLIB3R has 2434 fixups (locations 9 and 11) and no Easy OMF modules. Its memory models are `3sOc` (478 modules) and `3sOp` (1); 70 modules have no model comment. No library module carries a 0x9F default-library comment.
- 10.6 PLIB3R: 336 modules (303 parsed before COMDAT support, 33 failed on COMDAT-following FIXUPPs; all 336 parse now). 300 of them are Easy OMF with model `3fOp`.
- EMU387: in 10.5 and 10.6 only module `386inite` is Easy OMF; module `emu387` uses true 32-bit records. 11.0 has no Easy OMF module there, and its page size is 512.
- No segment in any library was marked unmaskable: the few LIDATA32 records are never followed by a FIXUPP.

## Task Commits

1. **Task 1: Tracer - read_library walks a LIB** - `c175aad` (test, RED), `1be538d` (feat, GREEN). Tracer gate: interactive, `end-of-phase`, automated-only verify; re-ran it (13 unit, 3 real, ruff clean) and continued.
2. **Task 2: FIXUPP threads, LIDATA, Easy OMF, BAKPAT, metadata** - `bdf593d` (test, RED), `f15b036` (feat, GREEN), then `82a1651` (test, RED) and `7c10476` (fix, GREEN) for the Easy OMF LIDATA rule.
3. **Task 3: COMDAT32, normalized hash, LIB386 sweep** - `c4b0eea` (test, RED), `01a2100` (feat, GREEN).

### RED evidence (semantic assessment)

- Task 1: collection failed with `ModuleNotFoundError: No module named 'reverseapoc.omf'` for both test files. The plan specified this ("fail on the missing module") because the whole module is new. It is not an assertion failure, so under the strict `INVALID_RED` classification it counts as a load failure. Recorded here, not hidden.
- Task 2: the first run failed at import (`LIDATA_MAX_DEPTH`). I switched the test to look it up as `omf.LIDATA_MAX_DEPTH` and re-ran. That run gave 32 failing new tests, each on the planned behavior (no fixups decoded, `DID NOT RAISE`, missing `Module.model`, wrong LIDATA bytes), while the 13 Task 1 tests passed.
- Easy OMF LIDATA: only `test_easy_omf_lidata_keeps_16bit_repeat_counts` failed ("body is truncated"); the other 7 LIDATA tests passed.
- Task 3: 8 new unit tests failed on missing COMDAT/hash behavior (a FIXUPP with no data record, `AttributeError: Comdat`/`normalized_object_sha1`). The real sweep x3 and PLIB tests failed on COMDAT-following FIXUPPs; the CLIB3R, EMU387 and page-512 tests passed (they pin facts about existing behavior).

## Files Created/Modified

- `tools/reverseapoc/omf.py` - the reader: named record and field constants, `_Cursor`, record handlers in a dispatch dict, LIB walk, normalized hash.
- `tests/omfimage.py` - synthetic builders: `record`, `index`, `name`, `theadr`, `lnames`, `segdef32`, `segdef16`, `segdef_easy`, `pubdef32`, `pubdef16`, `extdef`, `comdef`, `cextdef`, `ledata32`, `ledata16`, `lidata32`, `lidata16`, `lidata_blocks32`, `fixup`, `thread`, `fixupp32`, `fixupp16`, `coment`, `grpdef`, `bakpat32`, `comdat32`, `modend32`, `module`, `library`.
- `tests/test_omf.py` - 56 unit tests.
- `tests/test_omf_real.py` - 9 real-file tests (CLIB3R counts x3, sweep x3, EMU387 Easy OMF, 11.0 EMU387 page 512, PLIB3R COMDAT code).
- `tests/conftest.py` - `WATCOM_DIR`, `requires_version`, `requires_runner`, documented in the module docstring.

## Decisions Made

See `key-decisions` in the frontmatter. One decision needs a closer look in review: the Easy OMF LIDATA repeat width. It rests on one module's records, not on a spec text.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Easy OMF LIDATA (0xA2) read 32-bit repeat counts**
- **Found during:** Task 2 (real-data probe after GREEN)
- **Issue:** I had applied the Easy OMF rule ("16-bit-numbered records carry 32-bit fields") to the LIDATA repeat counts too. The only real Easy OMF LIDATA records (10.6 `DOS/GRAPH.LIB` module 77) fit neither the 16/16 nor the 32/32 interpretation. They fit to the last byte only as 32-bit offset with 16-bit repeat counts.
- **Fix:** repeat counts are 32-bit only in the odd (32-bit) record types; Easy OMF widens just the data offset. A test pins it.
- **Files modified:** tools/reverseapoc/omf.py, tests/omfimage.py (`lidata16`), tests/test_omf.py
- **Verification:** test RED then GREEN; GRAPH.LIB 10.5 and 10.6 now parse with 0 failures. This is a format rule, not a GRAPH.LIB special case.
- **Committed in:** `82a1651` (test), `7c10476` (fix)

**2. [Rule 1 - Wrong planned fact] "10.6 EMU387.LIB: every module easy_omf True"**
- **Found during:** Task 3 (pre-RED probe)
- **Issue:** 10.6 EMU387.LIB has two modules. Only `386inite` carries COMENT 0xAA; `emu387` uses true 32-bit records (0xA1/0xA3/0x9D) and has no 0xAA.
- **Fix:** `test_emu387_is_easy_omf` pins the measured fact: the Easy OMF modules are exactly `["386inite"]`, every module has a public, and there are no failures. The 11.0 page-512 check is its own test, `test_emu387_page_size_512_in_11_0`.
- **Files modified:** tests/test_omf_real.py
- **Committed in:** `c4b0eea`

**3. [Rule 2 - Missing critical] Records needed for correct extern numbering and C++ data**
- **Found during:** Task 2
- **Issue:** The plan says fixup target names come from the "EXTDEF/LEXTDEF/COMDEF order". COMDEF/LCOMDEF and CEXTDEF also take external numbers, so skipping them would misname every later extern.
- **Fix:** handlers for COMDEF/LCOMDEF (communal length encoding 0x81/0x84/0x88) and CEXTDEF; GRPDEF/PUBDEF group indexes are validated; `Module.nbkpat_records` counts NBKPAT records (the plan said "record count only"); `Comdat` gained `unmaskable` and `mask` to match `Segment`.
- **Files modified:** tools/reverseapoc/omf.py, tests
- **Committed in:** `f15b036`, `01a2100`

**4. [Rule 1 - Test bug] COMDAT continuation test**
- **Found during:** Task 3 GREEN
- **Issue:** my own test placed a 2-byte fixup at offset 4 of a 5-byte COMDAT. The reader correctly raised.
- **Fix:** moved the fixup to offset 3 and added `test_comdat32_fixup_past_block_raises` to pin the overrun error.
- **Committed in:** `01a2100`

**5. [Minor] `OMFFixup` dataclass defined in Task 1**
- `Segment.mask` and `Segment.fixups` are part of the Task 1 API, so the data type came in Task 1. Decoding came in Task 2, test-first.

---

**Total deviations:** 5 (2 wrong format facts corrected from real data, 1 missing-critical record set, 1 test bug, 1 ordering nit)
**Impact on plan:** No scope creep beyond records that change extern numbering. Every planned artifact and test exists. The sweep is stronger than planned: zero failures, GRAPH.LIB included.

## Issues Encountered

- The worktree sandbox refuses `$(git rev-parse ...)` inside a compound command. I ran the plan's real-file commands with the resolved value of that expression, `REVERSEAPOC_WATCOM_DIR="C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/.git/../third_party/watcom"`. That is the same path, read-only.
- Open observation, not acted on: in the Easy OMF `386inite` module (10.5/10.6) the SEGDEF P bit is clear, so `Segment.use32` is False. The same module in 11.0 (SEGDEF32) reports True. `use32` mirrors the P bit as the TIS spec defines it. Phase 5's omf2elf should decide whether an Easy OMF module implies USE32.
- `cli.main()` does not catch `OMFError` yet. PATTERNS suggested adding it, but `cli.py` is outside this plan's files; plan 04-05 adds the first CLI verb that reads OMF.

## User Setup Required

None. Real-file tests skip until `uv run reverseapoc install-watcom <version>` has run, or until REVERSEAPOC_WATCOM_DIR points at the installed trees.

## Next Phase Readiness

- 04-05 (libmatch) can use `Segment.data`, `Segment.mask`, `Segment.unmaskable`, `OMFFixup.segment_relative`/`target_kind`/`target_name`, `Module.publics` and `Module.comdats`.
- 04-08/04-09 can use `normalized_object_sha1` and `requires_runner()`.
- Verification: `uv run pytest -q` gives 498 passed, 54 skipped (the real-file tests skip without overrides in the worktree), and `uv run ruff check .` is clean. The real run of `tests/test_omf_real.py` gives 9 passed with no SKIPPED line.

---
*Phase: 04-compiler-identification*
*Completed: 2026-10-21*
