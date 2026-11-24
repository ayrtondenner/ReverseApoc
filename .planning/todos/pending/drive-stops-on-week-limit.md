---
title: A drive whose arms have used up the week keeps probing until the reset
created: 2026-11-24
area: driver
files: tools/reverseapoc/driver.py (_Pause, _limited), tools/reverseapoc/codexjson.py (limit text)
source: runs 20261120-codex, 20261121-codex, 20261124-codex2 (2026-11-20 to 24)
---

# Probing for days

**Why.** A Codex usage-limit message says either "try again at 10:32 AM" (the 5-hour window) or
"try again at Nov 25th" (the week). The driver treats both the same way: the arm pauses, then
launches a probe every 300 s until a session gets through. When the week is used up, that means a
probe every 5 minutes per worker for days (the week resets 4 d 12 h after 2026-11-24 11:16), with
each probe leaving an `attempt-N-uncounted-K` directory. The night ends only when the owner or the
orchestrator sends a Ctrl-C after reading a transcript by hand (owner pre-authorized that on
2026-11-24).

**Do.** Test first, with the Codex classifier's fixtures: tell a dated limit ("try again at <month>
<day>") from a timed one, and record the reset the message names. When every arm of the night is
blocked by a dated limit, end the night with STOPPED `quota-exhausted`, naming each arm and its
reset, and run the end-of-run checks as for ENDED. If only some arms are out for the week, the
other arms go on and the exhausted arm stops launching. Check the Claude, agy and Copilot limit
texts for the same distinction, and keep any harness without one on today's behaviour.

**Done when.** A drive whose arms all hit a dated limit ends by itself with a STOPPED
`quota-exhausted` record, an arm out for the week stops probing while the others run, and tests
pin both.
