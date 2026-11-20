---
title: A STOPPED record names each session whose stop it joins
created: 2026-11-20
area: driver
files: tools/reverseapoc/driver.py, tests/test_driver*.py
source: run 20261119-3s-new (quick 261119-cxerr debugging)
---

# Two stops read as one

**Why.** Run 20261119-3s-new STOPPED with one detail that joined two workers' stops: a "D-08 STOP
signal" from the tacp func_000677E0 session and a guardrail stray ("item 'item_5': type 'error'") from
the ufo2p func_00011CF0 session. `_fail` (driver.py ~3914) adds a later worker's stop to `halt_notes`
and `_stopped_workers` joins them without naming the session each came from, so the record read as
one stream and sent the first debugging pass to the wrong transcript.

**Do.** Test first: each joined stop in the end record and the console line carries its own
`<exe> <function> attempt <n> (<arm>)` label; older records stay readable.

**Done when.** A night with two simultaneous stops names both sessions in its STOPPED detail.
