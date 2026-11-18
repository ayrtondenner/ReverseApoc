---
title: Keep the transcript of a session that stops the night with a D-08 STOP
created: 2026-11-15
area: driver
files: tools/reverseapoc/driver.py
source: run 20261115-claude-push (STOPPED stop signal after 169 sessions, cause unknown)
---

# A STOP session's evidence is deleted

`_Night` raises `_Stop(STOP_SIGNAL, ...)` after `self._reset(session)`, which removes the attempt
directory, transcript included. On 2026-11-15 the night stopped on a D-08 STOP and no file was
left to say which session or which error: Codex answered normally right after, and every
remaining Claude result was clean. Do (test first): before the reset, copy the stopping
session's transcript and stderr to `build/driver/<run>/stop/` and name that path, the arm and
the classified signal (api_retry code, rate_limit status/errorCode, failure text) in the STOPPED
record's detail and on the console.
