---
title: The same over-cap rows open every Codex night
created: 2026-11-23
area: driver
files: tools/reverseapoc/driver.py (queue and pack cap), config/driver/backends.toml
source: todo limit-burst-at-start measurements (runs 20261120-codex2, 20261121-codex, 20261123-codex)
---

# About 80 skipped picks at each night's start

**Why.** At the start of 20261120-codex2, 78 of the 86 "started" lines (65 terra, 13 luna) were
picks whose pack was over the 24,576-byte cap. Each was "left for tonight" before any session ran.
The same 78-80 over-cap lines open 20261121-codex and 20261123-codex too, because the rows stay at
the head of the queue and come back every night.

**Do.** Measure which rows they are and why their packs pass the cap (function size, context
blocks). Then pick, with the owner, the smallest fix: skip known over-cap rows when the queue is
built, record them once so the next night does not retry them, or route them to an arm with a
larger cap.

**Done when.** A night's start does not re-try rows already known to be over the cap, and a test
pins it.
