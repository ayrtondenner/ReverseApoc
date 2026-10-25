"""The driver's session layer (AGT-01, AGT-03, D-06, D-07, D-35, D-44, D-45): the exact `claude -p`
argv, the /goal prompt and the process runner. Every session here runs tests/fakeclaude.py, the
stand-in that replays a synthetic stream fixture; no test ever starts the real claude."""

from __future__ import annotations

import os
import sys

from reverseapoc.session import build_argv, goal_prompt, run_session
from reverseapoc.streamjson import Disposition, classify

from conftest import REPO_ROOT

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
