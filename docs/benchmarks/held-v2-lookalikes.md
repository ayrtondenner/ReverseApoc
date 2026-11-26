# Pre-registration: look-alike retrieval on held-v2 (2026-11-25)

Written on 2026-11-25, before any run of held-v2. It is the pre-registration of todo
`held-v2-lookalikes` (owner rulings of 2026-11-25; design
[docs/superpowers/specs/2026-11-25-held-v2-design.md](../superpowers/specs/2026-11-25-held-v2-design.md)).
Once the first run below has started, this file is not edited. A deviation goes into the results
section of [model-comparison.md](../model-comparison.md) with its reason, and this file stays as
it was. Amendments made before the first run are added at the end, dated, as in
[held-v1b-ablations.md](held-v1b-ablations.md).

## Why a new set

The held-v1c ablations (model-comparison.md, "Held context ablations on held-v1c") had 0 exact
picks in all four conditions, so 0 discordant pairs and p = 1.0 for every factor. Those picks
were partial rows that earlier sessions had failed. held-v2 draws instead from rows that have
never had a session and are small enough for Haiku to match often.

## What is measured

One factor: look-alike retrieval, up to 3 matched functions most like the target (D-13). The
`no-lookalikes` pack variant switches it off (the pack's Look-alikes section says none, in the
launch pack and in `attempt context`; held-v1b-ablations.md "What is measured"). Carry is not
measured: a never-attempted row has nothing to carry, and a hold run's work never reaches another
run's pack (D-17). Effort is left for a later, separately pre-registered run.

## Picks

[config/benchmarks/held-v2.txt](../../config/benchmarks/held-v2.txt), 274 picks: a census at
base commit `6e55ae16`, with no sampling (owner ruling 2026-11-25, below).

- **Population.** Every row of config/mechanics-members.csv (all four tiers signed) that the tier
  queue serves, which is a member row with a member item, or a hub row (`picker._group_rows`).
  It must also be:
  - not a held row of the signed asm list (`mechanics.signed_held`);
  - not on config/handoff.csv;
  - never attempted: no config/<exe>/status.csv row and no attempt record in
    progress/attempts.jsonl;
  - under 256 B by functions.csv size.

  That gives 34 rows under 64 B, 118 at 64 to 127 B and 122 at 128 to 255 B. They are listed
  sorted, and tests/test_stats.py reproduces the file from the base commit.
- **Why a census (note of 2026-11-25, before any run).** The owner first ruled 200 picks, 120
  under 64 B and 80 at 64 to 127 B, drawn with seed 20261125 from a pool that included
  `closure` rows. The pre-registered dry run of that draw (unpublished, never run) refused 116 of
  the 200 picks as "not in the queue", because the tier queue never serves closure rows. Without
  them, only 34 never-attempted rows under 64 B remain. The owner then ruled the census above,
  with a simulated power of about 0.56 for a 3x effect. No session had run, and no result
  existed.
- **Reservation (owner ruling 2026-11-25).** held-v2.txt is listed in
  config/benchmarks/reserved.txt. Its picks queue only on a `--hold` night whose `--picks` file is
  held-v2.txt itself. Every other night leaves them out, including a `--picks` night over another
  file that overlaps them. A `--picks held-v2.txt` night without `--hold` is refused, because it
  would land matches. The reservation is released by a commit after the `--land-held` below.

## Arm, repeats, budget

- **Arm.** `claude-haiku-5-5` (Claude Code login), 8 workers (its `max_workers`), `--hold`.
- **Repeats.** k = 1: one session per pick and condition (`--attempts 1 --max-sessions 274`).
- **Budget.** `--arm-budget claude-haiku-5-5=2.8%week` per run. Haiku's session cap is
  floor(budget / 0.01%week), which is 279 or 280, so `--max-sessions 274` binds. The pair can use
  at most 5.6% of the Claude week. The meter at $9.6 a point (config/driver/quota.toml) predicts
  about 1 to 1.5% per run: fresh rows under 128 B ran $0.02 to $0.04 a session, and 128 to
  255 B rows about $0.04 to $0.07. At about 30 sessions an hour, a run takes about 9 hours.
- **When.** The runs go after the weekly reset of Fri 2026-11-27 16:00, on the owner's go and a
  fresh bar reading taken before and after each run.

## Run matrix and order

| Run id | Variants | Look-alikes |
|---|---|---|
| `20261127-v2-base` | none | on |
| `20261127-v2-lookalike-off` | `no-lookalikes` | off |

The ids carry 20261127 as a label and keep it if the runs start on another day. Base runs first,
then lookalike-off, both from a clean main checkout at one commit, back to back. In between there
is no other drive, no `--land-held`, and no commit to src/ or config/*/status.csv, because
look-alike retrieval reads the matched set. Each command is first checked once with `--dry-run`
in place of `--hold`.

```
uv run reverseapoc drive --hold --picks config/benchmarks/held-v2.txt --arm claude-haiku-5-5=8 --arm-budget claude-haiku-5-5=2.8%week --attempts 1 --max-sessions 274 --run 20261127-v2-base
uv run reverseapoc drive --hold --picks config/benchmarks/held-v2.txt --arm claude-haiku-5-5=8 --arm-budget claude-haiku-5-5=2.8%week --attempts 1 --max-sessions 274 --pack-variant no-lookalikes --run 20261127-v2-lookalike-off
```

**Incomplete runs.**
- A run that stops before it has given every pick its session is resumed once with the same
  `--run` (todo resumed-held-run-budgets: the budget is sized less what the run already spent).
  This covers a budget meter stop, a harness STOP, or a Ctrl-C on limit exhaustion.
- A run that stops at its first launch with 0 sessions, on a tooling fault, is re-run unchanged
  under a new suffix (`-b`, `-c`), as held-v1c did. The stopped run is named in the results.
- Picks that a run still did not finish are left out of the pair (`stats --compare`'s
  finished-picks rule) and named. That includes a pick over the pack cap.

**Ineligible picks.** A pick may become matched or land on the board before or between the runs
(the reservation keeps normal nights off it, but hand work could still do it). The drive then
refuses held-v2.txt. In that case both runs use a copy without those picks, named held-v2b and
frozen with the same tests as held-v1b. The dropped picks are named. The sample is never redrawn.

**After both runs (owner ruling 2026-11-25).** `drive --land-held '20261127-v2-*'` lands the exact
picks, then a commit removes held-v2.txt from reserved.txt. A later effort test gets its own pair
and its own pre-registration.

## Analysis and decision rule

- **Analysed picks (owner ruling 2026-11-25).** The primary test counts only the picks that have
  a look-alike at the run commit. Those are the picks whose best look-alike ratio
  (`driver.similarity` over the matched set, the pack's floor `LOOKALIKE_FLOOR` = 0.6) is above 0.
  For the other picks, both conditions build the same pack. The list is computed by a script
  and written to `build/gate/20261127-v2/with-lookalike.txt` before the base run starts, and its
  count goes into the results. At 6e55ae16's matched set it held 147 of 274: 32 of 34 under
  64 B, 88 of 118 at 64 to 127 B and 27 of 122 at 128 to 255 B. All 274 are reported as
  description.
- **Outcome.** For each pick and condition: exact (MATCHED or HOLD_EXACT, `stats --compare`'s
  rule) or not. A pick counts only if both runs finished it (model-comparison.md "Adding the next
  comparison").
- **Test.** The exact two-sided McNemar test on the discordant analysed picks, at alpha = 0.05,
  counted from `uv run reverseapoc stats --compare 20261127-v2-base 20261127-v2-lookalike-off
  --json`, restricted to the analysed list.
- **Decision.**
  - If p < 0.05 with base exact on more picks, the look-alikes are kept, now measured.
  - If p < 0.05 with lookalike-off ahead, the result goes to the owner as a proposal to drop the
    look-alike section from the pack.
  - Otherwise no difference is shown, and the pack stays as it is, recorded as "not shown to help
    at this power".
- **Description only.** Exact counts with Wilson 95% intervals, best percent per pick, tokens and
  cost per session, the split by size group, and the meter readings. None of these decide
  anything.

## Power, stated in advance

With n discordant picks all in one direction, the exact two-sided p is 2 x 0.5^n, so at least 6
are needed. A simulation (pick difficulty drawn from a Beta with mean m and concentration 1, the
variant's odds the base's times OR, exact McNemar at alpha 0.05, k = 1, 800 trials) gives, for
the 147 analysed picks:

| Analysed picks | m | Power at OR 3 | Power at OR 2 | Size at OR 1 |
|---|---|---|---|---|
| 147 | 10% | 0.45 | 0.21 | 0.03 |
| 147 | 15% | 0.60 | 0.28 | 0.03 |
| 147 | 20% | 0.75 | 0.32 | 0.03 |

The expected rate comes from the records at 7a57f0cb:

- Haiku through Claude Code matched 13 of 36 functions under 64 B and 9 of 148 at 64 to 255 B
  (`stats`, up to 3 sessions each).
- First-ever sessions on fresh 64 to 255 B rows: 5 of 99.

The analysed picks are mostly under 128 B (32 + 88 of 147), so the expected rate is about 12%.
That gives about 0.5 power for a 3x effect and about 0.25 for a 2x effect. This is a weak test,
accepted by the owner as the most the queue allows. "No difference shown" is a likely outcome
unless the effect is large, and the rule above covers it.

## Reporting

One dated section in [model-comparison.md](../model-comparison.md) above "Adding the next
comparison". It gives:

- the paired table and the decision;
- both runs' ids, heads, environment digests and controls;
- the meter readings;
- every run that doesn't count.

The stats files go under `build/gate/20261127-v2/`.
