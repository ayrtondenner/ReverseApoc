---
phase: 03-byte-identical-round-trip
plan: 09
subsystem: testing
tags: [le, splice, real-file-tests, mutants, docs]
gap_closure: true
gap_ids: [G-03-6]

requires:
  - phase: 03-byte-identical-round-trip
    provides: "03-05 real-file tests and the spike-confirmed FACTS table"
provides:
  - "real-file test helpers derived from le.py's reader (LE.page_va, LEPage, the object table's page range) instead of splice.py's arithmetic"
  - "the control-mutation test's within-object page label (IN-01 label, D-08)"
  - "docs/toolchain.md container orig/ row listing SMKP.EXE (IN-04)"
affects: [03-10 phase gate, IN-05, IN-04]

actuals:
  tokens: 8700      # chars/4 over the two changed files (34,925 chars); the diff itself is 9,285 chars
  tasks: 2
  commits: 2
plan_head_before: 0269b2ae4057c5a94e96266de82d24e510915def
plan_head_after: 154a73c601f523dfbd25a8ca83425be0797ba19e

tech-stack:
  added: []
  patterns:
    - "real-file helpers find pages through a functools.cache'd, VA-sorted index of (le.page_va(p.logical), p) and bisect"
    - "test oracles stay independent of the implementation: a reader-derived helper plus the spike FACTS table, proven by reverted mutants"

key-files:
  created: []
  modified:
    - tests/test_splice_real.py
    - docs/toolchain.md

key-decisions:
  - "_page_backed_end in the tests is also functools.cache'd (keyed on LE and the frozen LEObject): it is called once per fixup (about 28,000 in UFO2P), and scanning the page map each time would be slow"
  - "_page_at guards with an assert that names the VA only, so a wrong page-backed end surfaces as a VA, never as bytes"
  - "Mutant 3 was run in two forms: the consistent (page_va, page) pair of the previous page is an equivalent mutant on these files; the wrong page for the right address fails 9 tests"

patterns-established:
  - "Real-file helper independence: derive page geometry from le.py's page map, keep FACTS as the oracle, prove both with reverted mutants"

requirements-completed: [RT-03, RT-05]

coverage:
  - id: D1
    description: "IN-05: real-file helpers derive page offsets, page-backed ends, straddling and coverage from le.py's reader; FACTS byte-identical to main; 21 real-file tests pass with no skip"
    requirement: RT-05
    verification:
      - kind: integration
        ref: "REVERSEAPOC_ORIG=<main checkout>/orig uv run pytest -q -rs tests/test_splice_real.py (21 passed, 0 SKIPPED)"
        status: pass
      - kind: other
        ref: "cmp of the FACTS block of main:tests/test_splice_real.py against the worktree file"
        status: pass
      - kind: other
        ref: "! grep -nE 'page_count - 2|max\\(SRC_SIZE' tests/test_splice_real.py; grep -n '\\.page_va(' tests/test_splice_real.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "IN-05: reverted mutants show the suite still catches a splice.py error and that FACTS pins the new helpers"
    requirement: RT-03
    verification:
      - kind: other
        ref: "mutant 1 (splice._page_backed_end full last page): test_fields_cut_by_page_data_are_clipped fails x3; reverted, git diff --exit-code clean"
        status: pass
      - kind: other
        ref: "mutant 2 (test _page_backed_end + 1): test_measured_facts fails x3; reverted"
        status: pass
      - kind: other
        ref: "mutant 3b (_page_at returns the previous page for the right address): 9 tests fail; reverted"
        status: pass
    human_judgment: false
  - id: D3
    description: "IN-01 label: test_control_mutation_is_reported expects 'page K of object 1' with K counted from the object base"
    requirement: RT-03
    verification:
      - kind: integration
        ref: "tests/test_splice_real.py#test_control_mutation_is_reported (UFO2P.EXE, TACP.EXE, SMKP.EXE)"
        status: pass
    human_judgment: false
  - id: D4
    description: "IN-04: docs/toolchain.md line 136 lists UFO2P.EXE, TACP.EXE and SMKP.EXE; exactly one line changed"
    verification:
      - kind: other
        ref: "grep -nF '`orig/`: UFO2P.EXE, TACP.EXE and SMKP.EXE from your install, mounted at `/work/orig:ro`' docs/toolchain.md; git diff -U0 main -- docs/toolchain.md (1 removed, 1 added)"
        status: pass
      - kind: unit
        ref: "uv run pytest -q tests/test_hygiene.py (27 passed, 3 skipped container-only)"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-10-21
status: complete
---

# Phase 3 Plan 09: Real-file test independence and SMKP doc row Summary

**The real-file test helpers now find pages through a cached, VA-sorted `le.page_va` index and the object table's page range instead of copying splice.py's last-page formula and field-size constant. FACTS is unchanged, all 21 real-file tests pass with no skip, and three reverted mutants show the suite still fails when it should. docs/toolchain.md now lists SMKP.EXE in the container's orig/ row.**

## Performance

- **Duration:** about 6 min of execution (02:29 to 02:35 UTC)
- **Started:** 2026-10-21T02:29:00Z
- **Completed:** 2026-10-21T02:35:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- IN-05: `_page_index` (functools.cache, VA-sorted from `le.page_va`) and `_page_at` (bisect plus an assert that names the VA only) replace the `le.pages[obj.page_index + k - 1]` indexing that splice._object_pages also uses.
- IN-05: `_page_offset(le, va)` no longer takes the object. `_page_backed_end` takes the furthest `page_va + size` over the pages whose logical number is in `[page_index, page_index + page_count)`, instead of the `page_count - 2` formula. `_straddles` compares the pages `_page_at` returns (by identity). `_covered(fixups, va)` is a plain scan. `MAX_FIELD`, the `SRC_SIZE` and `bisect_left` imports and `_fixup_index` are gone.
- IN-01 label: the control test expects `page {K} of object 1` with `K = (va - obj.base) // page_size + 1`. For object 1 that is the same text as before, so the test passes before and after 03-08's label change.
- Module docstring: one sentence says the helpers derive from le.py's reader and that FACTS is the oracle.
- IN-04: the ninja row's "Supplied by you" cell in docs/toolchain.md lists all three D-07 rebuild targets.

## Real-file runs (REVERSEAPOC_ORIG = main checkout's orig/)

| Run | Result |
|---|---|
| Baseline at 0269b2a, before the refactor | `21 passed in 1.47s`, no SKIPPED |
| After the refactor (e3abcc6) | `21 passed in 1.62s`, no SKIPPED |
| After all mutants were reverted (tracer gate re-run) | `21 passed in 1.67s`, 0 SKIPPED lines |
| After the docs commit (154a73c) | `21 passed in 1.64s` |

Full suite in the worktree (no orig/): `310 passed, 44 skipped`. Full suite with REVERSEAPOC_ORIG: `343 passed, 11 skipped`. None of those 11 skips involve orig/: they are Windows file names, container-only and Watcom media. `uv run ruff check .`: `All checks passed!`

## Mutants (each applied alone, run, reverted; none committed)

| # | Mutant | Failed tests |
|---|---|---|
| 1 | `tools/reverseapoc/splice.py` `_page_backed_end` returns `obj.base + obj.page_count * le.page_size` (last page treated as full) | `test_fields_cut_by_page_data_are_clipped` for UFO2P.EXE, TACP.EXE and SMKP.EXE (`MaskedField.clipped` is False); 3 failed, 18 passed |
| 2 | test helper `_page_backed_end` returns one byte more | `test_measured_facts` x3 (UFO2P on `obj1_tail_past_vsize`, 1316 vs 1315; TACP and SMKP inside `_obj1_tail` through `_page_at`'s "is in no page" guard), `test_straddling_fields_are_masked` x3, `test_fields_cut_by_page_data_are_clipped[SMKP.EXE]`; 7 failed |
| 3 | `_page_at` returns `index[i - 1]` (the previous page with its own address) | none: 21 passed. This is an equivalent mutant on these files. Each object's pages lie in the file in VA order and back to back, so `prev.file_offset + va - prev_va` is the same offset |
| 3b | `_page_at` returns `(page_va, index[i - 1][1])` (the previous page for the right address) | `test_control_mutation_is_reported` x3 (first_diff off by one page), `test_straddling_fields_are_masked` x3, `test_measured_facts` x3; 9 failed, 12 passed |

After the last revert, `git diff --exit-code -- tools/reverseapoc/splice.py tests/test_splice_real.py` and `git diff --exit-code main -- tools/` both exit 0.

## Task Commits

1. **Task 1: real-file helpers derived from le.py's reader (IN-05, IN-01 label)**: `e3abcc6` (refactor). Plan 03-10 cites this for IN-05.
2. **Task 2: docs/toolchain.md lists SMKP.EXE (IN-04)**: `154a73c` (docs). Plan 03-10 cites this for IN-04.

**Plan metadata:** the SUMMARY commit that follows these two.

## Files Created/Modified

- `tests/test_splice_real.py`: adds the VA-sorted page index and `_page_at`. `_page_offset`, `_page_backed_end`, `_straddles` and `_covered` now derive from le.py's reader. The control test uses the within-object label. FACTS is byte-identical to main.
- `docs/toolchain.md`: line 136 lists SMKP.EXE. No other line changed, and the "Getting the Watcom compilers" and "OpenApoc CRC mismatch" sections are untouched.

## Decisions Made

- `_page_backed_end` is also `functools.cache`d. It runs once per fixup through `_backed_end`, and without the cache it would scan the 303 to 666 page map entries each time.
- Mutant 3 got a second, stronger form (3b) once the literal form turned out to be equivalent on these files. Both are recorded above.

## Deviations from Plan

### Sandbox deviation

**1. [Rule 3 - Blocking] Literal REVERSEAPOC_ORIG path instead of `$(git rev-parse ...)`**
- **Found during:** Task 1 verify
- **Issue:** The worktree sandbox refuses commands that combine `$(git ...)` with other commands, and also any path spelled through `.git/../orig`.
- **Fix:** I ran `git rev-parse --path-format=absolute --git-common-dir` on its own (it printed `C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/.git`) and then used the equivalent literal `REVERSEAPOC_ORIG=C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/orig`. The verify checks (exit 0, `21 passed`, no `SKIPPED`) ran as separate commands.
- **Files modified:** none

### Plan wording vs result

**2. Mutant 3's literal form survives**
- **Found during:** Task 1 mutants
- **Issue:** The plan expected "return the page before the right one" to fail the control test. Returning the previous page together with its own linear address computes the same file offset on these files, because pages are laid out in VA order and back to back within each object. So nothing can fail.
- **Fix:** I added mutant 3b, which pairs the right address with the previous page: 9 tests fail. No code change was needed. The surviving form is recorded as an equivalent mutant, not as a test gap.

**3. Mutant 2's failure point**
- The plan says mutant 2 fails test_measured_facts "on obj1_tail_past_vsize". For UFO2P it fails exactly there (1316 vs 1315). For TACP and SMKP the one-past address lies outside every page, so `_page_at`'s guard fails first, inside `_obj1_tail` in the same test. Either way, test_measured_facts fails on all three.

---

**Total deviations:** 1 sandbox workaround (Rule 3) and 2 recorded differences between the plan's wording and the mutant results.
**Impact on plan:** None on scope. FACTS, the expected values and tools/ are unchanged.

## Issues Encountered

None.

## User Setup Required

None. No external service configuration required.

## Next Phase Readiness

- Plan 03-10 (phase gate) can cite `e3abcc6` for IN-05 and `154a73c` for IN-04 once 03-07, 03-08 and 03-09 are merged.
- The control test's within-object label matches both the current `Region.describe` and 03-08's within-object count for object 1.

## Self-Check: PASSED

- FOUND: tests/test_splice_real.py, docs/toolchain.md, this SUMMARY
- FOUND: e3abcc6 and 154a73c are ancestors of HEAD
- `uv run pytest -q` (310 passed, 44 skipped), `uv run ruff check .` (clean), the real-file run (21 passed, 0 SKIPPED) and tests/test_hygiene.py (27 passed) all green

---
*Phase: 03-byte-identical-round-trip*
*Completed: 2026-10-21*
