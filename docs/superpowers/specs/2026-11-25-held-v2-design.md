# held-v2: a held benchmark set with power (design, 2026-11-25)

## Intent

held-v1c answered nothing. The four context-ablation runs of 2026-11-25 had 0 exact in every
condition, so 0 discordant pairs and p = 1.0 for every factor. Its picks were partial rows that
earlier sessions had already failed. An exact McNemar test needs about 6 or more discordant picks,
nearly all in one direction, to reach p < 0.05. held-v2 is a frozen held set whose expected match
rate is high enough to produce those pairs, so a pre-registered factor comparison can come out
either way.

## Goals, non-goals, anti-goals

- Goal: one paired, pre-registered answer for the look-alike section of the pack (base against
  `--pack-variant no-lookalikes`), at a power stated in advance.
- Goal: the set stays intact until its runs end, even if other nights run in between.
- Non-goal: carry and effort. Carry can't be tested on never-attempted rows: they have no earlier
  notes, records or give-ups, and a hold run's work never reaches another run's pack (D-17), so
  `no-carry` would equal base. Effort is left for a later run on the same set.
- Anti-goal: a sample redrawn, or rows swapped, after any result is seen. Also: a normal night
  quietly eating the set before its runs.

## Evidence (read 2026-11-25 from the records at 7a57f0cb)

- All four tiers of config/mechanics.toml are signed (tiers 2 and 3 on 2026-11-24). Rows a
  `--picks` night accepts that have never had a session, by size: 141 under 64 B (55 under 32 B,
  86 at 32-63 B), 230 at 64-127 B, 243 at 128-255 B, 730 at 256 B and up. Those counts still
  include the asm list's held rows; without them, the pool is 126 under 64 B and 219 at
  64-127 B. Eligible means a
  config/mechanics-members.csv row, functions.csv kind game or thunk, not an `asm` verdict in
  config/asm-functions.csv, not on config/handoff.csv, no config/<exe>/status.csv row and no
  attempt record.
- Haiku 5.5 through Claude Code (`stats`, per function over up to 3 sessions): 13 of 36 matched
  under 64 B, 9 of 148 at 64-255 B. First-ever sessions on fresh 64-255 B rows: 5 of 99. First-ever
  sessions on any arm: 43 of 65 under 32 B, 18 of 94 at 32-63 B, 22 of 142 at 64-127 B.
- Power, by simulation. Pick difficulty is drawn from a Beta with mean m and concentration 1,
  the variant's odds are the base's times OR, the exact two-sided McNemar test is used at alpha
  0.05, and k = 1. Results:

  | Picks | m | Power at OR 3 | Power at OR 2 |
  |---|---|---|---|
  | 200 | 25% | 0.92 | 0.54 |
  | 150 | 25% | 0.78 | 0.39 |
  | 200 | 10% | 0.60 | 0.22 |

  Under the null hypothesis the test's size was 0.03-0.04. These rows assumed the first pool.
  For the census, 147 picks have a look-alike and the expected rate is about 12%. That gives
  about 0.5 power for a 3x effect and 0.25 for a 2x effect (0.45 / 0.60 / 0.75 for 3x at
  m = 10 / 15 / 20%; pre-registration "Power, stated in advance").
- Cost. A Haiku budget's session cap is floor(budget / 0.01%week) (config/driver/quota.toml). The
  meter between launches is cost_usd / $9.6 a point. Fresh small rows ran $0.02-0.04 a session,
  about 0.003-0.005%week. held-v1c ran about 0.010 and the 256 B night 0.018.
- Throughput: about 30-35 Haiku sessions an hour at 8 workers (todo drive-worker-throughput).

## Approaches considered

1. **Never-attempted small rows (picked).** It has the highest expected rate and a clean pack,
   because there is nothing to carry. It tests look-alikes and effort, but not carry.
2. Partial rows with 1-2 attempts. This makes carry testable, but those rows have already resisted
   a session, and the carry content differs from pick to pick.
3. A larger set of mixed partial rows (held-v1 style). This is the design that failed.

For keeping the set intact, the options were copy-without (held-v1b/v1c), a procedural freeze with
no other drive between runs, and tooling. The owner picked the **tooling** (below).

## Owner rulings (2026-11-25)

| Choice | Ruling |
|---|---|
| Pool | First ruled: eligible never-attempted rows under 128 B. Superseded the same day (the dry run refused the closure rows, which no night queues): **every never-attempted member or hub row under 256 B**, a census of 274 (34 under 64 B, 118 at 64-127 B, 122 at 128-255 B) |
| Size mix, count | First ruled: 200 picks, 120 under 64 B and 80 at 64-127 B. Superseded: the 274-row census |
| Seed | First ruled: 20261125. Unused under the census (listed sorted) |
| Rows matched after the freeze | Tooling: normal nights never queue a reserved set's picks until it is released |
| Factor first | Look-alikes only: base against `no-lookalikes` |
| k | 1 |
| Arm | `claude-haiku-5-5` (Claude Code), 8 workers, `--hold` |
| Budget | First ruled: 2.1%week per run. Under the census: 2.8%week per run (a cap of 279-280 sessions, with `--max-sessions 274` binding), 5.6% cap for the pair, about 9 h a run. Both runs back to back after the weekly reset of Fri 2026-11-27 16:00, launched on the owner's go and a fresh bar reading |

### After the builder check (owner rulings and my calls, 2026-11-25)

| Point | Settled |
|---|---|
| Analysed picks | Owner: only the picks with a look-alike at the run commit (147 of 274 at 6e55ae16), with the list written before the base run. All 274 are reported as description |
| After the pair | Owner: land the exact picks, then release held-v2. Effort gets its own pair and pre-registration |
| Who may queue reserved picks | Owner: only a `--hold` night whose `--picks` file is the reserved file. A non-hold night over it is refused, and any other night, including another picks file, leaves the reserved picks out |
| Incomplete runs | My call: resume once with the same `--run`. A run with 0 sessions on a tooling fault is re-run under a new suffix. Unfinished picks leave the pair and are named |
| Ineligible picks before the runs | My call: a copy without them (held-v2b, held-v1b's rule), never a redraw |
| When the look-alike count is taken | My call: at the launch commit, since nights may land between the freeze and Friday |

The population is 126 under 64 B and 219 at 64-127 B, once the signed asm list's held rows are
left out as the tier queue leaves them.

## The how

- **Reservation.** `config/benchmarks/reserved.txt` lists frozen sets by file name. A night never
  queues a reserved set's picks (tier queue, pools, near-miss lane), except a `--picks` night,
  whose own picks stay. The dry run says how many reserved rows it left out. A set is released by
  deleting its line in a commit, after its runs and `--land-held`.
- **Freeze.** `config/benchmarks/held-v2.txt` is the census at base commit 6e55ae16 (the
  reservation tooling's), listed sorted. The file carries a dated header and is added to
  `reserved.txt` in the same commit. Tests in tests/test_stats.py reproduce it from
  `git show <base>:` and check that it holds no board row and is reserved. A `--dry-run` of both
  commands must accept every pick before the push. The first draw (200 sampled picks) failed
  that check: 116 were closure rows, which the tier queue never serves (`picker._group_rows`).
  The recipe was fixed, and the owner ruled the census.
- **Pre-registration.** `docs/benchmarks/held-v2-lookalikes.md`, in held-v1b's form. Its decision
  rule is the exact McNemar test at alpha 0.05. The run ids are `20261127-v2-base` and
  `20261127-v2-lookalike-off`, both at one commit, back to back, with no landing and no src/ or
  status.csv commit between them, because look-alike retrieval reads the matched set. A pick
  matched anyway is dropped from both runs' comparison and named.

## Left to the builder

The exact place in driver.py where the reservation filter applies, the reserved-file parse
errors, the dry-run line wording and the test fixtures, all following how the hand-off board is
applied today.
