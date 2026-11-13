---
title: agy 1.5.7 edit_file step stops the night (agy audit)
created: 2026-11-13
source: night 20261113-cascade STOPPED guardrail at 22:54
---

# agy 1.5.7: `edit_file` is not a tool step the agy audit knows

agy auto-updated from 1.5.6 to 1.5.7. The Gemini Flash canary passed on 1.5.7, because the canary
session never edits a file. The night's one matching Gemini session did, and agy streamed a tool step
`edit_file` with keys `['name', 'parameters']`. `agyjson` failed closed on the unknown step, which
stopped the whole night (steps 25, 82 and 99 of that session).

Do (test first): capture the real 1.5.7 step shape from
`build/driver/20261113-cascade-gemini-flash/` transcripts, teach `agyjson` the `edit_file` step
(its target path into `write_targets`, judged against the write allowlist like `write_file`), keep
unknown steps failing closed, and make the agy canary exercise an edit so a version bump that
changes the edit step fails the canary, not the night. Gemini left the 64-255 B row until then.
