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
