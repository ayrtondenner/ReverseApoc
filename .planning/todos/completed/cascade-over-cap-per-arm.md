---
title: Cascade nights use the over-cap verdicts per arm
created: 2026-11-24
area: driver
files: tools/reverseapoc/driver.py, tests/test_driver_workers.py, docs/workflow.md
source: todo over-cap-rows-open-every-night ("Not on a cascade night"), owner batch 2026-11-24
---

# A cascade night saves over-cap verdicts but never acts on them

**Why.** The over-cap verdicts of build/driver/over-cap.json are kept per (exe, start, arm).
A plain or `--arm` night skips a row on the arm whose verdict is current. A cascade night only
saved them: its pass is the whole row of arms, and skipping the pick would skip it for the
arms that have no verdict too. So every cascade night packed those rows again on the arms
already known to be over the cap.

**Done when.** On a cascade night, an attempt on an arm with a current verdict for its row
passes to the row's next arm without building the pack, and a test pins it.

## Owner ruling (2026-11-24)

On a cascade night, a row's attempt on an arm with a current over-cap verdict for that row
passes straight to the row's next arm, as an arm that is capped or spent already does, without
building the pack. It spends no slot and prints one line. If every arm of the row has a
verdict, the row is left for tonight, as a lone over-cap row is.

Same batch: a damaged or unreadable over-cap.json no longer refuses the drive. One warning line
names the file and the night starts with no verdicts; a verdict it keeps rewrites the file.

## Resolution (2026-11-24)

- **The arms.** Before each cascade attempt is routed, `_Night._over_cap_arms(pick)` reads the
  verdicts of the pick's row (backends.route_for) and, only when one exists, the pick's pack key
  (`_pack_key`, under the gate lock, outside the night's condition). The arms whose verdict's
  key is the key now go in `local.over_cap_arms`, cleared when the pass ends.
- **The routing.** `_route_slot` skips such an arm before `_cascade_slot` asks it for a slot,
  listing it as "<arm> (over cap)", so the attempt's one ARM_SKIP_LINE names it next to capped
  and paused arms (`label (THE_ARM_THAT_TOOK_IT): skipped SONNET (over cap)`). A verdict arm
  counts as capped for the row's end: verdict and capped arms only end ARM_CAPPED; with a
  paused arm, ARM_WAITING. A row of nothing but verdict arms ends KNOWN_OVER_CAP at once: no
  claim, view, pack or line of its own, counted in `known_skips` (the end-of-night "skipped N
  picks known over the pack cap" line) and `over_caps` (the report). The coordinator parks it
  on the dispatch lane, as a lone over-cap row is.
- **The dispatch filter.** `_arm_state` passes an arm with any kept verdict for the row as it
  passes a capped one, without reading the key (it runs under the night's condition for every
  queued pick). So a pick whose free arm has a verdict and whose other arm is busy waits
  instead of being dispatched to skip again round after round. A stale verdict only makes the
  pick wait for its row's other arms; a row of verdicts and capped arms is ARM_CAPPED, which is
  dispatched, so the routing reads the keys and runs the stale arm.
- **The cache.** `load_over_caps` also turns an OSError into its DriverError; the drive's start
  prints `warning: <path> is not an over-cap list: <why>; starting with no over-cap verdicts`
  and goes on with none. The "over-cap list" REFUSED reason is gone.
- `_known_over_cap` still returns False on a cascade night: the routing handles it there.
- docs/workflow.md: the over-cap bullet says both.

### Tests (tests/test_driver_workers.py)

- `test_a_cascade_attempt_passes_an_arm_with_a_verdict_to_the_rows_next_arm`: row (HAIKU,
  SONNET), a SONNET verdict; all three attempts run on HAIKU, SONNET launches nothing, attempts
  2 and 3 print one skip line each, SONNET's verdict stays.
- `test_a_cascade_verdict_with_a_stale_key_skips_nothing`: the row climbs as before and SONNET's
  fitting pack drops its verdict.
- `test_a_cascade_row_with_a_verdict_on_every_arm_is_left_for_tonight` (pool and tier queues):
  no pack, no claim, no session, only the summary line, report.over_cap 1, the night ENDS.
- `test_arm_state_passes_an_arm_with_a_verdict` (free, busy, paused, capped other arm).
- `test_a_bad_over_cap_file_is_read_as_empty_with_a_warning` (not JSON, a bad entry) replaces
  `test_a_bad_over_cap_file_refuses_the_night`; `test_an_undecodable_over_cap_file_is_a_driver_error`.
- `test_a_cascade_night_never_skips_on_a_kept_verdict` is gone: its one-arm row with a current
  verdict is now the every-arm case.
