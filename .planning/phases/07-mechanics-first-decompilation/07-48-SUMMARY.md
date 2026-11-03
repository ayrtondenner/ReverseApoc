---
phase: 07-mechanics-first-decompilation
plan: 48
subsystem: match-gate
tags: [relocs, land, check, batch, x86, capstone, objdiff, watcom-filler]
bundle_nonce: 8a96802f5a2c

requires:
  - phase: 07-45
    provides: "the batch harness (judge, exact_trim) and spike 011's filler finding"
provides:
  - "relocs: original trailing Watcom filler accepted under the five option-A conditions (RelocResult.filler)"
  - "x86.is_alignment_filler from capstone operand detail, carried as the Insn field"
  - "land.build_patch: len(ours) + filler == row length, our bytes only, the tail stays original"
  - "check: compare_bytes counts the kept filler; FunctionCheck.filler, its report line and JSON; the objdiff target of a filler-accepted row cut at our length (branch B)"
  - "batch.is_alignment_filler delegates to x86"
  - "real fixture tests/fixtures/filler/tacp/f_0006bee0.c and tests/test_filler_real.py"
affects: [07-48b, 07-48c, "Task 2a (landing the alignment-only rows)", attempt check, driver sessions]

actuals:
  tokens: 16000  # chars/4 over the tools/tests/docs diff (64103 chars)
  tasks: 4
  commits: 10  # git rev-list --count plan_head_before..plan_head_after; the SUMMARY commit follows
plan_head_before: 68084cb530c1e2cac211b27beae6c6054e358038
plan_head_after: 4396f49e99c6dd765f0ca417f08c34d8760bb464

tech-stack:
  added: []
  patterns:
    - "A refusal keeps its stable prefix and appends `; <reason>`; negatives assert the reason so they are RED on the old code"
    - "Two filler predicates: x86.is_filler (eax-only, our own sizes) and x86.is_alignment_filler (any register, the original's tail)"
    - "check_source builds the objdiff target after the relocation check, over the rows relocs proved"

key-files:
  created:
    - tests/test_filler_real.py
    - tests/fixtures/filler/tacp/f_0006bee0.c
  modified:
    - tools/reverseapoc/x86.py
    - tools/reverseapoc/relocs.py
    - tools/reverseapoc/land.py
    - tools/reverseapoc/check.py
    - tools/reverseapoc/batch.py
    - tests/relocpair.py
    - tests/test_x86.py
    - tests/test_relocs.py
    - tests/test_land.py
    - tests/test_check.py
    - tests/test_batch.py
    - docs/matching.md
    - docs/learnings.md
    - docs/toolchain.md

key-decisions:
  - "07-48 objdiff decision B: objdiff scored tacp func_0006BEE0 89.6552% against the full row, so check_source cuts a filler-accepted row's target at start + reloc.length (100% after)"
  - "07-48 trailing filler (owner option A): a 1-15 byte shortfall passes check only when the row end is 16-aligned, no LE fixup lies in the tail, ours ends in a terminal instruction and the original's tail decodes to the row end as any-register alignment filler"
  - "07-48 condition 4 decodes ours with our fixup fields as data sites, so inline table data cannot decode on to a terminal by chance (Rule 2 deviation)"

patterns-established:
  - "Reason-asserting negatives: a widened gate's negatives assert the refusal reason, and a mutant run proves each guard"

requirements-completed: [DEC-02, DEC-03]

coverage:
  - id: D1
    description: "relocs accepts original trailing Watcom filler under exactly the five conditions; every other length difference is refused with the prefix and the first failing reason"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_relocs.py#test_filler_*"
        status: pass
      - kind: other
        ref: "build/gate/07-evidence/48-mutants.txt (14/14 guards: failed: yes)"
        status: pass
    human_judgment: false
  - id: D2
    description: "x86.is_alignment_filler from capstone operand detail; is_filler stays eax-only"
    verification:
      - kind: unit
        ref: "tests/test_x86.py#test_alignment_filler_any_register, test_not_alignment_filler_any_register, test_is_filler_stays_eax_only"
        status: pass
    human_judgment: false
  - id: D3
    description: "land keeps the tail original and refuses filler 0, a wrong count, ours longer than the row and a field outside our bytes"
    verification:
      - kind: unit
        ref: "tests/test_land.py#test_trailing_filler_lands_original_bytes, test_land_refuses_*"
        status: pass
    human_judgment: false
  - id: D4
    description: "check reports `bytes ok, N bytes of trailing filler kept`, compare_bytes counts the kept filler, the objdiff target is cut at kept filler, and batch.judge's exact follows"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_compare_bytes_*, test_function_check_*, test_check_source_*; tests/test_batch.py#test_judge_*"
        status: pass
    human_judgment: false
  - id: D5
    description: "the real tacp func_0006BEE0 passes check in a view in the container: objdiff 100, reloc ok, 15 bytes of filler kept, both whole-EXE SHA-1s equal the manifest"
    requirement: DEC-03
    verification:
      - kind: integration
        ref: "tests/test_filler_real.py (container: build/gate/07-evidence/48-real-container.log, 2 passed)"
        status: pass
    human_judgment: false
  - id: D6
    description: "both suites and the container gate --all are green; no committed function changes verdict"
    verification:
      - kind: other
        ref: "build/gate/07-evidence/48-host.log, 48-container.log, 48-gate-all-after.log, 48-gate-all.diff"
        status: pass
    human_judgment: false
  - id: D7
    description: "/code-review on the plan's diff"
    verification: []
    human_judgment: true
    rationale: "Deferred to the orchestrator: the executor did not run /code-review (R-D, no subagents); the exact command is in the Review section"

duration: 54min
completed: 2026-11-02
status: complete
---

# Phase 7 Plan 48: The trailing-filler rule Summary

**`check` now accepts a public that is short of its row only by the original linker's 1-15 bytes of 16-byte alignment filler, under the owner's five option-A conditions, and land keeps that tail original. The real tacp func_0006BEE0 passes in a view: objdiff 100 (once the target is cut at our length), reloc ok, 15 bytes of filler kept, and both EXEs SHA-1 identical.**

Bundle nonce: 8a96802f5a2c

## Performance

- **Duration:** 54 min
- **Started:** 2026-11-02T01:35:45Z
- **Completed:** 2026-11-02T02:30:22Z
- **Tasks:** 4 (all complete)
- **Files modified:** 16 (tools 5, tests 8 plus the fixture, docs 3)

## Owner ruling and counts

- Option A (2026-11-01). A shortfall passes only when all five conditions hold, checked in this order (`relocs._trailing_filler`):
  1. 0 < shortfall <= 15;
  2. the row ends on a 16-byte boundary;
  3. no LE fixup field overlaps the tail;
  4. ours decodes exactly to its size and ends in a terminal instruction;
  5. the original's tail decodes exactly to the row end, and every instruction is `x86.is_alignment_filler`.
- Nothing broader: no unit was recut, and orig/, config/, src/, configure.py, the build scripts and omf2elf are unchanged since 68084cb.
- Tier 1, before and after: `943 members, 63 matched, 76 partial, 804 unmatched`. The two counts are equal, as expected, because no src/ file changed.

## Accomplishments

- relocs.py:
  - `_trailing_filler` checks the five conditions, with one helper per condition.
  - The reasons are module constants. A refusal keeps the `length differs: ours N bytes, original M bytes` prefix and appends `; <reason>`.
  - `RelocResult.filler` is in to_json. The bytes, the fixups and reverse coverage run over our bytes.
- x86.py: `is_alignment_filler` is built from capstone operand detail and carried as the Insn field. `is_filler` and `FILLER_ENCODINGS` are unchanged.
- land.py: `build_patch` refuses ours longer than the row, and requires `len(ours) + filler == row length`. Fields must lie inside our bytes, and the patch is our bytes only.
- check.py:
  - `compare_bytes` counts the kept filler.
  - `FunctionCheck.filler` is a property, shown as `bytes ok, N bytes of trailing filler kept` and as `bytes.filler` in the JSON.
  - Branch B: `check_source` builds the target after the relocation check, with filler-accepted rows cut at `start + reloc.length`.
- batch.py: `is_alignment_filler` delegates to x86, its op_str regexes are gone, and the docstrings name the 07-48 rule.
- A real fixture (our C, cmp-identical to build/spike-011/agents/b064/f_0006bee0.c) and real-file tests on the host and in the container.

## Task Commits

1. **Task 1 (tracer): the rule, the predicate, land's guard**
   - `57215eb` test: failing tests, negatives first
   - `a92ea9c` feat: the five option-A conditions
   - `995a0b2` test and `f3fcbff` fix: condition 4 stops at inline data (deviation 1)
2. **Task 2: the kept-filler report and batch's delegate**
   - `c9d6eeb` test
   - `3a2cdfc` feat
3. **Task 3: the real fixture and objdiff branch B**
   - `cf4ff45` test: target cut (RED)
   - `93370e5` feat: cut the objdiff target at kept filler
   - `3989ad1` test: real-file fixture and tests
4. **Task 4: docs, suites and gate**
   - `4396f49` docs: the trailing-filler rule
   - then this SUMMARY's commit

## RED evidence (TDD)

| Record | Target | Verdict | Semantic assessment |
|---|---|---|---|
| 48-red-record.json | tests/test_land.py::test_trailing_filler_lands_original_bytes | RED_EVIDENCE_OK (37 failed, 91 passed) | The target ran and failed on its first assertion (`fn.reloc.ok`). The old code refuses the 7-vs-16-byte pair with the bare prefix: the planned behaviour, not a collection or fixture fault. |
| 48-red2-record.json | tests/test_batch.py::test_judge_exact_on_a_filler_pair | RED_EVIDENCE_OK (4 failed, 182 passed) | `exact` was False with reloc_ok True: compare_bytes still counted the 9 kept bytes as differing. |
| 48-red3-record.json | tests/test_check.py::test_check_source_cuts_the_target_at_kept_filler | RED_EVIDENCE_OK (1 failed, 1 passed) | The verdict assertions passed, then the test failed because build_target received the full 16-byte row. |

How the negatives failed on the old code:
- Each relocs negative failed on the missing `; <reason>`: the old code gave only the bare prefix.
- The x86 tests failed with AttributeError.
- The land negatives failed with the wrong LandError text, or with TypeError (no `filler` field).
- Two Task 2 tests and one Task 3 test pass on the old code too. They pin existing behaviour and are not RED:
  - test_compare_bytes_without_kept_filler_counts_the_shortfall;
  - test_judge_refused_tail_is_not_exact_but_exact_trim;
  - test_check_source_keeps_full_rows_without_kept_filler.

TDD gate compliance: every `feat(07-48)` commit is preceded by its `test(07-48)` commit (57215eb before a92ea9c, c9d6eeb before 3a2cdfc, cf4ff45 before 93370e5).

## Mutant proof (48-mutants.txt)

In each run, one guard was disabled and its negative test was run. Then the file was restored with `git checkout --`, and afterwards `git diff --quiet -- tools/` was clean.

| Guard | Test | Failed |
|---|---|---|
| cond1 shortfall > 15 | test_filler_refuses_a_shortfall_of_16 | yes |
| cond1 ours longer | test_filler_refuses_ours_longer_than_the_row | yes |
| cond2 row end aligned | test_filler_refuses_an_unaligned_row_end | yes |
| cond3 no LE fixup in tail | test_filler_refuses_an_le_fixup_in_the_tail | yes |
| cond4 ours ends terminal | test_filler_refuses_ours_without_a_terminal_last_instruction | yes |
| cond4 data sites in ours | test_filler_refuses_ours_ending_in_inline_data | yes |
| cond5 tail decodes to the end | test_filler_refuses_a_tail_that_does_not_decode_to_the_end | yes |
| cond5 tail all filler | test_filler_refuses_a_tail_that_is_not_filler | yes |
| build_patch longer than row | test_land_refuses_ours_longer_than_the_row | yes |
| build_patch ours + filler == row | test_land_refuses_a_wrong_filler_count, ..._short_bytes_with_filler_0 | yes |
| build_patch fields inside ours | test_land_refuses_a_field_in_the_kept_filler | yes |
| lea index | test_not_alignment_filler_any_register[8d3406] | yes |
| lea segment override | test_not_alignment_filler_any_register[268d36] | yes |
| lea displacement 0 | test_not_alignment_filler_any_register[8d7601] | yes |

## objdiff decision: branch B

- **Measured** (48-objdiff-measure.log, before any target change): `OBJDIFF func_0006BEE0 89.6552`, with `reloc ok  bytes ok, 15 bytes of trailing filler kept`. objdiff sees the original's filler as instructions we lack.
- **Branch B:** `check_source` cuts a filler-accepted row's target at `start + reloc.length`. The land step, `write_target` and the sweep's own cut are unchanged.
- **After** (48-objdiff-after.log, 48-real-container.log): `OBJDIFF func_0006BEE0 100`.
- **The real fixture's verdict line:** `OK        func_0006BEE0  0x0006BEE0  65 bytes  objdiff 100%  reloc ok  bytes ok, 15 bytes of trailing filler kept`. Every splice was ok, so both whole-EXE SHA-1s equal the manifest.
- **Host** (48-real-host.log): the judge test passed (exact, ours/row 65/80, filler 15). The view test skipped with `objdiff-cli is not on PATH (run in the container)`.

## Suites and gate

- **Host** (HEAD 4396f49, 48-host.log): 4378 passed, 41 skipped, exit=0. Every skip reason is an R-A one. ruff is clean (48-ruff.log, exit=0).
- **Container** (HEAD 4396f49, 48-container.log, after `docker compose build`): 4417 passed, 2 skipped (`Windows-only: msvcrt lock path`), ruff clean, exit=0.
- **Container `gate --all`** (48-gate-all-after.log): exit=0.
  - `OK UFO2P.EXE sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 landed 48`
  - `OK TACP.EXE sha1 48ef00969d8880a0a152de1b652853fa7ac27393 landed 24`
  - `ok`
- **Gate diff** (48-gate-all.diff): 4 lines per side, all of them noise:
  - the docker run's container name (`Creating` and `Created` lines);
  - uv's `Resolved 9 packages in Nms` and `Checked 8 packages in Nms` timings.

  No function line and no SHA-1 line differs.
- **Newly passing functions:** none, as expected, because no src/ file changed.
- `git status --porcelain -- config/ decomphub.progress.json` stayed empty, and `check-orig` passes.

## Review

- **`/code-review`: deferred to the orchestrator.** This executor did not run it, because R-D forbids subagents and the review may dispatch them. Command, at the default level only, never max or ultra: `/code-review` on `git diff main...HEAD`, from the main checkout on branch `gsd/07-48-filler-rule`.
- **The executor's own read of `git diff main...HEAD -- tools/`** found no defect. One cost was noted and kept: `is_alignment_filler` is computed for every decoded instruction (the plan puts it in `_insn`). Decode is about 17% slower: 0.54 s to 0.63 s over 512 KiB of TACP code.

## Decisions Made

- Objdiff branch B, as measured: 89.6552% before the cut, 100% after it.
- Reasons may add the first non-filler instruction's mnemonic and VA, such as `(int3 at 0x...)`. They never carry bytes.
- `filler_pair` and friends in tests/relocpair.py. `our_object` returns the OMF bytes, so judge can read an object from disk.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Condition 4 decodes ours with our fixup fields as data sites**
- **Found during:** the Task 2 read of check.with_relocs. The leading-table span goes through the same check_function.
- **Issue:** The table data of a leading jump table span, or an inline table at our end, could decode by chance into instructions that end on a `ret`. Condition 4 would then accept a filler tail for data. That would quietly widen 07-48b's ground.
- **Fix:** `_ours_reason` passes `data_sites` (the VAs of our fixups), the rule `x86.decode` and omf2elf already use. An instruction start at a fixup field ends the decode, so condition 4 refuses.
- **Files modified:** tools/reverseapoc/relocs.py, tests/test_relocs.py
- **Verification:** test_filler_refuses_ours_ending_in_inline_data was RED on a92ea9c and green after. Its mutant fails.
- **Committed in:** 995a0b2 (test) and f3fcbff (fix)

**2. [Rule 1 - JSON shape] Two exact-dict tests gain `filler: 0`**
- `test_good_pair_passes` (RelocResult.to_json) and `test_check_passes_a_matching_unit` (`bytes`) assert whole dicts, so each gained the new key.
- Both edits are part of their task commits (57215eb and 3a2cdfc).

**Sweep note (from the objective, not a code change):** `check --sweep` is not edited. Its byte compare follows the rule through check_function, but its target cut stays a full row, so a sweep cell on a filler row may still rank below objdiff 100. It only ranks, and nothing is gated on it.

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 test-shape update).
**Impact on plan:** Deviation 1 narrows what condition 4 accepts. It never widens it.

## Issues Encountered

- Windows `Path.write_text` turned three test files into CRLF in the working copy. Git stored LF (`eol=lf`), and the working copies were rewritten as LF. Later edits wrote bytes.

## Threat Flags

None. No new endpoint, file access or trust boundary. The new fixture is our own C: tracked, copied from spike output, and cmp-checked.

## User Setup Required

None.

## Next Phase Readiness

- **Task 2a**, for the orchestrator after main is fast-forwarded and pushed and CI is watched: land the alignment-only rows of spike 011, the 32 converter rows plus tacp 0x0006BEE0. Re-judge each one first with `batch.judge`, then land it through the normal gate.
- **Then 07-48b** (the same tail rule between a leading jump table and its head) and **07-48c** (`flags propose --from-batch`), one at a time on the main checkout.

## Self-Check: PASSED

- The key files exist: x86.py, relocs.py, land.py, check.py, batch.py, test_filler_real.py, the fixture, matching.md.
- All 10 task commits are ancestors of HEAD.
- `def _trailing_filler` is present.
- config/, src/, decomphub.progress.json, configure.py and omf2elf.py are unchanged since 68084cb.
- `check-orig`: 3 ok.
