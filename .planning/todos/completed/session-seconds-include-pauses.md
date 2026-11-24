---
title: Session times may include usage-limit pauses
created: 2026-11-23
area: driver
files: tools/reverseapoc/driver.py, docs/workflow.md, tests/test_driver.py, tests/test_driver_workers.py
source: drive logs of 20261120-codex2, 20261121-codex, 20261123-codex
---

# Sessions far past the 30-minute cap

**Why.** Drive log end lines report sessions far beyond the session time limit, for example
`ufo2p func_0006F830 attempt 1/3 (gpt-6.1-sol): MATCHED after 16357.9 s` (20261120-codex2) and
`ufo2p func_00075310 attempt 3/3 (gpt-6.1-terra): PARTIAL after 20502.7 s` (20261121-codex). Both
spanned a 5-hour usage-limit pause, so the backoff wait seemed to be counted as session time.

## Resolution (2026-11-23): the records were never skewed; only the console line changed

### Measured

| attempt | console "after" | span in the log | record `seconds` | record `duration_ms` | logged backoffs |
| --- | --- | --- | --- | --- | --- |
| ufo2p func_0006F830 attempt 1, 20261120-codex2-gpt-6.1-sol, MATCHED | 16357.9 s | 03:29:35 to 08:02:13 | 259.2 | 259201 | 47 waits, 13620 s |
| ufo2p func_00075310 attempt 3, 20261121-codex-gpt-6.1-terra, PARTIAL | 20502.7 s | 18:49:23 to 00:31:08 | 711.8 | 711764 | 4 waits, 720 s |

- The records hold the counted session alone (`_launch`: `seconds` from just before the
  session to its end; `duration_ms` is the CLI's own figure, and both agree). The console line
  (`_announced`) was the attempt's wall time: every LIMIT relaunch, every backoff, the time the
  worker was held at its arm's pause, and the gate. For func_0006F830 that is 13620 s of its own
  backoffs plus 47 limited relaunches and the gate (about 2479 s) plus the 259.2 s session. For
  func_00075310 the worker's session ended "usage limit, the night is already paused" at
  19:02:40, and the worker was then held at the other worker's pause until about 23:48
  (no record of its own covers that hold), then slept 720 s of backoffs of its own.
- stats.py reads only records: `_wall_ms` takes `duration_ms` (or `seconds` when null) and
  `_sums` sums `seconds`. So per-session time in `stats`, the drive-worker-throughput todo and
  time-based sizing were not skewed. No figure needs re-measuring.

### Changed (test first)

`_announced` now prints the attempt's wall time less its usage-limit waits, and when it waited,
the wall time and the waits in brackets:
`PARTIAL after 612.3 s (16357.9 s wall, 15745.6 s limit waits)`. A line with no wait is
unchanged. The waits are the backoffs the worker slept (`_limited`) and the time
`_Pause.wait_to_launch` held it, both on Deps.clock, summed per attempt in `local.waited`. The
shown figure still includes limited relaunches, transient retries and the gate, so it can
exceed the record's `seconds`. docs/workflow.md ("The console") says so. The records are
unchanged.

Tests: tests/test_driver.py test_console_attempt_seconds_leave_out_limit_waits (renamed from
test_console_attempt_seconds_cover_relaunches_and_backoffs; it also pins the record's 45 s),
tests/test_driver_workers.py test_console_seconds_leave_out_a_wait_at_another_workers_pause
(fails with the hold left out of the waits).
