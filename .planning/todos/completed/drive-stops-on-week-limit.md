---
title: A drive whose arms have used up the week keeps probing until the reset
created: 2026-11-24
area: driver
files: tools/reverseapoc/driver.py, tools/reverseapoc/codexjson.py, docs/workflow.md, tests/test_codex.py, tests/test_driver.py, tests/fixtures/codex/limit_*.jsonl
source: runs 20261120-codex, 20261121-codex, 20261124-codex2 (2026-11-20 to 24)
---

# Probing for days

**Why.** A Codex usage-limit message says either "try again at 10:32 AM" (the 5-hour window) or
"try again at Nov 25th" (the week). The driver treats both the same way: the arm pauses, then
launches a probe every 300 s until a session gets through. When the week is used up, that means a
probe every 5 minutes per worker for days (the week resets 4 d 12 h after 2026-11-24 11:16), with
each probe leaving an `attempt-N-uncounted-K` directory. The night ends only when the owner or the
orchestrator sends a Ctrl-C after reading a transcript by hand (owner pre-authorized that on
2026-11-24).

**Do.** Test first, with the Codex classifier's fixtures: tell a dated limit ("try again at <month>
<day>") from a timed one, and record the reset the message names. When every arm of the night is
blocked by a dated limit, end the night with STOPPED `quota-exhausted`, naming each arm and its
reset, and run the end-of-run checks as for ENDED. If only some arms are out for the week, the
other arms go on and the exhausted arm stops launching. Check the Claude, agy and Copilot limit
texts for the same distinction, and keep any harness without one on today's behaviour.

**Done when.** A drive whose arms all hit a dated limit ends by itself with a STOPPED
`quota-exhausted` record, an arm out for the week stops probing while the others run, and tests
pin both.

## Resolution (2026-11-24)

### What the transcripts showed

The 20261120-codex2 to 20261124-codex2 transcripts hold eight timed resets ("try again at 10:32
AM") and three dated ones. One dated reset is not the week: at 22:29 on 2026-11-20 the 5-hour
window said "try again at Nov 21st, 2026 2:46 AM". Codex writes the date whenever the reset
falls on another day, so a window that crosses midnight is dated too. A dated reset is read as
the week only when it is more than 5 hours after the local clock.

### The change

- `codexjson.week_reset(events, now)`: the reset text ("Nov 25th, 2026 10:32 PM") of a usage
  limit whose dated reset is more than 5 hours after `now`, else None. A timed reset, a dated
  one inside the window, a date that does not parse, or no limit all give None.
- `Deps.local_now` (default `datetime.now`) is the clock it reads, because Codex writes the
  reset in local time.
- `_Night._week_out`: a Codex LIMIT session with a week reset sets `_Lane.week_reset`. That
  closes the arm. It sleeps no backoff, takes no probe and launches nothing more
  (`_lane_end`, `_halt_if_closed`, and a check after a pause wait that hands back a probe
  taken meanwhile), and the quiet `_ArmClosed` halt ends the pass, inline too. The console line
  and the run record's detail say "<label>: arm <arm> is out of quota until <reset> (past its
  5-hour window); it launches nothing more". The other arms go on. On a cascade night, the
  LIMIT is recorded and handed off as before, and the closed arm is skipped as capped.
- `_end`: when every arm (the cascade's arm lanes, else the night's lanes) has a week reset,
  the night ends `QUOTA_EXHAUSTED` = "quota-exhausted". `_run_locked` records it as STOPPED,
  but only after the end-of-run checks, and with the status tables and feed committed and no
  `uncommitted` rows, as for an ENDED night. Exit code 1, as for any STOPPED.
- `RUN_REASONS[STOPPED]` takes "quota-exhausted". docs/workflow.md "End of run" names the
  exception.
- Claude, agy and Copilot keep today's behaviour. Their limit texts in the code, the fixtures
  and the drive transcripts carry no dated or timed reset to tell apart.

### Tests

- tests/fixtures/codex: limit_week.jsonl, limit_window.jsonl and limit_window_dated.jsonl.
  These are synthetic, in the real error plus turn.failed shape.
- tests/test_codex.py: test_a_dated_usage_limit_more_than_five_hours_away_is_the_week,
  test_a_timed_usage_limit_is_the_five_hour_window,
  test_a_dated_reset_inside_five_hours_is_the_window_past_midnight,
  test_no_week_reset_without_a_usage_limit (3 cases),
  test_a_night_whose_every_arm_is_out_for_the_week_stops_quota_exhausted (Night harness, one
  Codex arm: STOPPED quota-exhausted, end-of-run checks run, one launch, no sleep),
  test_an_arm_out_for_the_week_stops_while_the_others_run (Luna and Haiku: Luna launches once,
  Haiku's attempt runs, ENDED queue exhausted, with Luna's reset in the detail),
  test_a_timed_codex_limit_still_backs_off_and_probes (60 then 120 s, each probe a launch).
  The two night tests fail, rather than hang, when `_week_out` is disabled: a capped sleep
  seam (`_probes_capped`) ends a probing night STOPPED `error`.
- tests/test_driver.py: the Night harness passes a fixed `local_now` (2026-11-24 11:16).

Not covered: several workers of one arm while it closes. The check after a pause wait is there
for that case, but no test runs it.
