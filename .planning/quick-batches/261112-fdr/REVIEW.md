---
phase: quick-batch-261112-fdr
reviewed: 2026-11-12T00:00:00Z
depth: deep
files_reviewed: 17
files_reviewed_list:
  - tools/reverseapoc/driver.py
  - tools/reverseapoc/session.py
  - tools/reverseapoc/backends.py
  - tools/reverseapoc/cli.py
  - tools/reverseapoc/causes.py
  - tools/reverseapoc/slots.py
  - config/driver/backends.toml
  - tests/test_backends.py
  - tests/test_causes.py
  - tests/test_cli.py
  - tests/test_codex.py
  - tests/test_drive.py
  - tests/test_driver_workers.py
  - tests/test_session.py
  - tests/test_skill.py
  - tests/test_slots.py
  - tests/test_slots_real.py
findings:
  critical: 0
  warning: 3
  info: 7
  total: 10
status: issues_found
---

# Quick batch 261112-fdr: Code Review Report

**Reviewed:** 2026-11-12
**Depth:** deep (`git diff 8951dd96..HEAD -- tools/ tests/ config/driver/`, plus the callers and callees the diff touches: `_Pause`, `_Lane`, `_Coordinator`, `_Night` slot accounting, `TierQueue`, `search.memory_locals`, `batch._reloc_key`, `relocs` message formats)
**Files Reviewed:** 17
**Status:** issues_found

## Summary

I found no BLOCKER. I traced the locking and the slot accounting closely and found them sound:

- **Locks.** Every cascade path takes `self.cond`. It is a `threading.Condition()` with its default RLock, so the nesting in `_route_slot` → `_cascade_slot` → `_Pause.try_launch` and in `_arm_state` → `_lane_state` → `_Pause.ready` is safe.
- **Slots.** Each slot is reserved on the lane that `arm_lane` is bound to, and it is settled or released on that same lane. `_settled`'s `finally` covers every exit. I found no path that leaks `lane.reserved`. A leak there would leave an arm busy forever, so the night could not end.
- **Session counts.** No session is counted twice against `--arm-cap` or `--max-sessions`. Every `_count` call site runs on the attempt's own thread with `arm_lane` bound. The dispatch lane's counters are never bumped. `_night_totals` sums records per run id, so nothing is counted twice there either.
- **The probe.** `try_launch` runs last in `_cascade_slot`, so the probe is taken only when the slot is RESERVED. `local.probe` is cleared at every verdict, and `_hand_back` runs in `_settled`'s `finally`. I found no way for `probe_taken` to stay stuck.
- **Coordinator and worker agreement.** `_arm_state` and `_route_slot` apply the same rule to the same state, so they cannot keep disagreeing. When they disagree for a moment (a race), the result is a silent, uncounted bounce: the pick goes back through `deferred` or the tier queue.
- **Non-cascade nights are unchanged.** I checked every rewired site with `routing=()`. `arm_lane` is `self.lane`. `_settled` adds only a `_hand_back` that does nothing, because `local.probe` is always False there. `_ready`, `_tier_pick` and `_finished` reduce to their old forms. `waiting` is never set. `_retry_slot` is `_reserve`. `refuse_unproven` and `refuse_arms` reduce to their old loops. `load_arms` accepts the new `[routing]` table, and nothing else reads backends.toml directly.
- **causes.py regex.** It is linear-time. Inputs of 200 000 characters take about 30 ms, and the lookbehind confines the bare-hex branch to positions right after `at `. It folds what the fdu plan specifies.
- **slots.py predicates.** They match the plan's definitions of lines A, B and C exactly. `_TOP_SCOPE = 0` is consistent with `search._block_stacks`, which leaves the function's own block out (span[0] is the body's `{` line). `_two_arrays_then_ints` only runs when there are two or more locals, so its unpacking cannot fail.

The three WARNINGs are cascade-scheduling defects that tests built from small synthetic queues would not show:

1. In a tier queue, a waiting pick starves the other functions of its unit for as long as its arm stays busy. This is much more than "a short delay".
2. LIMIT launches do not count toward `--arm-cap`. My judgement for the owner's run follows in WR-02.
3. When every arm is capped, the owner's run ends by dispatching every remaining pick just to print a cap line, and the reason it reports is QUEUE_EXHAUSTED.

## Warnings

### WR-01: A tier pick waiting on a busy arm starves its whole unit for as long as that arm stays busy, not for one 0.2 s round

**File:** `tools/reverseapoc/driver.py:3050-3064` (`_Coordinator._tier_pick`), with `picker.py:369-375, 385-394` (`TierQueue._eligible` / `next_item`)

**Issue:** When `_arm_state(pick) == ARM_WAITING`, `_tier_pick` adds `(pick.exe, pick.unit)` to `skipped`. It then calls `next_eligible(busy | skipped)` again, and that skips every item of the unit. The next round (`_next`) starts with an empty `skipped`, but the tier order of the waiting pick has not changed: same tier, hub, aborts, passes, level and rank. So `next_item` offers the same pick first again, and the unit is skipped again.

The fds SUMMARY says the cost is only a short delay ("until the next round (0.2 s)"). In fact the starvation lasts as long as the arm stays busy. Terra has `max_workers = 1`. It is the only arm of `[256, inf)` and rung 2 of the other two rows, so on the owner's night it will be busy almost all the time.

**Failure scenario:** Unit U holds F (300 B, in the Terra-only row) and G (40 B, Haiku first). F orders before G, and Terra is running a 40-minute session for another function. For those 40 minutes every round offers F, skips U, and G never runs, though Haiku has 10 free `max_workers` and the dispatch lane has free workers. This repeats for each Terra session. Units that hold a Terra-bound function are held back for most of the night. In pool mode the problem does not occur, because `_eligible` checks `_ready` per pick.

**Fix:** Skip the waiting pick by key, not by unit. For example, give `TierQueue.next_item` a `skip_keys` argument (or add a generator over its eligible items in order), and have `_tier_pick` walk the candidates in order:
```python
skipped_keys: set[Key] = set()
while True:
    pick = lane.tiers.next_eligible(frozenset(self.busy), skip=frozenset(skipped_keys))
    if pick is None:
        return None
    if self.night.config.routing and self.night._arm_state(pick) == ARM_WAITING:
        skipped_keys.add((pick.exe, pick.start))
        self.waiting = True
        continue
    lane.tiers.take((pick.exe, pick.start))
    return pick
```
Pin it with a two-function, one-unit tier test. The first function is Terra-only with Terra held busy, and the second must launch on Haiku in the meantime.

### WR-02: A cascade LIMIT launch does not count toward `--arm-cap`, so `gemini-flash=1` can launch more than once (a real cap violation for the owner's run)

**File:** `tools/reverseapoc/driver.py:3953-3955` (`_attempt`'s cascade LIMIT branch returns before any `_count`/`_spend`), `3744-3751` (`_settled` then `_release`s the slot uncounted), `3338-3343` (`_lane_end` counts only `sessions + spent`)

**Issue:** After a LIMIT session, `_settled`'s `finally` gives the reserved slot back uncounted. `lane.sessions` and `lane.spent` therefore stay where they were, and `_lane_end(gemini)` stays False. Once the backoff runs out on the clock (60, 120, 240, then 300 s polls), `ready()` turns True. The next attempt whose rotated row reaches gemini-flash then takes the probe and launches agy again. Under the ladder, that is attempt 3 of pass 1, or any attempt of pass 2 or later, in the `[64, 256)` row.

The help text says `--arm-cap` limits launches ("arm NAME launches at most N sessions tonight"). By that wording this is a violation. The cap is not violated in the non-cascade sense: an old LIMIT relaunch kept its one slot and was counted once at the end. In the cascade, though, the slot leaves the arm, so the arm's count never sees the LIMIT launch.

**Judgement for the owner's run (Haiku 30, Terra 20, Gemini Flash 1):** this is a real violation of the owner's intent for Gemini only. docs/model-routing.md:904 says one Gemini Flash session took about 22% of its weekly group, "which is why the owner caps it at 1". Two outcomes:
- If the LIMIT means the week is used up, each probe is another agy launch that sends a context pack to Google under `--allow-egress`. Each one LIMITs again and writes a limit record. That could be about 90 launches over an 8-hour night at 300 s polls. It costs no quota, but each launch is an egress and noise in the log.
- If the LIMIT came mid-session from a shorter rate window, the session's partial work has already spent quota. A later probe then runs a full counted session, so the night spends about two sessions of Gemini quota against a cap of 1.

Haiku at 30 and Terra at 20 are not materially affected: probing a 5-hour window is the intended D-07 behaviour.

**Fix (pick one before the run):**
- (a) In the cascade LIMIT branch, count the launch on the arm only, not the night (`self.arm_lane.spent += 1` under `cond`, beside the release). A LIMIT then uses one unit of the arm's cap, and `gemini-flash=1` stops after its first launch of any kind. As a side effect, Haiku's and Terra's probes would also eat their caps.
- (b) Narrower: once a capped arm has hit a LIMIT, treat it as capped for the night (`lane.max_sessions is not None and lane limited`), so an `--arm-cap` arm is never probed.

Either way, pin it with a test: a cap-1 arm whose first session LIMITs, and the arm must launch nothing more.

### WR-03: Once every arm is capped, the owner's night dispatches every remaining pick to print one cap line, and ends QUEUE_EXHAUSTED

**File:** `tools/reverseapoc/driver.py:3019-3026` (`_ready` dispatches ARM_CAPPED picks), `3783-3795` (`_cascade_end` prints ARM_CAP_LINE), `3627-3637` (`_end` has no cap reason)

**Issue:** The owner's caps add up to 51 sessions, below `--max-sessions` 60. So `_end()` never returns MAX_SESSIONS. After Haiku, Terra and Gemini have all reached their caps, `_arm_state` answers ARM_CAPPED for every pick, and `_ready`/`_tier_pick` dispatch them by design. Each one costs a worker dispatch (a thread when `--workers` > 1) and prints one `every arm of its row has launched its cap tonight (...)` line. In tier mode each is then parked. The night ends only when the queue has been walked to its end, and the run record reports `QUEUE_EXHAUSTED`.

**Failure scenario:** On the owner's run with a few hundred eligible tier or pool picks, the console and log end with hundreds of identical cap lines, which bury the night's summary. The run record's reason hides the real one, that every arm reached its cap. This is certain to happen on the planned command line.

**Fix:** Give `_end()` a cascade reason. When every lane of `self.arm_lanes` is `_lane_end`, return a new `ARM_CAPS` reason (or reuse MAX_SESSIONS with a detail). Picks still running finish, and nothing more is dispatched. Keep the per-pick ARM_CAP_LINE for the case where only one row is fully capped.

## Info

### IN-01: A transient retry reserves its slot apart from the spend, and it aborts where a non-cascade retry would wait

**File:** `tools/reverseapoc/driver.py:3962-3969`, `3974-3979`

**Issue:** `_spend()` releases the arm's live slot and calls `notify_all`, and `_retry_slot()` then takes the condition again. In that window, another routing step (the coordinator's next dispatch, or another worker starting an attempt) can take Terra's single `live_cap` slot. The retry then gets ARM_WAITING, and the attempt ends ABORTED with an abort record. In pool mode an ABORTED pick is dropped for the night. The race is unlikely under the GIL. Separately, a retry on a cascade now aborts while a pause holds or the night's free slots are all reserved, where `_reserve` would wait. That is documented, but it means a transient error near a LIMIT costs the function its pass.

**Fix:** Spend and re-reserve in one hold of the condition: `with self.cond: self._settle(counted=False, spent=True); ok = self._cascade_slot() == RESERVED`. Optionally, end a retry that finds a paused or busy arm as ARM_WAITING with `resume`, not ABORTED.

### IN-02: HANDOFF_LINE can name the arm that just hit the limit as the receiver

**File:** `tools/reverseapoc/driver.py:3753-3772`

**Issue:** This happens when a session launched before its arm's pause ends LIMIT after the backoff has already run out on the clock. `on_limit(False)` returns None, the pause is `ready()`, and `_route_slot` reserves the same arm as the probe. The console then reads `usage limit; arm A pauses and passes this attempt to A`. The behaviour is correct (it is the probe), but the line is wrong.

**Fix:** In `_handed_off`, print the wait or probe form when `self.arm_lane.arm == arm`.

### IN-03: `_cascade_slot`'s docstring claims something `_attempt` never does

**File:** `tools/reverseapoc/driver.py:3241` vs `3960-3961`

**Issue:** The docstring says "A transient retry that still holds the probe keeps it". But `_attempt` runs `on_clear(probe)` and clears `local.probe` before its TRANSIENT branch, so a retry never holds a probe. The fds SUMMARY says the same. The code is right (a transient probe is a verdict, per D-07), but the docstring misleads anyone who edits the probe logic later.

**Fix:** Reword it: "a transient probe is itself a verdict (`on_clear`), so a retry takes a new probe through `try_launch`".

### IN-04: With every free arm capped and Terra LIMITed, the owner's night cannot end on its own

**File:** `tools/reverseapoc/driver.py:3007-3017` (`_finished`, `waiting`), `3627-3637`

**Issue:** This is the pre-existing D-08 poll-forever behaviour, but the cascade makes it likely on the owner's run. Every row contains Terra, the caps add up to less than `--max-sessions`, and LIMIT launches are not counted (WR-02). Suppose Haiku and Gemini are capped and Terra hits a weekly or 5-hour limit. Every row is then "not all capped", so `_arm_state` answers ARM_WAITING, `waiting` (or `deferred`) keeps the night open, and Terra probes every 300 s.

**Fix:** None is needed for correctness. Mention it beside the owner's command in docs/model-routing.md, or fold it into WR-03's `_end` reason, for example by ending when every arm is capped or paused and the streak has passed BACKOFF_S.

### IN-05: The dry-run preview ignores caps and skips

**File:** `tools/reverseapoc/driver.py:7440-7448` (`_cascade_preview`)

**Issue:** For a `[64, 256)` function at pass 2 or later, the preview prints `attempts gemini-flash, gemini-flash, gemini-flash`, although `--arm-cap gemini-flash=1` lets at most one of them run there (the rest wrap to Haiku). The preview is honest about the ladder's rungs, but it is not what the night will do.

**Fix:** Say "rung" in the line, or append the cap (`gemini-flash (cap 1)`). Do not simulate the skips.

### IN-06: Slot lines A to C admit counts beyond the ones measured

**File:** `tools/reverseapoc/slots.py:88-117`

**Issue:** Lines A to C cover more than their probes measured:

| Line | Measured | The predicate admits |
|---|---|---|
| A | 1 to 11 shorts | any count |
| B | 1 to 3 top ints, 1 to 5 later, up to 2 later blocks | unbounded |
| C | 3 or 4 arrays, 1 or 2 ints | unbounded |

The fdx plan defines the lines this way, so this is not a deviation. But `frame_layout` turns these frames into offsets, and its own docstring says "an offset the probe proves wrong is worse than none". The coordinator's post-merge curve measurement is the backstop.

**Fix:** None now. If the curve shows a known-and-wrong frame, cap the counts with named constants as `_MEASURED_ARRAYS` does.

### IN-07: `_Lane.live_cap` is documented as possibly None, which would crash

**File:** `tools/reverseapoc/driver.py:2787-2789, 2807` vs `3248` and `3285`

**Issue:** The docstring says live_cap is "None: its own workers bound it". But `_cascade_slot` and `_lane_state` compute `lane.reserved >= lane.live_cap`, which raises TypeError on None. This is unreachable today: every arm lane takes `max_workers`, which backends requires, and `_cascade_slot` only runs on a bound arm lane. It is a trap for later edits.

**Fix:** Drop the None wording from the docstring, or guard with `lane.live_cap is not None and ...`.

---

Not findings (checked):
- `causes._HEX_ADDRESS` is case-sensitive about `0x` and `at`, but relocs.py only writes lowercase `0x` (`_va`, `#x`), and the bare-`at` branch is in the plan and pinned.
- `reloc["problems"][:1]` is the same as before, because `batch._reloc_key` already reads only `problems[0]`.
- `func_XXXXXXXX_` names keep their digits on purpose (fdu plan).
- `_stop_arm`'s `len(self.lanes) == 1` makes a hook-denied write stop the whole cascade drive, which is fail-closed and documented.
- YAGNI: nothing material. The `arms=` parameter of `load_routing` is used only by tests, which is minor. The arm-cap check is repeated in cli `_arm_cap_conflict` and driver `_refuse_arm_caps`, which is defence in depth.

_Reviewed: 2026-11-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
