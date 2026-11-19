---
title: First matching night at 256 B and up
created: 2026-11-06
area: evaluation
files: .planning/phases/07-mechanics-first-decompilation/07-39-NIGHTS.md
source: owner ruling 1 at Phase 7.1's close
---

# First matching night at 256 B and up

This job holds Phase 7.1's outcome. The phase delivered the tools and their measurements: at point 6, 0 exact and 0 near at 256 B and up, on 445 rows.

**What it is.** A measured result at 256 B and up, from two sources:
- `search` over agent C near misses of that size, such as spike 011's tacp 0x000A19D0 (90.54, one slot pair swapped);
- a matching session run on the updated skill and the `attempt asm` notes.

**What the number is set against.** Spike 011's 2 of 5 at 256-1023 B and 0 of 3 at 1 KB and up.

**When.** D-11 keeps this off until Phase 7.1 closes.

**How to measure it.** Use the Phase 7.1 curve gate, `.planning/phases/07.1-matching-tooling/measure_curve.py`, with the matched-row control over the exact rows.

## Result of run 20261107-030004 (2026-11-07): still open

No number at 256 B and up exists yet, so this todo stays open.

- **Sessions:** the night was sized to reach no 256 B row, and it stopped at 57 of 100 sessions on a docker removal race. It ran 29 functions, all under 256 B, and no session ran at 256 B or up.
- **Search:** run before the night on spike 011's near misses, 0 of 3 at 256-1023 B and 0 of 3 at 1 KB and up came out exact. Those rows are the ones spike 011's agents failed on, so this is not comparable to its 2 of 5.
- **Slots notes:** the night's 10 notes that name `slots only?` all deny it, so it gave the search no new row.

**What closes this.** The queue's first 256 B row sat at pick 88 before the night, and the first 1 KB row at pick 289. Spike 011's 2 of 5 and 0 of 3 stay the numbers to beat. The per-night record is `.planning/phases/07-mechanics-first-decompilation/07-39-NIGHTS.md`.

## Result (2026-11-18): 0 of 14 at 256-1023 B, still open

Run `20261118-256`: one GPT-6.1 Terra arm, 5 workers, frozen list `build/driver/20261118-256-picks.txt`, 45 near-miss rows of 256-1023 B and 5 of 1 KB and up. The run ENDED `queue exhausted` after 36 sessions on 14 functions, all 256-1023 B, and 0 came out exact. Six rows raised their best percent (tacp func_0001E660 86.67 to 93.89, func_0003D160 85.62 to 91.95, func_000677E0 89.48 to 91.31, three by under a point). Tables: docs/model-comparison.md, "The 256 B night and a held Codex-tier comparison (2026-11-18/19)"; night record: 07-39-NIGHTS.md.

Why 0:
- **The stop rule, not the budget.** Every session used exactly 3 of its 15 checks and stopped on the watcom-decomp rule "three different C shapes leave objdiff below 100". No session got far enough to test what more checks would buy at this size.
- **The pack cap.** The tier queue could not supply the rows: 38 of its first 40 unattempted rows at 256 B and up had context packs over the 24,576-byte cap, so the night ran on near-miss rows that earlier sessions had already failed. The 5 rows of 1 KB and up got no session: the arm's 36-session budget cap ran out after 14 functions at up to 3 attempts each (the driver labels that `queue exhausted`). A rerun that wants the 1 KB rows should put them first in the picks file or cap attempts per function at 1.
- **One arm.** Terra only, at 1.10M input tokens and about 0.41% of the Codex week a session.

Spike 011's 2 of 5 at 256-1023 B stays the number to beat, and this result does not compare like for like with it: spike 011 sampled 5 fresh rows for Claude agents, this night gave Terra near-miss rows at 3 checks each.

**Next.** Two owner rulings: how the three-shapes rule counts shapes at 256 B and up (todo `three-shapes-rule-256b`), and what to do with packs over the cap at 1 KB and up. Then run this night again.
