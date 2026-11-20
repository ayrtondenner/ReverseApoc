---
title: How many parallel sessions this machine runs before sessions slow down
created: 2026-11-20
area: driver
files: config/driver/backends.toml, docs/model-routing.md
source: run 20261119-claude (Opus 10 + Sonnet 10 workers)
---

# Twenty sessions at once were CPU-bound

**Why.** Run 20261119-claude ran 20 Claude sessions at once; sessions took 25-45 minutes (1,400-3,000 s)
against roughly 6-10 minutes on lighter nights, and only 62 sessions finished in about 2 hours. Each
attempt check compiles and diffs in Docker, so wall time per session grows with the number in flight
and sessions per hour stop rising. Quota-sized nights (spend N% of a week in H hours) need the real
ceiling.

**Do.** One measured night per setting (e.g. 6, 10, 14, 20 workers on one arm, same lane): sessions per
hour, median session wall time, CPU and Docker load. Record the knee in docs/model-routing.md and cap
max_workers to it.

**Done when.** The docs name the worker count that maximises sessions per hour on this machine.
