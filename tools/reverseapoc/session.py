# SPDX-License-Identifier: GPL-3.0-or-later
"""One matching session of the driver (AGT-01, AGT-03, D-06, D-07, D-35, D-44, D-45).

`build_argv` is D-06's `claude -p` command as an argv list (never a shell string): the prompt
follows `-p` directly, so the variadic `--tools`/`--allowedTools` cannot swallow it, and the Bash
allow rule is built from hooks.ATTEMPT_PREFIX, the same prefix the matching hook and the attempt
wrapper use. `--bare` is never passed: it needs ANTHROPIC_API_KEY and would drop the owner's
subscription login (D-06). `--settings` and `--append-system-prompt-file` are relative to the
repository root, so the driver runs the session with `cwd` set to it (ruling F11).

`goal_prompt` is the /goal prompt for one claim (D-07), its stop clause the skill's STOP_RULES
(261109-gzx); `readability_goal` that of a
readability session, whose argv appends READABILITY_SKILL (07-38, D-18). `run_session` runs
the argv, saves every stdout line as it arrives to the attempt's transcript.jsonl and parses it
with streamjson. At
the 30-minute wall clock it kills the whole process tree with `kill_tree` (Pitfall 7) and
reports `timed_out`; streamjson.classify counts that as an attempt.

07.2-13 (D-13): `build_codex_argv` is a Codex arm's `codex exec --json` argv and `codex_prompt`
its prompt (the goal, the watcom-decomp skill's body and the session rules, since Codex loads
no skill and runs no hook); run_session runs it the same way.

07.2-15 (D-21, D-24): `build_agy_argv` is an Antigravity arm's `agy -p --output-format
stream-json` argv and `agy_prompt` its prompt (codex_prompt's).
"""

from __future__ import annotations

import json
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

from .hooks import _NOTES_NAME as _NOTES_FILE
from .hooks import ATTEMPT_NAME, ATTEMPT_PREFIX, SESSION_FILE_NAMES
from .streamjson import EXPECTED_TOOLS, parse_line

OPUS_MODEL = "claude-opus-5-5"  # D-35, the literal id
FABLE_MODEL = "claude-fable-5-1"  # Phase 7 D-09, the escalation model
HAIKU_MODEL = "claude-haiku-5-5"  # Phase 07.2 D-18: a Claude arm of spike 012
SONNET_MODEL = "claude-sonnet-5-5"  # Phase 07.2 D-18: a Claude arm of spike 012
MODEL = OPUS_MODEL  # the default model of a session (passes 1 and 2)
MODEL_NAMES = {  # the display name per model id, for the Co-Authored-By line (07-30)
    OPUS_MODEL: "Claude Opus 5.5",
    FABLE_MODEL: "Claude Fable 5.1",
    HAIKU_MODEL: "Claude Haiku 5.5",
    SONNET_MODEL: "Claude Sonnet 5.5",
}
ESCALATE_AFTER_PASSES = 2  # Phase 7 D-09: two capped Opus passes, then Fable
MAX_TURNS = 40  # D-07
MAX_BUDGET_USD = 5  # D-06 (Phase 7 D-07: per Opus session), a runaway guard
FABLE_BUDGET_USD = 12.5  # Phase 7 D-25: per Fable session
MAX_CHECK_RUNS = 25  # D-07's /goal clause
# The watcom-decomp skill's "When to give up" stops after exit `0`, in the skill's order and
# words; tests/test_skill.py pins the equality (261109-gzx).
STOP_RULES = (
    "a sweep printed `sweep hit: needs flags`",
    "three different C shapes leave objdiff below 100",
    f"all {MAX_CHECK_RUNS} check runs are used",
    "about 25 of 30 minutes or 35 of 40 turns are gone",
    "needs flags (no -s), a jump table that cannot lead the unit or has a target outside the "
    "function, or another check running in this attempt",
)
TIMEOUT_S = 30 * 60  # D-07's wall clock per session
_POLL_S = 1.0  # how often the reader looks at the clock while no line comes
_DRAIN_S = 5.0  # after a kill, how long to wait for each line the dying tree still wrote
_REAP_S = 10.0  # after a kill, how long to wait for the exit code
_TASKKILL_TIMEOUT_S = 30
_EOF = object()  # the reader's end-of-stdout marker
_POSIX = os.name != "nt"
SETTINGS = "config/driver/claude-settings.json"  # repo-relative (F11)
SKILL = ".claude/skills/watcom-decomp/SKILL.md"  # repo-relative (F11)
READABILITY_SKILL = ".claude/skills/watcom-readability/SKILL.md"  # 07-38 (D-18): readability
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
_GOAL_COMMAND = "/goal "  # Claude Code's /goal; a Codex prompt carries the goal without it
_FRONT_MATTER = "---"  # a SKILL.md's front matter fence


def model_for_pass(pass_number: int, *, row: Sequence[str] = (), attempt: int = 1,
                   attempts: int = 1) -> str:  # fmt: skip
    """The model (or arm) of a function's pass `pass_number` (1-based). With no `row`, Phase 7
    D-09: Opus while the pass is within ESCALATE_AFTER_PASSES, Fable for every later pass. With
    a `row` (quick 261112-fds, `drive --cascade`: a routing row's ladder), attempt `attempt` of
    `attempts` per pass runs on rung (pass_number - 1) * attempts + attempt, counted from 1, and
    the row's last arm takes every attempt past its end. ValueError for a pass below 1 and,
    with a row, for an attempt outside 1..attempts."""
    if pass_number < 1:
        raise ValueError(f"pass number {pass_number} is below 1")
    if not row:
        return OPUS_MODEL if pass_number <= ESCALATE_AFTER_PASSES else FABLE_MODEL
    if not 1 <= attempt <= attempts:
        raise ValueError(f"attempt {attempt} is outside 1..{attempts}")
    return row[min((pass_number - 1) * attempts + attempt - 1, len(row) - 1)]


def build_argv(
    prompt: str,
    *,
    claude: str,
    model: str = MODEL,
    max_budget_usd: float = MAX_BUDGET_USD,
    max_turns: int = MAX_TURNS,
    skill: str = SKILL,
) -> list[str]:
    """D-06's argv for one session, `claude` being the CLI executable. `model`, `max_budget_usd`
    and `max_turns` are the session's own values (Phase 7 D-09, D-25), `skill` the repo-relative
    skill appended to the system prompt (07-38, D-18: READABILITY_SKILL for a readability
    session); the defaults give D-06's argv token for token."""
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
        skill,
        "--max-budget-usd",
        str(max_budget_usd),
    ]


def build_codex_argv(prompt: str, *, codex: str, model: str, attempt_dir: Path) -> list[str]:
    """07.2-13 (D-13; RESEARCH Q8): the argv of one Codex session, `codex` being the CLI
    executable: `codex exec --json` in a workspace-write sandbox rooted at `attempt_dir`, no
    git-repo check, nothing persisted, no user config, approval `never` and the sandbox's
    network off, the Windows sandbox set in the argv (the ignored user config was all that
    enabled it, and with none Codex ran no sandbox and rejected every command) to unelevated
    (owner's ruling 2026-11-10: the mode the owner's own Codex runs; elevated needs an admin
    setup, and without it every command failed to start), and `attempt_dir` trusted so the
    per-session rules the driver generates under it (<attempt dir>/.codex/rules/) load. The
    approval key (RESEARCH A4) and the trusted project layer under gitignored build/ (A5) are
    assumptions the Codex canary settles. Never an auto-approval flag, the unrestricted sandbox
    mode or the flag that skips the rules files (tests/test_codex.py pins the list). The prompt
    is the last argument. Spike 012 round 5: the trust is an inline table under the plain key
    `projects`, since Codex 0.167 splits a `-c` key on every dot, quotes or not, and ignored
    the dotted-key form for an attempt dir whose run holds a dot (spike012-gpt-6.1-sol)."""
    trust = f"projects={{{json.dumps(str(attempt_dir))}={{trust_level=\"trusted\"}}}}"
    return [codex, "exec", "--json", "--model", model, "--sandbox", "workspace-write",
            "--cd", str(attempt_dir), "--skip-git-repo-check", "--ephemeral",
            "--ignore-user-config", "-c", 'approval_policy="never"',
            "-c", "sandbox_workspace_write.network_access=false",
            "-c", 'windows.sandbox="unelevated"', "-c", trust, prompt]  # fmt: skip


def build_agy_argv(prompt: str, *, agy: str, model: str, attempt_dir: Path, settings: Path,
                   timeout_s: float) -> list[str]:  # fmt: skip
    """07.2-15 (D-21, D-24; RESEARCH "D-21"): the argv of one Antigravity session, `agy` being
    the CLI executable: stream-json output, the model slug (an unknown one exits 1, so a wrong
    slug fails closed), the terminal sandbox, the attempt dir as the added workspace, the
    per-session settings file the driver wrote under build/ outside that workspace, no slash
    commands, and the session's wall clock (`timeout_s`) as the print timeout, a Go duration in
    whole seconds (`1800s`: agy 1.5.5 exits on a bare number, canary 2026-11-10).
    `-p` and the prompt come last (agy reads no stdin and wants `-p` last). Never the flag that
    skips permissions (tests/test_agy.py pins the list). The driver runs it with cwd = the
    attempt dir."""
    return [agy, "--output-format", "stream-json", "--model", model, "--sandbox",
            "--add-dir", str(attempt_dir), "--settings", str(settings),
            "--disable-slash-commands", "--print-timeout", f"{int(timeout_s)}s",
            "-p", prompt]  # fmt: skip


def _skill_body(skill_text: str) -> str:
    """A SKILL.md without its `---` front matter (the name and description lines)."""
    lines = skill_text.splitlines(keepends=True)
    if not lines or lines[0].strip() != _FRONT_MATTER:
        return skill_text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == _FRONT_MATTER:
            return "".join(lines[index + 1 :]).lstrip("\n")
    return skill_text


# 07.2 review WR-10: the skill tells a Claude session to look around with Read, Grep and Glob;
# a Codex or agy session has none of them, and a shell read is a stray. Each form named here is
# one the driver's rules allow (tests/test_codex.py checks them against hooks.bash_allowed).
# Canary round 3: Sol wrote its files with `Set-Content`, a command the audit flags, which stops
# the whole night; a file-edit tool's writes (Codex's apply_patch, reported as file_change
# items) are what the audit checks against the session's write allowlist.
# Spike 012 round 5: Codex's unified exec (and agy's background tasks) hand a long command back
# while it still runs; Luna, Sol and Terra then replied DONE and the session's end killed their
# `attempt check`. Said in both signed-in harnesses' prompts and in the Codex canary's.
WAIT_NOTE = ("A wrapper command, `attempt check` above all, can run for several minutes. If "
             "your shell tool hands a command back while it is still running, keep waiting on "
             "it (poll it) until it exits and you have its output before you do anything else; "
             "never end your turn while a wrapper command is still running.")
_HARNESS_NOTE = ("Harness note: this session has no Read, Grep or Glob tool, so where the skill "
                 "says to look around with them, read through the wrapper instead: "
                 "`attempt context` prints the context pack, `attempt asm` and "
                 "`attempt asm <NAME>` print listings, and `attempt check` prints its summary "
                 "and the paths of its evidence. Create and edit files only with your file-edit "
                 "tool, never with a shell command or redirection: the audit checks that "
                 "tool's edits, and a command that writes a file is a command other than the "
                 "wrapper. " + WAIT_NOTE)  # fmt: skip
# agy's settings (driver.agy_settings) also allow read_file inside the attempt dir, nowhere else
_AGY_READS = (" Your read_file tool may also read files inside this attempt's directory (your "
              "unit, checks/NNNN.json); nothing outside it.")  # fmt: skip


def _signed_in_prompt(goal: str, skill_text: str, note: str) -> str:
    files = ", ".join((_NOTES_FILE, *SESSION_FILE_NAMES))
    closing = (f"Session rules: the only command you may run is `{_WRAPPER}` with one of the "
               "forms the skill quotes, exactly as written; run nothing else, not even to read, "
               f"list or search a file. The files you may write are the private unit named "
               f"above and, in this attempt's directory, {files}. Every command you run and "
               "every file you write is checked after the session; anything else stops the "
               "night.")  # fmt: skip
    return "\n\n".join((goal.removeprefix(_GOAL_COMMAND), _skill_body(skill_text).strip(),
                        note, closing))  # fmt: skip


def codex_prompt(goal: str, skill_text: str) -> str:
    """07.2-13 (D-13): the prompt of a Codex session, which has no skill loader, no /goal and
    no hooks: the matching goal (goal_prompt's, without its /goal command), the watcom-decomp
    skill's body (`skill_text`, front matter stripped), the harness note (07.2 review WR-10:
    no Read, Grep or Glob; files are read through the wrapper's printing forms; canary round 3:
    files are written only with the file-edit tool, never by a shell command) and a closing
    block naming the session files beside notes.md and that only the attempt wrapper may be run
    (the driver audits every command and file afterwards)."""
    return _signed_in_prompt(goal, skill_text, _HARNESS_NOTE)


def agy_prompt(goal: str, skill_text: str) -> str:
    """07.2-15 (D-21): the prompt of an Antigravity session, which like Codex has no skill
    loader, no /goal and no hooks: codex_prompt's text, its harness note extended by the one
    read agy's settings allow (read_file inside the attempt dir, WR-10)."""
    return _signed_in_prompt(goal, skill_text, _HARNESS_NOTE + _AGY_READS)


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
    but a plain identifier or the view unit's exact shape reaches the prompt. Its stop clause is
    STOP_RULES, the skill's own stop list, so the /goal Stop hook admits the stops the skill asks
    for and blocks the rest (261109-gzx)."""
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
        "attempt's notes.md (its path follows `notes:` in the check output). Or stop with "
        "notes.md written once one of these holds, naming it and its evidence (check numbers or "
        f"the printed line) in your last message: {'; '.join(STOP_RULES)}. No other stop meets "
        "this goal."
    )


def readability_goal(unit: str, exe: str, *, unit_path: str) -> str:
    """07-38 (D-17, D-18): the /goal prompt of a readability session on the matched unit
    `exe`/`unit`, whose private view unit is `unit_path` (its function directory names the
    unit's lowest matched function). The session names, comments and types the unit without
    moving a byte; names change only through proposals the driver applies after the session
    (D-19) and are checked again at landing (ruling F18, the 07-31 note): the check's "pending
    rename" is no guarantee. Names and path are checked as goal_prompt checks them."""
    if exe not in EXES:
        raise ValueError(f"unknown EXE {exe!r}; expected one of {', '.join(EXES)}")
    if not _UNIT.fullmatch(unit):
        raise ValueError(f"unit {unit!r} is not a unit name ([a-z0-9_]+)")
    match = _VIEW_UNIT.fullmatch(unit_path) if isinstance(unit_path, str) else None
    function = match["func"] if match is not None else ""
    if not ATTEMPT_NAME.fullmatch(function):
        raise ValueError(f"unit_path {unit_path!r} names no claimed function")
    problem = _view_unit_problem(unit_path, function, unit, exe)
    if problem:
        raise ValueError(f"unit_path {unit_path!r} {problem}")
    return (
        f"/goal Make `{_CHECK}` report the check OK and readlint clean for the unit {exe}/{unit} "
        f"in your private copy {unit_path} (claim {exe}/{unit}): name, comment and type its "
        "matched functions without changing a byte of the compiled code. Edit only that file, "
        "write every rename of a function or data row as a proposal in this attempt's "
        "proposals.jsonl, and write this attempt's notes.md (its path follows `notes:` in the "
        "check output). Names are checked again at landing, after the driver applies your "
        "rename proposals, so a pending rename in the check output is no guarantee. Or stop "
        f"after {MAX_CHECK_RUNS} check runs, with notes.md written."
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
