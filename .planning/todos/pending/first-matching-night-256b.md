---
title: First matching night at 256 B and up
created: 2026-11-06
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
