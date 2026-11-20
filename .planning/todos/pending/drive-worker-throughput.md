---
title: How many parallel sessions this machine runs before sessions slow down
created: 2026-11-20
area: driver
files: config/driver/backends.toml, docs/model-routing.md
source: run 20261119-claude (Opus 10 + Sonnet 10 workers)
---

# Twenty sessions at once were CPU-bound

**Why.** Run 20261119-claude ran 20 Claude sessions at once; the drive log timed sessions at 1,400-3,000 s from launch to end (records: Opus median 7.6 min, Sonnet 20 min, 8 of 62 at the 30-minute limit)
against roughly 6-10 minutes on lighter nights, and only 62 sessions finished in about 2 hours. Each
attempt check compiles and diffs in Docker, so wall time per session grows with the number in flight
and sessions per hour stop rising. Quota-sized nights (spend N% of a week in H hours) need the real
ceiling.

**Do.** One measured night per setting (e.g. 6, 10, 14, 20 workers on one arm, same lane): sessions per
hour, median session wall time, CPU and Docker load. Record the knee in docs/model-routing.md and cap
max_workers to it.

**Done when.** The docs name the worker count that maximises sessions per hour on this machine.

## Data from run 20261120-quota (2026-11-20, 18 workers)

Setup: 18 workers (Fable 5.1 near-miss 10, Terra 5, Luna 1, Sol 1, Astra 1), all 18 launched at
15:23:28 after preflight; beside them about 11 Claude Code agents and a 46-minute host pytest run
in scratchpad clones, so this is a loaded reading, not a clean setting of the ladder above.

- Records' own `seconds` (T): Fable median 1,442 s (1,080-1,801, one at the 30-minute limit);
  Codex first attempts median about 715 s (683-760).
- Drive log, launch to end line (T): Codex 1,113-1,739 s, Fable 2,022-2,812 s. Every session ended
  430-1,010 s after its record's own time ran out.
- The end lines came one at a time, 70-210 s apart (15:42:01, 15:45:30, 15:47:18, 15:48:52,
  15:50:25, 15:51:50, 15:53:03, 15:54:13, then Fable 15:57:10 ... 16:10:20), although the sessions
  started together. That spacing points to a serialized step after each session (end-of-session
  audit, record or landing work under a lock) rather than to the model or CPU alone. Check this
  first: time each post-session step in the driver; if one step holds a lock for ~90-120 s at 18
  workers, sessions per hour are capped by that step, not by the worker count.
- 19 sessions finished in 47 minutes of matching (about 24 an hour).
