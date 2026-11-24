---
title: The console "started" line prints before the pack check
created: 2026-11-23
area: driver
files: tools/reverseapoc/driver.py (_announced, pack building)
source: todo limit-burst-at-start measurements (run 20261120-codex2)
---

# "started" for a session that never starts

**Why.** The drive prints "attempt N/3 (<arm>): started" before it builds the pack. A pick whose
pack is over the cap then prints "started" and is left for tonight, though no session ran. At the
start of 20261120-codex2 this made 8 launches look like about 86 and led to the limit-burst todo.

**Do.** Test first: print "started" only once the pack fits and the session is about to launch.
An over-cap pick prints one line that says so instead.

**Done when.** A drive log's "started" lines count real session launches, and a test pins it.
