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
