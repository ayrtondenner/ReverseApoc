# SPDX-License-Identifier: GPL-3.0-or-later
"""The driver's reading of an `agy -p --output-format stream-json` session (Phase 07.2 plan 15;
D-21, D-24, D-26; RESEARCH "D-21. Antigravity CLI (agy) adapter").

Each stdout line is one JSON event, read by streamjson's own `parse_line`/`parse` (a malformed
line is counted, never fatal): `init {cwd, tools, permission_mode, model}` (the model only when
`--model` was passed, which the driver always does), `step_update {step_index, state, tool_name,
tool_info, usage, ...}` (one or more per step) and `result {status, error, duration_seconds,
num_turns, usage, denied_actions}`. agy 1.5.5 wraps each one as `{"event": kind, kind: {...}}`
(spike 012's round-2 canaries) and this module reads the payload; a line of any other shape is
no event. The envelope, the init and result fields and a write step's
`tool_info.parameters.Path` come from those captured streams; the other field names come from
the CLI's docs (RESEARCH) and the owner's canary proves them.

- `init_event`/`init_problems`: the driver's init check (a STOP condition like check_init): the
  init must exist, its cwd be the attempt dir, its model the requested slug, and its permission
  mode no bypass.
- `has_result`: whether a result event ended the session (the driver's `measured`).
- `usage`/`turns`: the last result's `usage`: `input_tokens` as input, `output_tokens` plus
  `thinking_tokens` as output, `cache_read_tokens` as cache read, no cache creation, no cost (an
  AI Plus subscription is measured in quota); `num_turns`; `duration_seconds` in ms.
- `commands`, `write_targets`, `read_targets`: each tool step once (by `step_index`, as its last
  update left it, in the order it first appeared): a run_command step's
  `tool_info.parameters.CommandLine` (agy 1.5.5's shape, spike 012 round 3: tool_info holds
  `name`, `parameters` and, once DONE, `output`, whose text reads `Command exited with code
  <n>.`; a command step of any other shape is an unknown step and no command run), or its path
  (`path`, `file_path`, `target_file` or `absolute_path`), a read only for a known read-only
  tool (`read_file`) and a write for every other tool (07.2 review WR-02: fail closed). A step
  agy soft-denied never ran, so it is in none of the three lists: its own last state is DENIED
  (RESEARCH "Permissions") or, as spike 012 saw agy 1.5.5 do, ERROR with the permission
  check's message (`denials`); agy then ends the turn. An ERROR with any other message stays
  in the lists (fail closed). A result's `denied_actions` never stand for a step; they are hook
  blocks. The driver's audit reads them (D-26).
- `unknown_steps`: each tool step that ran and is not a known tool (`run_command` in agy
  1.5.5's shape, `read_file` or `write_file` with a path) in its known shape, a subagent's included:
  the audit counts each as a stray (WR-02).
- `denied_actions`: the result's denied actions as `action(target)` strings.
- `denials`, `undenied_steps`, `response` (the agy canary's evidence): each tool step agy's
  permission check refused, with its action and target read from the step's own error message
  (spike 012: `permission check failed for write_file "<path>": user denied permission for
  write_file(<path>)`, state ERROR), or a step ending DENIED by its tool and path or command;
  every other tool step (it ran); the result's response text.
- `failure`: the result's status and error when the status is not SUCCESS, else None.
- `classify`: the driver's action (streamjson.Disposition): a wall-clock timeout is counted; a
  failure is STOP when it says authentication is required, LIMIT when it says a quota or rate
  limit was hit, else STOP (unknown fails closed); a SUCCESS result is counted; no result is
  TRANSIENT.
"""

from __future__ import annotations

import json
import os
import re
import shlex
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NamedTuple

from . import streamjson
from .streamjson import Disposition, Usage

parse = streamjson.parse  # one reader for every CLI's JSONL, never a copy
parse_line = streamjson.parse_line

_KIND = "event"  # agy 1.5.5 (spike 012 canaries): {"event": kind, kind: {payload}}
_INIT = "init"
_STEP = "step_update"
_RESULT = "result"
_SUCCESS = "SUCCESS"
# agy 1.5.5 names a write step's path as tool_info.parameters.Path (spike 012); the rest are
# RESEARCH's documented spellings, unconfirmed
_PATH_KEYS = ("Path", "path", "file_path", "target_file", "absolute_path")
_PARAMETERS = "parameters"
_BYPASS = re.compile(r"bypass|skip|danger|yolo|auto", re.I)  # a mode that approves by itself
_AUTH_TEXT = re.compile(r"authentication required|not (signed|logged) in", re.I)
_LIMIT_TEXT = re.compile(r"quota|rate.?limit|resource.?exhausted|limit (was )?(hit|reached)",
                         re.I)  # fmt: skip
_MS_PER_S = 1000


def _mapping(value: object) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _flat(event: Mapping) -> dict:
    """One agy 1.5.5 line, {"event": kind, kind: {...}}, as {"type": kind, **payload}; a line
    of any other shape is no event ({})."""
    kind = event.get(_KIND)
    payload = event.get(kind) if isinstance(kind, str) else None
    return {**payload, "type": kind} if isinstance(payload, Mapping) else {}


def _events(events: Sequence[dict]) -> list[dict]:
    return [_flat(event) for event in events]


def init_event(events: Sequence[dict]) -> dict | None:
    """The session's first `init` event's payload, or None."""
    return next((e for e in _events(events) if e.get("type") == _INIT), None)


def _norm(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _same_dir(raw: object, path: Path) -> bool:
    return isinstance(raw, str) and bool(raw) and _norm(raw) == _norm(str(path))


def init_problems(init: Mapping | None, *, cwd: Path, model: str) -> list[str]:
    """Why the init event is not this session's, one text per problem; [] when it is clean."""
    if init is None:
        return ["no init event"]
    problems = []
    if not _same_dir(init.get("cwd"), cwd):
        problems.append(f"init cwd {init.get('cwd')!r} is not the attempt dir {str(cwd)!r}")
    if init.get("model") != model:
        problems.append(f"init model {init.get('model')!r} is not the requested {model!r}")
    mode = init.get("permission_mode")
    if not isinstance(mode, str) or _BYPASS.search(mode):
        problems.append(f"init permission_mode {mode!r} bypasses or skips approvals")
    return problems


def _result(events: Sequence[dict]) -> Mapping | None:
    results = [e for e in _events(events) if e.get("type") == _RESULT]
    return results[-1] if results else None


def has_result(events: Sequence[dict]) -> bool:
    """The session ended with a result event (the driver's `measured`)."""
    return _result(events) is not None


def turns(events: Sequence[dict]) -> int:
    """The last result's `num_turns` (0 with no result)."""
    return _count(_mapping(_result(events)).get("num_turns"))


def usage(events: Sequence[dict]) -> Usage:
    """The session's accounting (see the module docstring); zero with no result."""
    result = _mapping(_result(events))
    use = _mapping(result.get("usage"))
    seconds = result.get("duration_seconds")
    seconds = seconds if isinstance(seconds, int | float) and not isinstance(seconds, bool) else 0
    return Usage(input_tokens=_count(use.get("input_tokens")),
                 output_tokens=_count(use.get("output_tokens"))
                 + _count(use.get("thinking_tokens")),
                 cache_read_tokens=_count(use.get("cache_read_tokens")), cache_creation_tokens=0,
                 turns=turns(events), cost_usd=0.0,
                 duration_ms=round(seconds * _MS_PER_S))  # fmt: skip


def _denied(entry: object) -> str:
    """One denied action as `action(target)`; an entry of any other shape by its repr."""
    if isinstance(entry, str):
        return entry
    entry = _mapping(entry)
    action, target = entry.get("action"), entry.get("target")
    if isinstance(action, str) and isinstance(target, str):
        return f"{action}({target})"
    return repr(entry)


def denied_actions(events: Sequence[dict]) -> list[str]:
    """The last result's `denied_actions`, each as `action(target)`."""
    found = _mapping(_result(events)).get("denied_actions")
    return [_denied(entry) for entry in found] if isinstance(found, list) else []


# 07.2 review WR-02: the tools the audit knows, each in its one shape (the settings' three
# actions); any other tool step that ran is a stray (`unknown_steps`), and a path step is a
# read only for a tool named here as read-only.
_COMMAND_TOOLS = frozenset({"run_command"})
# spike 012 round 3: agy 1.5.5's run_command step is tool_info {name, parameters:
# {CommandLine}, output} (the output, once DONE: `Command exited with code <n>.` then `Command
# output:`), the only command shape the audit knows
_COMMAND_LINE = "CommandLine"
_NAME = "name"
_OUTPUT = "output"
_COMMAND_INFO = frozenset({_NAME, _PARAMETERS, _OUTPUT})
_LEGACY_COMMAND = "command"  # RESEARCH's documented tool_info.command, never seen: unknown
_READ_TOOLS = frozenset({"read_file"})
_WRITE_TOOLS = frozenset({"write_file"})
_DENIED_STATE = "DENIED"  # a step's own last state when the settings soft-denied it
_ERROR_STATE = "ERROR"  # agy 1.5.5's last state for a soft-denied step (spike 012)
_TOOL_STEP = "TOOL"
_TOOL_FIELDS = ("tool_name", "tool_info", "subagent_info")


def _tool_step(event: Mapping) -> bool:
    """A step_update that is a tool call: its step_type says so, or it carries a tool field (a
    text step carries none)."""
    return event.get("type") == _STEP and (
        event.get("step_type") == _TOOL_STEP or any(event.get(k) for k in _TOOL_FIELDS))


def _ran(step: Mapping) -> bool:
    """WR-02: a step never ran only when it itself is a denial (`_denial`: it ends DENIED, or
    ERROR with agy's permission-check message, spike 012); a result's denied action is a hook
    block and never stands for a step."""
    return _denial(step) is None


def _steps(events: Sequence[dict]) -> list[Mapping]:
    """Each tool step once, in the order it first appeared, as its last update left it (a step
    without an integer index counts every time)."""
    found: list[Mapping] = []
    place: dict[int, int] = {}
    for event in _events(events):
        if not _tool_step(event):
            continue
        index = event.get("step_index")
        if isinstance(index, int) and index in place:
            found[place[index]] = event
            continue
        if isinstance(index, int):
            place[index] = len(found)
        found.append(event)
    return found


def _command_text(command: object) -> str:
    """A command as one string: a list joined the way a POSIX shell would receive it; any other
    value is its repr, so the audit never passes it."""
    if isinstance(command, str):
        return command
    if isinstance(command, list) and all(isinstance(part, str) for part in command):
        return shlex.join(command)
    return repr(command)


def _path(info: Mapping) -> str | None:
    """A path step's path: in tool_info itself or in its `parameters` (agy 1.5.5)."""
    where = (info, _mapping(info.get(_PARAMETERS)))
    found = next(((place, k) for place in where for k in _PATH_KEYS if k in place), None)
    if found is None:
        return None
    value = found[0][found[1]]
    return value if isinstance(value, str) else repr(value)


def _command_line(info: Mapping) -> object:
    """A step's command: agy 1.5.5's tool_info.parameters.CommandLine, else RESEARCH's
    tool_info.command; None when it names neither."""
    parameters = _mapping(info.get(_PARAMETERS))
    return parameters[_COMMAND_LINE] if _COMMAND_LINE in parameters else info.get(_LEGACY_COMMAND)


def _real_command(name: str, info: Mapping) -> bool:
    """agy 1.5.5's run_command shape and nothing more: tool_info names the tool, holds only
    its name, parameters and output, and its parameters only a string CommandLine."""
    parameters = info.get(_PARAMETERS)
    return (info.get(_NAME) == name and set(info) <= _COMMAND_INFO
            and isinstance(parameters, Mapping) and set(parameters) == {_COMMAND_LINE}
            and isinstance(parameters[_COMMAND_LINE], str))  # fmt: skip


def commands(events: Sequence[dict]) -> list[str]:
    """The CommandLine of every run_command step that ran in agy 1.5.5's shape (see the module
    docstring); a command step of any other shape is an unknown step, never a command run."""
    return [_mapping(step["tool_info"])[_PARAMETERS][_COMMAND_LINE] for step in _steps(events)
            if _ran(step) and step.get("tool_name") in _COMMAND_TOOLS
            and _known(step)]  # fmt: skip


def _paths(events: Sequence[dict], *, writes: bool) -> list[str]:
    """WR-02: a path step that ran is a read only when its tool is a known read-only one;
    every other path step is a write."""
    out = []
    for step in _steps(events):
        info = _mapping(step.get("tool_info"))
        path = None if _command_line(info) is not None else _path(info)
        if path is None or not _ran(step):
            continue
        if (step.get("tool_name") not in _READ_TOOLS) == writes:
            out.append(path)
    return out


def write_targets(events: Sequence[dict]) -> list[str]:
    """Every path a tool step that ran names, but a known read-only tool's, in order."""
    return _paths(events, writes=True)


def read_targets(events: Sequence[dict]) -> list[str]:
    """Every path a known read-only tool step that ran names, in order."""
    return _paths(events, writes=False)


def _known(step: Mapping) -> bool:
    """A known tool in its known shape, with no subagent behind it."""
    name, info = step.get("tool_name"), _mapping(step.get("tool_info"))
    if step.get("subagent_info") or not isinstance(name, str):
        return False
    if name in _COMMAND_TOOLS:
        return _real_command(name, info)
    return (name in _READ_TOOLS | _WRITE_TOOLS and _command_line(info) is None
            and _path(info) is not None)  # fmt: skip


def unknown_steps(events: Sequence[dict]) -> list[str]:
    """WR-02 (fail closed): why each tool step that ran is not one the audit can judge: its
    tool name is missing or unknown, its shape is not its tool's, or a subagent ran it."""
    out = []
    for step in _steps(events):
        if _ran(step) and not _known(step):
            keys = sorted(_mapping(step.get("tool_info")))
            out.append(f"step {step.get('step_index')!r}: tool {step.get('tool_name')!r} with "
                       f"{keys} is not a tool step the agy audit knows")  # fmt: skip
    return out


# spike 012: agy 1.5.5's text for a step its permission check refused, in tool_info.error
# (its binary's format: `permission check failed for %s %q: %w`), the target Go-quoted
_PERMISSION_FAILED = re.compile(r'permission check failed for (\S+) "((?:[^"\\]|\\.)*)"')
_ERROR = "error"
_MESSAGE = "message"


class Denial(NamedTuple):
    """One tool step agy's permission check refused: its index, its tool, the permission
    action and the target (from the error message, else the step's path or command)."""

    step: int | None
    tool: str | None
    action: str | None
    target: str | None


def _unquote(raw: str) -> str:
    """A Go %q body as its text; one that is not also a JSON string body stays as written."""
    try:
        return json.loads(f'"{raw}"')
    except ValueError:
        return raw


def _denial(step: Mapping) -> Denial | None:
    info = _mapping(step.get("tool_info"))
    index, tool = step.get("step_index"), step.get("tool_name")
    index = index if isinstance(index, int) and not isinstance(index, bool) else None
    tool = tool if isinstance(tool, str) else None
    message = _mapping(info.get(_ERROR)).get(_MESSAGE)
    found = _PERMISSION_FAILED.search(message) if isinstance(message, str) else None
    if found is not None and step.get("state") in (_DENIED_STATE, _ERROR_STATE):
        return Denial(index, tool, found.group(1), _unquote(found.group(2)))
    if step.get("state") != _DENIED_STATE:
        return None
    command = _command_line(info)
    return Denial(index, tool, tool, _path(info) if command is None else _command_text(command))


def denials(events: Sequence[dict]) -> list[Denial]:
    """Every tool step agy's permission check refused, in order (the agy canary's evidence):
    a step ending ERROR whose error message is the permission check's, or ending DENIED."""
    return [found for step in _steps(events) if (found := _denial(step)) is not None]


def undenied_steps(events: Sequence[dict]) -> list[str]:
    """`step <index>: <tool> (<state>)` for every tool step that is not a denial: it ran."""
    return [f"step {step.get('step_index')!r}: {step.get('tool_name')} ({step.get('state')})"
            for step in _steps(events) if _denial(step) is None]  # fmt: skip


def response(events: Sequence[dict]) -> str:
    """The last result's response text, stripped ('' with none)."""
    text = _mapping(_result(events)).get("response")
    return text.strip() if isinstance(text, str) else ""


def failure(events: Sequence[dict]) -> str | None:
    """`agy result status <status>: <error>` when the last result's status is not SUCCESS,
    else None (no result included)."""
    result = _result(events)
    if result is None or result.get("status") == _SUCCESS:
        return None
    error = result.get("error")
    return f"agy result status {result.get('status')!r}: {error if isinstance(error, str) else ''}"


def classify(events: Sequence[dict], exit_code: int | None, timed_out: bool) -> Disposition:
    """The driver's action for an agy session (see the module docstring); `exit_code` is not
    read: the result's status decides."""
    if timed_out:
        return Disposition.ATTEMPT_DONE
    text = failure(events)
    if text is not None:
        if _AUTH_TEXT.search(text):
            return Disposition.STOP
        return Disposition.LIMIT if _LIMIT_TEXT.search(text) else Disposition.STOP
    return Disposition.ATTEMPT_DONE if _result(events) is not None else Disposition.TRANSIENT
