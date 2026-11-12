---
phase: quick-batch-261112-fdr
fixed_at: 2026-11-12T00:00:00Z
review_path: .planning/quick-batches/261112-fdr/REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
bundle_nonce: 702d1138a9e2
---

# Quick batch 261112-fdr: Code Review Fix Report

**Fixed at:** 2026-11-12
**Source review:** .planning/quick-batches/261112-fdr/REVIEW.md
**Iteration:** 1
**Scope (coordinator):** WR-01, WR-02, WR-03, IN-03, IN-04, IN-05. IN-01, IN-02, IN-06 and IN-07
are unchanged, as instructed.

**Summary:**
- Findings in scope: 6
- Fixed: 6 (WR-01 to WR-03 and IN-04 change scheduling logic: requires human verification)
- Skipped: 0

**Where verification ran:** in this agent's worktree (`.claude/worktrees/agent-a24cc0cd7f664b4ec`,
branch `worktree-agent-a24cc0cd7f664b4ec`). I did not create a second GSD worktree, because the
coordinator dispatched me into this one. `uv run pytest -q` (with
`REVERSEAPOC_WATCOM_DIR=../../../third_party/watcom`) and `uv run ruff check .` ran here.

## Fixed Issues

### WR-01: A tier pick waiting on a busy arm starved its whole unit

**Files modified:** `tools/reverseapoc/picker.py`, `tools/reverseapoc/driver.py`,
`tests/test_driver_workers.py`
**Commits:** 2c37217f (RED), 035c9af6 (GREEN)
**Applied fix:** `TierQueue.next_item` and `next_eligible` take a keyword `skip` (function
keys). `_Coordinator._tier_pick` now skips a waiting pick by `(exe, start)`, not by
`(exe, unit)`, so the other functions of its unit stay eligible. Pool mode was already correct
and is unchanged. Test: H (large, SONNET with max_workers 1) runs, F (large, F's unit) waits for
SONNET, and G (small, F's unit) must start on HAIKU while H's session is held open. On the old
code G never started within WAIT_S.
**Status:** fixed: requires human verification (scheduling logic)

### WR-02: A cascade LIMIT launch did not count toward --arm-cap

**Files modified:** `tools/reverseapoc/driver.py`, `tests/test_driver_workers.py`,
`tests/fixtures/agy/gemini_quota_limit.jsonl` (new, synthetic events only)
**Commits:** 1a9f1bb5 (RED), 19acb561 (GREEN)
**Applied fix:** option (a). In `_cascade_limited`, a LIMIT launch that is not a salvaged match
(a salvaged match is already `_count`ed) gives its reserved slot back and adds one to the arm
lane's `spent`, in one hold of the condition. It adds nothing to the night's `spent` or
`sessions`, so `--max-sessions` and the match counts are unchanged.

I chose (a) over (b) for three reasons:
- It matches the help text literally: "arm NAME launches at most N sessions tonight".
- It is one counter on the existing `spent` shape, with no new state.
- (b) would retire an arm on its first LIMIT. On the owner's run every arm has a cap, so (b)
  would also retire Haiku and Terra on a passing 5-hour window, which D-07 says should be
  probed.

The cost of (a) is the side effect the reviewer named: Haiku's and Terra's limit probes use up
their caps. That cost is also what ends IN-04's night.

Test: row (GEMINI, HAIKU), `--arm-cap gemini-flash=1`, and every agy session ends LIMIT through
the new fixture. With the backoff running out on a ticking clock, the old code launched agy 3
times. Now it launches agy once, and the later picks skip GEMINI as capped.
**Status:** fixed: requires human verification (cap accounting)

### WR-03: A night with every arm capped dispatched every remaining pick and ended QUEUE_EXHAUSTED

**Files modified:** `tools/reverseapoc/driver.py`, `tests/test_driver_workers.py`,
`docs/workflow.md`, `docs/model-routing.md`
**Commits:** 30b1c54e (RED), d4d282a4 (GREEN)
**Applied fix:**
- New end reason `ARMS_CAPPED = "arms capped"`, added to `RUN_REASONS[ENDED]` so the run
  record validates.
- `_Night._end()` returns it once every cascade arm lane is `_lane_end`. It is checked after
  TARGET_MATCHED and MAX_SESSIONS. A night without --cascade has no arm lanes and never takes
  this branch.
- Passes still running finish. `_next` dispatches nothing more, and the normal end of run
  follows: end_of_run, the ENDED run record, the attempt-log commit. The test checks all three.
- Documented in the End of run paragraph of docs/workflow.md and in a new "The end" bullet in
  docs/model-routing.md.

Two existing cascade tests (not non-cascade tests) had every routing arm capped, so they now
ended ARMS_CAPPED before printing the per-pick cap line they pin:
- `test_cascade_arm_cap_holds_the_function_for_tonight`
- `test_cascade_arm_cap_mid_pass_leaves_the_tier_queue`

Each now gives the large row an uncapped arm that its 20 B picks never use. That keeps the
"one row capped, another arm can still run" case, where the review says the cap line stays.
Their assertions are otherwise unchanged.
**Status:** fixed: requires human verification (end-of-night logic)

### IN-04: The owner's three-arm night could poll forever

**Files modified:** `tests/test_driver_workers.py`, `docs/model-routing.md`
**Commits:** 97e09296 (pin test), e897196c (docs)
**Applied fix:** no extra driver code. WR-02 (each limit probe uses a slot of the paused arm's
cap) and WR-03 (end once every arm is capped) together end the night once the paused arm is
capped too. The paused-night backoff and probe behaviour is unchanged.

The test: the owner's row shape with SONNET in Terra's place, caps HAIKU 2, SONNET 3, GEMINI 1,
medium picks only, and every SONNET and agy launch ends LIMIT. The night ENDS ARMS_CAPPED, each
arm launched exactly its cap, and no worker slept. A launch guard (18 launches) makes a
regression fail instead of hang.

The test passed on arrival, so its commit is a pin, not a RED. I saw it fail for the right
reason with each fix undone locally (not committed):
- WR-02's `lane.spent += 1` removed: the guard trips, STOPPED error at 18 launches.
- WR-03's `return ARMS_CAPPED` removed: the night ends QUEUE_EXHAUSTED.

docs/model-routing.md now says, beside the owner's command, how such a night ends: under two
hours of Terra polls when its week is used up. It also says, under Caps, that a LIMIT launch
counts against `--arm-cap`.
**Status:** fixed: requires human verification

### IN-03: `_cascade_slot`'s docstring claimed a retry keeps the probe

**Files modified:** `tools/reverseapoc/driver.py`
**Commit:** b8b5a09c (docstring only: no RED is possible)
**Applied fix:** the docstring now says that a transient probe is itself a verdict (`_attempt`
runs `on_clear` and clears `local.probe` before its transient branch), so a retry never holds
the probe and asks `try_launch` again. No code changed.

### IN-05: The dry-run preview ignored the caps

**Files modified:** `tools/reverseapoc/driver.py`, `tests/test_drive.py`, `docs/model-routing.md`
**Commits:** 451922d9 (RED), 451c6f43 (GREEN)
**Applied fix:** the coordinator asked that the preview honour `--arm-cap` (the reviewer had
suggested only a "rung" label). `_cascade_previews` now walks the dry run's picks in order:
- Each attempt it shows counts one launch of its arm against `_arm_caps`: `--arm-cap`, else
  `max_sessions`, else no cap. This is the same rule `_Night` uses, and `_cascade_line` now
  shares the helper.
- An attempt routes past a capped arm through `arms_for_attempt`, as the night does, and is
  shown as `<arm> (<arm> capped, ...)`.
- An attempt whose whole row is capped is shown as `every arm capped` (`PREVIEW_ROW_CAPPED`),
  which ends that pick's list, as ARM_CAPPED ends its pass.

Pauses and busy arms are not previewed. With no cap reached the output is byte-identical to
before: the existing dry-run test is unedited and green.

Tests: a unit test of the three forms, and a Rig dry run with every arm capped at 1. On the old
code that dry run showed 30 launches across two arms.

## Unchanged (as instructed)

- IN-01: the gap between a transient retry's spend and its re-reserve.
- IN-02: HANDOFF_LINE can name the arm that just hit the limit.
- IN-06: slot lines A to C admit more than their probes measured.
- IN-07: `_Lane.live_cap`'s "None" wording.

## Verification

- Every RED test was seen failing for the right reason before its GREEN:
  - WR-01: G never started.
  - WR-02: 3 agy launches against a cap of 1.
  - WR-03: ENDED queue exhausted instead of arms capped. I checked this with the reason
    string inlined in a temporary edit, because the RED's first error is the missing
    constant.
  - IN-05: 30 launches with caps of 1.
- Non-cascade tests: unedited. ARMS_CAPPED requires a non-empty `arm_lanes`, and the WR-02
  count runs only in the cascade LIMIT branch.
- Full suite and ruff: see the final lines in the hand-off.

---

_Fixed: 2026-11-12_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
