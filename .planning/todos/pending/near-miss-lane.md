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
