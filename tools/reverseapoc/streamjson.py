# SPDX-License-Identifier: GPL-3.0-or-later
"""The driver's reading of a `claude -p --output-format stream-json --verbose` session (AGT-03,
AGT-04, D-08).

Each stdout line of a session is one JSON object. `parse_line` reads one defensively: a line that
is not a JSON object is malformed, counted by `parse`, and never fatal or executed (T-06-42).
`classify` maps the parsed events to one driver action (`Disposition`). Nothing here talks to the
CLI; `session.run_session` feeds it.
"""

from __future__ import annotations

import enum
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

EXPECTED_MODEL = "claude-opus-5-5"  # D-35; session.MODEL passes the same id
EXPECTED_TOOLS = ("Read", "Edit", "Write", "Glob", "Grep", "Bash")  # D-45's --tools
_RESULT = "result"


class Disposition(enum.Enum):
    """What the driver does after a session (D-08)."""

    LIMIT = "limit"  # usage limit: back off, poll; not an attempt
    STOP = "stop"  # auth, billing or credit trouble: write a STOPPED record, end the run
    TRANSIENT = "transient"  # no result (overloaded, server error, crash): retry, not counted
    ATTEMPT_DONE = "attempt_done"  # counted; the outcome comes from the gate, never the result


@dataclass(frozen=True)
class Parsed:
    """The JSON-object lines of a stream, in order, and how many lines were malformed."""

    events: tuple[dict, ...]
    malformed: int


def parse_line(line: str | bytes) -> dict | None:
    """The JSON object on `line`, or None when the line is not one (malformed). Bytes are read
    as UTF-8, an undecodable byte replaced."""
    if isinstance(line, bytes):
        line = line.decode("utf-8", errors="replace")
    try:
        value = json.loads(line)
    except ValueError:
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


def _results(events: Sequence[dict]) -> list[dict]:
    return [event for event in events if event.get("type") == _RESULT]


def classify(events: Sequence[dict], exit_code: int | None, timed_out: bool) -> Disposition:
    """The driver's action for a session that produced `events` and ended with `exit_code`
    (None when it was killed before exiting), `timed_out` when the wall clock killed it."""
    if timed_out or _results(events):
        return Disposition.ATTEMPT_DONE
    return Disposition.TRANSIENT
