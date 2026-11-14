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
  one id (only one of each is read), and each event of a type outside KNOWN_EVENTS (a hook, a
  skill, a subagent, a permission prompt, a model switch...): the audit counts each as a
  stray. `hook_traces`: each tool result that carries a hook's guidance text (the owner's
  user-level postToolUse hook reached the capture's results): the per-session COPILOT_HOME
  turns every hook off, so any is a stray.
- `failure`: the first `session.error`'s errorType and message, else the result's non-zero
  exit code, else None. `classify`: a wall-clock timeout is counted; a session.error is LIMIT
  for a rate limit or a quota, counted for a context limit, STOP for anything else; a result
  with exit 0 is counted, any other exit STOP (fail closed); no result is TRANSIENT.
"""

from __future__ import annotations

import json
import os
import re
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


_SHAPES: dict[str, tuple[dict, dict]] = {
    VIEW: ({"path": _text}, {}),
    CREATE: ({"path": _text, "file_text": _text}, {}),
    EDIT: ({"path": _text, "old_str": _text, "new_str": _text}, {}),
    SHELL: ({"command": _text}, {"description": _text, "mode": lambda v: v in ("sync", "async"),
                                 "initial_wait": _seconds}),
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
# (compaction, errors, warnings, usage); any other type is an unknown step (fail closed).
KNOWN_EVENTS = frozenset({
    _START, "session.mcp_servers_loaded", "session.tools_updated", "instruction.update",
    "user.message", "assistant.turn_start", "model.call_start", "assistant.reasoning_delta",
    "assistant.reasoning", "assistant.message_start", "assistant.message_delta",
    "assistant.message", "assistant.tool_call_delta", "model.call_finished",
    "model.call_final_result", _TOOL_START, _TOOL_DONE, "tool.shell_output",
    "tool.execution_partial_result", "session.info", "session.background_tasks_changed",
    _TURN_END, "session.usage_checkpoint", "assistant.idle", _RESULT,
    "session.compaction_start", "session.compaction_complete", "session.compaction_summarized",
    "session.truncation", "session.usage_info", "assistant.usage", "assistant.turn_retry",
    "model.call_failure", _ERROR, "session.warning", "session.idle", "session.shutdown",
    "session.session_limits_changed",
})  # fmt: skip
# the events whose `model` field names the model that served the session
_MODEL_EVENTS = frozenset({"model.call_start", "assistant.message", _TOOL_START})
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
    others = sorted({str(model) for e in events if e.get("type") in _MODEL_EVENTS
                     and (model := _data(e).get("model")) is not None
                     and model not in accepted})  # fmt: skip
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


def known(call: Call) -> bool:
    """A call the audit can judge: a known tool in its known shape, by the main agent."""
    return call.own and _shaped(call.tool, call.arguments)


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


def _ran(events: Sequence[dict], tools: frozenset[str]) -> list[Call]:
    return [call for call in calls(events)
            if call.tool in tools and known(call) and denial(call) is None]  # fmt: skip


def commands(events: Sequence[dict]) -> list[str]:
    """The command of every known powershell call that was not denied, in order."""
    return [call.arguments["command"] for call in _ran(events, frozenset({SHELL}))]


def read_targets(events: Sequence[dict]) -> list[str]:
    """The path of every known view call that was not denied, in order."""
    return [call.arguments["path"] for call in _ran(events, frozenset({VIEW}))]


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


def unknown_steps(events: Sequence[dict]) -> list[str]:
    """Fail closed: why each tool call, completion or event is one the audit cannot judge (see
    the module docstring)."""
    out = [f"tool call {call.ident!r}: tool {call.tool!r} {_why(call)}"
           for call in calls(events) if not known(call)]  # fmt: skip
    seen: dict[tuple[object, object], int] = {}
    for event in events:
        kind, ident = event.get("type"), _data(event).get("toolCallId")
        if kind not in KNOWN_EVENTS:
            out.append(f"event type {kind!r} is not one the Copilot audit knows")
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
