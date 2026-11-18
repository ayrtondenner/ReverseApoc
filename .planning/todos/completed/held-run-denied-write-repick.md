---
title: A held run re-picks a function whose session ended on a denied write
created: 2026-11-17
area: driver
files: tools/reverseapoc/driver.py
source: run 20261116-fable-ab (owner ruling 2026-11-16 on Copilot denied writes)
---

# A session that ended on a denied write is not counted as the function's attempt

Under the owner ruling of 2026-11-16, a Copilot session whose only strays are writes Copilot's
rules denied ends GAVE_UP guardrail and its arm goes on (`driver._SessionEnded`). On a hold run
the function is then picked again: the resume logic treats a GAVE_UP guardrail record as "cut
short" and attempts the function anew. Copilot Sonnet tried `ufo2p func_000A5980` three times
this way in run 20261116-fable-ab, writing nothing each time, at about 25 credits a session.

**Do (test first):** on a hold run, a session that ended through `_SessionEnded` counts as that
arm's attempt of the function, like any other finished session. Keep the resume rule for
sessions a stop really cut short (an interrupt, another arm's guardrail).

**Done when:** a hold-run test with a Copilot denied-write session shows the function attempted
once by that arm, and a resumed hold run does not pick it again.

## Resolution (2026-11-18)

Done in batch 2026-11-18 (U3, merge b68c306e).
