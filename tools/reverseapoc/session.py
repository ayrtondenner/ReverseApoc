# SPDX-License-Identifier: GPL-3.0-or-later
"""One matching session of the driver (AGT-01, AGT-03, D-06, D-07, D-35, D-44, D-45).

`build_argv` is D-06's `claude -p` command as an argv list (never a shell string): the prompt
follows `-p` directly, so the variadic `--tools`/`--allowedTools` cannot swallow it, and the Bash
allow rule is built from hooks.ATTEMPT_PREFIX, the same prefix the matching hook and the attempt
wrapper use. `--bare` is never passed: it needs ANTHROPIC_API_KEY and would drop the owner's
subscription login (D-06). `--settings` and `--append-system-prompt-file` are relative to the
repository root, so the driver runs the session with `cwd` set to it (ruling F11).

`goal_prompt` is the /goal prompt for one claim (D-07). `run_session` runs the argv, saves every
stdout line as it arrives to the attempt's transcript.jsonl and parses it with streamjson.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .hooks import ATTEMPT_NAME, ATTEMPT_PREFIX
from .streamjson import EXPECTED_TOOLS, parse_line

MODEL = "claude-opus-5-5"  # D-35, the literal id
MAX_TURNS = 40  # D-07
MAX_BUDGET_USD = 5  # D-06, a runaway guard
MAX_CHECK_RUNS = 25  # D-07's /goal clause
SETTINGS = "config/driver/claude-settings.json"  # repo-relative (F11)
SKILL = ".claude/skills/watcom-decomp/SKILL.md"  # repo-relative (F11)
EXES = ("ufo2p", "tacp")
_UNIT = re.compile(r"[a-z0-9_]+")
_TOOLS = ",".join(EXPECTED_TOOLS)
_READ_WRITE_TOOLS = ",".join(tool for tool in EXPECTED_TOOLS if tool != "Bash")
_WRAPPER = " ".join(ATTEMPT_PREFIX)
_CHECK = f"{_WRAPPER} check"


def build_argv(prompt: str, *, claude: str) -> list[str]:
    """D-06's argv for one session, `claude` being the CLI executable."""
    return [
        claude,
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--max-turns",
        str(MAX_TURNS),
        "--model",
        MODEL,
        "--permission-mode",
        "dontAsk",
        "--tools",
        _TOOLS,
        "--allowedTools",
        f"{_READ_WRITE_TOOLS},Bash({_WRAPPER} *)",
        "--strict-mcp-config",
        "--setting-sources",
        "project",
        "--settings",
        SETTINGS,
        "--append-system-prompt-file",
        SKILL,
        "--max-budget-usd",
        str(MAX_BUDGET_USD),
    ]


def goal_prompt(function: str, unit: str, exe: str) -> str:
    """The /goal prompt for the claim `exe`/`unit` and its function (D-07). The names are
    checked first, so nothing but a plain identifier reaches the prompt."""
    if exe not in EXES:
        raise ValueError(f"unknown EXE {exe!r}; expected one of {', '.join(EXES)}")
    if not _UNIT.fullmatch(unit):
        raise ValueError(f"unit {unit!r} is not a unit name ([a-z0-9_]+)")
    if not ATTEMPT_NAME.fullmatch(function):
        raise ValueError(f"function {function!r} is not a function name")
    return (
        f"/goal Make `{_CHECK}` exit 0 for {function}, the claimed function in "
        f"src/{exe}/{unit}.c (claim {exe}/{unit}), and write this attempt's notes.md (its path "
        f"follows `notes:` in the check output); or stop after {MAX_CHECK_RUNS} check runs, "
        "with notes.md written."
    )


@dataclass(frozen=True)
class SessionResult:
    """What one session left: its JSON events in order, its exit code (None if it never
    exited), whether the wall clock killed it, how many stdout lines were malformed, and the
    transcript holding every raw line."""

    events: tuple[dict, ...]
    exit_code: int | None
    timed_out: bool
    malformed: int
    transcript: Path


def run_session(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    transcript: Path,
    popen: Callable[..., subprocess.Popen] = subprocess.Popen,
) -> SessionResult:
    """Run `argv` in `cwd` with exactly `env`, appending each raw stdout line to `transcript`
    as it arrives and parsing it (a malformed line is counted, never fatal)."""
    transcript.parent.mkdir(parents=True, exist_ok=True)
    events: list[dict] = []
    malformed = 0
    proc = popen(
        list(argv),
        cwd=os.fspath(cwd),
        env=dict(env),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
    )
    with transcript.open("ab") as log:
        for raw in iter(proc.stdout.readline, b""):
            log.write(raw)
            log.flush()
            if not raw.strip():
                continue
            event = parse_line(raw)
            if event is None:
                malformed += 1
                continue
            events.append(event)
    proc.stdout.close()
    exit_code = proc.wait()
    return SessionResult(tuple(events), exit_code, False, malformed, transcript)
