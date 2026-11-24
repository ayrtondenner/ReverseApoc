---
title: The console "started" line prints before the pack check
created: 2026-11-23
area: driver
files: tools/reverseapoc/driver.py (_announced, _launch), tests/test_driver_workers.py
source: todo limit-burst-at-start measurements (run 20261120-codex2)
---

# "started" for a session that never starts

**Why.** The drive prints "attempt N/3 (<arm>): started" before it builds the pack. A pick whose
pack is over the cap then prints "started" and is left for tonight, though no session ran. At the
start of 20261120-codex2 this made 8 launches look like about 86 and led to the limit-burst todo.

**Do.** Test first: print "started" only once the pack fits and the session is about to launch.
An over-cap pick prints one line that says so instead.

**Done when.** A drive log's "started" lines count real session launches, and a test pins it.

## Resolution (2026-11-24)

- `_announced` no longer prints the start line. It keeps the attempt's label in
  `local.started`, and `_launch` prints `<label>: started` once the pack fits, after the
  pinned-drift check and the Codex uv cache, right before the session call. It clears the
  label, so a LIMIT relaunch of the same attempt prints no second "started" (as before).
- A pick whose pack is over the cap prints only its OVER_CAP_LINE ("left for tonight (its
  context pack is N bytes, over the 24576-byte cap; ...)"), and no "started".
- With the companion todo over-cap-rows-open-every-night, a row already known to be over the
  cap on that arm prints nothing per pick, only one summary line at the night's end.
- Test: tests/test_driver_workers.py
  `test_an_over_cap_pick_prints_no_started_line` (1 and 2 workers): the over-cap pick's only
  line is OVER_CAP_LINE, and the "started" lines equal the launches. The earlier console tests
  in tests/test_driver.py (started, then the outcome) are unchanged and pass.
