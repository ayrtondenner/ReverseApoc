# SPDX-License-Identifier: GPL-3.0-or-later
"""The driver's reading of a `claude -p --output-format stream-json --verbose` session (AGT-03,
AGT-04, D-08, D-36).

Each stdout line of a session is one JSON object. `parse_line` reads one defensively: a line that
is not a JSON object is malformed, counted by `parse`, and never fatal or executed (T-06-42).
Nothing here talks to the CLI; `session.run_session` feeds it.

`classify` maps a session to one driver action (`Disposition`), from the `system/api_retry`
errors, `rate_limit_event`s, the `result` event and the CLI's error text (D-08). The principle:
anything unknown fails closed (STOP), and only a known transient condition is not counted.

- STOP: api_retry `authentication_failed`, `oauth_org_not_allowed`, `account_on_hold` or
  `billing_error`, or any api_retry error outside the known sets (`cloud_credential_error`,
  `model_not_found`, `invalid_request`, `max_output_tokens`, `unknown`, a missing or future
  code); a rate_limit_event with errorCode `credits_required`, or `rejected` with any other
  errorCode; a result whose `subtype` is not `success`, `error_max_turns`,
  `error_max_budget_usd` or `error_during_execution`; an error result whose `api_error_status`
  is neither 429 nor 5xx (401, 400, 403, a non-integer, ...); error text "Credit balance is too
  low" or "Not logged in"; and, last, a `success` error result that no known signal explains
  (no phrase, no 429/5xx status, no LIMIT event), such as "Invalid API key" or an expired OAuth
  token (fix round 2 R1).
- LIMIT: api_retry `rate_limit`; a `rejected` rate_limit_event without errorCode; a result with
  `api_error_status` 429; error text "hit your ... limit".
- TRANSIENT: an error result with a 5xx `api_error_status` (529 overloaded included); or no
  result event and no wall-clock timeout (api_retry `overloaded` or `server_error` with no
  result, a non-zero exit with no result, or no events at all).
- ATTEMPT_DONE: a clean `success` result, an `error_max_turns`, `error_max_budget_usd` or
  `error_during_execution` result (the subtype explains the error), or a wall-clock timeout. It
  is counted, and the outcome comes from the driver's gate, never from the result (T-06-39).

An error result is any result but `is_error: false`: a missing or non-boolean flag counts as an
error (fail closed, fix round 2 M1). An `is_error: false` result that still carries an
`api_error_status` or a non-empty `errors` is an error result too (fix round 3); only a clean
`is_error: false` result keeps its text unread. A subtype that is not a string is unknown.

Precedence when one stream carries several signals: STOP over LIMIT over TRANSIENT over
ATTEMPT_DONE. A run with a credit problem must end even if a limit was also hit, and a limit is
not an attempt even if a result followed it. TRANSIENT competes with ATTEMPT_DONE only through
a 5xx error result (which beats it: the server, not the agent, ended the session); a session
with no result is TRANSIENT by definition. An api_retry `overloaded`/`server_error` followed by
a clean result is ATTEMPT_DONE, since the session recovered. The unexplained-error STOP is
checked after LIMIT and TRANSIENT on purpose: it applies only when none of them explained the
error result.

Error text is the CLI's own: a result's `result` field only on an error result (on a clean
result it is the agent's last message), and `errors[]`. It is never read from the agent's
messages, so the model cannot stop or stall the run by writing the words (fix round 1 I2).

`check_init` asserts the `system/init` event (Pitfall 2, D-36, T-06-40); the driver treats any
problem as STOP. `usage` and `tool_uses` feed the attempt log (AGT-03) and the transcript audit.
"""

from __future__ import annotations

import enum
import json
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import NamedTuple

EXPECTED_MODEL = "claude-opus-5-5"  # D-35; session.MODEL passes the same id
# Phase 7 D-09: the init `model` values accepted per requested model. Literal ids, because
# session imports this module (never the other way round). The owner's Fable canary (07-39)
# settles what CLI 2.1.308 reports for Fable; this table is the one place to extend.
ACCEPTED_INIT_MODELS: Mapping[str, tuple[str, ...]] = {
    "claude-opus-5-5": ("claude-opus-5-5",),
    "claude-fable-5-1": ("claude-fable-5-1",),
}
EXPECTED_TOOLS = ("Read", "Edit", "Write", "Glob", "Grep", "Bash")  # D-45's --tools
_RESULT = "result"
_SYSTEM = "system"
_INIT = "init"
_API_RETRY = "api_retry"
_RATE_LIMIT_EVENT = "rate_limit_event"
_REJECTED = "rejected"
_CREDITS_REQUIRED = "credits_required"
_HTTP_TOO_MANY_REQUESTS = 429
_STOP_RETRY_ERRORS = frozenset(
    {"authentication_failed", "oauth_org_not_allowed", "account_on_hold", "billing_error"}
)
_LIMIT_RETRY_ERRORS = frozenset({"rate_limit"})
_TRANSIENT_RETRY_ERRORS = frozenset({"overloaded", "server_error"})
_KNOWN_RETRY_ERRORS = _STOP_RETRY_ERRORS | _LIMIT_RETRY_ERRORS | _TRANSIENT_RETRY_ERRORS
_HTTP_SERVER_ERRORS = range(500, 600)  # 5xx, 529 (overloaded) included
_SUCCESS = "success"
_ERROR_SUBTYPES = frozenset({"error_max_turns", "error_max_budget_usd", "error_during_execution"})
_KNOWN_SUBTYPES = _ERROR_SUBTYPES | {_SUCCESS}
_STOP_TEXT = re.compile(r"credit balance is too low|not logged in", re.IGNORECASE)
_LIMIT_TEXT = re.compile(r"hit your\b.*?\blimit", re.IGNORECASE | re.DOTALL)
_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:\s+\(Claude Code\))?")
_TARGET_FIELDS = ("file_path", "notebook_path", "command", "path")


class Disposition(enum.Enum):
    """What the driver does after a session (D-08). There is no outcome here: MATCHED,
    PARTIAL and GAVE_UP come from the driver's gate (T-06-39)."""

    LIMIT = "limit"  # usage limit: back off, poll; not an attempt
    STOP = "stop"  # auth, billing or credit trouble: write a STOPPED record, end the run
    TRANSIENT = "transient"  # no result (overloaded, server error, crash): retry, not counted
    ATTEMPT_DONE = "attempt_done"  # counted; the outcome comes from the gate, never the result


@dataclass(frozen=True)
class Parsed:
    """The JSON-object lines of a stream, in order, and how many lines were malformed."""

    events: tuple[dict, ...]
    malformed: int


@dataclass(frozen=True)
class Usage:
    """A session's accounting (AGT-03): tokens summed over the result's modelUsage per class,
    and turns, cost and duration copied from the result."""

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    turns: int
    cost_usd: float
    duration_ms: int


class ToolUse(NamedTuple):
    """One tool_use block: the tool and what it touched (file_path, notebook_path, command or
    path, the first present), None when it names none."""

    name: str
    target: str | None


def parse_line(line: str | bytes) -> dict | None:
    """The JSON object on `line`, or None when the line is not one (malformed). Bytes are read
    as UTF-8, an undecodable byte replaced. A line nested too deeply for the parser
    (RecursionError) is malformed too, never fatal."""
    if isinstance(line, bytes):
        line = line.decode("utf-8", errors="replace")
    try:
        value = json.loads(line)
    except ValueError, RecursionError:
        return None
    return value if isinstance(value, dict) else None


def parse(lines: Iterable[str | bytes]) -> Parsed:
    """Every JSON-object line of `lines`; blank lines are skipped, any other line that is not a
    JSON object is counted as malformed."""
    events: list[dict] = []
    malformed = 0
    for line in lines:
        if not line.strip():
            continue
        event = parse_line(line)
        if event is None:
            malformed += 1
            continue
        events.append(event)
    return Parsed(tuple(events), malformed)


def _mapping(value: object) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def _system(events: Sequence[dict], subtype: str) -> Iterator[Mapping]:
    for event in events:
        if event.get("type") == _SYSTEM and event.get("subtype") == subtype:
            yield event


def _results(events: Sequence[dict]) -> list[dict]:
    return [event for event in events if event.get("type") == _RESULT]


def _retry_errors(events: Sequence[dict]) -> set[str]:
    return {str(event.get("error")) for event in _system(events, _API_RETRY)}


def _rate_limits(events: Sequence[dict]) -> Iterator[Mapping]:
    for event in events:
        if event.get("type") == _RATE_LIMIT_EVENT:
            yield _mapping(event.get("rate_limit_info"))


def _is_error_result(result: Mapping) -> bool:
    """Whether a result is an error result: anything but `is_error: false`, so a missing or
    non-boolean flag counts as an error (fail closed, fix round 2 M1); and an `is_error: false`
    result that still carries an `api_error_status` or a non-empty `errors` (fix round 3)."""
    if result.get("is_error") is not False:
        return True
    return result.get("api_error_status") is not None or result.get("errors") not in (None, [])


def _result_texts(results: Sequence[dict]) -> Iterator[str]:
    """The CLI's own error text: `result` only on an error result (on a successful result it is
    the agent's last message, fix round 1 I2), and every string in `errors[]`."""
    for result in results:
        if _is_error_result(result) and isinstance(result.get("result"), str):
            yield result["result"]
        errors = result.get("errors")
        if isinstance(errors, list):
            yield from (error for error in errors if isinstance(error, str))


def _error_statuses(results: Sequence[dict]) -> list[object]:
    """The `api_error_status` of every error result that carries one."""
    return [
        result["api_error_status"]
        for result in results
        if _is_error_result(result) and result.get("api_error_status") is not None
    ]


def _unknown_subtype(results: Sequence[dict]) -> bool:
    """Whether a result's subtype is unknown; a non-string subtype is unknown (fix round 3)."""
    return any(
        not isinstance(subtype := result.get("subtype"), str) or subtype not in _KNOWN_SUBTYPES
        for result in results
    )


def _unexplained_error(results: Sequence[dict]) -> bool:
    """An error result whose subtype is `success`: nothing but a known signal (a STOP or LIMIT
    phrase, status 429 or 5xx, a LIMIT event) explains it, and classify asks this only after
    every such signal failed to match (fix round 2 R1). The error subtypes explain themselves."""
    return any(result.get("subtype") == _SUCCESS and _is_error_result(result) for result in results)


def _is_server_error(status: object) -> bool:
    return (
        isinstance(status, int)
        and not isinstance(status, bool)
        and _HTTP_SERVER_ERRORS.start <= status < _HTTP_SERVER_ERRORS.stop
    )


def _is_stop(events: Sequence[dict], results: Sequence[dict], texts: Sequence[str]) -> bool:
    if _retry_errors(events) - _KNOWN_RETRY_ERRORS or _retry_errors(events) & _STOP_RETRY_ERRORS:
        return True  # a known STOP code, or a code outside every known set (fail closed)
    if _unknown_subtype(results):
        return True  # fix round 2 R1
    for info in _rate_limits(events):
        code = info.get("errorCode")
        if code == _CREDITS_REQUIRED or (code and info.get("status") == _REJECTED):
            return True
    if any(status != _HTTP_TOO_MANY_REQUESTS and not _is_server_error(status)
           for status in _error_statuses(results)):  # fmt: skip
        return True
    return any(_STOP_TEXT.search(text) for text in texts)


def _is_limit(events: Sequence[dict], results: Sequence[dict], texts: Sequence[str]) -> bool:
    if _retry_errors(events) & _LIMIT_RETRY_ERRORS:
        return True
    if any(info.get("status") == _REJECTED and not info.get("errorCode")
           for info in _rate_limits(events)):  # fmt: skip
        return True
    if any(result.get("api_error_status") == _HTTP_TOO_MANY_REQUESTS for result in results):
        return True
    return any(_LIMIT_TEXT.search(text) for text in texts)


def classify(events: Sequence[dict], exit_code: int | None, timed_out: bool) -> Disposition:
    """The driver's action for a session that produced `events` and ended with `exit_code`
    (None when it never exited), `timed_out` when the wall clock killed it. See the module
    docstring for the signals and their precedence."""
    results = _results(events)
    texts = list(_result_texts(results))
    if _is_stop(events, results, texts):
        return Disposition.STOP
    if _is_limit(events, results, texts):
        return Disposition.LIMIT
    if any(_is_server_error(status) for status in _error_statuses(results)):
        return Disposition.TRANSIENT
    if _unexplained_error(results):
        return Disposition.STOP  # an error no known signal explained (fix round 2 R1)
    if results or timed_out:
        return Disposition.ATTEMPT_DONE
    return Disposition.TRANSIENT


def parse_version(text: str) -> tuple[int, int, int]:
    """(major, minor, patch) from `claude_code_version` ("2.1.240") or from `claude --version`
    output ("2.1.240 (Claude Code)"); anything else raises ValueError."""
    match = _VERSION.fullmatch(text.strip())
    if match is None:
        raise ValueError(f"not a Claude Code version: {text!r}")
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def init_event(events: Sequence[dict]) -> dict | None:
    """The session's first `system/init` event, or None when it has none."""
    return next(iter(_system(events, _INIT)), None)


def _version_problem(
    init: Mapping, tested_major: int, min_version: tuple[int, int, int]
) -> str | None:
    raw = init.get("claude_code_version")
    try:
        version = parse_version(raw if isinstance(raw, str) else "")
    except ValueError:
        return f"claude_code_version {raw!r} is not a version"
    shown = ".".join(map(str, version))
    if version[0] != tested_major:
        return f"claude_code_version {shown} is not the tested major {tested_major} (D-36)"
    if version < min_version:
        minimum = ".".join(map(str, min_version))
        return f"claude_code_version {shown} is below the minimum {minimum} (D-36)"
    return None


def _tools_problem(init: Mapping) -> str | None:
    tools = init.get("tools")
    if not isinstance(tools, list) or not all(isinstance(tool, str) for tool in tools):
        return f"tools {tools!r} is not a list of tool names"
    missing = [tool for tool in EXPECTED_TOOLS if tool not in tools]
    extra = sorted(set(tools) - set(EXPECTED_TOOLS))
    duplicate = sorted({tool for tool in tools if tools.count(tool) > 1})
    if not (missing or extra or duplicate):
        return None
    found = [f"{label} {','.join(names)}"
             for label, names in (("missing", missing), ("extra", extra),
                                  ("duplicate", duplicate)) if names]  # fmt: skip
    return f"tools are not exactly {','.join(EXPECTED_TOOLS)}: {'; '.join(found)}"


def _names(entries: object) -> str:
    if not isinstance(entries, list):
        return repr(entries)
    return ", ".join(str(_mapping(entry).get("name", entry)) for entry in entries)


def _model_problem(model: object, expected_model: str) -> str | None:
    """Why the init's `model` is not accepted for the requested `expected_model`, or None
    (Phase 7 D-09). A requested model with no accepted init ids fails closed, even when the init
    echoes it."""
    accepted = ACCEPTED_INIT_MODELS.get(expected_model)
    if accepted is None:
        return f"requested model {expected_model!r} has no accepted init IDs (D-09)"
    if model not in accepted:
        return f"model {model!r} is not accepted for the requested {expected_model} (D-09)"
    return None


def check_init(
    init: Mapping | None,
    *,
    tested_major: int,
    min_version: tuple[int, int, int] | str,
    expected_model: str = EXPECTED_MODEL,
) -> list[str]:
    """Every problem with a session's `system/init` event; empty when it is clean. The driver
    treats any problem as STOP (fail closed, Pitfall 2): a missing init, a version outside the
    tested major or below `min_version` (D-36), a model not accepted for `expected_model` or an
    unknown `expected_model` (D-35, Phase 7 D-09), tools other than exactly
    D-45's six, any MCP server (D-44) or any plugin."""
    if init is None:
        return ["no system/init event"]
    if isinstance(min_version, str):
        min_version = parse_version(min_version)
    problems = [_version_problem(init, tested_major, min_version)]
    problems.append(_model_problem(init.get("model"), expected_model))
    problems.append(_tools_problem(init))
    servers = init.get("mcp_servers")
    if servers != []:
        problems.append(f"mcp_servers not empty: {_names(servers)} (D-44)")
    plugins = init.get("plugins")
    if plugins != []:
        problems.append(f"plugins loaded: {_names(plugins)}")
    return [problem for problem in problems if problem]


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _amount(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return float(value)


def usage(result: Mapping) -> Usage:
    """The accounting of a `result` event: modelUsage summed per token class over every model
    (modelUsage, not usage, which covers the main loop only), with num_turns, total_cost_usd
    and duration_ms. A missing or ill-typed field counts as zero."""
    entries = [_mapping(entry) for entry in _mapping(result.get("modelUsage")).values()]

    def total(key: str) -> int:
        return sum(_count(entry.get(key)) for entry in entries)

    return Usage(
        input_tokens=total("inputTokens"),
        output_tokens=total("outputTokens"),
        cache_read_tokens=total("cacheReadInputTokens"),
        cache_creation_tokens=total("cacheCreationInputTokens"),
        turns=_count(result.get("num_turns")),
        cost_usd=_amount(result.get("total_cost_usd")),
        duration_ms=_count(result.get("duration_ms")),
    )


def _blocks(events: Sequence[dict]) -> Iterator[Mapping]:
    for event in events:
        if event.get("type") not in ("assistant", "user"):
            continue
        content = _mapping(event.get("message")).get("content")
        if isinstance(content, list):
            yield from (_mapping(block) for block in content)


def _target(tool_input: Mapping) -> str | None:
    return next((str(tool_input[field]) for field in _TARGET_FIELDS if field in tool_input), None)


def tool_uses(events: Sequence[dict]) -> list[ToolUse]:
    """Every tool_use block of the assistant and user messages, in stream order, with the
    path or command it names (for the driver's transcript audit, independent of the hooks)."""
    return [
        ToolUse(str(block.get("name")), _target(_mapping(block.get("input"))))
        for block in _blocks(events)
        if block.get("type") == "tool_use"
    ]
