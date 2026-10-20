---
phase: 03-byte-identical-round-trip
plan: 03
subsystem: tooling
tags: [le, splice, fixups, masking, rebuild, pytest, mutation-testing]

requires:
  - phase: 03-byte-identical-round-trip
    provides: "plan 03-01: splice.py region map, decompose/reassemble, rebuild_target, synthetic fixture options"
provides:
  - "splice(le, {va: bytes}) -> SpliceResult(data, regions, masked): linear-address patches written into page-backed object images and reassembled into a fresh buffer"
  - "Refusals (SpliceError naming patch VA, length, first unwritable address and reason): BSS of object M, past the end of object M, not in any object, crosses from object A into object B, overlap (also identical bytes), empty patch, non-bytes value, bad key"
  - "MaskedField(fixup, patch_va, start, end, backed_end, straddles_page) with clipped/partial; MAX_FIELD = max(SRC_SIZE.values())"
  - "rebuild_target(..., patches=None); RebuildResult.first_diff, first_diff_region, first_diff_va, diff_bytes, masked_fields; D-08 MISMATCH line"
affects: [03-04, 03-05, phase-5-landing, phase-6-driver]

actuals:
  tokens: 8200
  tasks: 3
  commits: 7
plan_head_before: 2c4e815430f1d6f638d15ac3a830cc9a82c0be04
plan_head_after: 17ced9f867c641e6abfe6b2b2c9177e6d21327c3

tech-stack:
  added: []
  patterns:
    - "Writable spans: one span per page of an object, page data clipped to vsize, bisect lookup, runs never leave the first byte's object"
    - "Masking by never writing: covered fixup ranges are subtracted from each run, per patch in VA space"
    - "Every refusal test also splices the same fixture with {} and checks the SHA-1 round trip (_assert_control)"

key-files:
  created: []
  modified:
    - tools/reverseapoc/splice.py
    - tests/test_splice.py

key-decisions:
  - "Patches are validated, copied and overlap-checked before decompose() touches anything; le.fixups() is only parsed when there is at least one patch, so splice(le, {}) stays the plain round trip"
  - "A masked field's backed_end is clipped to the page-backed end of the patch's object, so a field cut by the short last page is reported clipped and never extended into BSS"
  - "Masked bytes are never written (runs minus masked ranges) instead of being restored afterwards"
  - "OK and MISMATCH lines append '; masked N fixup fields' only when N > 0"

patterns-established:
  - "Negative tests carry an unpatched control so a gate that always fails cannot pass them"
  - "Pin tests for behaviour that already exists are proven by uncommitted mutants, each restored with git checkout -- <file>"

requirements-completed: [RT-02, RT-04]

coverage:
  - id: D1
    description: "splice() writes linear-address patches at their page-mapped file offsets (mid-page, page edges, across a boundary, permuted map, short last page, whole object), keeps file length and non-page regions, and never mutates its inputs"
    requirement: RT-02
    verification:
      - kind: unit
        ref: "tests/test_splice.py#test_splice_patch_lands_at_mapped_offset"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_mutation_page_edges"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_mutation_spanning_permuted_map"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_whole_object_patch"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_splice_output_is_reassembled"
        status: pass
    human_judgment: false
  - id: D2
    description: "splice() refuses writes outside page data clipped to vsize, cross-object runs, overlaps (also identical bytes), empty and badly typed patches, naming VA, length, address and reason, never the value"
    requirement: RT-02
    verification:
      - kind: unit
        ref: "tests/test_splice.py#test_refuse_bss_past_short_page"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_refuse_past_vsize_tail"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_refuse_cross_object"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_refuse_overlap"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_refuse_non_bytes_patch"
        status: pass
    human_judgment: false
  - id: D3
    description: "Fixup fields covered by a patch keep their original bytes (straddling off32, permuted straddler, ptr16:32, sel16, rel32, partial, BSS-cut) and are reported by address only"
    requirement: RT-02
    verification:
      - kind: unit
        ref: "tests/test_splice.py#test_mask_straddling_off32"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_mask_bss_cut_field_clipped"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_mask_report_has_no_bytes"
        status: pass
    human_judgment: false
  - id: D4
    description: "rebuild_target(..., patches=) reports a mismatch with first differing offset, region label, VA, differing-byte count and masked-field count; the unpatched rebuild of the three real files still prints three OK lines"
    requirement: RT-04
    verification:
      - kind: unit
        ref: "tests/test_splice.py#test_rebuild_target_reports_mutation"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_mutation_report_names_offset_without_bytes"
        status: pass
      - kind: unit
        ref: "tests/test_splice.py#test_mask_count_in_rebuild_result"
        status: pass
      - kind: other
        ref: "uv run reverseapoc rebuild --orig <main checkout>/orig (3 OK lines, exit 0)"
        status: pass
    human_judgment: false

duration: 14min
completed: 2026-10-20
status: complete
---

# Phase 3 Plan 03: Linear-address splice with refusals and fixup masking Summary

**`splice(le, {va: bytes})` writes patches through writable page spans into the object images, refuses BSS, page tails past vsize, unmapped and cross-object writes, overlaps and malformed patches, keeps every covered fixup field (straddling and page-cut ones included) at its link-time bytes, and the rebuild report now names the first differing offset, region, VA, byte count and masked-field count.**

## Performance

- **Duration:** about 14 min of execution (2026-10-20T20:57Z to 21:11Z), plus a resume after a power loss
- **Tasks:** 3 of 3, plus one pin-test commit
- **Files modified:** 2

## Accomplishments

- `splice()` and `SpliceResult` in `tools/reverseapoc/splice.py`: patches validated and copied first, `_writable_spans` (page data clipped to vsize, D-18), `_runs` by bisect that refuses with the exact reason, writes into the `decompose()` images, output from `reassemble()` (fresh buffer, D-16).
- Fixup masking (D-02): `le.fixups()` read once, bisect back by `MAX_FIELD - 1`, masked ranges clipped to page data and simply not written, so both halves of a straddling field keep their bytes even through a permuted page map. `MaskedField` carries addresses only.
- `rebuild_target(..., patches=None)` runs every rebuild through `splice()`; mismatches carry `first_diff`, `first_diff_region`, `first_diff_va`, `diff_bytes` and the line `...; first difference at 0x.. (page 1 of object 1, VA 0x00010800), 1 bytes differ`; `masked_fields` is appended when non-zero.
- 41 new synthetic tests in `tests/test_splice.py` (77 in the file).

## Task Commits

1. **Task 1 (tracer): one linear-address patch lands and the report names it**
   - RED `5492154` test(03-03): add failing tests for the linear-address splice tracer
   - GREEN `9ee09ee` feat(03-03): splice linear-address patches and name the first difference
2. **Task 2: refusals and D-13 edges**
   - RED `01c6205` test(03-03): add failing tests for splice refusals and D-13 page edges
   - GREEN `567670a` feat(03-03): refuse unwritable, overlapping and malformed splice patches
3. **Task 3: fixup masking (D-02)**
   - RED `d0fa7e0` test(03-03): add failing tests for fixup-field masking
   - GREEN `ed1877a` feat(03-03): mask fixup fields in flat address space and report them
4. **Pins:** `17ced9f` test(03-03): pin touching patches and the reassembled splice output

## TDD record

- **Task 1 RED:** the 4 tracer tests failed with `AttributeError: module 'reverseapoc.splice' has no attribute 'splice'` and `TypeError: rebuild_target() got an unexpected keyword argument 'patches'`. That is the planned missing API, not a fixture or import fault; the other 34 tests stayed green. The tracer gate (interactive, end-of-phase, automated-only verify) was re-run after GREEN: tests, ruff and the real rebuild (three OK lines) all passed before Task 2.
- **Task 2 RED:** 13 failures, all on the planned behaviour: wrong reason text (assertion failures for BSS, past-vsize, unmapped, negative and bool keys), `DID NOT RAISE` for cross-object, both overlap variants and the empty patch, and a raw `TypeError` for a `str` value or `str` key. Page-edge, permuted, short-page, whole-object, length, non-page, non-physical, bytes-like, no-mutation and order tests passed at RED; they pin behaviour Task 1 already had.
- **Task 3 RED:** 11 failures: the field bytes were overwritten (assertion failures on the changed-address lists) and `SpliceResult` had no `masked`.
- `gsd_run check tdd-red-evidence` was not run: pytest's default report is not one of its formats and this plan is `type: execute` with task-level `tdd="true"`.

## Negative tests proven able to fail

- **Unpatched control in every negative test:** `_refused()` and the mask/edge tests call `_assert_control(img)`, which splices the same fixture with `{}` and asserts SHA-1 equality, so no refusal test can pass because `splice()` always fails. `test_rebuild_target_reports_mutation` and `test_mask_count_in_rebuild_result` also rebuild without patches and expect `ok`.
- **RED runs** (above) show every refusal and masking test failing before its implementation.
- **Mutants** (each applied to `tools/reverseapoc/splice.py` alone, run, then restored with `git checkout -- tools/reverseapoc/splice.py`; `git diff --exit-code` clean after each; none committed):

| Mutant | Change | Failing tests |
|---|---|---|
| A | span end not clipped to vsize | `test_refuse_past_vsize_tail[0x11800-1]`, `[0x117FF-2]` |
| B | fixup search starts at `lo`, not `lo - MAX_FIELD + 1` | `test_mask_field_starting_before_patch` |
| C | masked field not clipped to page data | `test_mask_bss_cut_field_clipped` |
| E | output = copy of `le.data` with pages overwritten | `test_splice_output_is_reassembled` (and `tests/test_cli.py::test_rebuild_mismatch_exits_1`) |
| F | overlap check `>=` instead of `>` | `test_touching_patches_are_not_an_overlap` |

## Files Created/Modified

- `tools/reverseapoc/splice.py` - `splice`, `SpliceResult`, `MaskedField`, `MAX_FIELD`, private span/run/validation/masking helpers, `rebuild_target(..., patches=)`, D-08 report fields and line
- `tests/test_splice.py` - Task 1-3 tests and the two pins

## Decisions Made

- `le.fixups()` is parsed only when there is a patch, so the plain round trip does not depend on fixup parsing.
- Masking skips the covered bytes instead of restoring them; with overlaps refused first, the image bytes under a field are still the original ones.
- `backed_end` is clipped against the patch's object (the object every run of a patch is confined to).

## Deviations from Plan

### Auto-added

**1. [Rule 2 - Missing critical] Two pin tests beyond the plan's list**
- **Found during:** mutant review after Task 3
- **Issue:** a copy-then-overwrite `splice()` (the plan's prohibition) was caught only indirectly by a CLI test, and nothing pinned that touching patches are not an overlap.
- **Fix:** `test_splice_output_is_reassembled` and `test_touching_patches_are_not_an_overlap`, proven by mutants E and F.
- **Files modified:** tests/test_splice.py
- **Committed in:** `17ced9f`

### Additions within scope

- `test_mask_field_starting_before_patch` (proves the `MAX_FIELD - 1` back-off), `test_splice_accepts_bytes_like` (bytes, bytearray, memoryview), and a `bool` key case in `test_refuse_bad_va`.
- `_page_backed_end`, `_span_at`, `_checked_patch`, `_object_spans`, `_covered_fixups`, `_masked_fields`, `_unmasked`, `_unmasked_runs`, `_write`, `_mismatch` are small private helpers that keep `splice()` shallow (D-17).

### Mechanical notes

- The plan's real-file command uses `$(git rev-parse --path-format=absolute --git-common-dir)/../orig`; the worktree sandbox refuses git inside a command substitution, so it ran with the literal `C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/orig` (read only).
- The run was interrupted by a power loss after the seventh commit; on resume the branch, base and commits were re-checked and the full verification re-run before this SUMMARY.

**Total deviations:** 1 auto-added (Rule 2). **Impact:** test-only; no scope change.

## Verification

- `REVERSEAPOC_ORIG=C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/orig uv run pytest -q -rs`: 285 passed, 9 skipped (3 container-only hygiene, 6 absent Watcom media; none for a missing orig/ file).
- `uv run pytest -q` (no override): 273 passed, 21 skipped.
- `uv run ruff check .`: All checks passed.
- `-k "refuse or overlap or length or physical"`: 27 passed; `-k mask`: 10 passed; `-k "mutation or edge or short_page"`: 8 passed; `-k "mutation or round_trip"`: exits 0.
- `uv run reverseapoc rebuild --orig <main checkout>/orig`: three OK lines (UFO2P.EXE, TACP.EXE, SMKP.EXE), exit 0.
- The container gate was not run from this worktree, as instructed.

## Issues Encountered

- Power loss mid-run after all task commits; no work lost.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03-04 can surface `first_diff`/`first_diff_region`/`first_diff_va`/`diff_bytes`/`masked_fields` in `--json` straight from `RebuildResult`.
- Plan 03-05's real-file control can call `rebuild_target(..., patches={va: b"..."})` and assert the reported offset equals `page.file_offset + delta`.

## Self-Check: PASSED

Both modified files exist; all 7 commits (5492154, 9ee09ee, 01c6205, 567670a, d0fa7e0, ed1877a, 17ced9f) are ancestors of HEAD; `git rev-list --count 2c4e815..17ced9f` = 7.

---
*Phase: 03-byte-identical-round-trip*
*Completed: 2026-10-20*
