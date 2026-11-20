---
title: Judge Copilot CLI's remaining documented event types one by one
created: 2026-11-17
area: harness-copilot
files: tools/reverseapoc/copilotjson.py
source: 2026-11-16 drives (six Copilot audit stops in one day)
---

# About 80 documented Copilot event types are unknown to the audit

Copilot CLI 1.0.111's `schemas/session-events.schema.json` documents 242 type constants; the
audit (`copilotjson.KNOWN_EVENTS`, plus `prompt_cache_break` and `system.notification` of kind
`shell_completed`) knows the ones seen so far. Each new one stopped a whole multi-arm drive on
2026-11-16. A script over the schema listed the session-family ones still unknown, among them
`assistant.intent`, `assistant.streaming_delta`, `session.quota_observation`,
`session.usage_record`, `session.title_changed`, `session.todos_changed`,
`session.tool_outcomes_recorded`, `session.context_changed`, `session.workspace_file_changed`,
`tool.execution_progress` and the other `system.notification` kinds.

**Do:** for each type a locked-down headless session (no MCP, no skills, no subagents, five
tools) could emit, read its schema entry and decide: known as is, known only in an exact shape
(as `prompt_cache_break`), or kept unknown on purpose (anything naming instructions, agents,
hooks, permissions or a model switch). Add the known ones test-first, with the schema's own
wording in a comment, and re-run the review for every new CLI version (docs/learnings.md
2026-11-16 says where the schemas live: `runtime.node` for tool schemas,
`schemas/session-events.schema.json` for events).

**Done when:** every session-family event type is listed in copilotjson as known, shaped or
deliberately unknown, and a full Copilot night runs with no audit stop.

## Status (2026-11-18)

Status (batch 2026-11-18, U5): all 179 schema event types classified; replay of 436 recorded sessions gives 0 event-type stops. Left: a full Copilot night with no audit stop. Note: a test pins the installed CLI to 1.0.111, so a Copilot self-update turns the host suite red until re-reviewed.

## Status (2026-11-20)

- Installed CLI still 1.0.111 (`%LOCALAPPDATA%\copilot\pkg\win32-x64\` holds only that
  version), so the schema-coverage test still reads the reviewed schema and passes, not skipped.
- No Copilot session has run since the 2026-11-18 batch: the last Copilot runs are
  20261116-week and 20261116-fable-ab, and every drive since then was Codex, Claude, Fable or
  agy. So the "full Copilot night with no audit stop" half of Done is still open.
- Re-review of the 39 types the first capture made known (the 2026-11-18 batch read only the
  other 140). Four of them could carry what the review keeps unknown elsewhere. Each change
  narrows the audit, and each shape matches every recorded session:
  - `instruction.update` is now known only as the runtime's `sandbox-guidance` update, word
    for word. 436 of 436 sessions carry exactly that one. The schema also allows "host" and
    "managedPolicy" authority.
  - `session.mcp_servers_loaded` is now known only while every server it lists is `disabled`
    (436 of 436).
  - `session.session_limits_changed` is now kept unknown: "null clears the limits", so it
    could lift the driver's credit cap. No recorded session has one.
  - A second `user.message` in one session is now unknown. The driver sends one prompt, and
    436 of 436 sessions have exactly one.
- Tests: `test_copilotjson_only_the_runtimes_own_sandbox_guidance_instruction_is_known`,
  `test_copilotjson_mcp_servers_loaded_is_known_only_with_every_server_disabled`,
  `test_copilotjson_only_the_sessions_first_user_message_is_known`,
  `test_copilotjson_a_change_of_the_credit_cap_is_kept_unknown`. Replaying the 436 recorded
  streams through the audit after the change gives 0 unknown steps of any kind.

## Owner question: how to get the clean Copilot night (Done's second half)

Only a real Copilot drive can close this. That spends Copilot Pro AI credits, so it is your
call. Options:

- **A. A Copilot-only drive (Haiku 5.5 arm) once the current drive ends**, sized from
  docs/model-routing.md "Quota per session" (about 2.2 credits a Haiku session). Canary first.
  Close the todo when it ends with no audit stop.
- **B. Wait for the next planned night that has a Copilot arm.** Run it as its own drive, not
  as a lane of a multi-arm drive: a Copilot stop also ends the other arms' sessions in flight
  (learnings 2026-11-16).
- **C. Close the todo now on the replay evidence** (436 sessions, 0 unknown steps) and move
  the clean-night check into the next Copilot drive's checklist.

Recommendation: **B**, or **A** if no Copilot night is planned this week. The sessions do
matching work either way, so the credits are not spent only on the test. C would close the
todo on recorded data alone, and the todo was opened because recorded data missed live types.
