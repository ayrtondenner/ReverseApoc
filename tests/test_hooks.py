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


# --- Task 2: the full always-on layer (D-16, D-46, F16) ----------------------------------------


def _forms(repo: Path, rel: str) -> list[str]:
    """`rel` under `repo` in this platform's native form, POSIX separators, through `..`, and
    upper-cased (NTFS and the hook compare casefolded)."""
    target = repo.joinpath(*rel.split("/"))
    detour = repo / "tools" / ".." / rel
    found = [native(target), target.as_posix(), str(detour), native(repo / rel.upper())]
    if WINDOWS:
        found.append(str(target) + ".")  # NTFS drops a trailing dot
        found.append(str(target) + "::$DATA")  # and opens the main stream
    return found


@pytest.mark.parametrize(
    "rel",
    ["config/targets.toml", "config/watcom.toml", "config/ufo2p/x.sha1", "a.SHA1", "asm/x.s",
     "asm/ufo2p/ghidra/func_00010000.c", "build/x", "build/driver/r/ufo2p/f/other.md", "orig"],
)  # fmt: skip
def test_always_denies_protected_files(repo, rel):
    for form in _forms(repo, rel):
        decision = always(write(form))
        assert decision.deny, form
        assert "D-16" in decision.reason


@pytest.mark.parametrize(
    "rel",
    ["asm.md", "buildx/x", "orig_notes.md", "tools/reverseapoc/asm.py", "config/cflags.txt",
     "configure.py", "tests/test_x.py", "docs/x.md", ".planning/x.md", "config/targets.toml.bak",
     "src/README.md"],
)  # fmt: skip
def test_always_allows_near_miss_paths(repo, rel):
    for form in _forms(repo, rel):
        assert not always(write(form)).deny, form


def test_always_allows_the_attempt_notes(repo):
    notes = repo / "build" / "driver" / "run1" / "ufo2p" / "func_000A3980" / "a-1" / "notes.md"
    env = {"REVERSEAPOC_ATTEMPT_NOTES": native(notes)}
    assert not always(write(native(notes)), env).deny
    assert not always(write(notes.as_posix()), env).deny
    assert not always(write(native(repo / notes.relative_to(repo).as_posix().upper())), env).deny
    sibling = notes.with_name("other.md")
    assert always(write(native(sibling)), env).deny
    assert always(write(native(notes)), {}).deny
    elsewhere = repo / "build" / "other" / "notes.md"
    assert always(write(native(elsewhere)), {"REVERSEAPOC_ATTEMPT_NOTES": native(elsewhere)}).deny
    renamed = notes.with_name("notes.txt")
    assert always(write(native(renamed)), {"REVERSEAPOC_ATTEMPT_NOTES": native(renamed)}).deny
    escape = notes.parent / ".." / ".." / ".." / ".." / ".." / "orig" / "notes.md"
    assert always(write(native(escape)), {"REVERSEAPOC_ATTEMPT_NOTES": native(escape)}).deny


def test_always_resolves_relative_notes_against_the_payload_cwd(repo):
    notes = repo / "build" / "driver" / "r" / "notes.md"
    env = {"REVERSEAPOC_ATTEMPT_NOTES": "build/driver/r/notes.md"}
    assert not always(write(native(notes), cwd=repo), env).deny


UNIT = "src/ufo2p/u_000a34f0.c"
SCAFFOLD = '#include "common.h"\n\nINCLUDE_ASM(func_00010000);\nINCLUDE_ASM(func_00010010);\n'
ASM_TEXTS = {
    "asm": "void f(void) { _asm int 3 }\n",
    "dunder-asm": "void f(void) { __asm { int 3 } }\n",
    "pragma-op": '_Pragma("aux f = 0x90")\n',
    "pragma-aux-code": "#pragma aux f = 0x90 0xc3\n",
    "pragma-aux-spaced": "  #  pragma   aux   f = 0x90\n",
    "pragma-aux-continued": "#pragma aux f \\\n    = 0x90\n",
    "pragma-aux-comment": "#pragma /* x */ aux f /* y */ = 0x90\n",
    "trigraph-pragma": "??=pragma aux f = 0x90\n",
    "asm-spliced": "void f(void) { _a\\\nsm int 3 }\n",
    "asm-in-define": "#define TRAP _asm int 3\n",
    "asm-in-if0": "#if 0\n_asm int 3\n#endif\n",
    "lone-cr": 'char *s = "a\rb"; int x;\n',
}
# 06-03's INLINE_ASM_PROBES (tests/test_configure.py): wcc386 keeps `_asm int 3` live in each,
# though a scanner that reads the comment or literal naively would hide it.
CONTINUATION_ASM_PROBES = {
    "blank-splice-closer": "/* x *\\ \n/ void f(void) { _asm int 3 } /* y */\n",
    "blank-splice-string": 'char *s = "a\\ \nb"; void f(void) { _asm int 3 } char *t = "x";\n',
    "trigraph-closer": "/* x *??/\n/ void f(void) { _asm int 3 } /* y */\n",
    "crlf-closer": "/* x *\\\r\n/ void f(void) { _asm int 3 } /* y */\r\n",
}


def _unit(repo: Path, text: str = SCAFFOLD, rel: str = UNIT) -> Path:
    path = repo.joinpath(*rel.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def multi_edit(path: str, *edits: tuple[str, str]) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": path,
            "edits": [{"old_string": old, "new_string": new} for old, new in edits],
        },
    }


@pytest.mark.parametrize("name", sorted({**ASM_TEXTS, **CONTINUATION_ASM_PROBES}))
@pytest.mark.parametrize("rel", [UNIT, "include/new.h"])
def test_always_denies_inline_asm_in_src(repo, name, rel):
    text = {**ASM_TEXTS, **CONTINUATION_ASM_PROBES}[name]
    path = _unit(repo, rel=rel)
    assert always(write(native(path), SCAFFOLD + text)).deny
    assert always(edit(native(path), "INCLUDE_ASM(func_00010010);\n", text)).deny
    marker = "INCLUDE_ASM(func_00010000);"
    assert always(multi_edit(native(path), (marker, "int x;"), ("int x;", text))).deny


def test_always_denies_lone_cr_naming_the_reason(repo):
    path = _unit(repo)
    decision = always(write(native(path), ASM_TEXTS["lone-cr"]))
    assert decision.deny and "carriage return" in decision.reason


def test_always_denies_an_edit_that_completes_asm(repo):
    """The post-edit text is scanned, not the new string alone: `_a` + `sm` makes `_asm`."""
    path = _unit(repo, SCAFFOLD + "void f(void) { _aXX int 3 }\n")
    assert always(edit(native(path), "XX", "sm")).deny
    assert not always(edit(native(path), "X", "s")).deny  # once: `_asX`
    other = _unit(repo, SCAFFOLD + "void f(void) { _a_X int 3 } /* _a_X */\n")
    assert always(edit(native(other), "_X", "sm", replace_all=True)).deny


ALLOWED_TEXTS = {
    "block-comment": "/* uses _asm, __asm, _Pragma and #pragma aux f = 0x90 */\n",
    "line-comment": "// _asm __asm _Pragma\n",
    "string": 'char *s = "_asm __asm _Pragma #pragma aux f = 0x90";\n',
    "char": "char c = '_';\n",
    "calling-convention": "#pragma aux f parm [eax] value [eax] modify [ecx];\n",
    "identifiers": "int my_asm, asm_x, INCLUDE_ASM_x, _asmx, x__asm;\n",
    "scaffold": SCAFFOLD,
}


@pytest.mark.parametrize("name", sorted(ALLOWED_TEXTS))
def test_always_allows_asm_words_in_comments_and_strings(repo, name):
    path = _unit(repo)
    assert not always(write(native(path), SCAFFOLD + ALLOWED_TEXTS[name])).deny
    assert not always(edit(native(path), "INCLUDE_ASM(func_00010010);", ALLOWED_TEXTS[name])).deny


def test_always_allows_the_committed_headers_and_units(repo):
    """F16: the scaffold, include/common.h (its `#define INCLUDE_ASM(name) extern int
    INCLUDE_ASM_##name` kept) and watcom_compat.h (a `#pragma aux` only in a comment) pass."""
    for rel in ["include/common.h", "include/watcom_compat.h", "src/ufo2p/u_000a34f0.c",
                "src/tacp/u_00054f20.c"]:  # fmt: skip
        text = (REPO_ROOT / rel).read_bytes().decode("utf-8")
        path = _unit(repo, text, rel)
        assert not always(write(native(path), text)).deny, rel
    common = repo / "include" / "common.h"
    keep = "#define INCLUDE_ASM(name) extern int INCLUDE_ASM_##name"
    assert not always(edit(native(common), keep, keep + "\n/* note */")).deny


def test_always_denies_a_notebook_in_src(repo):
    payload = {
        "tool_name": "NotebookEdit",
        "tool_input": {"notebook_path": native(repo / "src" / "x.ipynb"), "new_source": "x"},
    }
    assert always(payload).deny
    payload["tool_input"]["notebook_path"] = native(repo / "docs" / "x.ipynb")
    assert not always(payload).deny


def test_always_ignores_paths_outside_the_repo(tmp_path):
    scratch = tmp_path / "scratch" / "orig" / "x.c"
    assert not always(write(native(scratch), "_asm int 3")).deny
    assert not always(write(native(tmp_path / "build" / "x"))).deny


def test_worktree_root_is_found(repo):
    worktree = repo / ".claude" / "worktrees" / "agent-x"
    worktree.mkdir(parents=True)
    (worktree / ".git").write_text("gitdir: ../../../.git/worktrees/agent-x\n", encoding="utf-8")
    decision = always(write(native(worktree / "orig" / "UFO2P.EXE")))
    assert decision.deny and "orig/" in decision.reason
    assert always(write(native(worktree / "build" / "x"))).deny
    assert not always(write(native(worktree / "tools" / "x.py"))).deny
    src = _unit(worktree)
    assert always(write(native(src), "_asm int 3\n")).deny
    gone = repo / ".claude" / "worktrees" / "agent-gone" / "config" / "targets.toml"
    assert always(write(native(gone))).deny  # a worktree whose .git is missing is still judged
