---
phase: 07-mechanics-first-decompilation
plan: 48b
subsystem: match-gate
tags: [relocs, check, land, batch, jump-table, watcom-filler]
bundle_nonce: b4ebb4f46aef

requires:
  - phase: 07-48
    provides: "the trailing-filler rule (_trailing_filler, conditions 1-5, REASON_* constants, RelocResult.filler)"
provides:
  - "relocs.check_function(table=False): with table=True, _trailing_filler skips condition 4 (a table is data)"
  - "check._reloc(..., table=) and _head_reloc's one table=True call for the leading table's span"
  - "synthetic gap-less leading-table tests: tracer, four negatives, spy, land of the head only"
  - "real fixture tests/fixtures/filler/tacp/f_0001e860.c and test_real_leading_table_gap_tacp_0001e860"
  - "docs/matching.md jump-table bullet with the 07-48b gap clause"
affects: [07-48c, "Task 2b (tacp 0x0001E860 joins its D-12 proposal list)", attempt check, driver sessions]

actuals:
  tokens: 6800  # chars/4 over the tools/tests/docs diff (27201 chars)
  tasks: 3
  commits: 5  # git rev-list --count plan_head_before..plan_head_after; the SUMMARY commit follows
plan_head_before: 03b28bb6428697470f537789bd544f82f06f15dc
plan_head_after: ab2e374154f2ad7c8b9a268548ff6d279a46a55e

tech-stack:
  added: []
  patterns:
    - "An explicit keyword (table=True), set by one caller and pinned by a spy test, instead of switching on a row's kind"

key-files:
  created:
    - tests/fixtures/filler/tacp/f_0001e860.c
  modified:
    - tools/reverseapoc/relocs.py
    - tools/reverseapoc/check.py
    - tests/test_check.py
    - tests/test_relocs.py
    - tests/test_land.py
    - tests/test_filler_real.py
    - docs/matching.md

key-decisions:
  - "07-48b: the leading table's span [table row start, head start) accepts ours short of the original only by alignment filler before a 16-aligned head, under 07-48's conditions 1, 2, 3 and 5; condition 4 is skipped only through check_function(table=True), which only check._head_reloc passes"
  - "07-48b: tacp func_0001E860 (f_0001e860.c) is exact only under -4r -oneatx -s -fpi (committed cell: code differs), so it joins Task 2b's D-12 proposal list through 07-48c, not Task 2a; the orchestrator lands it"

patterns-established:
  - "Negatives that a rule's earlier conditions already refused on the old HEAD are regression pins, not RED: say so in the notes"

requirements-completed: [DEC-02, DEC-03]

coverage:
  - id: D1
    description: "The table span passes a gap of original alignment filler before a 16-aligned head (conditions 1, 2, 3, 5; not 4)"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_table_gap_accepts_original_filler_before_the_head"
        status: pass
      - kind: unit
        ref: "tests/test_check.py#test_table_gap_refuses_a_gap_that_is_not_filler, test_table_gap_refuses_an_unaligned_head, test_table_gap_refuses_a_gap_of_16, test_table_gap_refuses_an_le_fixup_in_the_gap"
        status: pass
    human_judgment: false
  - id: D2
    description: "Only the span check passes table=True; every function check keeps condition 4"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_only_the_table_span_is_checked_as_a_table"
        status: pass
      - kind: unit
        ref: "tests/test_relocs.py#test_check_function_without_table_keeps_condition_4"
        status: pass
    human_judgment: false
  - id: D3
    description: "The table is never landed: land splices the head's row alone and the image equals the original"
    verification:
      - kind: unit
        ref: "tests/test_land.py#test_table_gap_lands_the_head_only"
        status: pass
    human_judgment: false
  - id: D4
    description: "tacp func_0001E860 re-judged under both cells from both agent files; its real table span passes under -oneatx; follow-on Task 2b"
    requirement: DEC-03
    verification:
      - kind: integration
        ref: "tests/test_filler_real.py#test_real_leading_table_gap_tacp_0001e860 (host and container)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Done gate: both suites green, container gate --all with both SHA-1s OK and no function line changed"
    verification:
      - kind: other
        ref: "build/gate/07-evidence/48b-host.log, 48b-container.log, 48b-gate-all-after.log"
        status: pass
    human_judgment: true
    rationale: "/code-review is deferred to the orchestrator (R-D), which runs it and re-runs the reported checks before fast-forwarding main"

duration: 48min
completed: 2026-11-02
status: complete
---

# Phase 7 Plan 48b: Leading-table gap rule Summary

**The span of a leading jump table now passes when ours lacks only the original's alignment filler before a 16-aligned head (07-48's conditions 1, 2, 3 and 5, never 4, through one `table=True` call in `check._head_reloc`), and tacp func_0001E860 judges exact under `-4r -oneatx -s -fpi`, so it joins Task 2b.**

Bundle nonce: b4ebb4f46aef

## Performance

- **Duration:** 48 min
- **Started:** 2026-11-02T03:25:24Z
- **Completed:** 2026-11-02T04:13:11Z
- **Tasks:** 3
- **Files modified:** 8 (2 tools, 4 tests, 1 fixture, 1 doc)

## Accomplishments

- **The rule as built.** `relocs.check_function` takes the keyword `table: bool = False` and passes it to `_trailing_filler(pair, *, table)`. With `table` set, condition 4 (ours ends in a terminal instruction) is skipped. Conditions 1, 2, 3 and 5 and their order are unchanged. `check._reloc` passes the flag on, and `check._head_reloc` is the one caller that sets it: `_reloc(span, exe, head, table=True)`. The docstrings of relocs, `check_function`, `LeadingTable`, `leading_table`, `_head_reloc` and `with_relocs` state the clause. A table is data and is never landed.
- **Tests.** In tests/test_check.py: the tracer, four negatives that each assert their reason text, and a spy that pins `table=True` to the span alone. `table_module` gained `filler=` and `symbol=` keywords, and `_gap_layout` builds the shifted made-up originals. tests/test_relocs.py pins that a data-only public keeps condition 4 by default. tests/test_land.py lands the head of a gap-less unit and gets the original image back.
- **The real row.** tacp func_0001E860 was re-judged from both spike 011 agent files under both cells. The fixture, a copy of f_0001e860.c, and `test_real_leading_table_gap_tacp_0001e860` pass on the host and in the container. With the rule disabled, the real test fails on the span.
- **docs/matching.md.** The jump-table bullet now has the 07-48b gap clause.

## RED evidence assessment (Task 1)

The record is build/gate/07-evidence/48b-red-record.json (JUnit from 48b-red.xml). The classifier returned `RED_EVIDENCE_OK`, target `tests/test_check.py::test_table_gap_accepts_original_filler_before_the_head`. On HEAD 03b28bb, 5 tests failed and 227 passed.

- The TARGET ran and failed on its planned assertion (`head.ok`) for the intended reason: `0x0001010C: length differs: ours 12 bytes, original 16 bytes; ours does not decode to a terminal instruction at its end`. That is condition 4 applied to a data span. There was no collection, import or fixture fault.
- test_table_gap_lands_the_head_only failed with the same span refusal.
- test_only_the_table_span_is_checked_as_a_table failed because no call carried `table=True`.
- test_check_function_without_table_keeps_condition_4 failed with a TypeError: there was no `table` keyword yet. Its first half, the default refusing a data-only public, already held.
- test_table_gap_refuses_a_gap_that_is_not_filler was RED for the wrong reason: it got condition 4's text, not its own `is not alignment filler`.
- **Three negatives were not RED (see Deviations):** the unaligned head, the 16-byte gap and the LE fixup in the gap passed on HEAD. `_trailing_filler` checks conditions 1, 2 and 3 before condition 4, so those gaps were already refused with their own reasons. They are regression pins: they prove that skipping condition 4 did not loosen conditions 1 to 3. The mutants below show each one catches that loosening.

Task 2's real test was written after the GREEN commit. It is a regression test on real data, not a RED gate: with `_head_reloc` temporarily set to `table=False`, it fails with a span problem at 0x0001E858 for the terminal-instruction reason. The edit was restored and tools/ is clean.

## Mutant table (48b-mutants.txt, each restored with `git checkout --`, tools/ clean)

| Mutant | Test that must fail | Failed |
|---|---|---|
| `_head_reloc` passes `table=False` | test_table_gap_accepts_original_filler_before_the_head | yes |
| `_trailing_filler` skips condition 4 always | test_check_function_without_table_keeps_condition_4 | yes |
| `_reloc` defaults `table` to True | test_only_the_table_span_is_checked_as_a_table | yes |
| table also skips condition 1 | test_table_gap_refuses_a_gap_of_16 | yes |
| table also skips condition 2 | test_table_gap_refuses_an_unaligned_head | yes |
| table also skips condition 3 | test_table_gap_refuses_an_le_fixup_in_the_gap | yes |
| table also skips condition 5 | test_table_gap_refuses_a_gap_that_is_not_filler | yes |

## Re-judge of tacp 0x0001E860 (48b-rejudge.txt, 48b-rejudge-neighbour.txt)

Row [0x0001E860, 0x0001E900), unit u_0001df90. The table row is 32 bytes, followed by 8 bytes of original filler. In our `-oneatx` object the first public is at offset 32, so the span is [table start, 0x0001E860), 40 bytes, and ours is 8 bytes short.

| Agent file | committed `[-4r -s -fpi]` | `[-4r -oneatx -s -fpi]` |
|---|---|---|
| f_0001e860.c | exact=False, score 58.72, len 152/160, first diff `mov esi, edx \| mov edi, edx` | **exact=True**, score 98.08, len 160/160 |
| f_0001e860_with_neighbour.c | exact=False, score 50.49, len 148/160, first diff `mov esi, edx \| mov edi, edx` | exact=False, score 100.0, len 160/160, first diff `reloc: _TEXT: own _TEXT target N outside func_0001E860 needs the unit's public-to-row map` |

Both judge runs exited normally (exit 0 and exit 1); neither was a tool error. Control run, 48b-rejudge-without-rule.txt: f_0001e860.c under `-oneatx` with the rule disabled is not exact, first diff `jmp dword ptr cs:[edx*N] | jmp dword ptr cs:[edx*N + N]`. So the gap rule is what makes it exact. Under the `-oneatx` cell the real table span has no problem.

**Route: Task 2b.** Only `-oneatx` is exact, so 0x0001E860 goes on Task 2b's list as a D-12 proposal through 07-48c's `flags propose --from-batch`, author `claude subagent (spike 011)`, with f_0001e860.c. It does not join Task 2a, because the committed rule is not exact (the code differs, not the gap). It is evidence only here and nothing went into src/; the orchestrator lands it.

## Suites and gate

- **Host suite** at ab2e374: 4390 passed, 41 skipped (R-A reasons only), exit=0 (1012 s). Ruff exit=0.
- **Container suite** at ab2e374, image rebuilt: 4429 passed, 2 skipped (`Windows-only: msvcrt lock path`), ruff clean, exit=0.
- **Real tests:** host 2 passed, 1 skipped (objdiff-cli not on PATH, run in the container); container 3 passed with no skip.
- **gate --all, before (03b28bb):** exit=0, `OK UFO2P.EXE sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 landed 57`, `OK TACP.EXE sha1 48ef00969d8880a0a152de1b652853fa7ac27393 landed 38`.
- **gate --all, after (ab2e374):** exit=0 with the same two SHA-1 lines, landed 57 and 38, no MISMATCH.
- **48b-gate-all.diff:** 4 lines on each side. They are the container run name (the `Creating` and `Created` lines) and uv's `Resolved 9 packages` / `Checked 8 packages` timings. No function line differs.
- **Newly passing functions:** none. As expected, no src/ file changed.
- `git status --porcelain -- config/ decomphub.progress.json` stayed empty.
- **Tier 1:** before and after are both `943 members, 86 matched, 61 partial, 796 unmatched`.

## Task Commits

1. **Task 1 RED:** `2cf9627` test(07-48b): failing tests for filler between a leading table and its head
2. **Task 1 GREEN:** `d190385` feat(07-48b): accept original filler between a leading table and its head
3. **Task 2 fixture and real test:** `1451b69` test(07-48b): real-file leading-table gap fixture for tacp func_0001E860
4. **Task 2 docs:** `cf92c74` docs(07-48b): the leading-table gap rule
5. **Task 2 fix-forward:** `ab2e374` fix(07-48b): the func_0001E860 fixture is LF, its provenance says so

## Files Created/Modified

- `tools/reverseapoc/relocs.py`: the `table` keyword. `_trailing_filler` skips condition 4 for a table span.
- `tools/reverseapoc/check.py`: `_reloc(..., table=)`, `_head_reloc`'s single `table=True`, and the docstrings.
- `tests/test_check.py`: the gap-less builders (`table_module(filler=, symbol=)`, `_gap_layout`), the tracer, four negatives and the spy.
- `tests/test_relocs.py`: test_check_function_without_table_keeps_condition_4.
- `tests/test_land.py`: test_table_gap_lands_the_head_only.
- `tests/test_filler_real.py`: test_real_leading_table_gap_tacp_0001e860 and EXACT_CELLS_0001E860; `_committed_rule(unit)`.
- `tests/fixtures/filler/tacp/f_0001e860.c`: our C, copied from the spike 011 b064 agent file.
- `docs/matching.md`: the jump-table bullet's 07-48b clause.

## Review

Code review is deferred to the orchestrator: this executor does not run `/code-review` (R-D: it may dispatch reviewer subagents). The command is `/code-review` on `git diff 03b28bb...HEAD`, at the default level, never max or ultra.

The executor read `git diff 03b28bb HEAD -- tools/` by hand and found no defect:
- there is exactly one `table=True` call, inside `_head_reloc`;
- both keywords default to False;
- the condition order is unchanged;
- the head's own verdict keeps its `filler` of 0 (`_with_table` merges only the span's problems).

## Decisions Made

- The flag is the explicit keyword `table`, not the row's kind (data-in-code), as the plan decided. The spy test and the `_reloc defaults True` mutant pin that.
- The fixture is f_0001e860.c, not the neighbour variant: only the former judges exact.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The fixture's provenance claimed a byte-identical copy, but git stores it as LF**
- **Found during:** Task 2 (fixture commit)
- **Issue:** The agent file has CRLF line ends, and `.gitattributes` (`* text=auto eol=lf`) stores the copy as LF. The plain `cmp` against the agent file can only hold for the working copy written before commit.
- **Fix:** Refreshed the working copy from git (`git checkout -- <fixture>`, now LF). The docstring now says the copy is byte-identical except for line ends. Host and container real tests were re-run on the LF copy and passed.
- **Verification:** `tr -d '\r' < build/spike-011/agents/b064/f_0001e860.c | cmp - tests/fixtures/filler/tacp/f_0001e860.c` exits 0. Real tests: host exit=0, container 3 passed, exit=0.
- **Committed in:** ab2e374

### Plan-text deviations (no code impact)

- **Branch:** the plan names `gsd/07-48-filler-rule`. Per the orchestrator ruling, the work ran on `gsd/07-48b-table-filler`, cut from main at 03b28bb.
- **Three negatives were regression pins, not RED.** The plan says each negative was RED on 07-48's HEAD. That holds only for the condition-5 negative (not filler). The unaligned head (condition 2), the 16-byte gap (condition 1) and the LE fixup in the gap (condition 3) are checked before condition 4, so on HEAD they already failed with their own reasons. They were kept as written, and their teeth are shown by mutants 4 to 6. Nothing was widened or distorted to force a RED.
- **The acceptance criterion `cmp tests/fixtures/... build/spike-011/...`** holds modulo CRLF to LF only (see auto-fix 1).

---

**Total deviations:** 1 auto-fixed (Rule 1), plus 3 plan-text notes.
**Impact on plan:** None on the rule. Option A semantics are exactly as specified.

## Issues Encountered

None.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- Orchestrator steps, not run here:
  - run `/code-review` on `git diff 03b28bb...HEAD`;
  - fast-forward main, push, `gh run watch`;
  - add tacp 0x0001E860 (f_0001e860.c, cell `-4r -oneatx -s -fpi`) to Task 2b's D-12 proposal list.
- 07-48c runs next, never at the same time.
- Mid-unit jump tables still fail closed.

## Self-Check: PASSED

- FOUND: tests/fixtures/filler/tacp/f_0001e860.c, tests/test_filler_real.py, tools/reverseapoc/relocs.py, tools/reverseapoc/check.py
- FOUND commits: 2cf9627, d190385, 1451b69, cf92c74, ab2e374 (each an ancestor of HEAD)
- Task 1, 2 and 3 automated verify commands passed. Task 3's ran before this SUMMARY and is re-run after its commit.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-11-02*
