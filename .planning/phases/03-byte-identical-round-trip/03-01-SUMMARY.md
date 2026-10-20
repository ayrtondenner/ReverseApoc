---
phase: 03-byte-identical-round-trip
plan: 01
subsystem: tooling
tags: [le, splice, rebuild, region-map, cli, pytest, mutation-testing]

requires:
  - phase: 02-container-and-target-ingest
    provides: "le.py read-only LE parser, targets.py manifest/hash API, cli.py, synthetic LE fixture"
provides:
  - "tools/reverseapoc/splice.py: SpliceError, Region (va_at, describe), layout, check_tiling, region_at, assemble, Decomposition, decompose, reassemble, RebuildResult, RebuildReport, rebuild_target, rebuild, DEFAULT_OUT, REGION_* constants, REGION_LABELS"
  - "le.py read helpers: public check_loadable, pages_end, _HDR_NONRES_NAME_TABLE_*/_HDR_DEBUG_INFO_* constants and the four raw header attributes"
  - "`uv run reverseapoc rebuild` (--orig, --manifest, --out): one OK/MISMATCH/MISSING/REFUSED line per target, exit 0 only when all OK"
  - "conftest: build_le_image page_numbers=, trailer=, extra_header_fields=, objects=; SYNTHETIC_TRAILER; SyntheticLE trailer_offset/fixup_start/fixup_end; REVERSEAPOC_ORIG override of ORIG_DIR"
affects: [03-02, 03-03, 03-04, 03-05, phase-5-landing, phase-6-driver]

actuals:
  tokens: 10400
  tasks: 3
  commits: 5
plan_head_before: 0eb58d6fab08caa1f672ef7a6630d8712c292474
plan_head_after: 72f15b475a938a176df3a4f14c17e812928365f9

tech-stack:
  added: []
  patterns:
    - "Fresh-buffer reassembly: assemble(size, pieces) never sees the original file"
    - "Page-backed object images sized page_count * page_size, filled from each page's full size through LEPage.file_offset"
    - "Region map from the file's own LE header, zero-length regions omitted, half-open intervals, bisect lookup"
    - "Mutant runs (copy-only, vsize-sized, logical-offset) prove the D-16 tests can fail"

key-files:
  created:
    - tools/reverseapoc/splice.py
    - tests/test_splice.py
  modified:
    - tools/reverseapoc/le.py
    - tools/reverseapoc/cli.py
    - tests/conftest.py
    - tests/test_cli.py
    - tests/test_le.py

key-decisions:
  - "rebuild() validates --out against orig/ and every target name before touching any target, so a bad manifest entry or --out writes nothing; rebuild_target repeats both checks for direct callers"
  - "LE parse/reassembly errors inside rebuild_target are re-raised with the target name prefixed, keeping the original exception type (LEError / LEUnsupportedError / SpliceError)"
  - "Page regions are built per LEPage with its owning object found by next(..., None); a page owned by no object raises LEError"
  - "splice.py imports the four _HDR_* constants from le.py so the D-19 refusal names the header field without a bare offset"

patterns-established:
  - "Rebuild report mirrors targets.CheckReport: frozen result dataclass with status, ok and format(width); no summary line (D-08)"
  - "Real-file tests run from a worktree with REVERSEAPOC_ORIG pointing at the main checkout's orig/ (read only)"

requirements-completed: [RT-01, RT-03, RT-05]

coverage:
  - id: D1
    description: "`reverseapoc rebuild` rebuilds every manifest target from its regions into --out and reports OK only when the written file's SHA-1 equals the manifest"
    requirement: RT-03
    verification:
      - kind: integration
        ref: "tests/test_cli.py#test_rebuild_ok_line_and_exit_code"
        status: pass
      - kind: integration
        ref: "tests/test_cli.py#test_rebuild_mismatch_exits_1"
        status: pass
      - kind: other
        ref: "uv run reverseapoc rebuild --orig <main checkout>/orig (3 OK lines, exit 0) + cmp build/<NAME> orig/<NAME> silent for UFO2P, TACP, SMKP"
        status: pass
    human_judgment: false
  - id: D2
    description: "rebuild refuses --out inside orig/, non-bare target names, missing and manifest-mismatching inputs, writing nothing"
    requirement: RT-03
    verification:
      - kind: integration
        ref: "tests/test_cli.py#test_rebuild_refuses_out_inside_orig"
        status: pass
      - kind: integration
        ref: "tests/test_cli.py#test_rebuild_refuses_target_name_with_a_path"
        status: pass
      - kind: integration
        ref: "tests/test_cli.py#test_rebuild_missing_target_exits_1"
        status: pass
      - kind: integration
        ref: "tests/test_cli.py#test_rebuild_refuses_orig_that_fails_the_manifest"
        status: pass
    human_judgment: false
  - id: D3
    description: "Reassembly from regions and page-mapped object images into a fresh buffer; copy-only, vsize-sized and logical-offset rebuilds fail the tests"
    requirement: RT-01
    verification:
      - kind: unit
        ref: "tests/test_splice.py#test_reassemble_sources_pages_from_images"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_reassemble_places_pages_through_permuted_map"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_round_trip_keeps_page_tail_past_vsize"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_round_trip_variants"
        status: pass
    human_judgment: false
  - id: D4
    description: "layout() tiles every fixture variant and the three real files, refuses D-19 header tables, loader/fixup section mismatch and non-physical pages; region_at/describe label any offset"
    requirement: RT-05
    verification:
      - kind: unit
        ref: "tests/test_splice.py#test_layout_regions_tile_the_bound_fixture"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_region_at_labels"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_layout_refuses_unmapped_header_table"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_layout_refuses_loader_section_mismatch"
        status: pass
      - kind: integration
        ref: "REVERSEAPOC_ORIG=<main checkout>/orig uv run pytest -q -rs tests/test_le_real.py (12 passed, no SKIPPED)"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-10-20
status: complete
---

# Phase 3 Plan 01: Rebuild from the region map Summary

**`reverseapoc rebuild` decomposes each LE target into a header-derived byte-region map plus page-backed object images and reassembles it into a fresh buffer; UFO2P.EXE, TACP.EXE and SMKP.EXE all come back SHA-1 identical to the manifest, and three mutants prove a copied or mis-paged rebuild fails the tests.**

## Performance

- **Duration:** about 9 min
- **Started:** 2026-10-20T20:37:45Z
- **Completed:** 2026-10-20T20:47:01Z
- **Tasks:** 3 of 3
- **Files modified:** 7 (2 created, 5 modified)

## Accomplishments

- New `tools/reverseapoc/splice.py`: `layout()` tiles the file (extender, stub, LE header, loader tables, fixup section, padding, one region per physical page, trailer) from the file's own header; `decompose()` builds per-object images of `page_count * page_size` bytes through `LEPage.file_offset`; `reassemble()` feeds `assemble(size, pieces)`, which has no access to the original.
- `uv run reverseapoc rebuild` writes build/<NAME> for every `[[targets]]` entry and prints `OK  <NAME>  sha1 <sha1> == manifest`; on the main checkout's orig/ all three lines are OK and `cmp` is silent for all three files.
- The region map refuses non-zero non-resident name table / debug info header fields (D-19), a loader section that does not end at the fixup section, and non-physical pages; `region_at(...).describe(offset)` labels any offset (e.g. `page 1 of object 1, VA 0x00010010 (physical page 2)`).
- Test fixture gained `page_numbers=`, `trailer=`, `extra_header_fields=`, `objects=` and the `REVERSEAPOC_ORIG` override, so real-file tests run from a worktree without skipping.

## Task Commits

1. **Task 1 (tracer): `reverseapoc rebuild` reassembles each LE from its regions**
   - RED `41bf5f5` test(03-01): add failing tests for the rebuild tracer
   - GREEN `6b39282` feat(03-01): rebuild each LE target from its region map into build/
2. **Task 2: region map refuses what it cannot tile and labels every offset**
   - RED `7a7498b` test(03-01): add failing tests for region map edges and labels
   - GREEN `b7a325d` feat(03-01): region map refuses what it cannot tile and labels offsets
3. **Task 3: prove "rebuilt, not copied"**
   - `72f15b4` test(03-01): prove the rebuild is reassembled, not copied (pin tests; green on commit, then proven by mutants)

## TDD record

- **Task 1 RED:** `tests/test_splice.py` failed at collection with `ImportError: cannot import name 'splice' from 'reverseapoc'`; the 7 new CLI tests failed with `SystemExit: 2` (argparse: no `rebuild` verb) and `ModuleNotFoundError` for the mismatch test. Semantic assessment: this is the failure the plan names ("the module and the verb do not exist yet"); it is a load-level failure, not an assertion failure, because the feature had no module at all.
- **Task 2 RED:** both test modules failed at collection on `ImportError: cannot import name 'SYNTHETIC_TRAILER' from 'conftest'` (missing fixture options and functions, as the plan names). After the conftest step of GREEN, an intermediate run showed the assertion-level failure `test_header_table_fields - AttributeError: 'LE' object has no attribute ...`, which the le.py attributes then fixed.
- **Task 3:** the plan pins behaviour Tasks 1-2 already had, so the tests were green on commit; their RED evidence is the mutant table below.
- The `gsd_run check tdd-red-evidence` classifier was not run: pytest's default report is not one of its supported formats, and this plan is `type: execute` (task-level `tdd="true"`), not a `type: tdd` plan.

## Mutants (Task 3, D-16 item 3)

Each mutant was applied to `tools/reverseapoc/splice.py` alone, `uv run pytest -q tests/test_splice.py` was run, and the file was restored with `git checkout -- tools/reverseapoc/splice.py` (`git diff --exit-code` clean after each). No mutant was committed.

| Mutant | Change | Failing tests observed |
|---|---|---|
| (a) copy-only | `reassemble` returns `le.data` | `test_reassemble_sources_pages_from_images`, `test_reassemble_places_pages_through_permuted_map` (2 failed; the plain round trips pass, which is Pitfall 1 and why these two exist) |
| (b) vsize-sized images | `decompose` stops filling at `obj.vsize` (the `load_flat` loop) | `test_round_trip_reproduces_synthetic_le`, `test_rebuild_target_writes_ok_output`, `test_rebuild_is_idempotent`, `test_reassemble_places_pages_through_permuted_map`, `test_round_trip_keeps_page_tail_past_vsize`, `test_round_trip_variants[bound]`, `[unbound]`, `[trailer]`, `[permuted]` (9 failed; `[contiguous]` has no tail past vsize and passes, as expected) |
| (c1) logical offset in decompose | page read from `data_pages_offset + (logical - 1) * page_size` | `test_reassemble_places_pages_through_permuted_map`, `test_round_trip_variants[permuted]` |
| (c2) logical offset in reassemble | page piece placed at `data_pages_offset + (logical - 1) * page_size` | `test_reassemble_places_pages_through_permuted_map`, `test_round_trip_variants[permuted]` |

Only the synthetic fixtures catch (b) and (c): the real files have all-zero obj1 tails and an identity page map (spikes 001/002).

## Files Created/Modified

- `tools/reverseapoc/splice.py` (new) - region map, tiling check, region lookup and labels, fresh-buffer assembly, decompose/reassemble, rebuild orchestration and report lines
- `tools/reverseapoc/le.py` - public `check_loadable`, `pages_end`, named D-19 header constants and raw attributes (read helpers only)
- `tools/reverseapoc/cli.py` - `rebuild` verb with `--orig`, `--manifest`, `--out`
- `tests/conftest.py` - fixture options, `SYNTHETIC_TRAILER`, `SyntheticLE` offsets, `REVERSEAPOC_ORIG`
- `tests/test_splice.py` (new) - Task 1-3 synthetic tests
- `tests/test_cli.py` - rebuild CLI tests
- `tests/test_le.py` - `pages_end`, `check_loadable`, header-table attribute tests

## Decisions Made

- `rebuild()` checks the `--out`/orig relation and every target name before rebuilding any target, so "refuses before writing anything" holds even when the bad entry is not first.
- Errors from parsing or reassembling a target are re-raised with the target name in front and the same exception type, so the CLI line says which EXE failed.
- `splice.py` imports le.py's `_HDR_*` constants rather than repeating the offsets (no bare offsets, D-17).

## Deviations from Plan

None in scope or behaviour. Mechanical notes:
- The plan's real-file commands use `"$(git rev-parse --path-format=absolute --git-common-dir)/../orig"`. The worktree sandbox refused `git` inside a command substitution, so the commands ran with that expression's resolved value, `C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/.git/../orig` (same directory, still read only).
- The plan-head ledger file under `.git/worktrees/<id>/` could not be written from the sandbox; the base SHA was taken from the dispatch (`0eb58d6`) and the commit count measured with `git rev-list --count 0eb58d6..HEAD` = 5.

**Total deviations:** 0 auto-fixed. **Impact:** none.

## Verification

- `uv run pytest -q` (worktree, no override): 225 passed, 21 skipped.
- `REVERSEAPOC_ORIG=<main checkout>/orig uv run pytest -q -rs`: 237 passed, 9 skipped; the skips are `test_hygiene.py` container-only (3) and absent Watcom media (6), none for a missing orig/ file.
- `REVERSEAPOC_ORIG=... uv run pytest -q -rs tests/test_le_real.py`: 12 passed, no SKIPPED.
- `uv run ruff check .`: All checks passed.
- `uv run reverseapoc rebuild --orig <main checkout>/orig`: three OK lines (UFO2P.EXE, TACP.EXE, SMKP.EXE), exit 0; `cmp build/<NAME> orig/<NAME>` silent for all three.
- `git diff --exit-code -- tools/reverseapoc/splice.py` clean after the mutant runs.
- The container gate (`docker compose run --rm test`) was not run from this worktree, as instructed; it runs later on the main checkout.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plans 03-03 (linear-address splice API), 03-04 (`--exe`/`--json`, parse-le trailer, diff report) and 03-05 (real-file round-trip tests, docs) can build on `layout`, `region_at`/`describe`, `decompose`/`reassemble`, `rebuild_target` and the `objects=`/`page_numbers=`/`trailer=` fixture options.
- The MISMATCH line carries both SHA-1s; the first-differing-offset/region/count report (D-08) belongs to plan 03-04.

---
*Phase: 03-byte-identical-round-trip*
*Completed: 2026-10-20*
