---
phase: 07-mechanics-first-decompilation
plan: 33
subsystem: cflags
tags: [d-14, d-33, cflags, default, owner-ruling, flags]

requires:
  - phase: 07-29
    provides: "two landed per-unit rules F-0001, F-0003 (wcc386@10.6 -4r -oneatx -s -fpi), 4 flag-approved functions"
  - phase: 07-24
    provides: "flags default --rule SPEC --by NAME --evidence (D-33 bar, writes nothing)"
provides:
  - "D-33 evidence for the only landed rule spec: bar not met (2 of 3 qualifying functions, 2 EXE regions)"
  - "Owner ruling: keep the `*` default wcc386@10.6 -4r -s -fpi in Phase 7 (2026-10-31)"
  - "docs/toolchain.md ### Phase 7 flag rules: the outcome sentence and a corrected D-33 paragraph"
affects: [07-matching-nights, cflags default, docs/toolchain.md]

actuals:
  tokens: 540
  tasks: 3
  commits: 1
plan_head_before: 7d2b21c92ef10d42f9c1e2df9c4d096113c4ed7c
plan_head_after: 53b5b3f0abfa66764dad6099ab7ebf658dd3f5b1

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified: [docs/toolchain.md]

key-decisions:
  - "The `*` default stays `wcc386@10.6 -4r -s -fpi` for Phase 7, kept by owner ruling 2026-10-31 (D-14, D-33): the candidate -4r -oneatx has 4 agreeing functions but only 2 qualify (func_00026FF0 branch, func_0006FC00 64 B) from 2 EXE regions"
  - "The 64-byte size is the planner's bar (07-24's D33_MIN_BYTES), not D-33's own wording; docs/toolchain.md now says so"

patterns-established: []

requirements-completed: [DEC-03]

coverage:
  - id: D1
    description: "D-33 evidence printed for the most common landed rule, with the plain verdict 'bar not met'"
    requirement: DEC-03
    verification:
      - kind: other
        ref: "uv run reverseapoc flags default --rule \"wcc386@10.6 -4r -oneatx -s -fpi\" --by \"Read Only\" --evidence (build/gate/07-evidence/33-evidence.txt, exit=0); Task 1 automated verify"
        status: pass
    human_judgment: false
  - id: D2
    description: "Owner ruled 'keep' at the blocking-human checkpoint"
    verification: []
    human_judgment: true
    rationale: "An owner decision (D-14); relayed by the orchestrator, not verifiable by a test"
  - id: D3
    description: "docs/toolchain.md records the outcome ('kept by owner ruling 2026-10-31') and the corrected D-33 wording; the committed `*` rule matches"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "uv run pytest -q tests/test_hygiene.py (77 passed, 3 skipped: only inside the container)"
        status: pass
      - kind: other
        ref: "grep -qE '(flipped to|kept by owner ruling)' docs/toolchain.md; grep -n '^\\*' config/cflags.txt"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-10-31
status: complete
---

# Phase 7 Plan 33: The `*` default ruling (D-14, D-33) Summary

**D-33's bar is not met for `wcc386@10.6 -4r -oneatx -s -fpi`, the rule both landed proposals share. Four functions agree with it, but only func_00026FF0 (branch) and func_0006FC00 (64 bytes) qualify, and they sit in only 2 EXE regions. The owner ruled "keep", so the `*` default stays `wcc386@10.6 -4r -s -fpi` for Phase 7. docs/toolchain.md records that and now names 64 bytes as the planner's bar, not D-33's wording.**

## Performance

- **Duration:** about 25 min of execution, spread over the owner checkpoint
- **Started:** 2026-10-30 (Task 1); resumed 2026-10-31T03:30:24Z (Task 3)
- **Completed:** 2026-10-31
- **Tasks:** 3 of 3
- **Files modified:** 1 tracked (docs/toolchain.md), plus gitignored evidence

## Accomplishments

- **Task 1 (tracer).** Two proposals have status "landed", F-0001 (tacp u_0006fbd0) and F-0003 (ufo2p u_00026dd0), and both share `wcc386@10.6 -4r -oneatx -s -fpi`. The `flags default --evidence` output for that rule:

  | Function | EXE | Size | Branch/loop | Region | Qualifies |
  |---|---|---|---|---|---|
  | func_00026FD0 | ufo2p | 32 B | no | 0x00020000 | no |
  | func_00026FF0 | ufo2p | 43 B | yes | 0x00020000 | yes (branch) |
  | func_0006FBD0 | tacp | 48 B | no | 0x00060000 | no |
  | func_0006FC00 | tacp | 64 B | no | 0x00060000 | yes (64 B) |

  The verb's verdict was "D-33 bar not met: only 2 of them have a branch or loop or at least 64 bytes; D-33 needs 3". Both EXEs are covered, but there are only 2 distinct (EXE, region) pairs.
- **Task 2 (owner).** The orchestrator relayed the owner's ruling, quoted here: **"keep". The `*` default stays `wcc386@10.6 -4r -s -fpi` for Phase 7.** The ruling date is 2026-10-31: the question was asked late on 2026-10-30 and answered after midnight. Only "keep" was offered, because the bar is not met.
- **Task 3.** I added the outcome sentence to docs/toolchain.md `### Phase 7 flag rules`: "The `*` default `wcc386@10.6 -4r -s -fpi` was kept by owner ruling 2026-10-31 for Phase 7 (D-14, D-33)." I also fixed the D-33 paragraph. It now gives D-33's own wording ("a branch or loop, or of a minimum size the planner sets") and says the planner set 64 bytes in `flags default` (07-24). Nothing was flipped, so no gate or ninja run was needed. `grep -n '^\*' config/cflags.txt` prints `*  wcc386@10.6  -4r -s -fpi`, which matches the sentence.

## Task Commits

1. **Task 1: D-33 evidence.** No commit; the plan asks for none. The evidence is gitignored and the tree stayed clean.
2. **Task 2: owner ruling.** No commit; this was the owner's decision.
3. **Task 3: record the outcome.** `53b5b3f` (docs).

**Plan metadata:** this SUMMARY's own commit, `docs(07-33): complete the cflags default ruling plan`.

## Files Created/Modified

- `docs/toolchain.md`: the corrected D-33 paragraph and the 07-33 outcome sentence.
- Gitignored evidence:
  - `build/gate/07-evidence/33-evidence.txt`: the verb output plus `exit=0`.
  - `build/gate/07-evidence/33-summary.txt`: the candidate, the agreeing functions, the D-33 conditions and "bar not met".

## Decisions Made

- I took the candidate from the landed rows of the queue. Both landed rows share the same spec, so there was only one choice.
- I used the owner's ruling date, 2026-10-31, as the orchestrator directed.

## Deviations from Plan

**1. [Rule 3 - Blocking] `flags default` requires `--by` even with `--evidence`**
- **Found during:** Task 1
- **Issue:** The plan's command `flags default --rule "<spec>" --evidence` leaves out `--by`, which argparse requires.
- **Fix:** I passed `--by "Read Only"`, as 07-24's read-only run did. Evidence mode writes nothing, and config/cflags.txt kept the same sha1sum.
- **Files modified:** none
- **Committed in:** n/a

**2. [Dispatch note] D-33 wording correction**
- The orchestrator asked me to correct the docs/toolchain.md D-33 paragraph in this plan. It had stated 64 bytes as if D-33 itself said so, but 64 bytes is the planner's number. I did that in the Task 3 commit `53b5b3f`.

**Total deviations:** 1 auto-fixed (blocking), plus 1 dispatch-directed doc fix. **Impact:** no scope change.

## Issues Encountered

None.

## User Setup Required

None: no external service configuration required.

## Next Phase Readiness

- The matching nights start under the unchanged default `wcc386@10.6 -4r -s -fpi`. Units that need other flags keep going through per-unit proposals (D-12).
- A later flip needs at least one more qualifying `-4r -oneatx` match, with a branch or loop or 64 bytes or more, from a third EXE region.

## Verification

- Task 1 verify: PASS. The summary is present, it says "bar not met", and the tree was clean.
- Task 3 verify: PASS. The outcome sentence is present, and the hygiene tests passed (77 passed, 3 skipped: only inside the container). No gate log exists, because nothing was flipped.
- `uv run ruff check .`: All checks passed.
- Acceptance: config/cflags.txt is unchanged, and its `*` line is `*  wcc386@10.6  -4r -s -fpi`.

## Self-Check: PASSED

- FOUND: docs/toolchain.md (contains "kept by owner ruling 2026-10-31")
- FOUND: build/gate/07-evidence/33-evidence.txt, 33-summary.txt
- FOUND commit 53b5b3f (ancestor of HEAD)

EXECUTION-CONTEXT-END-NONCE: d3dbcd4a99d4cc1d

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-31*
