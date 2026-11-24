---
title: A drive that starts under a usage limit fans out dozens of doomed launches
created: 2026-11-23
area: driver
files: tools/reverseapoc/driver.py
source: run 20261120-codex2 (started 21:36 on 2026-11-20, Codex window empty until 21:44)
---

# A burst of limited launches

**Why.** Run 20261120-codex2 finished preflight at 21:36 while the Codex 5-hour window was still
empty. Between 21:36:54 and 21:38:14 the drive log shows about 80 "started" lines across the 8
workers before the first "usage limit, next launch in 60 s" at 21:38:37, and build/driver/ kept
many `attempt-N-uncounted-*` directories. Each LIMIT launch spends a slot of its arm's cap
(quick 261112-fdr) and cycles picks for nothing.

**Do.** Measure first from that run's records and directories (how many LIMIT launches, slots
spent, picks touched). Then, test first, make the first LIMIT of an arm pause that arm's other
workers before they launch (or probe once per arm when a drive starts), so a drive that starts
under a limit spends one probe, not a burst.

**Done when.** A drive started while its arm is limited launches at most one probe per arm before
the pause, and a test pins it.

## Measured (2026-11-23), read-only from the main checkout

Sources: the drive log 20261120-codex2.err.txt (21:36:54 to the first "usage limit" at
21:38:37), build/driver/20261120-codex2-*/ and the run's records in progress/attempts.jsonl.
Arms: gpt-6.1-terra=5, gpt-6-luna=1, gpt-6.1-sol=1, gpt-6-astra=1 (8 workers, `--arm` lanes,
not a cascade).

- **86 "started" lines, 8 launches.** 78 of the 86 were attempts "left for tonight (its context
  pack is N bytes, over the 24576-byte cap)" (65 terra, 13 luna): `_PackOver`, raised
  before any session, with the slot, claim and probe handed back. `_announced` prints "started"
  before the pack is built. Only 8 sessions launched, one per worker: terra 5, luna 1, sol 1,
  astra 1. The same pattern opens the next nights too: 78, 80 and 80 over-cap lines in
  20261120-codex2, 20261121-codex and 20261123-codex.
- **Classification.** All 8 were LIMIT: no TRANSIENT, no abort record. The first ones were not
  LIMIT at once because Codex took a while to answer. The astra session's transcript is 4
  events (thread.started, turn.started, error "You've hit your usage limit ... try again at
  9:44 PM", turn.failed), written by 21:38:00, 66 s after its launch; its LIMIT line came at
  21:38:37, after the audit and salvage. Terra's 2nd to 5th sessions launched at 21:38:03 to
  21:38:14, before any LIMIT verdict, so no pause held them yet.
- **Limit records.** 4 at first, one per arm (workers 7, 6, 4, 5; 60 s, streak 1). The other 4
  terra sessions printed "usage limit, the night is already paused" and wrote none. Each arm's
  pause then probed once per backoff (60, 120, 240, 300 s...), 124 limit records per arm over
  the night, 496 in all.
- **Slots and picks.** 0 slots spent: on an `--arm` night a LIMIT relaunches the same claim
  (`_limited`, then `continue`), with no `_spend`. Only TRANSIENT spends a slot, and a cascade
  arm's LIMIT spends one of its own cap (`_cascade_limited`, quick 261112-fdr). Picks touched:
  the 8 launched picks, each relaunched on its own claim (8 `attempt-1-uncounted-1` dirs
  created 21:36:54 to 21:38:14; all 8 later ended PARTIAL). None was cycled. The 78 over-cap
  picks do not depend on the limit.
- **What a probe-first start would have saved.** 4 limited launches (terra's 2nd to 5th) and
  their 4 uncounted dirs, on a night where they cost no slot and no quota.

## Open: needs an owner ruling before any code

The burst behind "about 80 started lines" is mostly the over-cap packs, not limited launches.
The limit part is one launch per worker. Question: "Should a drive's start hold each arm's
other workers behind one probe, and until when?" Options:
1. Hold them until the probe's session ends (the `_Pause` as it is, set paused with the probe
   due at night start). Small, but every night start then idles (workers - 1) workers per arm
   for one whole session (the first sessions of this run took 305 to 645 s). On a cascade the
   held attempts would pass to the row's next arm.
2. Hold them until the probe's first sign of life. That needs a per-event hook in
   run_session and a "past the limit check" rule per harness (Claude, Codex, agy, Copilot
   streams).
3. No change: on an `--arm` night the saving is (workers - 1) limited launches per arm, with
   no slot spent. Instead, file the over-cap rows at the queue head as their own todo (they
   are "left for tonight" and come back every night).
