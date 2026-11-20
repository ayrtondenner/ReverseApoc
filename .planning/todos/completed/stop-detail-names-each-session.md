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

## Resolution

Done 2026-11-20 (tools/reverseapoc/driver.py). `_Stop` carries the console label of the attempt
it came from (`_label`: `<exe> func_XXXXXXXX attempt <n>/<N>`, plus ` (<arm>)` on a night of several
arms or a cascade), set in `_announced` as the stop leaves the attempt. `_fail` puts that label in
front of each later stop it adds to `halt_notes`; `_raise_failure` puts the first stop's label in
front of its detail whenever it joins notes to it; `_stopped_workers` (the interrupt record) labels
the first failure too. A lone stop's detail is unchanged. The run record's `detail` stays one
free-text string (`_optional(_is_text)`), so older STOPPED records validate and read as before;
nothing in tools/ parses the detail's parts. The console line prints `report.detail`, the same text.

Test: `tests/test_driver_workers.py::test_two_stops_at_once_name_each_session` (two arms: Haiku's
session sends a STOP signal, Sonnet's, held until the night stops, leaves a stray; both the record
and the report open with Haiku's label and carry Sonnet's label before `guardrail: `; the record
validates). RED before the fix (the detail opened "the session's stream carries a D-08 STOP
signal ..."); GREEN after. `tests/test_driver_workers.py`: 149 passed in 337 s; `ruff check .` clean.
