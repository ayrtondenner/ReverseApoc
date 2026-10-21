"""The tracked commit-msg hook (.githooks/commit-msg). Under Claude Code, which sets CLAUDECODE=1
for every command it runs, the hook adds a Co-Authored-By trailer to a message that has none,
so GSD's own commits (`gsd-tools query commit`, `git merge --no-ff --no-edit -m ...`) carry
one too. Without CLAUDECODE it leaves the message alone, and it never fails a commit."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import REPO_ROOT

HOOKS_DIR = REPO_ROOT / ".githooks"
HOOK = HOOKS_DIR / "commit-msg"
DEFAULT_TRAILER = "Co-Authored-By: Claude <noreply@anthropic.com>"
OVERRIDE = "Claude Opus 5.5 (1M context) <noreply@anthropic.com>"


def _find_sh(git: str | None) -> str | None:
    """`sh` on PATH, else the one Git for Windows ships (<Git>/cmd/git.exe -> <Git>/bin/sh.exe),
    which is the shell git itself runs hooks with."""
    found = shutil.which("sh")
    if found or git is None:
        return found
    bundled = Path(git).resolve().parents[1] / "bin" / "sh.exe"
    return str(bundled) if bundled.is_file() else None


GIT = shutil.which("git")
SH = _find_sh(GIT)
pytestmark = pytest.mark.skipif(not (SH and GIT), reason="needs sh and git on PATH")


class _Env(dict):
    """A subprocess environment whose repr stays short, so a failing assert never prints the
    user's environment variables."""

    def __repr__(self) -> str:
        return f"<env CLAUDECODE={self.get('CLAUDECODE')!r}>"


def _env(tmp_path: Path, *, claudecode: bool, config: dict[str, str] | None = None) -> _Env:
    """The current environment without CLAUDECODE and git's repo/config overrides, with an
    empty global config so the user's own git settings cannot leak in."""
    env = _Env(
        (k, v)
        for k, v in os.environ.items()
        if k != "CLAUDECODE" and not (k.startswith("GIT_") and k != "GIT_EXEC_PATH")
    )
    global_config = tmp_path / "global.gitconfig"
    global_config.touch()
    env["GIT_CONFIG_GLOBAL"] = str(global_config)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    if claudecode:
        env["CLAUDECODE"] = "1"
    for i, (key, value) in enumerate((config or {}).items()):
        env[f"GIT_CONFIG_KEY_{i}"] = key
        env[f"GIT_CONFIG_VALUE_{i}"] = value
    if config:
        env["GIT_CONFIG_COUNT"] = str(len(config))
    return env


def _run_hook(msg: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [SH, HOOK.as_posix(), msg.as_posix()],
        env=env,
        cwd=msg.parent,
        capture_output=True,
        text=True,
        check=False,
    )


def _coauthor_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.lower().startswith("co-authored-by:")]


def _message(tmp_path: Path, text: str) -> Path:
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_bytes(text.encode("utf-8"))
    return msg


# ---- the hook on its own ------------------------------------------------------------------


def test_adds_the_default_trailer_under_claude_code(tmp_path):
    msg = _message(tmp_path, "feat: one\n\nA body line.\n")
    result = _run_hook(msg, _env(tmp_path, claudecode=True))
    assert result.returncode == 0
    text = msg.read_text(encoding="utf-8")
    assert text.startswith("feat: one\n\nA body line.\n")
    assert _coauthor_lines(text) == [DEFAULT_TRAILER]
    assert text.rstrip("\n").splitlines()[-1] == DEFAULT_TRAILER


def test_subject_only_message_gets_the_trailer(tmp_path):
    msg = _message(tmp_path, "chore: merge executor worktree (x)\n")
    assert _run_hook(msg, _env(tmp_path, claudecode=True)).returncode == 0
    assert _coauthor_lines(msg.read_text(encoding="utf-8")) == [DEFAULT_TRAILER]


def test_without_claudecode_the_message_is_untouched(tmp_path):
    original = "feat: one\n\nA body line.\n"
    msg = _message(tmp_path, original)
    assert _run_hook(msg, _env(tmp_path, claudecode=False)).returncode == 0
    assert msg.read_text(encoding="utf-8") == original


@pytest.mark.parametrize(
    "trailer",
    [
        "Co-Authored-By: Someone <someone@example.com>",
        "co-authored-by: Someone <someone@example.com>",
        "CO-AUTHORED-BY: Someone <someone@example.com>",
    ],
    ids=["canonical", "lower", "upper"],
)
def test_an_existing_trailer_in_any_case_is_kept_as_is(tmp_path, trailer):
    original = f"feat: one\n\nA body line.\n\n{trailer}\n"
    msg = _message(tmp_path, original)
    assert _run_hook(msg, _env(tmp_path, claudecode=True)).returncode == 0
    assert msg.read_text(encoding="utf-8") == original


def test_a_message_without_a_final_newline_keeps_its_subject(tmp_path):
    # git 2.43 hands a `merge -m` message to commit-msg without a final newline; interpret-trailers
    # then glues the trailer onto the subject line instead of starting a trailer block
    msg = _message(tmp_path, "chore: merge executor worktree (x)")
    assert _run_hook(msg, _env(tmp_path, claudecode=True)).returncode == 0
    assert msg.read_text(encoding="utf-8") == (
        f"chore: merge executor worktree (x)\n\n{DEFAULT_TRAILER}\n"
    )


@pytest.mark.parametrize(
    "text",
    ["", "\n", "# Please enter the commit message.\n#\n"],
    ids=["empty", "blank", "comments"],
)
def test_an_empty_message_stays_empty_so_git_aborts(tmp_path, text):
    msg = _message(tmp_path, text)
    assert _run_hook(msg, _env(tmp_path, claudecode=True)).returncode == 0
    assert msg.read_text(encoding="utf-8") == text


def test_an_empty_commit_under_claude_code_is_still_aborted(repo, tmp_path):
    env = _env(tmp_path, claudecode=True)
    _commit(repo, env, "a.txt", "feat: one")
    (repo / "b.txt").write_text("b", encoding="utf-8")
    _git(repo, env, "add", "b.txt")
    result = subprocess.run(
        [GIT, "commit", "-q", "-m", ""], cwd=repo, env=env, capture_output=True, text=True
    )
    assert result.returncode != 0
    assert _git(repo, env, "log", "-1", "--format=%s").strip() == "feat: one"


# `commit -v` (or commit.verbose) puts the diff below git's scissors line in the message file;
# git cuts there before its own empty-message check, so the hook must not count the diff either
SCISSORS_AND_DIFF = (
    "# ------------------------ >8 ------------------------\n"
    "# Do not modify or remove the line above.\n"
    "# Everything below it will be ignored.\n"
    "diff --git a/b.txt b/b.txt\n"
    "new file mode 100644\n"
    "--- /dev/null\n"
    "+++ b/b.txt\n"
    "@@ -0,0 +1 @@\n"
    "+b\n"
)
VERBOSE_HELP = "# Please enter the commit message for your changes.\n#\n"


def test_an_untouched_verbose_message_stays_empty(tmp_path):
    text = f"\n{VERBOSE_HELP}{SCISSORS_AND_DIFF}"
    msg = _message(tmp_path, text)
    assert _run_hook(msg, _env(tmp_path, claudecode=True)).returncode == 0
    assert msg.read_text(encoding="utf-8") == text


def test_a_verbose_message_gets_the_trailer_above_the_scissors(tmp_path):
    msg = _message(tmp_path, f"feat: one\n\n{VERBOSE_HELP}{SCISSORS_AND_DIFF}")
    assert _run_hook(msg, _env(tmp_path, claudecode=True)).returncode == 0
    text = msg.read_text(encoding="utf-8")
    above, cut, below = text.partition(SCISSORS_AND_DIFF.splitlines(keepends=True)[0])
    assert cut
    assert above.startswith("feat: one\n")
    assert _coauthor_lines(above) == [DEFAULT_TRAILER]
    assert cut + below == SCISSORS_AND_DIFF


@pytest.mark.parametrize(
    "args",
    [["commit", "-v"], ["-c", "commit.verbose=true", "commit"]],
    ids=["dash-v", "commit.verbose"],
)
def test_an_untouched_verbose_commit_under_claude_code_is_still_aborted(repo, tmp_path, args):
    env = _env(tmp_path, claudecode=True)
    _commit(repo, env, "a.txt", "feat: one")
    head = _git(repo, env, "rev-parse", "HEAD")
    (repo / "b.txt").write_text("b", encoding="utf-8")
    _git(repo, env, "add", "b.txt")
    env["GIT_EDITOR"] = "true"  # an editor that leaves the message as git wrote it
    result = subprocess.run([GIT, *args], cwd=repo, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "Aborting commit due to empty commit message" in result.stderr
    assert _git(repo, env, "rev-parse", "HEAD") == head


def test_running_twice_adds_one_trailer(tmp_path):
    msg = _message(tmp_path, "feat: one\n")
    env = _env(tmp_path, claudecode=True)
    assert _run_hook(msg, env).returncode == 0
    once = msg.read_text(encoding="utf-8")
    assert _run_hook(msg, env).returncode == 0
    assert msg.read_text(encoding="utf-8") == once
    assert _coauthor_lines(once) == [DEFAULT_TRAILER]


def test_git_config_overrides_the_trailer_value(tmp_path):
    msg = _message(tmp_path, "feat: one\n")
    env = _env(tmp_path, claudecode=True, config={"reverseapoc.coauthor": OVERRIDE})
    assert _run_hook(msg, env).returncode == 0
    assert _coauthor_lines(msg.read_text(encoding="utf-8")) == [f"Co-Authored-By: {OVERRIDE}"]


def test_a_missing_message_file_does_not_fail_the_commit(tmp_path):
    result = _run_hook(tmp_path / "absent", _env(tmp_path, claudecode=True))
    assert result.returncode == 0
    assert not (tmp_path / "absent").exists()


# ---- end to end in a throwaway repository -------------------------------------------------


def _git(repo: Path, env: dict, *args: str) -> str:
    result = subprocess.run(
        [GIT, *args], cwd=repo, env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result.stdout


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    env = _env(tmp_path, claudecode=False)
    _git(repo, env, "init", "-q", "-b", "main")
    for key, value in [
        ("user.name", "Test"),
        ("user.email", "test@example.com"),
        ("commit.gpgsign", "false"),
        ("core.hooksPath", HOOKS_DIR.as_posix()),
    ]:
        _git(repo, env, "config", key, value)
    return repo


def _commit(repo: Path, env: dict, name: str, message: str) -> None:
    (repo / name).write_text(name, encoding="utf-8")
    _git(repo, env, "add", name)
    _git(repo, env, "commit", "-q", "-m", message)


def _trailers(repo: Path, env: dict) -> list[str]:
    out = _git(repo, env, "log", "-1", "--format=%(trailers:key=Co-Authored-By)")
    return [line for line in out.splitlines() if line]


def test_commit_under_claude_code_gets_the_trailer(repo, tmp_path):
    env = _env(tmp_path, claudecode=True)
    _commit(repo, env, "a.txt", "feat: one")
    assert _trailers(repo, env) == [DEFAULT_TRAILER]


def test_merge_commit_under_claude_code_gets_the_trailer(repo, tmp_path):
    plain = _env(tmp_path, claudecode=False)
    _commit(repo, plain, "a.txt", "feat: base")
    _git(repo, plain, "checkout", "-q", "-b", "side")
    _commit(repo, plain, "b.txt", "feat: side")
    _git(repo, plain, "checkout", "-q", "main")
    _commit(repo, plain, "c.txt", "feat: main")
    env = _env(tmp_path, claudecode=True)
    _git(repo, env, "merge", "--no-ff", "--no-edit", "-m", "chore: merge executor worktree (x)",
         "side")  # fmt: skip
    assert len(_git(repo, env, "log", "-1", "--format=%P").split()) == 2
    assert _git(repo, env, "log", "-1", "--format=%s").strip() == (
        "chore: merge executor worktree (x)"
    )
    assert _trailers(repo, env) == [DEFAULT_TRAILER]


def test_commit_without_claude_code_gets_no_trailer(repo, tmp_path):
    env = _env(tmp_path, claudecode=False)
    _commit(repo, env, "a.txt", "feat: one")
    assert _trailers(repo, env) == []
    assert _git(repo, env, "log", "-1", "--format=%B").strip() == "feat: one"
