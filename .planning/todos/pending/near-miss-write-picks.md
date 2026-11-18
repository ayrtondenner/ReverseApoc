---
title: Write a near-miss pick list with the driver's own ranking
created: 2026-11-17
area: picking
files: tools/reverseapoc/cli.py, tools/reverseapoc/driver.py
source: run 20261116-fable-ab (picks built by a scratchpad script)
---

# --write-picks works only with --stratify

The Fable A/B needed a frozen list of near-miss rows for `--hold --picks`. `--write-picks`
needs `--stratify`, so the coordinator rebuilt the near-miss rule in a scratchpad script from
status.csv and functions.csv. Two of its 160 picks (`tacp 0x000C6287`, `ufo2p 0x0009C3A0`) were
not in the queue, and the drive refused at start until they were removed.

**Do (test first):** accept `--near-miss [MIN] --write-picks FILE [--max-picks N]` with
`--dry-run`, writing the first N rows of the driver's own near-miss ranking
(`driver.near_miss_picks`), so every written pick is in the queue.

**Done when:** a dry run writes a picks file that a following `--hold --picks FILE` drive
accepts without refusal.
