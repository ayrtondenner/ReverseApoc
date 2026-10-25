# SPDX-License-Identifier: GPL-3.0-or-later
"""One matching session of the driver (AGT-01, AGT-03, D-06, D-07, D-35, D-44, D-45).

`build_argv` is D-06's `claude -p` command as an argv list (never a shell string): the prompt
follows `-p` directly, so the variadic `--tools`/`--allowedTools` cannot swallow it, and the Bash
allow rule is built from hooks.ATTEMPT_PREFIX, the same prefix the matching hook and the attempt
wrapper use. `--bare` is never passed: it needs ANTHROPIC_API_KEY and would drop the owner's
subscription login (D-06). `--settings` and `--append-system-prompt-file` are relative to the
repository root, so the driver runs the session with `cwd` set to it (ruling F11).

`goal_prompt` is the /goal prompt for one claim (D-07). `run_session` runs the argv, saves every
stdout line as it arrives to the attempt's transcript.jsonl and parses it with streamjson. At
the 30-minute wall clock it kills the whole process tree with `kill_tree` (Pitfall 7) and
reports `timed_out`; streamjson.classify counts that as an attempt.
"""

from __future__ import annotations

import ntpath
import os
import queue
import re
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from .hooks import ATTEMPT_NAME, ATTEMPT_PREFIX
from .streamjson import EXPECTED_TOOLS, parse_line

MODEL = "claude-opus-5-5"  # D-35, the literal id
MAX_TURNS = 40  # D-07
MAX_BUDGET_USD = 5  # D-06, a runaway guard
MAX_CHECK_RUNS = 25  # D-07's /goal clause
TIMEOUT_S = 30 * 60  # D-07's wall clock per session
_POLL_S = 1.0  # how often the reader looks at the clock while no line comes
_DRAIN_S = 5.0  # after a kill, how long to wait for each line the dying tree still wrote
_REAP_S = 10.0  # after a kill, how long to wait for the exit code
_TASKKILL_TIMEOUT_S = 30
_EOF = object()  # the reader's end-of-stdout marker
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


def _taskkill() -> str:
    """taskkill.exe by its System32 path, so no PATH entry can stand in for it."""
    root = os.environ.get("SystemRoot") or os.environ.get("SYSTEMROOT") or r"C:\Windows"
    return ntpath.join(root, "System32", "taskkill.exe")


def kill_tree(
    pid: int,
    *,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    windows: bool = os.name == "nt",
) -> None:
    """Kill process `pid` and every process under it (Pitfall 7: claude, the wrapper, any
    `docker compose run`). Windows: `taskkill /T /F /PID <pid>` as an argv list, never a shell.
    POSIX: SIGKILL to the process group `pid` leads (run_session starts a new session)."""
    if windows:
        run(
            [_taskkill(), "/T", "/F", "/PID", str(pid)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=_TASKKILL_TIMEOUT_S,
            check=False,
        )
        return
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # the whole group has already exited


def _group_options() -> dict:
    """Popen options that make the session the root of its own process group, so kill_tree
    reaches everything it starts."""
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _pump(stream: IO[bytes], lines: queue.SimpleQueue) -> None:
    """Move raw lines from the session's stdout into `lines`, then the end marker."""
    try:
        for raw in iter(stream.readline, b""):
            lines.put(raw)
    finally:
        lines.put(_EOF)


class _Reader:
    """The session's stdout as a queue of raw lines, so the caller can stop waiting at the
    deadline even when no line comes."""

    def __init__(self, stream: IO[bytes]) -> None:
        self._stream = stream
        self._lines: queue.SimpleQueue = queue.SimpleQueue()
        self._thread = threading.Thread(target=_pump, args=(stream, self._lines), daemon=True)
        self._thread.start()

    def get(self, timeout: float) -> bytes | object | None:
        """The next raw line, _EOF at the end, or None when `timeout` passes first."""
        try:
            return self._lines.get(timeout=max(timeout, 0.0))
        except queue.Empty:
            return None

    def close(self) -> None:
        self._thread.join(_DRAIN_S)
        if not self._thread.is_alive():
            self._stream.close()


class _Transcript:
    """Appends raw lines to the transcript and parses each one."""

    def __init__(self, log: IO[bytes]) -> None:
        self._log = log
        self.events: list[dict] = []
        self.malformed = 0

    def add(self, raw: bytes) -> None:
        self._log.write(raw)
        self._log.flush()
        if not raw.strip():
            return
        event = parse_line(raw)
        if event is None:
            self.malformed += 1
            return
        self.events.append(event)


def _read_until(reader: _Reader, record: _Transcript, deadline: float, clock) -> bool:
    """Record lines until the end of stdout (True) or the deadline (False)."""
    while (remaining := deadline - clock()) > 0:
        raw = reader.get(min(remaining, _POLL_S))
        if raw is _EOF:
            return True
        if raw is not None:
            record.add(raw)
    return False


def _drain(reader: _Reader, record: _Transcript) -> None:
    """After a kill, keep what the dying tree still wrote, waiting at most _DRAIN_S per line."""
    while (raw := reader.get(_DRAIN_S)) not in (None, _EOF):
        record.add(raw)


def _reap(proc: subprocess.Popen, timeout: float) -> int | None:
    try:
        return proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        return None


def run_session(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    transcript: Path,
    timeout_s: float = TIMEOUT_S,
    popen: Callable[..., subprocess.Popen] = subprocess.Popen,
    clock: Callable[[], float] = time.monotonic,
) -> SessionResult:
    """Run `argv` in `cwd` with exactly `env` and no stdin, as the root of a new process group.
    Each raw stdout line is appended to `transcript` (opened for append) as it arrives and
    parsed; a malformed line is counted, never fatal. When `timeout_s` passes on `clock`
    (monotonic) before the session ends, the whole tree is killed and the result says
    `timed_out` (D-07's 30-minute wall clock). stderr is inherited, so the driver's console
    shows it."""
    transcript.parent.mkdir(parents=True, exist_ok=True)
    deadline = clock() + timeout_s
    proc = popen(
        list(argv),
        cwd=os.fspath(cwd),
        env=dict(env),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        **_group_options(),
    )
    try:
        reader = _Reader(proc.stdout)
        with transcript.open("ab") as log:
            record = _Transcript(log)
            ended = _read_until(reader, record, deadline, clock)
            exit_code = _reap(proc, max(deadline - clock(), 0.0)) if ended else None
            timed_out = exit_code is None
            if timed_out:
                kill_tree(proc.pid)
                _drain(reader, record)
                exit_code = _reap(proc, _REAP_S)
        reader.close()
    except BaseException:
        # Fix round 1 I1: the new process group keeps Ctrl+C from the session, and the caller
        # gets no pid when this raises, so no exception may leave the tree running.
        if proc.poll() is None:
            kill_tree(proc.pid)
            _reap(proc, _REAP_S)
        raise
    return SessionResult(tuple(record.events), exit_code, timed_out, record.malformed, transcript)
