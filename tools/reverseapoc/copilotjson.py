# SPDX-License-Identifier: GPL-3.0-or-later
"""The driver's reading of a `copilot -p --output-format json` session (spike 013; owner
ruling 2026-11-13: GitHub Copilot CLI on the owner's Copilot Pro as a drive harness).

Each stdout line is one JSON event, read by streamjson's own `parse_line`/`parse` (a malformed
line is counted, never fatal; the UTF-8 BOM Copilot CLI 1.0.111 writes before its first line is
taken off there): `{"type", "data", "id", "timestamp", "parentId"}` (plus `ephemeral`, and
`agentId` on a subagent's events), then a last `{"type": "result", "exitCode", "usage"}`. The
shapes below are the ones the coordinator's 1.0.111 capture showed (spike 013's README) and the
CLI's own event schema (schemas/session-events.schema.json in its package); the canary proves
them for each arm.

- `init_event`/`init_problems`: the driver's init check (a STOP condition like check_init):
  `session.start` must exist, its `context.cwd` be the attempt dir, its `selectedModel` an id
  the arm accepts and its `sessionLimits.maxAiCredits` the cap the driver passed; and no model
  call, message or tool call may name another model (an automatic switch fails closed).
- `has_result`/`turns`: whether the `result` line ended the session (the driver's
  `measured`); the number of `assistant.turn_end` events.
- `usage`: the stream carries no token counts, so they come from the `--usage-output-file`
  document (`read_usage`): its `tokenDetails` uncached `input`, `output`, `cache_read` and
  `cache_write` (cache creation); the turns; the result's `sessionDurationMs`; no cost (Copilot
  Pro is a monthly AI-credit allowance). `credits`: its `totalNanoAiu` / 1e9, the AI credits
  the session spent.
- `calls`: each tool call, once, by its `toolCallId`: its `tool.execution_start` (tool name and
  arguments) and its `tool.execution_complete` (success, error, fileEdits, result). A call is
  known only when its tool is one of KNOWN_TOOLS in its known argument shape, started by the
  main agent (no `agentId`, no parent, program or MCP field). `denials`: each known call that
  failed with code `denied` and exactly one of 1.0.111's two refusal texts (a rule named, or no
  allow rule and nobody to ask); it never ran. `commands`, `write_targets`, `read_targets`:
  the powershell commands, the create/edit paths (plus every completion's fileEdits and the
  result's filesModified: fail closed) and the view paths of the known calls that were not
  denied. `denied_writes`: the paths of the create/edit calls that were. The driver's audit
  reads them (D-26).
- `unknown_steps` (fail closed): each call that is not known, each start or completion whose
  toolCallId is not a string, each completion with no start, each second start or completion of
  one id (only one of each is read), a second `user.message` (the driver sends one prompt),
  each event carrying `agentId` (a subagent's), and each
  event of a type outside KNOWN_EVENTS that is not one of SHAPED_EVENTS in its known shape:
  one of KEPT_UNKNOWN (a hook, a skill, a subagent, a
  permission prompt, a model switch...) names its reason, any other is a type no review read.
  The audit counts each as a stray. `hook_traces`: each tool result that carries a hook's
  guidance text (the owner's user-level postToolUse hook reached the capture's results): the
  per-session COPILOT_HOME turns every hook off, so any is a stray.
- `failure`: the first `session.error`'s errorType and message, else the result's non-zero
  exit code, else None. `classify`: a wall-clock timeout is counted; a session.error is LIMIT
  for a rate limit or a quota, counted for a context limit, STOP for anything else; a result
  with exit 0 is counted, any other exit STOP (fail closed); no result is TRANSIENT.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NamedTuple

from . import streamjson
from .streamjson import Disposition, Usage

parse = streamjson.parse  # one reader for every CLI's JSONL, never a copy
parse_line = streamjson.parse_line

_START = "session.start"
_RESULT = "result"
_TURN_END = "assistant.turn_end"
_TOOL_START = "tool.execution_start"
_TOOL_DONE = "tool.execution_complete"
_ERROR = "session.error"
# 1.0.111: "a delivered inter-agent prompt", queued or steering; each of the 436 recorded
# sessions has exactly one, the driver's prompt, so a second is unknown (unknown_steps)
_USER = "user.message"
# the tools the driver makes visible (session.build_copilot_argv's --available-tools), in order
AVAILABLE_TOOLS = ("view", "create", "edit", "powershell", "read_powershell")
VIEW, CREATE, EDIT, SHELL, POLL = AVAILABLE_TOOLS
# Each known tool's arguments: the keys it must have, then the keys it may have (each a check
# of its value). view/create/edit/powershell{command, description} are the capture's shapes.
# powershell's `mode` and `initial_wait` come from the CLI's own tool table (its bundled
# cli-main.js lists them for its shell tool, with read_<shell> for polling), and read_powershell's
# `shellId` from the capture's shell results ("structuredContent": {"shellId": "0"}); neither
# was captured in a call: the canary's `attempt check` step settles them.
def _text(value: object) -> bool:
    return isinstance(value, str)


def _seconds(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value >= 0


def _line_range(value: object) -> bool:
    """view's `view_range` (night 20261114-nearmiss): [start, end], two integers."""
    return (isinstance(value, list) and len(value) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) for v in value))  # fmt: skip


def _flag(value: object) -> bool:
    return isinstance(value, bool)


_SHAPES: dict[str, tuple[dict, dict]] = {
    # view: 1.0.111's own schema {path, view_range?, forceReadLargeFiles?: boolean} (its
    # runtime.node, read 2026-11-16 after run 20261114-opus-sonnet): the flag lifts only the
    # size check. Its flattened view_range[0]/[1] form stays unknown.
    VIEW: ({"path": _text}, {"view_range": _line_range, "forceReadLargeFiles": _flag}),
    CREATE: ({"path": _text, "file_text": _text}, {}),
    # edit: the CLI's own schema is {path, old_str, new_str?} (its bundled cli-main.js)
    EDIT: ({"path": _text, "old_str": _text}, {"new_str": _text}),
    # 1.0.111's own schema adds timeout, async and shellId (cli-main.js, read 2026-11-14; night
    # 20261114-nearmiss6 named a shell "ctx" for the wrapper): the command stays Copilot's
    # permission check's and the audit's to judge. Its sandbox-bypass requests stay unknown, and
    # so does `detach` (runtime.node: a process that outlives the session, past the audit).
    SHELL: ({"command": _text}, {"description": _text, "mode": lambda v: v in ("sync", "async"),
                                 "initial_wait": _seconds, "timeout": _seconds,
                                 "async": _flag, "shellId": _text}),
    POLL: ({"shellId": _text}, {"delay": _seconds}),
}
KNOWN_TOOLS = frozenset(_SHAPES)
_PATH_TOOLS = frozenset({VIEW, CREATE, EDIT})
_WRITE_TOOLS = frozenset({CREATE, EDIT})
# a start field that says another agent, a program or an MCP server made the call
_FOREIGN_START = frozenset({"parentToolCallId", "programToolCallId", "mcpServerName",
                            "mcpConfigServerName", "mcpToolName", "mcpTransport",
                            "mcpConfigSource", "toolDescription"})  # fmt: skip
_AGENT = "agentId"  # on the envelope of a subagent's events (the CLI's event schema)
# Every event type the capture streamed, plus the session-level ones that run nothing
# (compaction, errors, warnings, usage); any other type is an unknown step (fail closed). The
# review of 2026-11-20 moved three of them out: instruction.update and
# session.mcp_servers_loaded are known only in their recorded shape (SHAPED_EVENTS), and
# session.session_limits_changed is kept unknown (_KEPT); and only a session's first
# user.message is known (unknown_steps).
KNOWN_EVENTS = frozenset({
    _START, "session.tools_updated", _USER, "assistant.turn_start", "model.call_start",
    "assistant.reasoning_delta",
    "assistant.reasoning", "assistant.message_start", "assistant.message_delta",
    "assistant.message", "assistant.tool_call_delta", "model.call_finished",
    "model.call_final_result", _TOOL_START, _TOOL_DONE, "tool.shell_output",
    "tool.execution_partial_result", "session.info", "session.background_tasks_changed",
    _TURN_END, "session.usage_checkpoint", "assistant.idle", _RESULT,
    "session.compaction_start", "session.compaction_complete", "session.compaction_summarized",
    "session.truncation", "session.usage_info", "assistant.turn_retry",
    "model.call_failure", _ERROR, "session.warning", "session.idle", "session.shutdown",
    # The event review of 2026-11-18 (todo copilot-event-types-review): every event type 1.0.111's
    # schemas/session-events.schema.json documents is in KNOWN_EVENTS, SHAPED_EVENTS or
    # KEPT_UNKNOWN (tests/test_copilot.py reads the installed schema). Known as is, each in the
    # schema's own words; none runs anything or names a tool, path, model, agent, hook,
    # permission or instruction text the audit would have to judge:
    "assistant.intent",  # "agent intent description for current activity or plan"
    "assistant.streaming_delta",  # "streaming response progress with cumulative byte count"
    "session.title_changed",  # "the new display title for the session"
    # "the agent's todos or todo_deps table was written to": only through the sql tool, which
    # the session does not have (a call to it is an unknown call)
    "session.todos_changed",
    # "a provider-owned quota observation, distinct from per-call usage and charge accounting";
    # a quota stop comes as a session.error (classify)
    "session.quota_observation",
    # "behavior-neutral record of structured runtime facts present when an agent completion
    # decision is accepted" (stop reason, final tool, tool counts)
    "session.completion_receipt",
    "pending_messages.modified",  # "empty payload; ... the pending message queue has changed"
    "capabilities.changed",  # "session capability change notification" (its UI capabilities)
    # "session command list change notification"; running one (command.execute, .queued) is
    # kept unknown
    "commands.changed",
    # "canonical bytes for a content-addressed binary asset shared by reference across events"
    # (an image a view returned); the call that returned it is judged as any call
    "session.binary_asset",
    # "internal durable marker that the server rejected a compressed model request body"
    "session.request_body_compression_disabled",
    "session.indexed_search",  # "transient indexed-search status and diagnostics"
    # "links a standalone replay head to its complete preceding numbered journal archive"
    "session.journal_link",
    # "internal content-free receipt for the first model request that consumed one or more
    # pending canonical instruction updates": the text came in an instruction.update
    "instruction.update_delivery",
    # "session limit exhaustion notification requiring user action": the driver's own
    # --max-ai-credits cap reached; its answer is shaped (_limit_kept)
    "session_limits_exhausted.requested",
})  # fmt: skip
# the events whose `model` field names the model that served the session
_MODEL_EVENTS = frozenset({"model.call_start", "assistant.message", _TOOL_START,
                           "assistant.usage"})  # fmt: skip
_USAGE_RECORD = "session.usage_record"
_PROGRESS = "tool.execution_progress"
_LIMIT_DONE = "session_limits_exhausted.completed"
# The event review of 2026-11-18: why each documented type the session could not emit locked
# down (no MCP, skills, subagents, hooks or custom instructions; five tools; headless) is kept
# unknown on purpose. Each stops the night with its reason.
_KEPT = {
    "a hook ran": ("hook.start", "hook.progress", "hook.end"),
    "a skill ran or was loaded": ("skill.invoked", "skill.invoked_ref", "skill.context_delivered",
                                  "skill.context_delivered_ref", "session.skills_loaded"),
    "a subagent, custom agent or background agent ran": (
        "subagent.started", "subagent.completed", "subagent.failed", "subagent.selected",
        "subagent.deselected", "subagent.configured", "session.custom_agents_updated"),
    "a HydraFusion multi-model turn": (
        "assistant.fusion_phase_started", "assistant.fusion_phase_activity",
        "assistant.fusion_phase_completed", "assistant.fusion_phase_failed",
        "session.fusion_route_started", "session.fusion_route_failed", "session.fusion_resolved",
        "session.fusion_handoff", "session.fusion_commit_started", "session.fusion_completed",
        "session.fusion_change_checkpoint"),
    "an MCP server, MCP app or MCP sampling": (
        "mcp.oauth_required", "mcp.oauth_completed", "mcp.oauth_recovery_completed",
        "mcp.headers_refresh_required", "mcp.headers_refresh_completed",
        "mcp.tools.list_changed", "mcp.prompts.list_changed", "mcp.resources.list_changed",
        "mcp_app.tool_call_complete", "session.mcp_server_status_changed",
        "session.mcp_server_tools_loaded", "session.mcp_server_needs_reconnect",
        "session.mcp_server_removed", "sampling.requested", "sampling.completed"),
    # 1.0.111 persists a permission.requested and .completed per refusal but streams neither
    "a permission prompt, decision or mode": (
        "permission.requested", "permission.completed", "permission.assentDetected",
        "permission.carriedForward", "permission.contextualAuthorization",
        "permission.messageAuthorization", "permission.messageAuthorizationDegraded",
        "permission.messageAuthorizationRead", "session.permissions_changed",
        "session.permission_recovery", "program.permission_requested"),
    "a model switch or Auto model routing": (
        "session.model_change", "session.model_deselected", "session.auto_mode_resolved",
        "session.auto_tier_recommendation", "session.auto_tier_switch_failed",
        "auto_mode_switch.requested", "auto_mode_switch.completed",
        "auto_mode_recovery.outcome", "auto_mode_recovery_consent.requested",
        "auto_mode_recovery_consent.completed"),
    "an agent mode, plan mode or Autopilot objective": (
        "session.mode_changed", "session.mode_notice_delivered", "session.plan_changed",
        "exit_plan_mode.requested", "exit_plan_mode.completed",
        "session.autopilot_objective_changed", "session.autopilot_stopped",
        "session.task_complete"),
    # 1.0.111 persists one system.message per session but streams none
    "instruction text the driver did not write": ("system.message", "session.custom_notification",
                                                  "session.managed_settings_resolved",
                                                  "session.managed_settings_enforced"),
    "a tool, program or command outside the session's five tools": (
        "external_tool.requested", "external_tool.completed", "program.execution",
        "program.tool_execution_start", "program.tool_execution_complete", "tool.user_requested",
        "tool_search.activated", "assistant.server_tool_progress", "command.execute",
        "command.queued", "command.completed", "workflow.run_started", "workflow.run_updated",
        "workflow.run_settled", "session.memory_changed", "sandbox.decision"),
    # "internal durable record of tool calls that ran without their own tool events"
    "tool calls the stream does not show": ("session.tool_outcomes_recorded",),
    "a question, form or reply that needs a person": (
        "user_input.requested", "user_input.completed", "elicitation.requested",
        "elicitation.completed", "human_response.recorded", "ui.ephemeral_query"),
    "an IDE, canvas, extension or plugin": (
        "ide.connection_changed", "ide.selection_changed", "ide.add_file_reference",
        "ide.elicitation_complete", "session.canvas.opened", "session.canvas.closed",
        "session.canvas.recorded", "session.canvas.removed", "session.canvas.registry_changed",
        "session.canvas.unavailable", "session.extensions_loaded",
        "session.extensions.attachments_pushed", "session.managed_plugin_progress"),
    # the driver never interrupts a session: it ends one with taskkill /F, in its own process
    # group, so no console Ctrl-C reaches it either
    "an interrupt the driver did not send": ("abort", "agent.interrupted"),
    "another session, host or schedule steering this one": (
        "session.resume", "session.handoff", "session.remote_steerable_changed",
        "session.schedule_created", "session.schedule_cancelled", "session.schedule_rearmed",
        "session.snapshot_rewind", "session.context_cleared"),
    # the audit resolves relative paths from session.start's cwd, the attempt dir
    "a working directory the audit did not resolve paths from": ("session.context_changed",),
    # "relative path within the session workspace files directory", under COPILOT_HOME
    "a write into Copilot's own session workspace that no tool call names": (
        "session.workspace_file_changed",),
    # "current session limits, or null when no limits are active ... Null clears the limits"
    # (the review of 2026-11-20); none of the 436 recorded sessions has one
    "a change of the driver's credit cap (null clears it)": ("session.session_limits_changed",),
}
KEPT_UNKNOWN = {kind: why for why, kinds in _KEPT.items() for kind in kinds}


def _usage_known(usage: object) -> bool:
    """A model call's usage (1.0.111's AssistantUsageData) of the main agent: initiator `user`
    (the first call) or `agent`, interactionType conversation-agent (all 7,405 usage records of
    the 436 recorded sessions), no sub-agent's parentToolCallId. The schema's other initiators
    ("sub-agent", "mcp-sampling") and classes (conversation-subagent, -sampling, -background)
    stay unknown."""
    usage = _mapping(usage)
    return (usage.get("initiator") in ("user", "agent")
            and usage.get("interactionType") == "conversation-agent"
            and "parentToolCallId" not in usage)  # fmt: skip


# The review of 2026-11-20: `instruction.update` is "an authoritative developer-instruction
# update" from the runtime, "the SDK host" or "managed policy" (1.0.111's event schema). All 436
# recorded sessions carry exactly this one, stream and persisted log alike; any other is
# instruction text the driver did not write.
_INSTRUCTION = "instruction.update"
_SANDBOX_GUIDANCE = {
    "content": "<system_reminder>\n<environment_limitations>\nCurrent command-sandbox guidance, "
               "superseding earlier sandbox status:\nYou are *not* operating in a sandboxed "
               "environment dedicated to this task. You may be sharing the environment with "
               "other users.\n</environment_limitations>\n</system_reminder>",
    "authority": "runtime", "lifetime": "persistent", "boundary": "nextModelRequest",
    "fallback": "rebuildSystemPrompt", "name": "sandbox-guidance", "postInitial": False,
}  # fmt: skip
# The same review: "MCP server status summaries" (connected, failed, needs-auth, pending,
# disabled, stopped or not_configured). Every server of the 436 recorded sessions is disabled;
# one in any other state could hand the model its tools or instructions.
_MCP_LOADED = "session.mcp_servers_loaded"
_MCP_OFF = "disabled"


def _mcp_all_off(event: dict) -> bool:
    servers = _data(event).get("servers")
    return isinstance(servers, list) and all(_mapping(s).get("status") == _MCP_OFF
                                             for s in servers)  # fmt: skip


def _limit_kept(event: dict) -> bool:
    """An exhausted-cap prompt answered `cancel`: "leave the limit unchanged and cancel the
    blocked model request" (add, set and unset would lift the driver's cap)."""
    return _mapping(_data(event).get("response")).get("action") == "cancel"


# Run 20261116-copilot: "a detected loss of a previously cached prompt prefix" (1.0.111's event
# schema). It runs nothing; it is known only while both of its requests list none but the
# session's tools (_cache_break_known), and their models join init_problems' model check.
_CACHE_BREAK = "prompt_cache_break"
_CACHE_REQUESTS = ("beforeRequest", "afterRequest")


# Run 20261116-fable-ab: "runtime events like background task completion" (1.0.111's event
# schema). Only kind shell_completed is known: it reports a powershell command the audit judges
# by its own call. Its other kinds stay unknown on purpose (the review of 2026-11-18):
_NOTIFICATION = "system.notification"
KEPT_UNKNOWN_NOTIFICATIONS = {
    "agent_completed": "a background agent completed",
    "agent_idle": "a background agent went idle",
    "new_inbox_message": "a message from another sender",
    # powershell's `detach` is itself kept unknown
    "shell_detached_completed": "a detached shell, which outlives the audit",
    "instruction_discovered": "an instruction file found during tool access",
    "workflow_completed": "a workflow run",
    "unclassified": "an external host's notification",
}


def _notification_known(event: dict) -> bool:
    kind = _mapping(_data(event).get("kind"))
    code = kind.get("exitCode")
    return (kind.get("type") == "shell_completed" and isinstance(kind.get("shellId"), str)
            and isinstance(code, int) and not isinstance(code, bool))  # fmt: skip


def _cache_requests(event: dict) -> list:
    return [_data(event).get(side) for side in _CACHE_REQUESTS]


def _cache_break_known(event: dict) -> bool:
    for request in _cache_requests(event):
        tools = _mapping(request).get("tools")
        if not isinstance(tools, list) or not tools:
            return False
        if any(_mapping(tool).get("name") not in AVAILABLE_TOOLS for tool in tools):
            return False
    return True


def _served_models(events: Sequence[dict]) -> list:
    """Every model a model call, message, tool call, usage, usage record or cache-break request
    names (a usage's `responseModel` is the provider's own spelling, never an arm's id)."""
    out = [_data(e).get("model") for e in events if e.get("type") in _MODEL_EVENTS]
    for event in events:
        if event.get("type") == _CACHE_BREAK:
            out += [_mapping(r).get("model") for r in _cache_requests(event)]
        elif event.get("type") == _USAGE_RECORD:
            out.append(_mapping(_data(event).get("usage")).get("model"))
    return out
# 1.0.111's two refusal texts (the capture): a rule named, and no allow rule with nobody to ask
_DENIED_CODE = "denied"
_BY_RULES = re.compile(r"Permission to run this tool was denied due to the following rules: "
                       r"(`[^`]+`(?:, `[^`]+`)*)")  # fmt: skip
_NO_APPROVAL = ("Permission denied because no interactive user response was available. Retry in "
                "an interactive session so the user can approve it, or try an alternative that "
                "does not require this permission.")  # fmt: skip
# the text a hook's output leaves on a tool result (the capture: "Tool "view" succeeded.
# Additional guidance from postToolUse hooks:")
_HOOK_TEXT = re.compile(r"Additional (?:guidance|context) from \w+ hooks?", re.I)
_LIMITS = frozenset({"rate_limit", "quota"})  # session.error types that pause the arm
_COUNTED = frozenset({"context_limit"})  # counted like a turn cap
_NANO_PER_CREDIT = 1_000_000_000
_EXCERPT = 160


def _mapping(value: object) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _data(event: Mapping) -> Mapping:
    return _mapping(event.get("data"))


def _norm(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def init_event(events: Sequence[dict]) -> dict | None:
    """The first `session.start` as {"model", "cwd", "version", "max_ai_credits"}, or None."""
    start = next((e for e in events if e.get("type") == _START), None)
    if start is None:
        return None
    data = _data(start)
    return {"model": data.get("selectedModel"), "cwd": _mapping(data.get("context")).get("cwd"),
            "version": data.get("copilotVersion"),
            "max_ai_credits": _mapping(data.get("sessionLimits")).get("maxAiCredits")}


def init_problems(events: Sequence[dict], *, cwd: Path, accepted: Sequence[str],
                  max_ai_credits: int) -> list[str]:  # fmt: skip
    """Why the session is not the one the driver launched, one text per problem; [] when it
    is (see the module docstring)."""
    init = init_event(events)
    if init is None:
        return ["no session.start event"]
    problems = []
    raw = init["cwd"]
    if not isinstance(raw, str) or not raw or _norm(raw) != _norm(str(cwd)):
        problems.append(f"session.start cwd {raw!r} is not the attempt dir {str(cwd)!r}")
    if init["model"] not in accepted:
        problems.append(f"session.start model {init['model']!r} is not one of {list(accepted)}")
    if init["max_ai_credits"] != max_ai_credits or isinstance(init["max_ai_credits"], bool):
        problems.append(f"session.start sessionLimits.maxAiCredits {init['max_ai_credits']!r} is "
                        f"not the requested {max_ai_credits}")  # fmt: skip
    others = sorted({str(model) for model in _served_models(events)
                     if model is not None and model not in accepted})  # fmt: skip
    if others:
        problems.append(f"the session was served by {', '.join(others)}, not {list(accepted)}")
    return problems


def _result(events: Sequence[dict]) -> Mapping | None:
    results = [e for e in events if e.get("type") == _RESULT]
    return results[-1] if results else None


def has_result(events: Sequence[dict]) -> bool:
    """The session ended with its `result` line (the driver's `measured`)."""
    return _result(events) is not None


def turns(events: Sequence[dict]) -> int:
    """The number of `assistant.turn_end` events."""
    return sum(e.get("type") == _TURN_END for e in events)


def read_usage(path: Path) -> dict | None:
    """The --usage-output-file document: a JSON object, else None (missing, unreadable, not
    JSON or not an object)."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _tokens(doc: Mapping | None, key: str) -> int:
    return _count(_mapping(_mapping(_mapping(doc).get("tokenDetails")).get(key)).get("tokenCount"))


def usage(events: Sequence[dict], doc: Mapping | None) -> Usage:
    """The session's accounting (see the module docstring); tokens 0 with no usage document."""
    duration = _mapping(_mapping(_result(events)).get("usage")).get("sessionDurationMs")
    return Usage(input_tokens=_tokens(doc, "input"), output_tokens=_tokens(doc, "output"),
                 cache_read_tokens=_tokens(doc, "cache_read"),
                 cache_creation_tokens=_tokens(doc, "cache_write"), turns=turns(events),
                 cost_usd=0.0, duration_ms=_count(duration))  # fmt: skip


def credits(doc: Mapping | None) -> float | None:
    """The AI credits the session spent (`totalNanoAiu` / 1e9), or None when the document
    names no whole number of nano AIU of 0 or more."""
    nano = _mapping(doc).get("totalNanoAiu")
    if not isinstance(nano, int) or isinstance(nano, bool) or nano < 0:
        return None
    return nano / _NANO_PER_CREDIT


class Call(NamedTuple):
    """One tool call: its id, tool, arguments, its start and completion data (None: never
    completed) and whether its events came from the main agent with no foreign start field."""

    ident: str
    tool: object
    arguments: object
    start: Mapping
    complete: Mapping | None
    own: bool


def calls(events: Sequence[dict]) -> list[Call]:
    """Every tool call with a start, once, in start order (see the module docstring)."""
    found: dict[str, Call] = {}
    for event in events:
        kind, data = event.get("type"), _data(event)
        ident = data.get("toolCallId")
        if not isinstance(ident, str):
            continue
        own = _AGENT not in event
        if kind == _TOOL_START and ident not in found:
            found[ident] = Call(ident, data.get("toolName"), data.get("arguments"), data, None,
                                own and not _FOREIGN_START & set(data))  # fmt: skip
        elif kind == _TOOL_DONE and ident in found:
            call = found[ident]
            found[ident] = call._replace(complete=data, own=call.own and own)
    return list(found.values())


def _shaped(tool: object, arguments: object) -> bool:
    if tool not in _SHAPES or not isinstance(arguments, Mapping):
        return False
    need, may = _SHAPES[tool]
    if not set(need) <= set(arguments) or not set(arguments) <= set(need) | set(may):
        return False
    checks = {**need, **may}
    return all(checks[key](value) for key, value in arguments.items())


# Nights 20261114-nearmiss7 and -lanesC3: the two keys seen on create calls that the CLI drops
# (no schema of its own has them). Security review of 469cab57: an allowlist of exactly these,
# on create and edit only, and only when the completion's fileEdits name the call's own path.
_DROPPED_KEYS = frozenset({"description", "file_path", "old_path"})  # old_path: 20261116-fable-ab


def _dropped_keys_only(call: Call) -> bool:
    """A create or edit whose only extra keys are _DROPPED_KEYS and whose completion edited
    exactly its own path (the write the audit then judges)."""
    if call.tool not in _WRITE_TOOLS or not isinstance(call.arguments, Mapping):
        return False
    extra = set(call.arguments) & _DROPPED_KEYS
    rest = {k: v for k, v in call.arguments.items() if k not in _DROPPED_KEYS}
    edits = _list(_mapping(call.complete).get("fileEdits"))
    path = rest.get("path")
    return (bool(extra) and _shaped(call.tool, rest) and len(edits) == 1
            and _mapping(edits[0]).get("path") == path)  # fmt: skip


def known(call: Call) -> bool:
    """A call the audit can judge: a known tool in its known shape, by the main agent."""
    return call.own and (_shaped(call.tool, call.arguments) or _dropped_keys_only(call))


def request(call: Call) -> str:
    """A known call's request: its path, its command, or its shell id."""
    arguments = call.arguments
    key = "path" if call.tool in _PATH_TOOLS else "command" if call.tool == SHELL else "shellId"
    return arguments[key]


class Denial(NamedTuple):
    """One known call Copilot refused: its id, tool, request (path or command) and the rules
    its refusal named (None: no allow rule and nobody to ask)."""

    ident: str
    tool: str
    request: str
    rule: str | None


def denial(call: Call) -> Denial | None:
    """The call as Copilot's refusal (see `denials`), or None: it ran."""
    done = call.complete
    if not known(call) or done is None or done.get("success") is not False:
        return None
    error = _mapping(done.get("error"))
    message = error.get("message")
    if error.get("code") != _DENIED_CODE or not isinstance(message, str):
        return None
    if message == _NO_APPROVAL:
        return Denial(call.ident, call.tool, request(call), None)
    found = _BY_RULES.fullmatch(message)
    return Denial(call.ident, call.tool, request(call), found.group(1)) if found else None


def denials(events: Sequence[dict]) -> list[Denial]:
    """Every known call Copilot refused in one of its two exact forms, in order."""
    return [found for call in calls(events) if (found := denial(call)) is not None]


# night 20261114-nearmiss: an edit of a path that does not exist fails with code `failure` and
# this exact text before Copilot's permission check (an edit of an existing file outside the
# write rules is refused, `denied`: the coordinator's probe the same night), so it wrote nothing
_FAILURE_CODE = "failure"
_ENOENT = "Unhandled error: Error: ENOENT: no such file or directory, open '{path}'"


def _missing_edit(call: Call) -> bool:
    """A known edit that failed with exactly ENOENT on its own path: it wrote nothing."""
    done = _mapping(call.complete)
    error = _mapping(done.get("error"))
    return (call.tool == EDIT and known(call) and done.get("success") is False
            and error.get("code") == _FAILURE_CODE
            and error.get("message") == _ENOENT.format(path=request(call)))  # fmt: skip


def _ran(events: Sequence[dict], tools: frozenset[str]) -> list[Call]:
    return [call for call in calls(events)
            if call.tool in tools and known(call) and denial(call) is None
            and not _missing_edit(call)]  # fmt: skip


def commands(events: Sequence[dict]) -> list[str]:
    """The command of every known powershell call that was not denied, in order."""
    return [call.arguments["command"] for call in _ran(events, frozenset({SHELL}))]


# night 20261114-nearmiss2: a tool result too large to show is saved by Copilot itself to
# SPILL_DIR/<n>-copilot-tool-output-<pid>-<uuid>.txt and announced in that result; the model
# may then view it. Only that exact announced path, in that form, counts as the session's own.
SPILL_DIR = Path(tempfile.gettempdir())
_SPILL_NAME = re.compile(r"\d+-copilot-tool-output-\d+-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
                         r"\.txt")  # fmt: skip
_SPILLED = re.compile(r"Output too large to read at once \([\d.]+ KB\)\. Saved to: (\S+)")


def _forward(path: str) -> str:
    """A path with forward slashes and case folded the platform's way, for comparing paths the
    CLI reports (backslashes on Windows) with SPILL_DIR on any platform (CI runs on Linux)."""
    return os.path.normcase(path).replace("\\", "/")


def _own_spill(path: str) -> bool:
    folder, _, name = path.replace("\\", "/").rpartition("/")
    return (_SPILL_NAME.fullmatch(name) is not None
            and _forward(folder) == _forward(str(SPILL_DIR)))  # fmt: skip


def read_targets(events: Sequence[dict]) -> list[str]:
    """The path of every known view call that was not denied, in order, except a view of a
    spill an earlier result of this session announced (`_SPILLED`, `_own_spill`)."""
    out, announced = [], set()
    ran = {call.ident for call in _ran(events, frozenset({VIEW}))}
    for call in calls(events):
        if call.ident in ran:
            path = call.arguments["path"]
            if path not in announced:
                out.append(path)
        texts = _texts(_mapping(call.complete).get("result"))
        announced |= {m.group(1) for text in texts for m in _SPILLED.finditer(text)
                      if _own_spill(m.group(1))}  # fmt: skip
    return out


def _edits(events: Sequence[dict]) -> list[str]:
    """Every path a completion's fileEdits or the result's filesModified names (one that is not
    a string by its repr, so the audit never passes it)."""
    out = []
    for call in calls(events):
        for edit in _list(_mapping(call.complete).get("fileEdits")):
            path = _mapping(edit).get("path")
            out.append(path if isinstance(path, str) else repr(edit))
    changes = _mapping(_mapping(_mapping(_result(events)).get("usage")).get("codeChanges"))
    out += [p if isinstance(p, str) else repr(p) for p in _list(changes.get("filesModified"))]
    return out


def _list(value: object) -> list:
    return value if isinstance(value, list) else [] if value is None else [value]


def write_targets(events: Sequence[dict]) -> list[str]:
    """Every path a known create or edit call that was not denied names, then every fileEdits
    and filesModified path, each once, in order (see the module docstring)."""
    paths = [call.arguments["path"] for call in _ran(events, _WRITE_TOOLS)]
    return list(dict.fromkeys([*paths, *_edits(events)]))


def denied_writes(events: Sequence[dict]) -> list[str]:
    """The path of every create or edit call Copilot refused, in order (the night audit's
    denied writes, as agyjson.denied_writes)."""
    return [d.request for d in denials(events) if d.tool in _WRITE_TOOLS]


def _why(call: Call) -> str:
    if not call.own:
        return "made by a subagent, a program or an MCP server"
    if call.tool not in KNOWN_TOOLS:
        return "not a tool the Copilot audit knows"
    keys = sorted(call.arguments) if isinstance(call.arguments, Mapping) else call.arguments
    return f"with arguments {keys!r}, not its known shape"


# Nights 20261114-nearmiss3 and -nearmiss4: an edit missing a required field is answered in one
# of two exact forms, code `failure`, and never runs. Only those forms, only for edit, only
# naming a required field the call really lacks, with no edits on its completion, are excused
# (the security review of the first, broader rule).
_REJECTED_EDIT = (re.compile(r"Invalid inputs: (\w+) is required"),
                  re.compile(r'"(\w+)": Required'))


def _rejected(call: Call) -> bool:
    """A main-agent edit (run 20261116-copilot3: or create) the CLI refused for a missing
    required field: it never ran."""
    done = _mapping(call.complete)
    error = _mapping(done.get("error"))
    message = error.get("message")
    if not (call.own and call.tool in _WRITE_TOOLS and isinstance(call.arguments, Mapping)
            and done.get("success") is False and error.get("code") == _FAILURE_CODE
            and isinstance(message, str) and not done.get("fileEdits")):  # fmt: skip
        return False
    found = next((m for form in _REJECTED_EDIT if (m := form.fullmatch(message))), None)
    need, may = _SHAPES[call.tool]
    if found is not None:
        return found.group(1) in need and found.group(1) not in call.arguments
    if call.tool != EDIT:
        return False
    # night 20261114-nearmiss5: an edit lacking old_str of a file not yet written failed with
    # ENOENT on its own path before the CLI checked old_str: it wrote nothing
    path = call.arguments.get("path")
    return (isinstance(path, str) and set(call.arguments) <= set(need) | set(may)
            and message == _ENOENT.format(path=path))  # fmt: skip


def _progress_known(event: dict, seen: Mapping) -> bool:
    """Progress of a call this session already started (`seen` holds the starts read so far)."""
    ident = _data(event).get("toolCallId")
    return isinstance(ident, str) and (_TOOL_START, ident) in seen


# Each of the types known only in an exact shape: its check (the event, the tool starts read so
# far) and why an event outside that shape is unknown. With KNOWN_EVENTS and KEPT_UNKNOWN they
# cover every event type of the reviewed schema.
_SHAPE_CHECKS = {
    _CACHE_BREAK: (lambda e, _: _cache_break_known(e), "lists a tool the session was not given"),
    _NOTIFICATION: (lambda e, _: _notification_known(e),
                    "of a kind the Copilot audit does not know"),
    "assistant.usage": (lambda e, _: _usage_known(_data(e)), "is not a main-agent usage"),
    _USAGE_RECORD: (lambda e, _: _usage_known(_data(e).get("usage")),
                    "is not a main-agent usage"),
    _PROGRESS: (_progress_known, "names no tool call this session started"),
    _LIMIT_DONE: (lambda e, _: _limit_kept(e), "answers the credit cap with anything but cancel"),
    _INSTRUCTION: (lambda e, _: _data(e) == _SANDBOX_GUIDANCE,
                   "is not the runtime's own sandbox guidance: instruction text the driver did "
                   "not write"),
    _MCP_LOADED: (lambda e, _: _mcp_all_off(e), "lists an MCP server that is not disabled"),
}
SHAPED_EVENTS = frozenset(_SHAPE_CHECKS)


def _event_problem(event: dict, seen: Mapping) -> str | None:
    """Why the audit cannot judge this event, or None (see unknown_steps)."""
    kind = event.get("type")
    if not isinstance(kind, str):
        return f"event type {kind!r} is not one the Copilot audit knows"
    if _AGENT in event:  # the CLI's schema: on the envelope of a subagent's events
        return f"event type {kind!r} carries agentId: a subagent's event"
    if kind in KNOWN_EVENTS:
        return None
    if kind in SHAPED_EVENTS:
        check, why = _SHAPE_CHECKS[kind]
        if check(event, seen):
            return None
        sort = _mapping(_data(event).get("kind")).get("type") if kind == _NOTIFICATION else None
        if isinstance(sort, str) and sort in KEPT_UNKNOWN_NOTIFICATIONS:
            return (f"event type {kind!r} of kind {sort!r} is kept unknown on purpose: "
                    f"{KEPT_UNKNOWN_NOTIFICATIONS[sort]}")  # fmt: skip
        return f"event type {kind!r} {why}"
    if kind in KEPT_UNKNOWN:
        return f"event type {kind!r} is kept unknown on purpose: {KEPT_UNKNOWN[kind]}"
    return f"event type {kind!r} is not one the Copilot audit knows"


def unknown_steps(events: Sequence[dict]) -> list[str]:
    """Fail closed: why each tool call, completion or event is one the audit cannot judge (see
    the module docstring)."""
    out = [f"tool call {call.ident!r}: tool {call.tool!r} {_why(call)}"
           for call in calls(events) if not known(call) and not _rejected(call)]  # fmt: skip
    seen: dict[tuple[object, object], int] = {}
    for event in events:
        kind, ident = event.get("type"), _data(event).get("toolCallId")
        why = _event_problem(event, seen)
        if why is not None:
            out.append(why)
        if kind == _USER:  # the driver's one prompt (the review of 2026-11-20)
            seen[(kind, None)] = seen.get((kind, None), 0) + 1
            if seen[(kind, None)] == 2:
                out.append("a second user.message: text the driver did not write")
        if kind not in (_TOOL_START, _TOOL_DONE):
            continue
        key = (kind, ident if isinstance(ident, str) else repr(ident))
        seen[key] = seen.get(key, 0) + 1
        if not isinstance(ident, str):  # calls() cannot pair it, so nothing else judges it
            out.append(f"{kind} with tool call id {ident!r}, not a string")
        elif kind == _TOOL_DONE and (_TOOL_START, ident) not in seen:
            out.append(f"tool call {ident!r}: completed with no start")
        elif seen[key] == 2:  # a second start or completion: only one of each is read
            out.append(f"tool call {ident!r}: a second {kind}")
    return out


def _texts(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _texts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _texts(item)


# Copilot's own --max-ai-credits reporting, which it hands back as postToolUse guidance: the
# whole rest of a result after the guidance header, and nothing else (the coordinator's check of
# 2026-11-13: present with the cap, absent without it, under a fresh COPILOT_HOME)
_CREDIT_CAP_LINE = re.compile(r":\n\[cost: \d{1,3}% used · \$\d+\.\d{2} left\]")


def _hook_text(text: str) -> re.Match | None:
    """The hook guidance in one result text, unless it is only the credit cap's own line."""
    found = _HOOK_TEXT.search(text)
    if found is None or _CREDIT_CAP_LINE.fullmatch(text, found.end()):
        return None
    return found


def hook_traces(events: Sequence[dict]) -> list[str]:
    """Each tool result that carries a hook's guidance text, named by its call and the text
    (the credit cap's own line alone is none)."""
    out = []
    for call in calls(events):
        result = _mapping(call.complete).get("result")
        found = next((m for text in _texts(result) if (m := _hook_text(text))), None)
        if found is not None:
            out.append(f"tool call {call.ident!r}: its result carries hook text "
                       f"{found.string[found.start():found.start() + _EXCERPT]!r}")
    return out


def response(events: Sequence[dict]) -> str:
    """The last assistant message's text, stripped ('' with none)."""
    messages = [_data(e).get("content") for e in events if e.get("type") == "assistant.message"]
    texts = [m for m in messages if isinstance(m, str) and m.strip()]
    return texts[-1].strip() if texts else ""


def _session_error(events: Sequence[dict]) -> Mapping | None:
    return next((_data(e) for e in events if e.get("type") == _ERROR), None)


def failure(events: Sequence[dict]) -> str | None:
    """`copilot session.error <type>: <message>` for the first session.error, else `copilot
    exited <code>` for a result with a non-zero exit code, else None."""
    error = _session_error(events)
    if error is not None:
        return f"copilot session.error {error.get('errorType')!r}: {error.get('message')}"
    result = _result(events)
    if result is not None and result.get("exitCode") != 0:
        return f"copilot exited {result.get('exitCode')!r}"
    return None


def classify(events: Sequence[dict], exit_code: int | None, timed_out: bool) -> Disposition:
    """The driver's action for a Copilot session (see the module docstring); `exit_code` is not
    read: the result line's own exit code and the session.error type decide."""
    if timed_out:
        return Disposition.ATTEMPT_DONE
    error = _session_error(events)
    if error is not None:
        kind = error.get("errorType")
        if kind in _LIMITS:
            return Disposition.LIMIT
        return Disposition.ATTEMPT_DONE if kind in _COUNTED else Disposition.STOP
    result = _result(events)
    if result is None:
        return Disposition.TRANSIENT
    return Disposition.ATTEMPT_DONE if result.get("exitCode") == 0 else Disposition.STOP
