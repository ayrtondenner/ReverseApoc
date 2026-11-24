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

## Built: the step timings (2026-11-24)

Every attempt record now carries `step_seconds` (optional in the v3 schema, so earlier lines stay
valid; `driver.STEPS`), the seconds of the driver's own steps around its session on Deps.clock,
to 1 decimal:

- `launch_wait`/`launch`: the gate lock at the launch's snapshot (before the session).
- `cleanup`: container removal, a Codex session's uv cache, the broker (already inside the
  record's `seconds`, as before).
- `audit_wait`/`audit`: the gate lock around the after-session snapshot and audit.
- `proposals_wait`/`proposals`: a readability session's proposals under the gate lock.
- `land_wait`/`land`: the landing section's gate lock; the hold runs up to the record's write,
  so it holds `lint`, `gate` and `partial_gate`, which are timed on their own too.
- `git_wait`/`git`: every driver git call of the launch, waiting for and holding the git lock
  (the hold overlaps the gate-lock holds).

Not in the record, because they come after its write: a match's commit and the claim's release.
A slow commit shows up as the next attempts' `land_wait`. The likely serialized step is the
whole-EXE gate, which runs inside the landing's gate-lock hold: 18 workers whose gates take
70-210 s each would give exactly the spacing of the end lines above. The first run with the
field shows whether it does.

`stats --run RUN` adds a block, "driver steps per attempt": the session's own `seconds` and each
step, median and max, over the attempts that carry the field; the total of every `_wait` step;
and the counted sessions per hour over the selected end records' wall clock. JSON: `steps`
(`attempts`, `session`, `steps`, `lock_wait`, `per_hour`); null without `--run`.

## The Haiku worker ladder (to run)

One arm, `claude-haiku-5-5`, on one lane: matching rows of 64 to 255 B from the signed tier
queue, frozen once and split round-robin, so each setting gets rows of the same spread and no
row twice. No `--hold`: the gate under the landing's lock is the step to measure. No agents
or host pytest beside the drives (the 20261120 reading above was a loaded one).

Settings asked: 4, 8, 12 and 16 workers. backends.toml gives Haiku `max_workers = 10`, and
`--arm` refuses more before any command, so capped at it the ladder is **4, 8 and 10**. 12 and
16 need the owner to raise Haiku's `max_workers` first (an owner question, not decided here):

- (a) keep the cap: three drives (4, 8, 10), about 0.75% of the week;
- (b) raise `max_workers` to 16 for the ladder: four drives (4, 8, 12, 16), about 1%;
- (c) keep the cap and add 6 as the fourth setting (4, 6, 8, 10), about 1%.

About 25 sessions per setting, one drive per setting run one after another, each with
`--arm-budget claude-haiku-5-5=0.25%week` (Haiku about 0.01% of the week a session: 25
sessions) and `--max-sessions 25`.

```
# once, on the main checkout: 100 rows of 64-255 B (with fewer in the 400-pick window the
# dry run exits 2 and writes nothing; then run --stratify 0,25,0 before each drive instead:
# the rows a drive attempted are no longer taken)
uv run reverseapoc drive --dry-run --stratify 0,100,0 --write-picks build/driver/ladder-picks.txt
# round-robin into one file per setting (PowerShell; here option (b)'s four)
$rows = @(Get-Content build/driver/ladder-picks.txt | Where-Object { $_.Trim() -and -not $_.StartsWith('#') })
$settings = 4, 8, 12, 16
for ($k = 0; $k -lt $rows.Count; $k++) { Add-Content "build/driver/ladder-picks-w$($settings[$k % 4]).txt" $rows[$k] }
# one drive per setting; start the next only after the last one's driver has exited
uv run reverseapoc drive --detach --log $env:TEMP\ladder-w4.log --run ladder-w4 --arm claude-haiku-5-5=4 --arm-budget claude-haiku-5-5=0.25%week --max-sessions 25 --picks build/driver/ladder-picks-w4.txt
uv run reverseapoc drive --detach --log $env:TEMP\ladder-w8.log --run ladder-w8 --arm claude-haiku-5-5=8 --arm-budget claude-haiku-5-5=0.25%week --max-sessions 25 --picks build/driver/ladder-picks-w8.txt
uv run reverseapoc drive --detach --log $env:TEMP\ladder-w12.log --run ladder-w12 --arm claude-haiku-5-5=12 --arm-budget claude-haiku-5-5=0.25%week --max-sessions 25 --picks build/driver/ladder-picks-w12.txt
uv run reverseapoc drive --detach --log $env:TEMP\ladder-w16.log --run ladder-w16 --arm claude-haiku-5-5=16 --arm-budget claude-haiku-5-5=0.25%week --max-sessions 25 --picks build/driver/ladder-picks-w16.txt
# after each drive: ninja verify and gate --all by hand (CLAUDE.md "Drives"), then
uv run reverseapoc stats --run 'ladder-w4*'
```

Under (a) or (c), `$settings` and the drives are `4, 8, 10` (three files, `$k % 3`) or
`4, 6, 8, 10`, with `=N`, `-wN` and `--run ladder-wN` to match.

Metrics per setting, all from `stats --run 'ladder-wN*'` (the `*` takes the arm's run id
`ladder-wN-claude-haiku-5-5` and the night's own ENDED record `ladder-wN`): sessions per hour
(`per_hour`), median session wall time (`session` median), and each step's median and max with
the total lock wait. The knee is the setting past which sessions per hour stop rising. If
`land_wait` grows with the workers while `gate` stays flat, the landing's gate-lock hold caps
the night, not the worker count. Record the knee in docs/model-routing.md and cap
`max_workers` to it.

## Owner ruling (2026-11-24): the ladder

Haiku's max_workers is 10 (backends.toml), so 12 and 16 would be refused. The options were:
(a) 4/8/10; (b) raise max_workers to 16 and run 4/8/12/16; (c) 4/6/8/10. Chosen: **(c) 4 / 6 /
8 / 10**, four drives of about 25 sessions each, about 1% of the Claude week, run as `ladder-w4`,
`ladder-w6`, `ladder-w8` and `ladder-w10` with the commands above and the worker count changed.
