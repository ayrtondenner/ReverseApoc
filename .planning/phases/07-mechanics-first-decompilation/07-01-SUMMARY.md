---
phase: 07-mechanics-first-decompilation
plan: 01
subsystem: planning-docs
tags: [roadmap, requirements, done-rule, decomp.wtf, owner-ruling]

requires: []
provides:
  - "DEC-03 and DEC-05 reworded per owner ruling D-05 (refined by D-22, D-23, D-31)"
  - "ROADMAP Phase 7 SC3/SC5 reworded; AGT-11 on the Requirements line plus a Carry-in line"
  - "docs/workflow.md Phase 7 roadmap row carries the same gate"
  - "D-06/D-24 recorded: decomp.wtf not re-evaluated (spike 006 stands), one checkout, private views"
affects: [07-41 phase gate, VERIFICATION.md, 07-15 coverage view, 07-22 Tier 1 sign-off]

actuals:
  tokens: 3435
  tasks: 2
  commits: 2
plan_head_before: 0f9de364337258572e5dcddb10a133cd2c95c821
plan_head_after: 5fa287e874795775fb26aff7e27de0bbc5ae487d

tech-stack:
  added: []
  patterns:
    - "Every reworded gate line cites the owner ruling ID and date (D-05, 2026-10-26)"

key-files:
  created: []
  modified:
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - docs/workflow.md
    - .planning/PROJECT.md

key-decisions:
  - "Phase 7 gate = Tier 1's must-match set matched (zero regressions, both EXEs SHA-1 identical) plus every tier 1-4 located and signed off; Tiers 2-4 keep matching in Milestone 2 (D-05)"
  - "AGT-11 sits on ROADMAP's Requirements line as a bare ID; the carry-in text is on its own **Carry-in** line (F25)"

patterns-established:
  - "Owner-ruling citations: (owner ruling D-NN, YYYY-MM-DD) at the end of the reworded line"

requirements-completed: [DEC-03, DEC-05, DEC-06]

coverage:
  - id: D1
    description: "REQUIREMENTS.md DEC-03 and DEC-05 reworded per D-05/D-22/D-23/D-31, citing D-05 and 2026-10-26"
    requirement: DEC-03
    verification:
      - kind: other
        ref: "grep -n 'DEC-03\\*\\*' .planning/REQUIREMENTS.md | grep -q D-05; DEC-03/DEC-05 lines contain 2026-10-26 and D-05"
        status: pass
    human_judgment: true
    rationale: "Whether the wording drops nothing D-05/D-22/D-23 did not drop (plan prohibition, verification: judgment) needs a human or the gate plan's read"
  - id: D2
    description: "ROADMAP Phase 7 SC3 and SC5 reworded; Requirements line ends with AGT-11; Carry-in line added"
    requirement: DEC-05
    verification:
      - kind: other
        ref: "grep -c 'must-match set' .planning/ROADMAP.md >= 2; SC3 keeps rebuild, cmp, zero regressions; node gsd-tools.cjs query roadmap.get-phase 7 parses all 6 criteria"
        status: pass
    human_judgment: true
    rationale: "Judgment prohibition: the rewording must not weaken the done rule beyond the owner's rulings"
  - id: D3
    description: "docs/workflow.md Phase 7 roadmap row and the D-06/D-24 decomp.wtf record; PROJECT.md Hybrid pipeline row outcome updated"
    requirement: DEC-06
    verification:
      - kind: other
        ref: "grep -q 'spike 006 stands' docs/workflow.md .planning/PROJECT.md; ! grep -q 're-evaluated for Phase 7'; one '| Hybrid pipeline' row; D-24 next to the private views sentence"
        status: pass
      - kind: unit
        ref: "uv run pytest -q tests/test_hygiene.py tests/test_listings.py (104 passed, 3 container-only skips)"
        status: pass
    human_judgment: false

duration: 7min
completed: 2026-10-27
status: complete
---

# Phase 7 Plan 01: D-05/D-06 paperwork Summary

**The Phase 7 done rule now reads "Tier 1's must-match set matched (hub rule D-22, asm rows out D-23, entries always in D-31), zero regressions, both EXEs SHA-1 identical, every tier 1-4 signed off" in REQUIREMENTS DEC-03/DEC-05, ROADMAP SC3/SC5 and the docs/workflow.md roadmap row. Each reworded line cites owner ruling D-05 (2026-10-26). decomp.wtf is recorded as not re-evaluated (spike 006 stands, D-06), with one checkout and private views (D-24).**

## Performance

- **Duration:** 7 min
- **Started:** 2026-10-27T14:50:58Z
- **Completed:** 2026-10-27T14:57:47Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- DEC-03 now names Tier 1's must-match set (entry functions plus callees down to the signed hub rule, minus owner-signed asm rows). It keeps objdiff 100%, the relocation check, both EXEs SHA-1 identical and zero regressions, adds Tiers 1-4 located and signed off, and says Tiers 2-4 keep matching in Milestone 2.
- DEC-05 and SC5 now ask for per-item coverage with both the must-match and full-closure figures, asm rows as their own group, and the located and signed-off state for tiers not matched yet.
- SC3 keeps `rebuild` plus `cmp` silent for both EXEs with zero regressions. It is now scoped to the must-match set and adds the tier sign-off.
- ROADMAP's Phase 7 Requirements line now ends in `AGT-11`. A new `**Carry-in**:` line keeps the 10 unattended matches (3/10 so far) in the phase.
- The docs/workflow.md Phase 7 row has the same gate. The Phase 6 decomp.wtf paragraph and the PROJECT.md Hybrid pipeline row now close the "re-evaluate for Phase 7" note.

## Task Commits

1. **Task 1 (tracer): reword the Phase 7 done rule** - `8d846d4` (docs)
2. **Task 2: record D-06/D-24** - `5fa287e` (docs)

**Plan metadata:** this SUMMARY commit (docs)

## Files Created/Modified
- `.planning/REQUIREMENTS.md` - DEC-03 and DEC-05 reworded (only these two lines)
- `.planning/ROADMAP.md` - Phase 7 Requirements line, new Carry-in line, SC3 and SC5 (the F6 exemption; nothing else touched)
- `docs/workflow.md` - L64 decomp.wtf sentence replaced; L256 Phase 7 roadmap gate cell reworded
- `.planning/PROJECT.md` - Hybrid pipeline row, Outcome cell clause replaced

## Decisions Made
- The rewording kept "zero regressions", "both EXEs SHA-1 identical", the relocation check and `rebuild` + `cmp` (T-07-02). AGT-11's 10 unattended matches are kept through the Requirements and Carry-in lines. The readlint and stats parts of D-05 stay in SC4/SC6, DEC-04 and DEC-07, which this plan did not change.
- The tracer feedback gate ran in interactive, end-of-phase mode with an automated-only verify: I re-ran the verify, it passed, and I went on to Task 2 without a checkpoint. GSD's own parser (`roadmap.get-phase 7`) still reads all 6 success criteria after the edit.

## Deviations from Plan

### Orchestrator rulings applied

**Orchestrator ruling F6:** a named exemption for `.planning/ROADMAP.md`. I edited only the Phase 7 `**Requirements**:` line, success criteria 3 and 5, and the new `**Carry-in**:` line. I made no other ROADMAP edit, did not touch STATE.md, and did not run the plan-progress update.

**Orchestrator ruling F25:** the Requirements line stays a bare comma list ending `..., DEC-07, AGT-11`. "AGT-11 (carried in from Phase 6, 3/10)" goes on its own `**Carry-in**:` line. Task 1's last grep became `grep -q "AGT-11"` plus `grep -q '^\*\*Carry-in\*\*: AGT-11 (carried in from Phase 6, 3/10)'`; both pass, and so does the plan's original grep.

### Auto-fixed Issues

None.

---

**Total deviations:** 0 auto-fixed; 2 orchestrator rulings applied (F6, F25).
**Impact on plan:** None beyond the rulings. The scope is unchanged.

## Verification

- Task 1 verify (with the F25 grep): PASS. Acceptance: the DEC-03 and DEC-05 lines contain `2026-10-26` and `D-05` (PASS). SC3 contains `rebuild`, `cmp` and `zero regressions` (PASS).
- Task 2 verify: the greps PASS. `uv run pytest -q tests/test_hygiene.py tests/test_listings.py` gives 104 passed and 3 skipped (`only inside the container`, existing). Acceptance: exactly one `| Hybrid pipeline` row (PASS); `D-24` sits next to the private views sentence (PASS).
- Done gate in the worktree: `uv run pytest -q` gives 2680 passed and 229 skipped. All skips are existing real-file skips (`orig/*.EXE not present`, `third_party/watcom/10.6 not installed`, `third_party/watcom-media not present`, `only inside the container` and similar) because the worktree has no gitignored game or compiler files. This plan adds no tests, so no skip reason is new. `uv run ruff check .`: All checks passed.
- Container step deferred to the orchestrator (R-B): `docker compose run --rm test`. This plan changes docs only.

## Issues Encountered
- The worktree-isolation harness refused shell commands that combine `git rev-parse --git-dir` with writes. So the plan-commit ledger (base `0f9de36`) was kept in the session scratchpad rather than under the git dir. `commits: 2` was measured with `git rev-list --count 0f9de36..HEAD`.

## User Setup Required

None. No external service configuration is needed.

## Next Phase Readiness
- VERIFICATION.md and the gate plan 07-41 can check the D-05 wording now. 07-15 (coverage view) and 07-22 (Tier 1 sign-off, hub rule) build on the must-match/full-closure split written here.
- The orchestrator still needs to: update the plan checkbox and progress for ROADMAP and STATE, and mark DEC-03/DEC-05/DEC-06 complete in REQUIREMENTS once their sibling plans finish. Those IDs are shared with many Phase 7 plans, so this plan does not mark them.

Execution context nonce: 4e4a84359403051a

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*

## Self-Check: PASSED
- FOUND: .planning/REQUIREMENTS.md, .planning/ROADMAP.md, docs/workflow.md, .planning/PROJECT.md (modified)
- FOUND: 8d846d4, 5fa287e (ancestors of HEAD)
