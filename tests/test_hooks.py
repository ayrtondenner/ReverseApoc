"""The guardrail hooks (tools/reverseapoc/hooks.py, AGT-05, D-15..D-18, D-44..D-46, DI-07).

`decide` gets synthetic PreToolUse payloads for files in a scratch repository (a tmp directory
holding `.git`); the entry point runs once for real in a subprocess. A path test that needs a
platform's own path form picks it by sys.platform inside one test (rulings R-A)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from reverseapoc import hooks

WINDOWS = sys.platform == "win32"
ALWAYS_COMMAND = "uv run --frozen python -I -m reverseapoc.hooks pre-tool-use --layer always"
EDIT_TOOLS = "Edit|Write|MultiEdit|NotebookEdit"


class _Env(dict):
    """A subprocess environment whose repr stays short, so a failing assert never prints the
    user's environment variables."""

    def __repr__(self) -> str:
        return f"<env of {len(self)} variables>"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A scratch checkout: a directory holding a `.git` directory."""
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    return root


def native(path: Path) -> str:
    """`path` as Claude Code sends it on this platform (backslashes on Windows)."""
    return str(path)


def write(path: str, content: str = "x\n", *, cwd: Path | None = None) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": path, "content": content},
        "cwd": str(cwd) if cwd is not None else "",
    }


def edit(path: str, old: str, new: str, *, replace_all: bool = False) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {
            "file_path": path, "old_string": old, "new_string": new, "replace_all": replace_all,
        },
    }  # fmt: skip


def always(payload: dict, env: dict | None = None) -> hooks.Decision:
    return hooks.decide(payload, layer="always", env=env or {}, tracked=lambda _: True)


def test_always_denies_a_write_under_orig(repo):
    forms = [native(repo / "orig" / "UFO2P.EXE"), (repo / "orig" / "x").as_posix()]
    if WINDOWS:
        text = str(repo)
        forms.append(text[0].swapcase() + text[1:] + "\\orig\\UFO2P.EXE")  # the drive's case
    for form in forms:
        decision = always(write(form))
        assert decision.deny, form
        assert "orig/" in decision.reason


def test_always_allows_a_tools_edit(repo):
    target = repo / "tools" / "reverseapoc" / "x.py"
    target.parent.mkdir(parents=True)
    target.write_text("a = 1\n", encoding="utf-8")
    assert not always(edit(native(target), "a = 1", "a = 2")).deny


def _run_entry(stdin: bytes, layer: str = "always") -> subprocess.CompletedProcess[bytes]:
    env = _Env(os.environ)
    return subprocess.run(
        [sys.executable, "-I", "-m", "reverseapoc.hooks", "pre-tool-use", "--layer", layer],
        input=stdin, capture_output=True, env=env, timeout=60, check=False,
    )  # fmt: skip


def test_entry_point_end_to_end(repo):
    payload = write(native(repo / "orig" / "UFO2P.EXE"), cwd=repo)
    done = _run_entry(json.dumps(payload).encode("utf-8"))
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    specific = out["hookSpecificOutput"]
    assert specific["hookEventName"] == "PreToolUse"
    assert specific["permissionDecision"] == "deny"
    assert "orig/" in specific["permissionDecisionReason"]

    allowed = _run_entry(json.dumps(write(native(repo / "tools" / "x.py"))).encode("utf-8"))
    assert (allowed.returncode, allowed.stdout) == (0, b"")

    broken = _run_entry(b"{not json")
    assert broken.returncode == 2
    assert broken.stdout == b""
    assert b"reverseapoc hooks" in broken.stderr


def test_project_settings_wire_the_always_layer():
    settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings["enabledPlugins"] == {
        "claude-md-management@claude-plugins-official": True,
        "code-review@claude-plugins-official": True,
        "code-simplifier@claude-plugins-official": True,
        "security-guidance@claude-plugins-official": True,
        "superpowers@claude-plugins-official": True,
        "i-have-adhd@i-have-adhd": True,
        "clangd-lsp@claude-plugins-official": True,
    }
    assert settings["extraKnownMarketplaces"] == {
        "i-have-adhd": {"source": {"source": "github", "repo": "ayghri/i-have-adhd"}}
    }
    assert set(settings) == {"enabledPlugins", "extraKnownMarketplaces", "hooks"}
    assert settings["hooks"] == {
        "PreToolUse": [
            {
                "matcher": EDIT_TOOLS,
                "hooks": [{"type": "command", "command": ALWAYS_COMMAND}],
            }
        ]
    }
    assert "onFailure" not in json.dumps(settings)
