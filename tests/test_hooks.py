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


# --- Task 3: the matching layer (D-17, D-18, D-44, D-45, DI-07) -------------------------------

CLAIM = {"REVERSEAPOC_CLAIM": "ufo2p/u_000a34f0"}
MATCHING_COMMAND = "uv run --frozen python -I -m reverseapoc.hooks pre-tool-use --layer matching"
WRAPPER = "uv run --frozen reverseapoc attempt"


def matching(payload: dict, env: dict | None = None, tracked=lambda _: False) -> hooks.Decision:
    return hooks.decide(
        payload, layer="matching", env=CLAIM if env is None else env, tracked=tracked
    )


def tool(name: str, repo: Path, **tool_input) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": name, "tool_input": tool_input,
            "cwd": str(repo)}  # fmt: skip


def bash(command: str, repo: Path) -> dict:
    return tool("Bash", repo, command=command, description="x")


def in_repo(payload: dict, repo: Path) -> dict:
    return {**payload, "cwd": str(repo)}


def test_matching_allows_only_the_claimed_unit(repo):
    unit = _unit(repo)
    assert not matching(in_repo(write(native(unit), SCAFFOLD), repo)).deny
    assert not matching(in_repo(write(unit.as_posix(), SCAFFOLD), repo)).deny
    assert not matching(in_repo(edit(native(unit), "INCLUDE_ASM(func_00010010);", ""), repo)).deny
    marker = "INCLUDE_ASM(func_00010000);"
    assert not matching(in_repo(multi_edit(native(unit), (marker, "int x;")), repo)).deny
    for rel in ["src/ufo2p/u_other.c", "src/tacp/u_000a34f0.c", "config/ufo2p/status.csv",
                "decomphub.progress.json", "progress/attempts.jsonl", "tools/x.py", "tests/x.py",
                "configure.py", "config/cflags.txt", ".claude/x", ".github/x", "src/ufo2p/x.h",
                "docs/x.md", ".planning/x.md", "src/ufo2p/u_000a34f0.c.bak"]:  # fmt: skip
        target = repo.joinpath(*rel.split("/"))
        assert matching(in_repo(write(native(target)), repo)).deny, rel
    outside = repo.parent / "elsewhere" / "src" / "ufo2p" / "u_000a34f0.c"
    assert matching(in_repo(write(native(outside), SCAFFOLD), repo)).deny


def test_matching_include_rules(repo):
    new = repo / "include" / "foo.h"
    assert not matching(in_repo(write(native(new), "int foo(void);\n"), repo)).deny
    for name in ["common.h", "watcom_compat.h", "COMMON.H", "sub/x.h", "x.c", "x.h.bak"]:
        target = repo / "include" / name
        assert matching(in_repo(write(native(target), "int foo(void);\n"), repo)).deny, name
    payload = in_repo(write(native(new), "int foo(void);\n"), repo)
    assert matching(payload, tracked=lambda _: True).deny


def test_matching_allows_the_attempt_notes(repo):
    notes = repo / "build" / "driver" / "r" / "ufo2p" / "func_000A3980" / "a-1" / "notes.md"
    env = {**CLAIM, "REVERSEAPOC_ATTEMPT_NOTES": native(notes)}
    assert not matching(in_repo(write(native(notes), "# notes\n"), repo), env).deny
    assert matching(in_repo(write(native(notes.with_name("x.md"))), repo), env).deny


def test_matching_denies_every_pragma_aux(repo):
    unit = _unit(repo)
    for text in ["#pragma aux f parm [eax];\n", "#pragma aux f = 0x90\n", "_asm int 3\n",
                 "# pragma \\\n aux f parm [eax];\n", 'char *s = "a\rb";\n']:  # fmt: skip
        assert matching(in_repo(write(native(unit), SCAFFOLD + text), repo)).deny, text
    header = repo / "include" / "foo.h"
    assert matching(in_repo(write(native(header), "#pragma aux f parm [eax];\n"), repo)).deny
    assert not matching(in_repo(write(native(unit), SCAFFOLD + "/* #pragma aux */\n"), repo)).deny


def test_attempt_forms_are_the_shared_constants():
    assert hooks.ATTEMPT_PREFIX == ("uv", "run", "--frozen", "reverseapoc", "attempt")
    assert hooks.ATTEMPT_FORMS == (
        ("check",), ("check", "--sweep"), ("asm",), ("asm", "<NAME>"), ("context",),
    )  # fmt: skip
    assert hooks.attempt_form_matches(("asm", "func_000A3980"))
    assert hooks.attempt_form_matches(["check", "--sweep"])
    assert not hooks.attempt_form_matches(("asm", "<NAME>"))
    assert not hooks.attempt_form_matches(("asm", "1abc"))
    assert not hooks.attempt_form_matches(("check", "--sweep", "x"))
    assert not hooks.attempt_form_matches(())


@pytest.mark.parametrize(
    "command",
    [f"{WRAPPER} check", f"{WRAPPER} check --sweep", f"{WRAPPER} asm",
     f"{WRAPPER} asm func_000A3980", f"{WRAPPER} asm D_0012EFAC", f"{WRAPPER} asm _Alphabet",
     f"{WRAPPER} context"],
)  # fmt: skip
def test_matching_bash_allows_exact_wrapper_forms(repo, command):
    assert not matching(bash(command, repo)).deny


@pytest.mark.parametrize(
    "command",
    ["ls", "git status", "uv run reverseapoc check ufo2p/u --json", f"{WRAPPER} check --cflags x",
     f"{WRAPPER} check; ls", f"{WRAPPER} check && ls", f"{WRAPPER} check | cat",
     f"{WRAPPER} check > f", f"{WRAPPER} asm $(x)", f"{WRAPPER} asm `x`", f"{WRAPPER} check\nls",
     f"{WRAPPER} 'check'", f'{WRAPPER} "check"', f"{WRAPPER} asm func-x", f"{WRAPPER} asm 1abc",
     "uv run reverseapoc attempt check", f"{WRAPPER} check --sweep --sweep", f"{WRAPPER}\tcheck",
     f"{WRAPPER} check &", f"{WRAPPER} asm x*", f"{WRAPPER} asm ~", f"{WRAPPER} context # x",
     f"FOO=1 {WRAPPER} check", f"{WRAPPER} asm fé", f"{WRAPPER} check\r", f"{WRAPPER}", ""],
)  # fmt: skip
def test_matching_bash_denies_everything_else(repo, command):
    assert matching(bash(command, repo)).deny


def test_matching_reads_stay_in_the_repo(repo):
    inside = repo / "asm" / "ufo2p" / "x.s"
    assert not matching(tool("Read", repo, file_path=native(inside))).deny
    assert not matching(tool("Glob", repo, pattern="src/**/*.c")).deny
    assert not matching(tool("Glob", repo, pattern="*.c", path=native(repo / "src"))).deny
    assert not matching(tool("Grep", repo, pattern="func_", path=native(repo / "src"))).deny
    assert not matching(tool("Grep", repo, pattern="func_")).deny
    credentials = Path.home() / ".claude" / ".credentials.json"
    for raw in [native(credentials), "~/.claude/.credentials.json", native(repo.parent / "x"),
                native(repo / ".env"), native(repo / ".env.local"), native(repo / "a" / ".ENV"),
                native(repo / "src" / ".." / ".." / "x")]:  # fmt: skip
        assert matching(tool("Read", repo, file_path=raw)).deny, raw
    assert matching(tool("Glob", repo, pattern="*", path=native(repo.parent))).deny
    assert matching(tool("Glob", repo, pattern="../**/*")).deny
    assert matching(tool("Glob", repo, pattern=native(repo.parent / "*"))).deny
    assert matching(tool("Grep", repo, pattern="KEY", path=native(repo.parent))).deny
    assert matching(tool("Grep", repo, pattern="KEY", path=native(repo / ".env"))).deny
    assert matching(tool("Grep", repo, pattern="KEY", glob=".env*")).deny


@pytest.mark.parametrize(
    "name",
    ["Agent", "Task", "WebFetch", "WebSearch", "TodoWrite", "NotebookEdit", "PowerShell", "Skill",
     "mcp__x__y", "mcp__reverseapoc__check", "LS", "BashOutput", "KillShell", "ExitPlanMode"],
)  # fmt: skip
def test_matching_denies_other_tools(repo, name):
    payload = tool(name, repo, notebook_path=native(repo / "src" / "x.ipynb"), new_source="x")
    assert matching(payload).deny


@pytest.mark.parametrize("claim", [None, "", "ufo2p", "dos/u_1", "ufo2p/U_1", "ufo2p/../x",
                                   "ufo2p/u_1/x", " ufo2p/u_000a34f0"])  # fmt: skip
def test_matching_without_a_claim_denies_writes_and_bash(repo, claim):
    env = {} if claim is None else {"REVERSEAPOC_CLAIM": claim}
    unit = _unit(repo)
    assert matching(in_repo(write(native(unit), SCAFFOLD), repo), env).deny
    assert matching(bash(f"{WRAPPER} check", repo), env).deny
    assert not matching(tool("Read", repo, file_path=native(unit)), env).deny


def test_matching_write_allowed_is_the_one_allowlist():
    claim, notes = "ufo2p/u_000a34f0", "build/driver/r/ufo2p/func_000A3980/a-1/notes.md"

    def allowed(rel: str, tracked: bool = False) -> bool:
        return hooks.matching_write_allowed(
            rel, claim=claim, notes=notes, tracked=lambda _: tracked
        )

    assert allowed("src/ufo2p/u_000a34f0.c")
    assert allowed(notes)
    assert allowed("include/new.h")
    assert not allowed("include/new.h", tracked=True)
    for rel in ["include/common.h", "include/watcom_compat.h", "src/ufo2p/u_other.c",
                "config/ufo2p/status.csv", "build/driver/r/x/notes.md", "tools/x.py"]:  # fmt: skip
        assert not allowed(rel), rel
    assert not hooks.matching_write_allowed(
        "src/ufo2p/u_000a34f0.c", claim=None, notes=None, tracked=lambda _: False
    )
    assert not hooks.matching_write_allowed(
        "build/x/notes.md", claim=claim, notes="build/x/notes.md", tracked=lambda _: False
    )


def test_main_tracks_headers_with_git():
    tracked = hooks._git_tracked(str(REPO_ROOT))
    assert tracked("include/common.h")
    assert tracked("INCLUDE/COMMON.H")
    assert not tracked("include/zz_not_a_header_of_the_repo.h")


def test_matching_entry_point_end_to_end():
    env = _Env({**os.environ, **CLAIM})
    env.pop("REVERSEAPOC_ATTEMPT_NOTES", None)

    def run(payload: dict) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, "-I", "-m", "reverseapoc.hooks", "pre-tool-use", "--layer",
             "matching"],
            input=json.dumps(payload).encode("utf-8"), capture_output=True, env=env, timeout=60,
            check=False,
        )  # fmt: skip

    denied = run(bash("ls", REPO_ROOT))
    assert denied.returncode == 0, denied.stderr
    assert json.loads(denied.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    wrapper = run(bash(f"{WRAPPER} check", REPO_ROOT))
    assert (wrapper.returncode, wrapper.stdout) == (0, b"")
    header = REPO_ROOT / "include" / "zz_hooks_test.h"
    new = run(tool("Write", REPO_ROOT, file_path=native(header), content="int x;\n"))
    assert (new.returncode, new.stdout) == (0, b""), new.stderr
    common = run(tool("Write", REPO_ROOT, file_path=native(REPO_ROOT / "include" / "common.h"),
                      content="int x;\n"))  # fmt: skip
    assert b'"deny"' in common.stdout
    assert run({"tool_name": "Write"}).returncode == 2


def _hook_entries(settings: dict) -> list[dict]:
    return settings["hooks"]["PreToolUse"]


def test_driver_settings_shape():
    project = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    driver_file = REPO_ROOT / "config" / "driver" / "claude-settings.json"
    driver = json.loads(driver_file.read_text(encoding="utf-8"))
    assert set(driver["enabledPlugins"]) == set(project["enabledPlugins"])
    assert not any(driver["enabledPlugins"].values())
    assert driver["autoMemoryEnabled"] is False
    assert driver["disableClaudeAiConnectors"] is True
    assert "mcpServers" not in driver and "disableAllHooks" not in driver
    entries = _hook_entries(driver)
    (always_entry,) = _hook_entries(project)
    assert always_entry in entries
    (matching_entry,) = [e for e in entries if e != always_entry]
    assert matching_entry["matcher"] == "*"
    (handler,) = matching_entry["hooks"]
    assert handler == {"type": "command", "command": MATCHING_COMMAND, "timeout": 120,
                       "onFailure": "block"}  # fmt: skip
    assert set(driver["hooks"]) == {"PreToolUse"}
