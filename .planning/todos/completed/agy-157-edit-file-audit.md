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

2026-11-13, closed (test first: RED `cbbd4ae4`, then the GREEN `fix(agy)` commit after it). agy is now 1.5.8.
The coordinator captured an allowed and a denied edit on 1.5.8 (gemini-3.8-flash-medium, scratch dirs) instead of
reading the night's transcripts. The step is `tool_info {name: edit_file, parameters: {Path}}` (ACTIVE, then DONE,
or ERROR with `error`), and agy checks it against the `write_file` permission rules: the denied one ended ERROR,
TOOL_ERROR, `permission check failed for write_file "<path>": Permission denied for write_file(<path>). Matches
user-configured deny rule.` So the session's `write_file(<path>)` allow rules already scope its edits.

Done: `agyjson` knows `edit_file` in exactly that shape (its Path judged as a write like `write_file`;
`agyjson.edits` lists the edits that ran), reads that deny-rule refusal as a denial with the `write_file` action (a
denied write at night), and keeps every other shape, tool or message failing closed. The agy canary's allowed
session now writes plan.json with an empty frame and edits it in place with its file-edit tool before `attempt
plan`, and `_agy_allowed_checks` requires a known `edit_file` step that ran. Fixtures under `tests/fixtures/agy/`:
`agy158_edit_allowed` and `agy158_edit_denied` (the captures, with placeholders for the paths, model and ids),
`gemini_edit`, `denied_edit`, `canary_agy_allowed_no_edit` and `canary_agy_allowed_edit_reshaped`.

Still open: every agy arm needs a live canary on 1.5.8 (the coordinator's, after merge). Never captured: agy's
soft-deny message for an `edit_file` no rule matches (such a step counts as run, so an edit outside the allowlist
still stops the night), and whether 1.5.8 words the read probes' deny-rule refusals the same new way; if it does,
those probes FAIL as `not denied` and need the same treatment.
