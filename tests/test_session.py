"""The driver's session layer (AGT-01, AGT-03, D-06, D-07, D-35, D-44, D-45): the exact `claude -p`
argv, the /goal prompt and the process runner. Every session here runs tests/fakeclaude.py, the
stand-in that replays a synthetic stream fixture; no test ever starts the real claude."""

from __future__ import annotations

import ctypes
import io
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from reverseapoc.session import build_argv, goal_prompt, kill_tree, run_session
from reverseapoc.streamjson import Disposition, classify

FAKECLAUDE = REPO_ROOT / "tests" / "fakeclaude.py"
STREAMS = REPO_ROOT / "tests" / "fixtures" / "stream"

# D-06 token for token, as the owner decided it (the prompt is a stand-in).
D06_ARGV = [
    "claude",
    "-p",
    "/goal stand-in",
    "--output-format",
    "stream-json",
    "--verbose",
    "--max-turns",
    "40",
    "--model",
    "claude-opus-5-5",
    "--permission-mode",
    "dontAsk",
    "--tools",
    "Read,Edit,Write,Glob,Grep,Bash",
    "--allowedTools",
    "Read,Edit,Write,Glob,Grep,Bash(uv run --frozen reverseapoc attempt *)",
    "--strict-mcp-config",
    "--setting-sources",
    "project",
    "--settings",
    "config/driver/claude-settings.json",
    "--append-system-prompt-file",
    ".claude/skills/watcom-decomp/SKILL.md",
    "--max-budget-usd",
    "5",
]


def _fake(*args: str) -> list[str]:
    return [sys.executable, str(FAKECLAUDE), *args]


def _env() -> dict[str, str]:
    return dict(os.environ)


def test_build_argv_is_d06():
    argv = build_argv("/goal stand-in", claude="claude")
    assert argv == D06_ARGV
    assert argv[argv.index("-p") + 1] == "/goal stand-in"
    assert "--bare" not in argv


def test_goal_prompt_names_the_claim():
    prompt = goal_prompt("func_00010000", "u_00010000", "ufo2p")
    assert prompt.startswith("/goal ")
    assert "func_00010000" in prompt
    assert "u_00010000" in prompt
    assert "uv run --frozen reverseapoc attempt check" in prompt
    assert "notes.md" in prompt
    assert "stop after 25 check runs" in prompt


def test_run_session_with_fakeclaude_success(tmp_path):
    transcript = tmp_path / "attempt" / "transcript.jsonl"
    result = run_session(
        _fake("--scenario", "success"), cwd=tmp_path, env=_env(), transcript=transcript
    )
    kinds = [(event.get("type"), event.get("subtype")) for event in result.events]
    assert ("system", "init") in kinds
    assert ("result", "success") in kinds
    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.malformed == 0
    assert result.transcript == transcript
    assert transcript.read_bytes() == (STREAMS / "success.jsonl").read_bytes()
    assert classify(result.events, result.exit_code, result.timed_out) is Disposition.ATTEMPT_DONE


# Task 3: the wall clock, the tree kill, and the stand-in's writes and exits.

_STILL_ACTIVE = 259  # GetExitCodeProcess's code for a running process
_QUERY_LIMITED_INFORMATION = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
_GONE_WITHIN_S = 10.0
# The plan says 1 s; 3 s leaves a slow host time to start fakeclaude and its child (two Python
# start-ups, through the venv launcher on Windows) before the deadline, and is still a tenth of
# the stand-in's 30 s sleep.
_TREE_TIMEOUT_S = 3


def _alive(pid: int) -> bool:
    """Whether process `pid` still runs. Windows asks the kernel for its exit code (os.kill
    there would terminate it); POSIX probes with signal 0 and counts a zombie as gone."""
    if sys.platform == "win32":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        code = ctypes.c_ulong()
        try:
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        finally:
            kernel32.CloseHandle(handle)
        return bool(ok) and code.value == _STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    stat = Path(f"/proc/{pid}/stat")
    if stat.is_file():
        return stat.read_text().rsplit(")", 1)[1].split()[0] != "Z"
    return True


def _gone(pid: int) -> bool:
    deadline = time.monotonic() + _GONE_WITHIN_S
    while _alive(pid):
        if time.monotonic() > deadline:
            return False
        time.sleep(0.1)
    return True


def test_alive_probe_sees_a_live_process():
    """The probe the tree-kill test relies on can say 'alive', so its 'gone' means something."""
    sleeper = subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(60)"])
    try:
        assert _alive(sleeper.pid)
    finally:
        sleeper.kill()
        sleeper.wait()
    assert _gone(sleeper.pid)


def test_timeout_kills_the_tree(tmp_path):
    transcript = tmp_path / "attempt" / "transcript.jsonl"
    started = time.monotonic()
    result = run_session(
        _fake("--scenario", "no_result", "--spawn-child", "--sleep", "30"),
        cwd=tmp_path,
        env=_env(),
        transcript=transcript,
        timeout_s=_TREE_TIMEOUT_S,
    )
    elapsed = time.monotonic() - started
    assert result.timed_out is True
    assert elapsed < 20, elapsed
    children = [event["pid"] for event in result.events if event.get("subtype") == "fake_child"]
    assert len(children) == 1, result.events
    assert _gone(children[0]), f"child {children[0]} outlived the tree kill"
    assert classify(result.events, result.exit_code, result.timed_out) is Disposition.ATTEMPT_DONE


def test_kill_tree_runs_taskkill_as_an_argv_list_on_windows():
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0)

    kill_tree(4321, run=run, windows=True)
    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert isinstance(argv, list)
    assert Path(argv[0]).name.lower() == "taskkill.exe"
    assert argv[1:] == ["/T", "/F", "/PID", "4321"]
    assert not kwargs.get("shell")


def test_fakeclaude_write_reaches_the_disk(tmp_path):
    target = tmp_path / "src" / "ufo2p" / "u_x.c"
    result = run_session(
        _fake("--scenario", "success", "--write", str(target)),
        cwd=tmp_path,
        env=_env(),
        transcript=tmp_path / "attempt" / "transcript.jsonl",
    )
    assert result.exit_code == 0
    assert target.is_file()


def test_session_cwd_keeps_relative_writes_under_it(tmp_path):
    """Ruling F11: the session runs in `cwd`, so a relative write lands under it only."""
    work = tmp_path / "checkout"
    work.mkdir()
    rel = Path("src") / "ufo2p" / "u_f11_probe.c"
    result = run_session(
        _fake("--scenario", "success", "--write", rel.as_posix()),
        cwd=work,
        env=_env(),
        transcript=tmp_path / "attempt" / "transcript.jsonl",
    )
    assert result.exit_code == 0
    assert (work / rel).is_file()
    assert not (REPO_ROOT / rel).exists()
    assert not (Path.cwd() / rel).exists()


def test_nonzero_exit_without_result_is_transient(tmp_path):
    result = run_session(
        _fake("--scenario", "no_result", "--exit", "1"),
        cwd=tmp_path,
        env=_env(),
        transcript=tmp_path / "attempt" / "transcript.jsonl",
    )
    assert result.exit_code == 1
    assert result.timed_out is False
    assert [event.get("type") for event in result.events] == ["system", "assistant"]
    assert classify(result.events, result.exit_code, result.timed_out) is Disposition.TRANSIENT


# Fix round 1, I1: an exception mid-read never leaves the session tree alive, and a line the
# JSON parser cannot handle (deep nesting) is malformed, never fatal.

_DEEP_LINE = b"[" * 100_000 + b"\n"
_INTERRUPT_AFTER_S = 3.0  # long enough for fakeclaude to report its child


class _FakePopen:
    """A finished session in place of subprocess.Popen: `lines` on stdout, exit `code`."""

    def __init__(self, lines: list[bytes], code: int = 0) -> None:
        self.stdout = io.BytesIO(b"".join(lines))
        self.code = code
        self.pid = 0
        self.argv: list[str] | None = None
        self.kwargs: dict = {}

    def __call__(self, argv, **kwargs) -> _FakePopen:
        self.argv, self.kwargs = list(argv), kwargs
        return self

    def poll(self) -> int:
        return self.code

    def wait(self, timeout: float | None = None) -> int:
        return self.code


def test_run_session_through_an_injected_popen_counts_a_deep_line_as_malformed(tmp_path):
    lines = (STREAMS / "success.jsonl").read_bytes().splitlines(keepends=True)
    fake = _FakePopen([lines[0], _DEEP_LINE, *lines[1:]])
    try:
        result = run_session(
            ["claude-stand-in"],
            cwd=tmp_path,
            env={},
            transcript=tmp_path / "attempt" / "transcript.jsonl",
            popen=fake,
        )
    except RecursionError as exc:
        pytest.fail(f"a deeply nested line was fatal: {exc!r}")
    assert fake.argv == ["claude-stand-in"]
    assert fake.kwargs["cwd"] == os.fspath(tmp_path)
    assert fake.kwargs["stdin"] is subprocess.DEVNULL
    assert result.malformed == 1
    assert result.exit_code == 0
    assert [event["type"] for event in result.events] == ["system", "assistant", "user", "result"]


def _child_pid(transcript: Path) -> int | None:
    for line in transcript.read_bytes().splitlines():
        if b'"fake_child"' in line:
            return json.loads(line)["pid"]
    return None


def _kill_pid(pid: int) -> None:
    """Test cleanup only: end one process whatever the code under test did."""
    if not _alive(pid):
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, check=False)
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def test_an_exception_mid_read_kills_the_tree_and_propagates(tmp_path):
    procs: list[subprocess.Popen] = []

    def popen(argv, **kwargs) -> subprocess.Popen:
        procs.append(subprocess.Popen(argv, **kwargs))
        return procs[-1]

    start = time.monotonic()

    def clock() -> float:
        now = time.monotonic()
        if now - start > _INTERRUPT_AFTER_S:
            raise KeyboardInterrupt
        return now

    transcript = tmp_path / "attempt" / "transcript.jsonl"
    child = None
    try:
        with pytest.raises(KeyboardInterrupt):
            run_session(
                _fake("--scenario", "no_result", "--spawn-child", "--sleep", "30"),
                cwd=tmp_path,
                env=_env(),
                transcript=transcript,
                timeout_s=60,
                popen=popen,
                clock=clock,
            )
        child = _child_pid(transcript)
        assert child is not None, transcript.read_text()
        assert _gone(procs[0].pid), "the session root outlived the exception"
        assert _gone(child), f"child {child} outlived the exception"
    finally:
        if child is not None:
            _kill_pid(child)
        for proc in procs:
            _kill_pid(proc.pid)
            proc.wait()
