---
phase: 05-split-and-first-matches
plan: 07
subsystem: tooling
tags: [capstone, x86, discovery, le, fixups, jump-tables, pytest]
requires:
  - phase: 05-split-and-first-matches
    provides: "05-03 x86.decode/decode_one/is_filler and Insn; 05-04 functions.csv EVIDENCE vocabulary and libmatch.read_runtime_csv"
provides:
  - "tools/reverseapoc/discover.py: Discovery (starts, evidence, decoded_bytes, jump_tables, ignored_seeds, to_json, format), discover, ends, code_objects, DiscoverError"
  - "Per-start D-07 evidence (entry, runtime, fixup, call) from le.py's unrelocated image, fixup operands resolved through target_va"
  - "Jump tables as data-in-code ranges (leading tables included); D-07 function ends"
affects: [05-13, 05-16, reconcile, boundaries-csv, functions-csv]
actuals:
  tokens: 6715
  tasks: 2
  commits: 5
plan_head_before: 532a74582239727dd92c0ee200d1d3e8d81b87cf
plan_head_after: 3c9a32af6a7dd05e11104e9f31b3af602355ee59
tech-stack:
  added: []
  patterns:
    - "Windowed capstone decoding (0x200-byte windows clipped to the object end): capstone's disasm decodes a whole buffer up front, so a path never hands it the rest of the object"
    - "Function-pointer seeding iterates to a fixed point, then drops fixup evidence whose source turned out to be a jump-table entry"
    - "Discovery repr/format/to_json are counts only, so a failing real-file assertion never dumps addresses or bytes"
key-files:
  created:
    - tools/reverseapoc/discover.py
    - tests/test_discover.py
    - tests/test_discover_real.py
  modified: []
key-decisions:
  - "Jump-table detection moved into Task 1: without it the tracer real-file bound failed (2,954 / 2,772 starts, jump-table entries seeded as fixup starts)"
  - "A jump table is `jmp [reg*4+T]` whose displacement field is a code-pointing LE fixup; it extends over consecutive code-to-code off32/ptr16:32 fixups; neither the entries nor the jmp's own field give fixup evidence"
  - "Fixup evidence covers off32 and the offset half of ptr16:32 (the kinds whose target_va is an address); sel16 is never a seed"
  - "ignored_seeds counts entry and runtime seeds outside every executable object; call targets outside code are dropped without counting"
  - "Real tests seed runtime starts from config/<exe>/runtime.csv when present"
patterns-established:
  - "_Image base class (code objects, unrelocated flat image, fixup map and sites) shared by the descent and the end scan"
requirements-completed: [SPL-02]
coverage:
  - id: D1
    description: "Recursive descent seeded with entry, runtime and code-pointing fixups (target_va), call targets become starts with call evidence"
    requirement: SPL-02
    verification:
      - kind: unit
        ref: "tests/test_discover.py#test_call_chain, test_runtime_seed, test_fixup_seed, test_evidence_merges, test_report_has_counts_only"
        status: pass
    human_judgment: false
  - id: D2
    description: "Jump tables as data-in-code ranges with case labels in the same function; leading tables; inline data stops decoding"
    requirement: SPL-02
    verification:
      - kind: unit
        ref: "tests/test_discover.py#test_jump_table, test_leading_table, test_inline_data"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-07 end rule (padding after a terminal instruction, fall-through to next start) and object-edge handling"
    requirement: SPL-02
    verification:
      - kind: unit
        ref: "tests/test_discover.py#test_function_ends, test_seed_outside_code_object, test_function_at_object_edges, test_no_read_past_object_edges"
        status: pass
    human_judgment: false
  - id: D4
    description: "Discovery on the real UFO2P.EXE and TACP.EXE: entry is a start, starts inside the code object, counts in range, ends tile"
    requirement: SPL-02
    verification:
      - kind: integration
        ref: "REVERSEAPOC_ORIG=<main>/orig uv run pytest -q -rs tests/test_discover_real.py (8 passed, 0 skipped)"
        status: pass
    human_judgment: false
duration: 10min
completed: 2026-10-24
status: complete
---

# Phase 5 Plan 07: Capstone function discovery Summary

**Capstone recursive descent over le.py's unrelocated image, seeded and resolved through the LE fixups, with jump tables as data-in-code and the D-07 end rule: 1,946 starts in UFO2P.EXE and 1,930 in TACP.EXE**

Execution context nonce: a03e2f62b0bbe543

## Performance

- **Duration:** about 10 min (executor clock; reading the context took longer)
- **Started:** 2026-10-24T00:55:49Z
- **Completed:** 2026-10-24T01:05:17Z
- **Tasks:** 2
- **Files modified:** 3 (all new)

## Accomplishments

- `discover(le, *, runtime_starts)` runs a worklist descent (with a visited set and no recursion) over `load_flat(relocate=False)`. It is seeded with the entry point, the runtime starts and every off32/ptr16:32 LE fixup whose `target_va` lands in an executable object. The raw field is never read as an address. Every LE fixup site is a data site, so an instruction start on a fixup field ends the path.
- Jump tables: a `jmp [reg*4+T]` whose displacement field is a code-pointing fixup starts a table, which then runs over consecutive code-to-code fixups. The table is reported as a `[start, end)` range. Its targets are decoded as case labels of the same function, and neither the entries nor the jmp's own field count as `fixup` evidence.
- `ends(discovery, le)` applies the D-07 rule. A function ends at the first filler or zero byte after a terminal instruction, where any leading jump table of the next function counts as padding. Otherwise it ends at the next start, so a function that falls through is not cut short.
- Real counts (runtime.csv seeds included). The research's naive estimate was 1,880 / 1,837 starts and 4,588 / 4,220 jump-table bytes:

  | | UFO2P.EXE | TACP.EXE |
  |---|---|---|
  | starts | 1,946 | 1,930 |
  | call / entry / fixup / runtime evidence | 1,458 / 1 / 508 / 121 | 1,528 / 1 / 405 / 132 |
  | decoded bytes / code object size | 708,010 / 785,117 | 697,665 / 795,983 |
  | jump tables (bytes) | 104 (4,720) | 94 (4,468) |
  | seeds outside the code object | 0 | 0 |
  | functions ending at the next start | 1,637 | 1,609 |

  Most functions sit back to back, with no padding after their last `ret`. This matches the research's probe observation.
- The real test takes about 10 s per EXE.

## Task Commits

1. **Task 1: Tracer: recursive descent, real EXEs**
   - `c721536` test(05-07): add failing tests for capstone recursive-descent discovery (RED: ModuleNotFoundError, module absent)
   - `14e3dd7` test(05-07): add failing jump-table test; keep real-file failures counts-only (RED: `assert () == ((0x10200, 0x1020c),)`)
   - `2129261` feat(05-07): capstone recursive-descent discovery with LE evidence (GREEN)
2. **Task 2: Jump tables, padding, inline data, object edges**
   - `0ffcf4d` test(05-07): add failing tests for the D-07 end rule, leading tables and object edges (RED: 4 tests fail with `AttributeError: ... no attribute 'ends'`; test_inline_data and test_seed_outside_code_object passed at RED, see Deviations)
   - `3c9a32a` feat(05-07): D-07 function ends with padding, leading tables and fall-through (GREEN)

## Files Created/Modified

- `tools/reverseapoc/discover.py`: KKND derivation header on line 1. Contains the `Discovery` report, `discover`, `ends`, `code_objects`, `DiscoverError`, and the `_Image` / `_Descent` / `_EndScan` internals.
- `tests/test_discover.py`: 12 synthetic tests on made-up bytes patched into the conftest LE.
- `tests/test_discover_real.py`: 4 tests per EXE (UFO2P.EXE and TACP.EXE, REVERSEAPOC_ORIG). They assert on counts only.

## Decisions Made

See key-decisions in the frontmatter. One addition: only the two game EXEs are parametrised. SMKP.EXE is not part of the phase-5 split, and the plan's ranges do not apply to it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Jump-table detection pulled from Task 2 into Task 1**
- **Found during:** Task 1 (tracer real-file verify)
- **Issue:** Without jump tables, every table entry was seeded as a `fixup` start. That gave 2,954 / 2,772 starts, above the plan's 2,500 bound, so the tracer verify failed.
- **Fix:** Added `test_jump_table` as a second Task 1 RED commit (`14e3dd7`), then implemented table detection in the Task 1 GREEN commit, together with fixed-point pointer seeding that excludes table entries.
- **Files modified:** tools/reverseapoc/discover.py, tests/test_discover.py
- **Verification:** The real test passed with 1,946 / 1,930 starts.
- **Committed in:** 14e3dd7, 2129261

**2. [Rule 1 - Bug] Real-file assertions could dump addresses**
- **Found during:** Task 1 (first real run)
- **Issue:** pytest printed the whole `Discovery` repr, with addresses and evidence, in the failure output. The plan requires that real tests print nothing beyond counts.
- **Fix:** Assertions now compare local counts, and `Discovery.__repr__` returns the counts-only `format()`.
- **Files modified:** tests/test_discover_real.py, tools/reverseapoc/discover.py
- **Committed in:** 14e3dd7, 2129261

**3. Added beyond the plan**
- `test_evidence_merges` (call plus runtime on one start), `test_report_has_counts_only`, `test_no_read_past_object_edges` (exact decoded-byte count past the object end) and the real `test_ends_tile` (every end lies in (start, next start]).
- Windowed decoding: capstone's `disasm` decodes its whole buffer at once, so each path decodes 0x200-byte windows clipped to the object end. This mitigates T-05-14.

**4. RED note:** In Task 2, test_inline_data and test_seed_outside_code_object already passed at RED, because the plan's Task 1 action already asked for fixup data sites and `ignored_seeds`. They pin that behaviour. The other four Task 2 tests failed for the intended reason.

No orchestrator ruling amends 05-07, so none was applied.

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug), plus additive tests.
**Impact on plan:** The Task 1/Task 2 split moved by one feature. Scope is unchanged.

## Issues Encountered

- The harness refuses compound shell commands that contain the main checkout path or `$(git ...)`. The verify was therefore run as separate commands with the literal path `REVERSEAPOC_ORIG=C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/orig`. Its output in build/discover-real.out was `8 passed`, with no SKIPPED line.

## Known Stubs

None.

## Threat Flags

None. No new surface: discovery reads orig/ through le.py and reports counts and addresses only. T-05-14 is mitigated by the worklist, the visited set and the clipped windows. T-05-15 is mitigated by the counts-only format, to_json and repr.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 05-13 can reconcile `discover` starts and evidence against the Ghidra export. Things it should know:
  - `jump_tables` are the data-in-code candidates.
  - `ends()` gives capstone's boundary for each start.
  - About 500 / 400 starts per EXE are fixup-only (function pointers in instruction operands or data). Most capstone-only disagreements will come from these, as the research predicted.
- The table walk does not stop at a known start that happens to carry a fixup at its first byte. This cannot happen for real code entries, but two back-to-back tables of different switches merge into one range. This may be one reason our table byte counts are slightly above the research's.

## Self-Check: PASSED

- FOUND: tools/reverseapoc/discover.py, tests/test_discover.py, tests/test_discover_real.py
- FOUND commits: c721536, 14e3dd7, 2129261, 0ffcf4d, 3c9a32a
- Acceptance: line 1 is the KKND header; `-k "jump or leading or inline or ends or outside or edges"` selects 7 tests, all passing; the real test passes for both EXEs, unskipped; `uv run pytest -q` gives 1012 passed, 185 skipped; `uv run ruff check .` is clean.

## Review fixes (round 1)

**Important: the D-07 end rule now follows the plan.** Before this fix, a terminal instruction ended a function only when everything up to the next start was padding. As a result, code after the padding that had no start evidence was absorbed into the previous function. Following the orchestrator ruling, a function now ends at the first padding byte (filler or zero) after a terminal instruction. It also ends at a terminal instruction that is followed only by jump tables and padding up to the next start, which covers a leading table that comes directly after a `ret`. Code after the padding is no longer part of the function: it stays uncovered as a gap for 05-13 to judge. A non-terminal last instruction still ends at the next start (fall-through).
- Test `test_ends_leave_gap_code_outside` covers: ret, padding, decodable gap code without evidence, then the next start. The first function ends at the padding and the gap lies outside every range. At RED it failed with the old 0xB end against the expected 6.
- `test_ends_tile` (real) still asserts start < end <= next start, so ranges never overlap. Its docstring now says gaps may exist. It did not fail, and the 2,500-start limit is unaffected because `ends` does not change discovery.

**Minor:**
- `test_report_has_counts_only` now asserts that `format()`, `repr()` and `to_json()` contain no `0x` and no run of 5 or more digits.
- New `test_errors_carry_no_address_in_assertions` checks `DiscoverError` by type only, for a start outside the code object and for an LE without an executable object. No real-file test raises it.

**Commits:** `c3e06f3` test(05-07) (RED), `2842afe` fix(05-07) (GREEN).

**Commands and output:**
- `uv run pytest -q tests/test_discover.py`: `14 passed`
- `REVERSEAPOC_ORIG=C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/orig uv run pytest -q -rs tests/test_discover_real.py`: `8 passed in 27.26s`, 0 SKIPPED
- `uv run pytest -q`: `1014 passed, 185 skipped in 14.00s`
- `uv run ruff check .`: `All checks passed!`

**Real counts after the fix:**

| | UFO2P.EXE | TACP.EXE |
|---|---|---|
| starts | 1,946 | 1,930 |
| decoded bytes | 708,010 | 697,665 |
| bytes covered by ranges / code object size | 753,779 / 785,117 | 747,561 / 795,983 |
| functions ending at the next start (was 1,637 / 1,609) | 1,466 | 1,457 |
| gaps (gap bytes) | 480 (31,338) | 473 (48,422) |
| gaps longer than 16 bytes | 134 | 111 |

The gap bytes include padding and leading jump tables as well as uncovered code.
