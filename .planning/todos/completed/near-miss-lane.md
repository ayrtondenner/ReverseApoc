---
title: Near-miss lane - a drive queue of partial rows ranked by bytes left to match
created: 2026-11-13
source: owner Q&A on the low byte percent (main session, 2026-11-13)
---

# Near-miss lane for partial functions

The headline byte percent is 0.81% (11,543 of 1,425,165 bytes, 2026-11-13). The partial rows in
`config/<exe>/status.csv` hold about 100 KB, almost 9 times the matched bytes, and many are close:

| best_percent | functions | bytes | headline if all matched |
|---|---|---|---|
| >= 90 | 42 | 7,964 | 1.37% |
| >= 80 | 125 | 21,909 | 2.35% |
| >= 50 | 297 | 79,075 | 6.4% |

(From `tools/progress.py --report`, both EXEs, asm-list rows excluded.)

The tier queue (`tools/reverseapoc/picker.py`) already gives a partial row later passes, but it
ranks by (tier, member before hub, aborted passes, finished passes, level, rank), and inside a
group every eligible row runs pass N before any runs pass N+1. So a 95% row waits behind fresh
rows, and nothing points the attempts at the rows that would move the percent most.

Do (test first):
- a picker mode (a drive flag, for example `--near-miss [MIN_PERCENT]`, default 80) that queues
  only partial rows with best_percent >= MIN_PERCENT, ranked by bytes left,
  size * (100 - best_percent) / 100, ascending (cheapest finish first); ties by size descending,
  then start;
- keep the guards the tier queue keeps: never matched, in flight, claimed units, asm or held
  rows; decide with the owner whether callee-first still applies (a near-miss row already passed
  its callee gate once, so probably not);
- let the lane run as one `--arm NAME=N` lane next to the normal queue, so a night can split its
  sessions between them;
- the attempt pack for a near-miss row starts from its best previous view unit and objdiff diff,
  not from scratch, if the records hold them; say so in the pack if they do not;
- `--dry-run` lists the lane's picks with best_percent and bytes left, so the owner can size a
  night from it (docs/model-routing.md "Quota per session").

Done when the lane passes tests and ruff in the container, and a dry run on the committed
status.csv lists the >= 90% rows first by bytes left.

## Result (2026-11-13, worker unit)

Built test first; the command and the rules are in docs/model-routing.md "Near-miss lane".

- `drive --near-miss [MIN_PERCENT]` (bare: 80) and `--near-miss-arm NAME=WORKERS`
  (repeatable). The lane runs beside the `--arm` or `--night-model` lanes in one drive (one
  lock, one audit, one commit queue), and alone when neither is given. Its arms join
  `night_arms`, so the backends.toml, max_workers, egress, canary and `--arm-budget` checks
  hold for them too.
- The queue is `picker.NearMissQueue`, a TierQueue subclass:
  - it orders by bytes left ascending, then size descending, then start;
  - it keeps the tier queue's guards (matched, in flight, claimed units, parked);
  - `driver.near_miss_source` leaves out the signed asm list's asm and held rows.
  The other lanes park every row of the lane (`_Lane.done`), so no row is offered by two lanes.
  The unit claims still keep two sessions off one unit.
- Callee-first does not apply. The coordinator ruled this on 2026-11-13 with the owner's
  delegation; the ruling is in the code and the docs. A capped pass leaves the lane for the
  rest of the drive: one pass per row per drive. A restarted drive offers the row again.
  Several near-miss arms share one queue.
- The pack. The committed records hold only `check.best_percent` and the give-up's
  first-difference text. They hold no C and no objdiff diff. The pack already showed the best
  earlier C when its `build/driver/.../best/<unit>.c` is on the machine. When the best
  attempt's C is not readable there, the "Earlier best C" section now says so plainly and names
  that attempt (`Notes.best_gone`). With no earlier C at all it shows `BEST_C_GONE`. Before a
  weaker attempt's C it shows `BEST_C_WEAKER`. No data is invented.
- The dry run lists the other lanes' picks without the lane's rows, then a `near-miss lane:`
  line, then the lane's first `--max-sessions` rows with best_percent, bytes left and pass. The
  JSON adds `near_miss`.

The dry run on the committed status.csv lists 49 rows at 90% or more, by bytes left; the
signed list excludes none of them. The table above says 42; it predates the 20261113-lanes4
records. Seven of the 49 are partial rows at 100.00% (0 bytes left), and they come first. A
partial row shown at 100.00% either rounds up from just under 100, or failed the gate for a
reason other than its bytes. The owner may want those seven looked at by hand.
