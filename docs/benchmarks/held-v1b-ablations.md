# Pre-registration: context-pack ablations on held-v1b (2026-11-24)

Written on 2026-11-24, before any of the runs below. It is the pre-registration of todos
`held-context-ablations` and `held-benchmark-statistics` (owner rulings of 2026-11-24): the
ablations are the held benchmark's first pre-registered comparisons. Once the first run below
has started, this file is not edited. A deviation goes into the results section of
[model-comparison.md](../model-comparison.md) with its reason, and this file stays as it was.

## What is measured

Three parts of a matching session's context were never measured: (1) look-alike retrieval, up
to 3 matched functions most like the target (D-13), (2) carrying the work of earlier attempts
into the pack (07.2-02: the earlier best C, the give-up lines, notes.md texts and attempt
records), and (3) reasoning effort, which every night leaves at the CLI's default (the attempt
record's `effort` is null, D-17).

Each factor is switched on and off with `drive --pack-variant NAME`:

| Variant | What changes | Where |
|---|---|---|
| `no-lookalikes` | The pack's Look-alikes section says none, and no other EXE is loaded for it | the launch pack and `attempt context` |
| `no-carry` | No earlier notes, records, give-ups or best C in the pack | the launch pack and `attempt context` |
| `effort-high` | Each session runs `claude ... --effort high`, and the attempt record's `effort` is `"high"` | the claude argv |

A drive with no `--pack-variant` behaves as before: the same argv, session environment, pack and
environment digest (pinned by tests). A drive with variants names them, sorted, in its STARTED
record's `environment.variants`, so they are part of its digest, and in each session's
`REVERSEAPOC_PACK_VARIANTS`, so the wrapper's `attempt context` builds the same pack as the
launch did. `stats --run` prints them on each run's environment line.

Effort on Haiku 5.5: the Claude Code CLI (2.1.311) takes `--effort <level>` with low, medium,
high, xhigh and max, and Haiku 5.5 accepts all five on the API (its API default is medium). The
"off" side is the default, as nights run today: no `--effort`, so the CLI picks the effort. The
comparison answers whether a night should pass `high` instead of the default.

## Picks, arm and repeats

- **Picks.** [config/benchmarks/held-v1b.txt](../../config/benchmarks/held-v1b.txt): held-v1
  (60 picks, seed 20261118) without the 4 picks matched by 9b98ecc7. That leaves 56 picks: 18
  under 64 B, 19 of 64 to 255 B and 19 of 256 B and up.
- **Arm.** `claude-haiku-5-5` (Claude Code login), 8 workers (its `max_workers`), `--hold`.
  Amended 2026-11-24, before any run of this matrix: the owner capped Haiku at 8 workers after the
  throughput ladder, so the commands below say 8 where they said 10. Workers change throughput,
  not a session's pack or arm, so the hypotheses and decision rules stand as written.
- **Repeats.** k = 2 per condition. Each repeat is its own hold run. A hold run's work never
  reaches another run's pack (D-17), so repeat 2 does not see repeat 1.

## Run matrix

The three "on" sides of look-alikes and carry and the "off" side of effort are all the default
pack, so one baseline condition serves all three factors. That makes 4 conditions x 2 repeats =
8 hold runs, and 4 runs per factor.

| Run id | Variants | Look-alikes | Carry | Effort |
|---|---|---|---|---|
| `20261125-abl-base-r1`, `-r2` | none | on | on | off (CLI default) |
| `20261125-abl-lookalike-off-r1`, `-r2` | `no-lookalikes` | off | on | off |
| `20261125-abl-carry-off-r1`, `-r2` | `no-carry` | on | off | off |
| `20261125-abl-effort-on-r1`, `-r2` | `effort-high` | on | on | on (`high`) |

The base run stands for `lookalike-on`, `carry-on` and `effort-off`. The ids carry 20261125 as
a label. They keep it if the runs start on another day.

**Order.** All four r1 runs, then all four r2 runs: base, lookalike-off, carry-off, effort-on.
Nothing else runs in between. No other drive, no `--land-held` and no commit to src/ or
config/*/status.csv until the eighth run has ended. A later night would change the carried
notes and the matched set, and `--picks` refuses a pick that has become matched. If a pick
gets matched anyway, it is dropped from every run's comparison, and the comparison names it
(the held-v1 header rule).

**Sessions and budget.** One session per pick and run: 8 x 56 = 448 sessions. At 0.01% of the
weekly Claude bar per Haiku session (docs/model-routing.md "Quota per session", config/driver/quota.toml)
that is about 4.5% of the week. The owner's share for this design is 6.6%. The base,
lookalike-off and carry-off runs get 0.6%week each. That budget caps them at 60 sessions,
which covers 56 picks and a few attempts tried again. The effort-on runs get 1.0%week each,
since a higher effort may cost more per session. The cap is 6 x 0.6 + 2 x 1.0 = 5.6% of the
week. If an effort-on run stops on its budget before it finishes, it is resumed once with the
same `--run` while the 6.6% share lasts, and is otherwise compared on the picks it finished.

## The commands

Each drive is launched as the owner launches drives, one at a time (one drive per checkout). It
is started from a clean main checkout at one commit, the same for all eight runs, after the
Haiku canary has passed on the installed CLI. Each run's meters are read before and after it.

```
uv run reverseapoc drive --hold --picks config/benchmarks/held-v1b.txt --arm claude-haiku-5-5=8 --arm-budget claude-haiku-5-5=0.6%week --run 20261125-abl-base-r1
uv run reverseapoc drive --hold --picks config/benchmarks/held-v1b.txt --arm claude-haiku-5-5=8 --arm-budget claude-haiku-5-5=0.6%week --pack-variant no-lookalikes --run 20261125-abl-lookalike-off-r1
uv run reverseapoc drive --hold --picks config/benchmarks/held-v1b.txt --arm claude-haiku-5-5=8 --arm-budget claude-haiku-5-5=0.6%week --pack-variant no-carry --run 20261125-abl-carry-off-r1
uv run reverseapoc drive --hold --picks config/benchmarks/held-v1b.txt --arm claude-haiku-5-5=8 --arm-budget claude-haiku-5-5=1.0%week --pack-variant effort-high --run 20261125-abl-effort-on-r1
uv run reverseapoc drive --hold --picks config/benchmarks/held-v1b.txt --arm claude-haiku-5-5=8 --arm-budget claude-haiku-5-5=0.6%week --run 20261125-abl-base-r2
uv run reverseapoc drive --hold --picks config/benchmarks/held-v1b.txt --arm claude-haiku-5-5=8 --arm-budget claude-haiku-5-5=0.6%week --pack-variant no-lookalikes --run 20261125-abl-lookalike-off-r2
uv run reverseapoc drive --hold --picks config/benchmarks/held-v1b.txt --arm claude-haiku-5-5=8 --arm-budget claude-haiku-5-5=0.6%week --pack-variant no-carry --run 20261125-abl-carry-off-r2
uv run reverseapoc drive --hold --picks config/benchmarks/held-v1b.txt --arm claude-haiku-5-5=8 --arm-budget claude-haiku-5-5=1.0%week --pack-variant effort-high --run 20261125-abl-effort-on-r2
```

Before the first run, each command is checked once with `--dry-run` in place of `--hold`. The
cli refuses `--hold` together with `--dry-run`, and a dry run starts no session.

## Analysis and decision rules

**Outcome.** Per pick and condition: exact (MATCHED or HOLD_EXACT, `stats --compare`'s rule)
in at least one of the two repeats, or not. A pick counts only if both conditions finished it
(the held-comparison rule in model-comparison.md "Adding the next comparison"). `stats
--compare` computes this directly when each condition is named by its run prefix, since a pick
is exact for a prefix when any of its runs matched it:

```
uv run reverseapoc stats --compare '20261125-abl-base-r*' '20261125-abl-lookalike-off-r*'
uv run reverseapoc stats --compare '20261125-abl-base-r*' '20261125-abl-carry-off-r*'
uv run reverseapoc stats --compare '20261125-abl-base-r*' '20261125-abl-effort-on-r*'
```

**Why "any repeat" and not one pair per repeat.** The todo asks for one paired result per
factor on frozen picks, and McNemar's test needs independent pairs. Two repeats of one pick are
not independent: the same function is easy or hard in both. Counting them as two pairs would
double the sample without doubling the information. One pair per pick keeps the pairs
independent. Any-of-2 is the pass@2 the research note on the frozen benchmark names
(docs/research/notes-ideas-tooling-reproducibility.md #3), and at match rates of a few
percent it is the reading that gives each condition the most matches to compare. The
per-repeat pairs (r1 against r1, r2 against r2) are reported too, as description only.

**Test.** Exact two-sided McNemar test on the discordant picks, one test per factor, each at
alpha = 0.05. Each factor gets its own keep or drop decision, as the todo asks, so the three
tests are not pooled. `stats --compare` prints the raw p and, with two runs named, a Holm p
equal to it. The three p-values are also reported with a Holm adjustment over the three
factors, as description only.

**Decision per factor.**

- **Look-alikes.** p < 0.05 with base exact on more picks: the look-alikes are kept, now
  measured. p < 0.05 with lookalike-off ahead: the result goes to the owner as a proposal to
  drop the look-alike section from the pack. Otherwise no difference is shown and the pack
  stays as it is, recorded as "not shown to help at this power".
- **Carry.** The same rule with carry-off in place of lookalike-off. A drop would leave the
  earlier best C, give-ups and notes out of the pack.
- **Effort.** p < 0.05 with effort-on ahead: the result goes to the owner as a proposal to give
  the Haiku arm an effort of `high` on nights. That needs an effort setting per arm, which is
  not built. p < 0.05 with effort-on behind, or p >= 0.05: nights keep the CLI default.

No decision rests on raw counts, best percent or cost. Those are reported as description: the
best percent per pick, tokens and cost per session (`stats --run`), and how far the two
repeats of each condition agree on which picks matched.

**Power, stated in advance.** With n discordant picks all in one direction, the exact two-sided
p is 2 x 0.5^n. Five discordant picks give 0.0625 and six give 0.031. So a factor reaches
p < 0.05 only with at least six discordant picks, all or nearly all in one direction. At the
match rates of recent Haiku nights (22 of 312 sessions by 2026-11-14, from config/driver/quota.toml,
and lower on rows earlier sessions failed), a few matches per condition are expected. The most
likely outcome is "no difference shown", and the decisions above already cover that outcome. A
larger held set (held-v2), which the attempt-check-full-diff todo also needs, is the next step
if a factor comes close.

## Reporting

One dated section in [model-comparison.md](../model-comparison.md) per factor, above "Adding
the next comparison". Each gives the paired table, the decision under the rule above, the run
ids, environment digests and controls of all eight runs, and the meter readings. The stats files
go under `build/gate/20261125-abl/`.
