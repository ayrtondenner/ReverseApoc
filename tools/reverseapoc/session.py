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

OPUS_MODEL = "claude-opus-5-5"  # D-35, the literal id
FABLE_MODEL = "claude-fable-5-1"  # Phase 7 D-09, the escalation model
MODEL = OPUS_MODEL  # the default model of a session (passes 1 and 2)
MODEL_NAMES = {  # the display name per model id, for the Co-Authored-By line (07-30)
    OPUS_MODEL: "Claude Opus 5.5",
    FABLE_MODEL: "Claude Fable 5.1",
}
ESCALATE_AFTER_PASSES = 2  # Phase 7 D-09: two capped Opus passes, then Fable
MAX_TURNS = 40  # D-07
MAX_BUDGET_USD = 5  # D-06 (Phase 7 D-07: per Opus session), a runaway guard
FABLE_BUDGET_USD = 12.5  # Phase 7 D-25: per Fable session
MAX_CHECK_RUNS = 25  # D-07's /goal clause
TIMEOUT_S = 30 * 60  # D-07's wall clock per session
_POLL_S = 1.0  # how often the reader looks at the clock while no line comes
_DRAIN_S = 5.0  # after a kill, how long to wait for each line the dying tree still wrote
_REAP_S = 10.0  # after a kill, how long to wait for the exit code
_TASKKILL_TIMEOUT_S = 30
_EOF = object()  # the reader's end-of-stdout marker
_POSIX = os.name != "nt"
SETTINGS = "config/driver/claude-settings.json"  # repo-relative (F11)
SKILL = ".claude/skills/watcom-decomp/SKILL.md"  # repo-relative (F11)
EXES = ("ufo2p", "tacp")
_UNIT = re.compile(r"[a-z0-9_]+")
_VIEW_UNIT = re.compile(  # 07-13 (D-24): the repo-relative view unit of one attempt
    r"build/driver/(?P<run>[A-Za-z0-9_.-]+)/(?P<exe>[a-z0-9]+)/(?P<func>[A-Za-z0-9_]+)"
    r"/attempt-[1-9][0-9]*/view/src/(?P<exe2>[a-z0-9]+)/(?P<unit>[a-z0-9_]+)\.c"
)
_TOOLS = ",".join(EXPECTED_TOOLS)
_READ_WRITE_TOOLS = ",".join(tool for tool in EXPECTED_TOOLS if tool != "Bash")
_WRAPPER = " ".join(ATTEMPT_PREFIX)
_CHECK = f"{_WRAPPER} check"


def model_for_pass(pass_number: int) -> str:
    """The model of a function's pass `pass_number` (1-based, Phase 7 D-09): Opus while the pass
    is within ESCALATE_AFTER_PASSES, Fable for every later pass."""
    if pass_number < 1:
        raise ValueError(f"pass number {pass_number} is below 1")
    return OPUS_MODEL if pass_number <= ESCALATE_AFTER_PASSES else FABLE_MODEL


def build_argv(
    prompt: str,
    *,
    claude: str,
    model: str = MODEL,
    max_budget_usd: float = MAX_BUDGET_USD,
    max_turns: int = MAX_TURNS,
) -> list[str]:
    """D-06's argv for one session, `claude` being the CLI executable. `model`, `max_budget_usd`
    and `max_turns` are the session's own values (Phase 7 D-09, D-25); the defaults give D-06's
    argv token for token."""
    return [
        claude,
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--max-turns",
        str(max_turns),
        "--model",
        model,
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
        str(max_budget_usd),
    ]


def _view_unit_problem(unit_path: str, function: str, unit: str, exe: str) -> str | None:
    """Why `unit_path` is not the repo-relative view unit of this claim, or None (07-13, D-24):
    `build/driver/<run>/<exe>/<function>/attempt-<n>/view/src/<exe>/<unit>.c`, forward slashes,
    a run id of [A-Za-z0-9_.-]+ that is not `.` or `..`, and n >= 1."""
    if not isinstance(unit_path, str):
        return "is not a string"
    match = _VIEW_UNIT.fullmatch(unit_path)
    if match is None:
        return ("is not build/driver/<run>/<exe>/<function>/attempt-<n>/view/src/<exe>/<unit>.c")
    if match["run"] in (".", ".."):
        return f"names the run {match['run']!r}"
    named = (match["exe"], match["func"], match["exe2"], match["unit"])
    if named != (exe, function, exe, unit):
        return f"names another claim than {exe}/{unit} {function}"
    return None


def goal_prompt(function: str, unit: str, exe: str, *, unit_path: str) -> str:
    """The /goal prompt for the claim `exe`/`unit` and its function (D-07). The session edits
    its private view unit (07-13, D-24), so the prompt names `unit_path`, the repo-relative view
    unit, as the file the function is in. The names and the path are checked first, so nothing
    but a plain identifier or the view unit's exact shape reaches the prompt."""
    if exe not in EXES:
        raise ValueError(f"unknown EXE {exe!r}; expected one of {', '.join(EXES)}")
    if not _UNIT.fullmatch(unit):
        raise ValueError(f"unit {unit!r} is not a unit name ([a-z0-9_]+)")
    if not ATTEMPT_NAME.fullmatch(function):
        raise ValueError(f"function {function!r} is not a function name")
    problem = _view_unit_problem(unit_path, function, unit, exe)
    if problem:
        raise ValueError(f"unit_path {unit_path!r} {problem}")
    return (
        f"/goal Make `{_CHECK}` exit 0 for {function}, the claimed function in your private "
        f"copy {unit_path} of the unit (claim {exe}/{unit}); edit only that file, and write this "
        "attempt's notes.md (its path follows `notes:` in the check output); or stop after "
        f"{MAX_CHECK_RUNS} check runs, with notes.md written."
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
    POSIX: SIGKILL to the process group `pid` leads (run_session starts a new session); a pid
    below 1 is refused, since killpg(0) would hit the caller's own group. A descendant that
    calls setsid has left the group and escapes the POSIX kill (a known limit)."""
    if pid < 1:
        raise ValueError(f"refusing to kill process group {pid}")
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
    on_start: Callable[[int], None] | None = None,
    on_end: Callable[[int], None] | None = None,
) -> SessionResult:
    """Run `argv` in `cwd` with exactly `env` and no stdin, as the root of a new process group.
    Each raw stdout line is appended to `transcript` (opened for append) as it arrives and
    parsed; a malformed line is counted, never fatal. When `timeout_s` passes on `clock`
    (monotonic) before the session ends, the whole tree is killed and the result says
    `timed_out` (D-07's 30-minute wall clock). stderr is inherited, so the driver's console
    shows it. 07-21 (D-07 stop-all): `on_start(pid)` is called with the session's pid right
    after it starts, before any line is read, and `on_end(pid)` once it has ended, also when
    this raises, so the driver's registry can kill every live session tree on a stop."""
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
        return _run_started(proc, transcript, deadline, clock, on_start)
    finally:
        if on_end is not None:
            on_end(proc.pid)


def _run_started(proc: subprocess.Popen, transcript: Path, deadline: float,
                 clock: Callable[[], float],
                 on_start: Callable[[int], None] | None) -> SessionResult:  # fmt: skip
    """run_session once the process exists: report it, read it, reap it (see run_session)."""
    try:
        if on_start is not None:
            on_start(proc.pid)
        reader = _Reader(proc.stdout)
        with transcript.open("ab") as log:
            record = _Transcript(log)
            ended = _read_until(reader, record, deadline, clock)
            exit_code = _reap(proc, max(deadline - clock(), 0.0)) if ended else None
            timed_out = exit_code is None
            if not timed_out and _POSIX:
                # Fix round 1 minor: a descendant that outlived the session dies with its
                # group. Windows cannot: taskkill /T needs the parent alive (a known limit).
                kill_tree(proc.pid)
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
        elif _POSIX:
            kill_tree(proc.pid)  # fix round 2 M3: the root exited, its group may live on
        raise
    return SessionResult(tuple(record.events), exit_code, timed_out, record.malformed, transcript)
