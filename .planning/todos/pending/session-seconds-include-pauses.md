---
title: Session times may include usage-limit pauses
created: 2026-11-23
area: driver
files: tools/reverseapoc/driver.py, tools/reverseapoc/stats.py
source: drive logs of 20261120-codex2, 20261121-codex, 20261123-codex
---

# Sessions far past the 30-minute cap

**Why.** Drive log end lines report sessions far beyond the session time limit, for example
`ufo2p func_0006F830 attempt 1/3 (gpt-6.1-sol): MATCHED after 16357.9 s` (20261120-codex2) and
`ufo2p func_00075310 attempt 3/3 (gpt-6.1-terra): PARTIAL after 20502.7 s` (20261121-codex). Both
spanned a 5-hour usage-limit pause, so the backoff wait seems to be counted as session time. If the
attempt records' `seconds` carry the same figure, per-session time in `stats`, the throughput todo
(drive-worker-throughput) and any time-based sizing are skewed.

**Do.** First measure: compare the log's "after N s" with the records' `seconds` for those
sessions. If the records include the pause, test first, then record the time the session ran
(excluding backoff waits) and keep the wall figure separately if it is used anywhere.

**Done when.** A session that spans a limit pause records its own run time, a test pins it, and
the affected stats or docs figures are re-measured or flagged.
