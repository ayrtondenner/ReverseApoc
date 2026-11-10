# SPDX-License-Identifier: GPL-3.0-or-later
"""The driver's reading of a `codex exec --json` session (Phase 07.2 plan 13; D-13, D-16;
RESEARCH Q8).

Each stdout line is one JSON event, read by streamjson's own `parse_line`/`parse` (a malformed
line is counted, never fatal): `thread.started`, `turn.started`, `item.started`/`updated`/
`completed` (items `command_execution {command, aggregated_output, exit_code, status}`,
`file_change {changes: [{path, kind}]}`, `agent_message`, ...), `turn.completed {usage}`,
`turn.failed {error}` and a top-level `error`. No event names the model, so the driver records
the requested model and a null `model`, and runs no init check.

- `usage`: tokens summed over every `turn.completed`: `input_tokens` as input,
  `cached_input_tokens` as cache read, no cache creation, and `output_tokens` plus
  `reasoning_output_tokens` as output (ASSUMPTION, confirm at the canary: Codex reports the
  reasoning tokens apart from the output). Turns are the `turn.completed` count; the duration is
  the session's wall clock; there is no cost (a Plus subscription is measured in tokens).
- `commands`: each `command_execution` item's command, once per item id, in stream order (a
  started item the session never finished counts too), a list command joined as a POSIX shell
  would receive it, with one Windows shell layer (`powershell.exe -Command <cmd>`) taken off
  (the text the audit judges); `executions`: each such item with that text, its output, its
  exit code and its command as reported (the layer still on: what a stray finding names);
  `write_targets`: every path a `file_change` item names. The driver's Codex audit reads the
  executions and the write targets (D-26). `unknown_items`: every item of a type outside
  KNOWN_ITEMS (an MCP tool call, a web search, ...), each a stray (07.2 review WR-03: fail
  closed).
- `failure`: the text of the first `turn.failed` or top-level `error`, else None.
- `classify`: the driver's action (streamjson.Disposition): a wall-clock timeout is counted; a
  failure is LIMIT when its text says a usage limit was hit, else STOP (unknown fails closed);
  a session with a completed turn is counted; one with none is TRANSIENT.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Mapping, Sequence
from typing import NamedTuple

from . import streamjson
from .streamjson import Disposition, Usage

parse = streamjson.parse  # one reader for both CLIs' JSONL, never a copy
parse_line = streamjson.parse_line

_TURN_COMPLETED = "turn.completed"
_TURN_FAILED = "turn.failed"
_ERROR = "error"
_ITEM_EVENTS = ("item.started", "item.updated", "item.completed")
_COMMAND = "command_execution"
_FILE_CHANGE = "file_change"
# WR-03: the items the audit reads (the two above) or that do nothing (text, reasoning, a plan)
KNOWN_ITEMS = frozenset({"agent_message", "reasoning", "todo_list", _COMMAND, _FILE_CHANGE})
_MS_PER_S = 1000
# _unwrapped: the shell's program (double-quoted, single-quoted or bare), then its arguments
_SHELL = re.compile(r"""\s*(?:"(?P<dq>[^"]+)"|'(?P<sq>[^']+)'|(?P<bare>[^\s"']+))\s""")
_PATH_SEPARATORS = re.compile(r"[\\/]+")  # a run of either slash, POSIX-escaped `\\` too
# Only the real shells by absolute path: a bare name, a relative path or another directory could
# be a binary the session planted, run while the audit judged only its harmless argument
_WINDOWS_SHELLS = frozenset({r"c:\windows\system32\windowspowershell\v1.0\powershell.exe",
                             r"c:\program files\powershell\7\pwsh.exe"})  # fmt: skip
_SHELL_FLAGS = (["-command"], ["-noprofile", "-command"])  # casefolded, before the one <cmd>


def _mapping(value: object) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _completed(events: Sequence[dict]) -> list[Mapping]:
    return [_mapping(e.get("usage")) for e in events if e.get("type") == _TURN_COMPLETED]


def turns(events: Sequence[dict]) -> int:
    """The number of `turn.completed` events."""
    return len(_completed(events))


def usage(events: Sequence[dict], seconds: float = 0.0) -> Usage:
    """The session's accounting (see the module docstring); `seconds` is its wall clock."""
    usages = _completed(events)

    def total(key: str) -> int:
        return sum(_count(entry.get(key)) for entry in usages)

    return Usage(input_tokens=total("input_tokens"),
                 output_tokens=total("output_tokens") + total("reasoning_output_tokens"),
                 cache_read_tokens=total("cached_input_tokens"), cache_creation_tokens=0,
                 turns=len(usages), cost_usd=0.0,
                 duration_ms=round(seconds * _MS_PER_S))  # fmt: skip


def _items(events: Sequence[dict], kind: str) -> list[Mapping]:
    """Each item of `kind` once, in the order it first appeared, as its last event left it
    (an item without an id counts every time)."""
    found: list[Mapping] = []
    place: dict[str, int] = {}
    for event in events:
        if event.get("type") not in _ITEM_EVENTS:
            continue
        item = _mapping(event.get("item"))
        if item.get("type") != kind:
            continue
        ident = item.get("id")
        if isinstance(ident, str) and ident in place:
            found[place[ident]] = item
            continue
        if isinstance(ident, str):
            place[ident] = len(found)
        found.append(item)
    return found


class Execution(NamedTuple):
    """One command_execution item: its command as audited (as `commands` gives it), its output,
    its exit code (None while it ran or when the stream holds none) and its command as the
    session reported it (`reported`, the Windows shell layer still on: what a stray names)."""

    command: str
    output: str
    exit_code: int | None
    reported: str


def executions(events: Sequence[dict]) -> list[Execution]:
    """Every command_execution item, in order, as it ended (the Codex canary reads its
    outputs and exit codes)."""
    out = []
    for item in _items(events, _COMMAND):
        output = item.get("aggregated_output")
        code = item.get("exit_code")
        reported, audited = _command_texts(item.get("command"))
        out.append(Execution(audited, output if isinstance(output, str) else "",
                             code if isinstance(code, int) and not isinstance(code, bool)
                             else None, reported))  # fmt: skip
    return out


def _command_texts(command: object) -> tuple[str, str]:
    """A command as one string, as reported and as audited: a list is joined the way a POSIX
    shell would receive it; any other value is its repr, so the audit never passes it. The
    audited text has one Windows shell layer off (_unwrapped)."""
    if isinstance(command, list) and all(isinstance(part, str) for part in command):
        command = shlex.join(command)
    if isinstance(command, str):
        return command, _unwrapped(command)
    shown = repr(command)
    return shown, shown


def _unwrapped(text: str) -> str:
    """The Windows CLI reports a command wrapped in the shell that ran it, `"<...>\\powershell
    .exe" -Command <cmd>` (spike 012's rejected-command lines, a POSIX-quoted argv): that is
    <cmd>. The shell is one of _WINDOWS_SHELLS at its absolute path (any case, either slash,
    quoted or not), never a bare name or another path; at most one -NoProfile comes before
    -Command and exactly one argument after it. One layer only: a shell left inside stays as
    written, and any other shape is `text` unchanged, so the audit sees it."""
    found = _SHELL.match(text)
    if found is None:
        return text
    program = found.group("dq") or found.group("sq") or found.group("bare")
    if _PATH_SEPARATORS.sub(r"\\", program).casefold() not in _WINDOWS_SHELLS:
        return text
    try:
        args = shlex.split(text[found.end():])
    except ValueError:  # an unbalanced quote: no argv to read, audited as written
        return text
    flags = [arg.casefold() for arg in args[:-1]]
    return args[-1] if flags in _SHELL_FLAGS else text


def commands(events: Sequence[dict]) -> list[str]:
    """Every `command_execution` item's command, in order (see the module docstring)."""
    return [execution.command for execution in executions(events)]


def write_targets(events: Sequence[dict]) -> list[str]:
    """Every path a `file_change` item names, in order; a change with no string path is
    named by its repr, so the audit never passes it."""
    out = []
    for item in _items(events, _FILE_CHANGE):
        changes = item.get("changes")
        for change in changes if isinstance(changes, list) else [changes]:
            path = _mapping(change).get("path")
            out.append(path if isinstance(path, str) else repr(change))
    return out


def unknown_items(events: Sequence[dict]) -> list[str]:
    """07.2 review WR-03 (fail closed): one text per item, once per id, whose type is outside
    KNOWN_ITEMS (an MCP tool call, a web search, an item with no type, an item that is not an
    object): the audit has no reading of what it did, so each is a stray."""
    out: list[str] = []
    seen: set[str] = set()
    for event in events:
        if event.get("type") not in _ITEM_EVENTS:
            continue
        item = event.get("item")
        kind = item.get("type") if isinstance(item, Mapping) else None
        if kind in KNOWN_ITEMS:
            continue
        ident = item.get("id") if isinstance(item, Mapping) else None
        if isinstance(ident, str) and ident in seen:
            continue
        if isinstance(ident, str):
            seen.add(ident)
        shown = f"type {kind!r}" if isinstance(item, Mapping) else f"{item!r}, not an object"
        out.append(f"item {ident!r}: {shown} is not an item the Codex audit knows")
    return out


def _message(value: object) -> str:
    if isinstance(value, str):
        return value
    message = _mapping(value).get("message")
    return message if isinstance(message, str) else repr(value)


def failure(events: Sequence[dict]) -> str | None:
    """The text of the first `turn.failed` error or top-level `error`, else None."""
    for event in events:
        kind = event.get("type")
        if kind == _TURN_FAILED:
            return _message(event.get("error"))
        if kind == _ERROR:
            return _message(event.get("message", event))
    return None


def classify(events: Sequence[dict], exit_code: int | None, timed_out: bool) -> Disposition:
    """The driver's action for a Codex session (see the module docstring); `exit_code` is not
    read: a completed turn is counted whatever the CLI exited with."""
    if timed_out:
        return Disposition.ATTEMPT_DONE
    text = failure(events)
    if text is not None:
        return Disposition.LIMIT if streamjson._LIMIT_TEXT.search(text) else Disposition.STOP
    return Disposition.ATTEMPT_DONE if turns(events) else Disposition.TRANSIENT
