---
phase: 05-split-and-first-matches
plan: 09
subsystem: tooling
tags: [relocation-check, land, splice, sha1, omf, le, kknd, objdiff-blind-spot]

requires:
  - phase: 05-split-and-first-matches
    provides: "05-04 symbols.SymbolTable.address_of and functions.FunctionRow; 05-01 spike plant P3 (objdiff 100.0 on a wrong 2nd relocation)"
  - phase: 04-compiler-identification
    provides: "splice.splice / _write_atomic / _refuse_inside_orig / _refuse_same_file, targets.hash_bytes / load_manifest"
provides:
  - "relocs.check_function: the authoritative relocation check of our OMF function against its LE row, in flat VA space, without ELF or objdiff (SPL-09)"
  - "relocs.RelocResult (ok, problems, ours, theirs, to_json), RelocError, LOCAL_SEGMENT_PROBLEM, FIELD_SIZE"
  - "land.build_patch (KKND keep-original rule at ours | theirs), land.land (splice + SHA-1, first differing VA), land.write_landed, LandedFunction, LandResult, LandError (SPL-10)"
  - "tests/relocpair.py: synthetic original-LE / our-OMF function pair builder for later plans' tests"
affects: [05-17 check verb, 05-14 ninja verify, 05-18 real cmain386 proof, 05-19 first game matches]

actuals:
  tokens: 10287
  tasks: 3
  commits: 6
plan_head_before: 532a74582239727dd92c0ee200d1d3e8d81b87cf
plan_head_after: 691a978b0fa4bf6f52cb177147485ba24abc8ff8

tech-stack:
  added: []
  patterns:
    - "One helper per check rule, each a generator of '0xVVVVVVVV: <what>' problem strings; the verdict sorts them, so the order of OMF fixups does not matter"
    - "want = base + stored + displacement (mod 2**32); base is address_of(symbol) for an extern and start - off for our own _TEXT"
    - "land builds every patch (and so verifies every check) before calling splice()"

key-files:
  created:
    - tools/reverseapoc/relocs.py
    - tools/reverseapoc/land.py
    - tests/relocpair.py
    - tests/test_relocs.py
    - tests/test_land.py
  modified: []

key-decisions:
  - "A length mismatch is the only problem reported for that function: every later rule compares [start, end) byte for byte, which needs equal lengths"
  - "Any segment target other than our own _TEXT (CONST, CONST2, _DATA, _BSS or another) fails as a local segment reference; group and frame targets fail as unsupported"
  - "Our own _TEXT resolves for self-relative fixups too (a call to a static function in the unit), not only for segment-relative case labels"
  - "Only location-9 (offset32) fixups are accepted, the same rule omf2elf applies; a field that crosses the public's boundary is a problem"
  - "write_landed turns splice's path refusals into LandError; overlapping patches stay splice's SpliceError, as the plan specifies"
  - "land refuses two functions at one start (the patch dict would otherwise drop one silently)"

patterns-established:
  - "Relocation check problems name a VA, a symbol and addresses; tests assert no problem holds a hex byte dump"
  - "A forged ok RelocResult still fails land's SHA-1 gate: the check and the hash are independent gates"

requirements-completed: [SPL-09, SPL-10, SPL-13]

coverage:
  - id: D1
    description: "relocs.check_function passes a synthetic good pair (call rel32 + mov eax,[abs32]) with ours == theirs plus the call field"
    requirement: SPL-09
    verification:
      - kind: unit
        ref: "tests/test_relocs.py#test_good_pair_passes"
        status: pass
    human_judgment: false
  - id: D2
    description: "Negative suite: wrong call target, wrong 2nd relocation of one instruction (the objdiff-blind P3 case), missing fixup, local segment reference (CONST/CONST2/_DATA/_BSS), length mismatch, differing byte, unknown symbol, sel16 LE field, self-relative over an LE fixup, field crossing the public end; each fails naming the VA and symbol, never bytes"
    requirement: SPL-13
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_relocs.py -k \"wrong or missing or local or length or differing or unknown or straddler or no_relocations or sorted\" (15 selected, passed)"
        status: pass
      - kind: other
        ref: "scratchpad mutate.py: disabling each of _segment_relative, _self_relative, _reverse_coverage, _bytes, _length makes tests/test_relocs.py fail"
        status: pass
    human_judgment: false
  - id: D3
    description: "Edges of the check: adjacent fields checked independently, page-straddling LE field passes, no relocations passes, own-_TEXT references resolve (and a wrong label fails), zero-size public / zero-length row / public past the segment end raise RelocError, problems sorted for any fixup order"
    requirement: SPL-09
    verification:
      - kind: unit
        ref: "tests/test_relocs.py (24 passed)"
        status: pass
    human_judgment: false
  - id: D4
    description: "land: a checked function lands to the manifest SHA-1 with the original call displacement kept (Pitfall 2); refuses a failed check before splicing; no functions is the plain rebuild; order independent; adjacent functions land; overlap refused by splice(); a forged ok check fails the SHA-1 with the first differing VA; write_landed is atomic and refuses orig/ and the source"
    requirement: SPL-10
    verification:
      - kind: unit
        ref: "tests/test_land.py (15 passed)"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-10-24
status: complete
---

# Phase 5 Plan 09: Relocation check and land step Summary

**relocs.check_function compares our OMF function with its LE row in flat VA space (equal length, bytes outside both sides' fields, every fixup's target, reverse coverage) and fails the wrong-second-relocation case objdiff scores 100.0. land.build_patch keeps the original bytes at every relocated field on either side, and land.land splices and hashes the EXE against the manifest.**

Execution context nonce: efd221352bbcc3eb

## Performance

- **Duration:** about 9 min of execution after reading the context (recorded start 2026-10-24T00:55:56Z)
- **Completed:** 2026-10-24T01:04:36Z
- **Tasks:** 3 (Task 1 tracer, Tasks 2-3 auto, all TDD)
- **Files:** 5 created, none modified

## Accomplishments

- `relocs.py` (KKND build_kknd.py header, CC0) implements research Pattern 7 rules 1-6 with one helper per rule: `_length`, `_bytes`, `_self_relative`, `_segment_relative`, `_own_segment`, `_local_segment`, `_reverse_coverage`. It needs no ELF and no objdiff.
- The objdiff blind spot (spike 005 plant P3) is pinned: in `mov dword [A], imm32 B` with a wrong data symbol on B, the check reports exactly one problem, at B's field, naming the wrong symbol. A's field is reported fine.
- `land.py` (KKND header) builds each patch from our bytes with the original bytes at `ours | theirs`. A function whose check did not pass is refused before anything is spliced. Then it splices all patches and compares the SHA-1 with the expected manifest value. On a miss it names the first differing VA. `write_landed` writes atomically and refuses `orig/` and the source file.
- `tests/relocpair.py` builds a synthetic pair: the conftest LE image with patched pages and fixup records, and an omfimage module with `_TEXT` plus a local data segment. Later plans can reuse it.

## Task Commits

1. **Task 1 (tracer): a synthetic good pair passes the check and lands to the original SHA-1.** RED `3a20959`, GREEN `bfecdb4`
2. **Task 2: the negative suite and the edges of the relocation check.** RED `d18fe01`, GREEN `b071705`
3. **Task 3: land step edges, refusals and the landed-EXE writer.** RED `919c9d5`, GREEN `691a978`

Tracer gate (Task 1): interactive run, `human_verify_mode` end-of-phase, automated-only verify. Both verify commands were re-run and passed (2 passed, ruff clean) before expansion.

## TDD notes

- Task 1 and Task 3 RED failed at import (`reverseapoc.relocs` / `reverseapoc.land`, then `write_landed`, did not exist yet). That is the normal first RED for a new module. The plan is `type: execute` and `workflow.tdd_mode` is off, so the tdd-red-evidence classifier gate does not apply.
- Task 2 RED: 12 of 24 tests failed on assertions or on the wrong exception: the four local-segment cases, unknown symbol, field crossing, the three own-_TEXT cases and the three RelocError refusals. The other 12 already passed. Task 1's GREEN implemented the plan's core rules (length, bytes, self-relative, segment-relative extern, reverse coverage, sorting), so the wrong-target, wrong-2nd-relocation, missing-fixup, length, differing-byte, sel16, straddler and no-relocation tests were green on first run. To show they still bite, a mutation run disabled each of the five core rules in turn, and the suite failed every time.

## Files Created/Modified

- `tools/reverseapoc/relocs.py`: `check_function`, `RelocResult`, `RelocError`, `FIELD_SIZE`, `LOCAL_SEGMENT_PROBLEM`, one helper per rule
- `tools/reverseapoc/land.py`: `LandedFunction`, `LandResult` (`ok`, `first_difference`, `format`, `to_json`), `build_patch`, `land`, `write_landed`, `LandError`
- `tests/relocpair.py`: synthetic pair builder (made-up bytes and names)
- `tests/test_relocs.py`: 24 tests
- `tests/test_land.py`: 15 tests

## Decisions Made

See key-decisions in the frontmatter. In short: a length mismatch stops the comparison. Every segment except our own `_TEXT` is a local reference. Own-`_TEXT` resolution also covers self-relative calls to static functions. Only offset32 fixups are accepted, as in omf2elf. Two functions at one start are refused.

## Deviations from Plan

No orchestrator ruling amends 05-09. The "For 05-09 and 05-11" note (aliases need `SymbolTable.build(..., aliases=runtime_aliases(...))` with LIB386 loaded) needs no change here. `check_function` takes a built `SymbolTable` and calls `address_of`. Building the table with aliases is the caller's job (05-17 `check`, 05-18).

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Shared test builder `tests/relocpair.py` outside files_modified**
- **Found during:** Task 1
- **Issue:** test_relocs.py and test_land.py need the same synthetic original-LE / our-OMF pair. Duplicating it, or importing one test module from another, would be fragile.
- **Fix:** a test-only helper module next to `omfimage.py` and `libtree.py`, with the same made-up-bytes rule.
- **Committed in:** `3a20959` (extended in `d18fe01`)

**2. [Rule 2 - Missing critical] land refuses two functions at one start**
- **Found during:** Task 3
- **Issue:** `splice(le, {start: patch})` takes a dict, so a second function at the same start would silently replace the first.
- **Fix:** `_patches` raises LandError naming the VA. Test: `test_two_functions_at_one_start_are_refused`.
- **Committed in:** `919c9d5` / `691a978`

**3. [Rule 2 - Missing critical] Extra refusals in the check and the patch builder (T-05-18, T-05-19)**
- A public outside its segment, or a row past the image, raises RelocError instead of an IndexError.
- A fixup field crossing the public's boundary, a non-offset32 location, and a group or frame target are problems.
- build_patch refuses bytes whose length differs from the row, and a field outside the row.
- Tests: `test_public_past_the_segment_end_is_refused`, `test_our_field_crossing_the_public_end_fails`, `test_refuses_bytes_of_the_wrong_length`, `test_refuses_a_field_outside_the_row`.
- **Committed in:** `b071705`, `691a978`

**4. [Rule 2 - Missing critical] Own-_TEXT tests**
- The must-have truth names the own-`_TEXT` rule, but Task 2's behaviour list had no test for it. Added `test_own_segment_absolute_reference_resolves`, `test_own_segment_call_resolves` and `test_own_segment_reference_to_the_wrong_label_fails`.
- **Committed in:** `d18fe01`

---

**Total deviations:** 4 auto-fixed (1 Rule 3, 3 Rule 2). No orchestrator rulings applied (none address 05-09).
**Impact on plan:** Public API names are as planned. Additions: `FIELD_SIZE`, `LOCAL_SEGMENT_PROBLEM`, the `test_*` extras above, and `tests/relocpair.py`. No scope creep.

## Issues Encountered

- The worktree harness refused compound git commands with `$(...)`. The plan ledger was written with the literal base SHA instead.
- REQUIREMENTS.md was not touched. SPL-13 is also declared by later plans (05-18/05-19 real proof), and the orchestrator owns the tracking files after merge.

## Known Stubs

None.

## User Setup Required

None.

## Next Phase Readiness

- 05-17 (`check`) and 05-14 (`ninja verify`) can call `check_function` then `land` with `expected_sha1` from `load_manifest()`, and write with `write_landed(..., orig_dir=orig/, source=orig/<EXE>)`.
- 05-18: the real `__CMain` pair names runtime publics (`main_`, `exit_`, `____Argv`, ...). Build the SymbolTable with `aliases=runtime_aliases(runtime_entries(...))` so `address_of` resolves them.
- Jump-table functions are covered by the own-`_TEXT` rule but stay out of first matches (D-15).

## Verification

- `uv run pytest -q tests/test_relocs.py tests/test_land.py`: 39 passed
- `uv run pytest -q`: 1039 passed, 177 skipped (real-file tests skip in the worktree)
- `uv run ruff check .`: All checks passed!
- No commit touches `orig/`, `config/`, STATE.md or ROADMAP.md. No commit deletes a file.

## Self-Check: PASSED

- Files exist: tools/reverseapoc/relocs.py, tools/reverseapoc/land.py, tests/relocpair.py, tests/test_relocs.py, tests/test_land.py
- Commits on this branch: 3a20959, bfecdb4, d18fe01, b071705, 919c9d5, 691a978
