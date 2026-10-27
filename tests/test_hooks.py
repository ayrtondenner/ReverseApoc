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
from test_configure import INLINE_ASM_PROBES

WINDOWS = sys.platform == "win32"
# Fix round 1 C3: the project is pinned and any failure of the command itself becomes exit 2.
ALWAYS_COMMAND = (
    'uv run --frozen --project "$CLAUDE_PROJECT_DIR" python -I -m reverseapoc.hooks '
    "pre-tool-use --layer always || exit 2"
)
EDIT_TOOLS = "Edit|Write|MultiEdit|NotebookEdit"
# Review WR-02: the always handler fails closed on a slow or hung hook too, like the matching one.
ALWAYS_HANDLER = {"type": "command", "command": ALWAYS_COMMAND, "timeout": 120,
                  "onFailure": "block"}  # fmt: skip
# git's safe.directory=* for the tests that run real git against this checkout (ruling F2b): in
# the container the bind mount belongs to another user, and git refuses it ("dubious
# ownership"). Passed through the environment, as tests/test_githooks.py does; hooks.py itself
# stays fail-closed when git refuses (exit 2).
SAFE_GIT_ENV = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory",
                "GIT_CONFIG_VALUE_0": "*"}  # fmt: skip


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
        "frontend-design@anthropic-plugin-directory": True,
    }
    assert settings["extraKnownMarketplaces"] == {
        "i-have-adhd": {"source": {"source": "github", "repo": "ayghri/i-have-adhd"}}
    }
    assert set(settings) == {"enabledPlugins", "extraKnownMarketplaces", "hooks"}
    assert settings["hooks"] == {
        "PreToolUse": [
            {
                "matcher": EDIT_TOOLS,
                "hooks": [ALWAYS_HANDLER],
            }
        ]
    }


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
# 06-03's INLINE_ASM_PROBES (tests/test_configure.py), imported so the two cannot drift (fix
# round 1 M3): wcc386 keeps `_asm int 3` live in each, though a scanner that reads the comment or
# literal naively would hide it.
CONTINUATION_ASM_PROBES = INLINE_ASM_PROBES


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


def test_always_denies_an_edit_that_cannot_be_placed_exactly(repo):
    """Fix round 1 I2: in src/ and include/, an old_string that is not in the file verbatim is
    denied, so a tool that places it loosely (curly quotes for straight ones) cannot complete
    `_asm` behind the scan. Outside those trees the hook has no opinion on it."""
    path = _unit(repo, "void f(void) { _a'' int 3 }\n", "include/q.h")
    assert always(edit(native(path), "’’", "sm")).deny
    assert always(edit(native(path), "''", "sm")).deny
    assert always(edit(native(path), "not in the file", "int x;")).deny
    assert always(multi_edit(native(path), ("void", "int"), ("absent", "x"))).deny
    assert always(edit(native(repo / "src" / "missing.c"), "x", "y")).deny
    tool_file = repo / "tools" / "x.py"
    tool_file.parent.mkdir(parents=True)
    tool_file.write_text("a = 1\n", encoding="utf-8")
    assert not always(edit(native(tool_file), "not in the file", "b")).deny


def test_always_scans_an_edit_that_creates_a_file(repo):
    new = repo / "src" / "ufo2p" / "new.c"
    assert not always(edit(native(new), "", SCAFFOLD)).deny
    assert always(edit(native(new), "", "_asm int 3\n")).deny
    existing = _unit(repo)
    assert always(edit(native(existing), "", "int x;\n")).deny  # an empty old_string on a file


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
MATCHING_COMMAND = (
    'uv run --frozen --project "$CLAUDE_PROJECT_DIR" python -I -m reverseapoc.hooks '
    "pre-tool-use --layer matching || exit 2"
)
WRAPPER = "uv run --frozen reverseapoc attempt"


def matching(payload: dict, env: dict | None = None, tracked=lambda _: False) -> hooks.Decision:
    return hooks.decide(
        payload, layer="matching", env=CLAIM if env is None else env, tracked=tracked
    )


def tool(name: str, repo: Path, **tool_input) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": name, "tool_input": tool_input,
            "cwd": str(repo)}  # fmt: skip


CHECK_TIMEOUT_MS = 600_000  # the Bash tool's timeout every attempt check needs (review WR-04)


def bash(command: str, repo: Path, timeout: object = CHECK_TIMEOUT_MS) -> dict:
    """A Bash payload; `timeout` None leaves the tool's timeout out, as a session may."""
    extra = {} if timeout is None else {"timeout": timeout}
    return tool("Bash", repo, command=command, description="x", **extra)


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


PILOT_PRAGMAS = [  # fix round 1 M14(b): every #pragma, not only aux
    "#pragma on (check_stack)\n",  # changes code the way a flag does; flags are owner-only
    "#pragma off (check_stack)\n",
    "#pragma pack(1)\n",
    "#pragma warning 1 4\n",
    "  #  pragma once\n",
    "#pragma \\\n off (check_stack)\n",
    "#pragma/* x */off (check_stack)\n",
    "??=pragma off (check_stack)\n",
    "%:pragma off (check_stack)\n",  # fix round 2 N6: the digraph spelling of `#`
    "%:  pragma pack(1)\n",
    "  %: pragma once\n",
]


@pytest.mark.parametrize("text", PILOT_PRAGMAS)
def test_matching_denies_every_pragma(repo, text):
    """M14(b): during the pilot a matching session writes no #pragma of any kind in src/ or
    include/; the always layer is unchanged (it denies only a code-emitting #pragma aux)."""
    unit = _unit(repo)
    decision = matching(in_repo(write(native(unit), SCAFFOLD + text), repo))
    assert decision.deny
    assert "#pragma of any kind" in decision.reason
    header = repo / "include" / "foo.h"
    assert matching(in_repo(write(native(header), text), repo)).deny
    assert not always(write(native(unit), SCAFFOLD + text)).deny


def test_matching_allows_pragma_words_outside_code(repo):
    unit = _unit(repo)
    for text in ["/* #pragma off (check_stack) */\n", 'char *s = "#pragma once";\n',
                 "int pragma_count;\n", "/* %:pragma once */\n",
                 'char *t = "%:pragma once";\n']:  # fmt: skip
        assert not matching(in_repo(write(native(unit), SCAFFOLD + text), repo)).deny, text


def _background(command: str, repo: Path, value: object) -> dict:
    payload = bash(command, repo)
    payload["tool_input"]["run_in_background"] = value
    return payload


@pytest.mark.parametrize("value", [True, "true", 1])
def test_matching_denies_a_background_bash(repo, value):
    """M14(a): checks run in the foreground, one at a time; a background wrapper call is
    denied (the lock alone does not stop edits made while a background check runs)."""
    decision = matching(_background(f"{WRAPPER} check", repo, value))
    assert decision.deny
    assert "checks run in the foreground, one at a time" in decision.reason


def test_matching_allows_a_foreground_bash(repo):
    assert not matching(_background(f"{WRAPPER} check", repo, False)).deny
    assert not matching(bash(f"{WRAPPER} check", repo)).deny


@pytest.mark.parametrize("form", ["check", "check --sweep"])
@pytest.mark.parametrize("timeout", [None, 120_000, 599_999.5, True, "600000", float("nan")])
def test_matching_denies_a_check_without_the_long_bash_timeout(repo, form, timeout):
    """Review WR-04: the Bash tool kills a check at its 120 s default, check.lock stays behind
    and every later check of the attempt is refused; a run needs up to 580 s plus clean-up."""
    decision = matching(bash(f"{WRAPPER} {form}", repo, timeout))
    assert decision.deny
    assert "rerun it with `timeout: 600000`" in decision.reason


@pytest.mark.parametrize("timeout", [600_000, 600_000.0, 600_001])
def test_matching_allows_a_check_with_the_long_bash_timeout(repo, timeout):
    assert not matching(bash(f"{WRAPPER} check --sweep", repo, timeout)).deny
    assert hooks.CHECK_TIMEOUT_MS == CHECK_TIMEOUT_MS


@pytest.mark.parametrize("form", ["asm", "asm func_000A3980", "context"])
def test_matching_needs_no_bash_timeout_for_the_quick_forms(repo, form):
    assert not matching(bash(f"{WRAPPER} {form}", repo, None)).deny


def test_always_ignores_background_bash(repo):
    """The always layer has no opinion on Bash, background or not (M14 is matching-only)."""
    assert not always(_background("ls", repo, True)).deny


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


def test_main_tracks_headers_with_git(monkeypatch):
    for key, value in SAFE_GIT_ENV.items():
        monkeypatch.setenv(key, value)
    tracked = hooks._git_tracked(str(REPO_ROOT))
    assert tracked("include/common.h")
    assert tracked("INCLUDE/COMMON.H")
    assert not tracked("include/zz_not_a_header_of_the_repo.h")


def test_matching_entry_point_end_to_end():
    env = _Env({**os.environ, **CLAIM, **SAFE_GIT_ENV})
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


# CLI 2.1.308's built-in plugins (cc-plugin-<alias>, on by default); the key drops the
# `cc-plugin-` prefix, as two probes proved on 2026-10-25 (canary1 FAILed on all three).
CLI_BUILTIN_PLUGINS = {"agents-md@builtin", "telemetry@builtin", "plugin-authoring@builtin"}


def test_driver_settings_switch_off_the_cli_builtin_plugins():
    """canary1 (CLI 2.1.308): init listed cc-plugin-agents-md, cc-plugin-telemetry and
    cc-plugin-plugin-authoring; the short `<alias>@builtin: false` keys switch them off."""
    driver_file = REPO_ROOT / "config" / "driver" / "claude-settings.json"
    plugins = json.loads(driver_file.read_text(encoding="utf-8"))["enabledPlugins"]
    for key in sorted(CLI_BUILTIN_PLUGINS):
        assert plugins.get(key) is False, key


def test_driver_settings_shape():
    project = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    driver_file = REPO_ROOT / "config" / "driver" / "claude-settings.json"
    driver = json.loads(driver_file.read_text(encoding="utf-8"))
    assert set(driver["enabledPlugins"]) == set(project["enabledPlugins"]) | CLI_BUILTIN_PLUGINS
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


# --- Fix round 1 (review-06-12.md) ------------------------------------------------------------


def _win_volume(path: Path) -> tuple[str, str]:
    """(`\\\\?\\Volume{GUID}`, `\\\\?\\GLOBALROOT\\Device\\HarddiskVolumeN`) of `path`'s drive."""
    import ctypes

    drive = str(path)[:2]
    volume = ctypes.create_unicode_buffer(1024)
    assert ctypes.windll.kernel32.GetVolumeNameForVolumeMountPointW(drive + "\\", volume, 1024)
    device = ctypes.create_unicode_buffer(1024)
    assert ctypes.windll.kernel32.QueryDosDeviceW(drive, device, 1024)
    return volume.value.rstrip("\\"), "\\\\?\\GLOBALROOT" + device.value


PATH_FORMS = [
    "native", "posix", "rooted-no-drive", "rooted-no-drive-slash", "dot-device-slash",
    "dot-device", "qmark-device", "qmark-device-slash", "nt-object", "volume-guid", "globalroot",
    "git-bash", "trailing-dot", "data-stream", "relative",
]  # fmt: skip


def path_form(form: str, path: Path, cwd: Path) -> str:
    """`path` written in `form`. On Windows these are the forms NT opens (C1); on POSIX each
    form is a POSIX spelling of the same file (a doubled slash, `/./`, `..`), so one test
    covers both hosts (rulings R-A)."""
    posix = path.as_posix()
    if not WINDOWS:
        return {
            "native": posix, "posix": posix, "rooted-no-drive": posix,
            "rooted-no-drive-slash": "/" + posix, "dot-device-slash": "/." + posix,
            "dot-device": posix.replace("/", "/./", 1), "qmark-device": "//" + posix.lstrip("/"),
            "qmark-device-slash": "///" + posix.lstrip("/"),
            "nt-object": str(path.parent / ".." / path.parent.name / path.name),
            "volume-guid": posix, "globalroot": posix, "git-bash": posix, "trailing-dot": posix,
            "data-stream": posix, "relative": os.path.relpath(path, cwd),
        }[form]  # fmt: skip
    text = str(path)
    volume, globalroot = _win_volume(path)
    return {
        "native": text, "posix": posix, "rooted-no-drive": text[2:],
        "rooted-no-drive-slash": posix[2:], "dot-device-slash": "//./" + posix,
        "dot-device": "\\\\.\\" + text, "qmark-device": "\\\\?\\" + text,
        "qmark-device-slash": "//?/" + posix, "nt-object": "\\??\\" + text,
        "volume-guid": volume + text[2:], "globalroot": globalroot + text[2:],
        "git-bash": "/" + text[0].lower() + posix[2:], "trailing-dot": text + ".",
        "data-stream": text + "::$DATA", "relative": os.path.relpath(path, cwd),
    }[form]  # fmt: skip


@pytest.mark.parametrize("form", PATH_FORMS)
def test_always_denies_every_path_form(repo, form):
    """C1: each form of a protected path, and of a src/ file holding `_asm`, is denied."""
    for rel in ["orig/UFO2P.EXE", "config/targets.toml"]:
        raw = path_form(form, repo.joinpath(*rel.split("/")), repo)
        decision = always(write(raw, cwd=repo))
        assert decision.deny, (form, raw)
    unit = _unit(repo)
    raw = path_form(form, unit, repo)
    assert always(write(raw, "void f(void) { _asm int 3 }\n", cwd=repo)).deny, (form, raw)
    tool_file = repo / "tools" / "x.py"
    assert not always(write(path_form(form, tool_file, repo), cwd=repo)).deny, form


@pytest.mark.parametrize("form", PATH_FORMS)
def test_matching_reads_deny_every_path_form_outside_the_repo(repo, tmp_path, form):
    """C1: the matching layer's Read/Grep/Glob use the same canonicaliser, so a secret outside
    the repo is denied in every form."""
    secret = tmp_path / "home" / ".claude" / ".credentials.json"
    secret.parent.mkdir(parents=True)
    secret.write_text("{}", encoding="utf-8")
    raw = path_form(form, secret, repo)
    assert matching(tool("Read", repo, file_path=raw)).deny, (form, raw)
    home = path_form(form, secret.parent, repo)
    assert matching(tool("Grep", repo, pattern="x", path=home)).deny, (form, home)
    assert matching(tool("Glob", repo, pattern="*", path=home)).deny, (form, home)


@pytest.mark.parametrize(
    "raw",
    ["\\\\?\\Volume{00000000-0000-0000-0000-000000000000}\\x", "\\\\.\\pipe\\x",
     "\\\\.\\PhysicalDrive0", "//./pipe/x", "\\??\\Volume{00000000-0000-0000-0000-0000000}\\x",
     "Q:relative\\x"],
)  # fmt: skip
def test_unmappable_device_paths_fail_closed(repo, raw):
    """C1: a device form that cannot be mapped to a drive-letter path, or a drive-relative path
    on another drive, cannot be judged: decide raises and the entry point exits 2."""
    with pytest.raises(hooks.HookError):
        always(write(raw, cwd=repo))
    with pytest.raises(hooks.HookError):
        matching(tool("Read", repo, file_path=raw))


def test_unmappable_device_path_exits_2(repo):
    done = _run_entry(json.dumps(write("\\\\.\\pipe\\x", cwd=repo)).encode("utf-8"))
    assert (done.returncode, done.stdout) == (2, b"")


def test_always_a_planted_git_does_not_move_the_root(repo):
    """C2: a `.git` written into config/ or src/ does not make targets.toml or a unit escape;
    the path is judged against every ancestor holding `.git`."""
    for planted in ["config", "src", "src/ufo2p"]:
        marker = repo.joinpath(*planted.split("/"), ".git")
        marker.parent.mkdir(parents=True, exist_ok=True)
        assert not always(write(native(marker), "gitdir: x\n")).deny
        marker.write_text("gitdir: x\n", encoding="utf-8")
    assert always(write(native(repo / "config" / "targets.toml"))).deny
    unit = repo / "src" / "ufo2p" / "u.c"
    assert always(write(native(unit), "void f(void) { _asm int 3 }\n")).deny
    (repo / "orig" / ".git").mkdir(parents=True)
    assert always(write(native(repo / "orig" / "x"))).deny


def test_always_judges_against_the_project_root(tmp_path):
    """C2: $CLAUDE_PROJECT_DIR anchors the path even where no `.git` is found."""
    project = tmp_path / "project"
    project.mkdir()
    env = {"CLAUDE_PROJECT_DIR": native(project)}
    assert always(write(native(project / "orig" / "x")), env).deny
    assert always(write(native(project / "src" / "u.c"), "_asm int 3\n"), env).deny
    assert not always(write(native(project / "tools" / "x.py")), env).deny
    assert not always(write(native(project / "orig" / "x")), {}).deny  # no anchor at all


def test_the_project_root_defaults_to_the_repo_holding_hooks():
    root = Path(hooks.__file__).resolve().parents[2]
    assert (root / "tools" / "reverseapoc" / "hooks.py").is_file()
    assert hooks.project_roots({}) == hooks.project_roots({"CLAUDE_PROJECT_DIR": str(root)})


@pytest.mark.parametrize(
    "rel",
    ["tools/reverseapoc/hooks.py", ".claude/settings.json", "config/driver/claude-settings.json",
     "config/driver/x.json", "pyproject.toml", "uv.lock"],
)  # fmt: skip
def test_matching_denies_the_guardrail_files(repo, rel):
    """I1 (security finding 2): the always layer leaves these editable by design (D-16); the
    matching layer, deny by default (D-17), refuses them."""
    target = repo.joinpath(*rel.split("/"))
    assert matching(in_repo(write(native(target), "{}\n"), repo)).deny
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}\n", encoding="utf-8")
    assert matching(in_repo(edit(native(target), "{}", "[]"), repo)).deny
    assert not always(write(native(target), "{}\n")).deny


@pytest.mark.parametrize("pattern", ["src/**/*.{c,h}", "{.env,x}", ".[e]nv", "*[!a].c", "a]b"])
def test_matching_refuses_brace_and_class_globs(repo, pattern):
    """M2: a pattern with { } [ ] is refused rather than judged."""
    assert matching(tool("Glob", repo, pattern=pattern)).deny
    assert matching(tool("Grep", repo, pattern="x", glob=pattern)).deny


def _hook_shell() -> str:
    """The shell Claude Code runs a command hook with: bash, which on Windows is Git for
    Windows' bash (CLAUDE_CODE_GIT_BASH_PATH when set, else <Git>/bin/bash.exe next to git)."""
    import shutil

    if not WINDOWS:
        found = shutil.which("bash")
        assert found, "bash is required: Claude Code runs command hooks with it"
        return found
    configured = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")
    if configured:
        return configured
    git = shutil.which("git")
    assert git, "Git for Windows is required: its bash runs Claude Code's command hooks"
    found = [p / "bin" / "bash.exe" for p in Path(git).resolve().parents]
    bash = next((b for b in found if b.is_file()), None)
    assert bash is not None, f"no bin/bash.exe above {git}"
    return str(bash)


def _settings_commands() -> list[tuple[str, str]]:
    found = []
    for name in [".claude/settings.json", "config/driver/claude-settings.json"]:
        settings = json.loads((REPO_ROOT / name).read_text(encoding="utf-8"))
        for entry in settings["hooks"]["PreToolUse"]:
            found.extend((name, handler["command"]) for handler in entry["hooks"])
    return found


def _through_shell(command: str, payload: dict, *, cwd: Path, env: dict) -> tuple[int, bytes]:
    done = subprocess.run(
        [_hook_shell(), "-c", command], input=json.dumps(payload).encode("utf-8"),
        capture_output=True, cwd=cwd, env=_Env(env), timeout=120, check=False,
    )  # fmt: skip
    return done.returncode, done.stdout


def _session_env() -> dict:
    """The environment a hook sees outside `uv run`: no CLAUDE_PROJECT_DIR, no VIRTUAL_ENV, no
    UV_* variable and no PATH entry inside the checkout (pytest runs with the project's venv on
    PATH). UV_PROJECT_ENVIRONMENT is kept when set (ruling F2b): the container's venv lives at
    /opt/venv outside the bind mount, and without it uv would try to replace the host's .venv."""
    root = str(REPO_ROOT).casefold()
    dropped = ("CLAUDE_PROJECT_DIR", "VIRTUAL_ENV")
    kept = ("UV_PROJECT_ENVIRONMENT",)
    env = {k: v for k, v in os.environ.items()
           if k not in dropped and (k in kept or not k.startswith("UV_"))}  # fmt: skip
    keep = [d for d in env.get("PATH", "").split(os.pathsep)
            if d and not os.path.abspath(d).casefold().startswith(root)]  # fmt: skip
    return {**env, "PATH": os.pathsep.join(keep)}


def _without_uv(env: dict) -> dict:
    """`env` with every PATH entry that holds uv removed."""
    names = ("uv.exe", "uv") if WINDOWS else ("uv",)
    keep = [d for d in env.get("PATH", "").split(os.pathsep)
            if d and not any(Path(d, n).is_file() for n in names)]  # fmt: skip
    return {**env, "PATH": os.pathsep.join(keep)}


def _always_handler_text(name: str) -> str:
    """The raw text of the always handler's object in settings file `name`."""
    text = (REPO_ROOT / name).read_text(encoding="utf-8")
    start = text.rindex("{", 0, text.index("--layer always"))
    return text[start:text.index("}", start) + 1]


def test_the_always_handlers_are_byte_identical():
    commands = [c for _, c in _settings_commands() if "--layer always" in c]
    assert commands == [ALWAYS_COMMAND, ALWAYS_COMMAND]
    texts = [_always_handler_text(n) for n in [".claude/settings.json",
                                               "config/driver/claude-settings.json"]]  # fmt: skip
    assert texts[0] == texts[1]
    assert json.loads(texts[0]) == ALWAYS_HANDLER


@pytest.mark.parametrize("index", range(3))
def test_settings_commands_fail_closed_through_the_hook_shell(tmp_path, index):
    """C3: the literal command of each handler, run by the hook shell from a directory outside
    the project, denies a protected path with the project pinned and still lets a tooling path
    through; with no project to find, or with uv missing from PATH, it exits 2."""
    name, command = _settings_commands()[index]
    base = _session_env()
    env = {**base, "CLAUDE_PROJECT_DIR": str(REPO_ROOT), **CLAIM}
    protected = write(native(REPO_ROOT / "orig" / "UFO2P.EXE"), cwd=REPO_ROOT)
    allowed = (write(native(REPO_ROOT / "tools" / "zz_hooks_probe.py"), cwd=REPO_ROOT)
               if "--layer always" in command else bash(f"{WRAPPER} check", REPO_ROOT))  # fmt: skip
    code, out = _through_shell(command, protected, cwd=tmp_path, env=env)
    assert code == 0 and b'"deny"' in out, (name, code, out)
    assert _through_shell(command, allowed, cwd=tmp_path, env=env) == (0, b""), name
    assert _through_shell(command, protected, cwd=tmp_path, env=base)[0] == 2, name
    assert _through_shell(command, allowed, cwd=tmp_path, env=base)[0] == 2, name
    assert _through_shell(command, protected, cwd=tmp_path, env=_without_uv(env))[0] == 2, name


# --- 06-REVIEW CR-02: an #include names a bare header, never a path --------------------------
# A path include could pull an unscanned file (the attempt's notes.md under build/driver/, or any
# other) into the compile, carrying a #pragma or inline asm past the scan.

NOTES_INCLUDE = '#include "../../build/driver/r/ufo2p/func_000A3980/attempt-1/notes.md"\n'
PATH_INCLUDES = {
    "quoted-path": '#include "sub/x.h"\n',
    "angle-path": "#include <../build/x.h>\n",
    "dotdot": '#include "../include/common.h"\n',
    "not-h": '#include "notes.md"\n',
    "notes-md": NOTES_INCLUDE,
    "backslash": '#include "sub\\x.h"\n',
    "absolute": "#include </work/include/common.h>\n",
    "macro": "#include HEADER\n",
    "spaced": '  #  include   "../x.h"\n',
    "continued": '#include \\\n "../x.h"\n',
    "digraph": '%:include "../x.h"\n',
    "trigraph": '??=include "../x.h"\n',
    "comment-split": '#/* x */include "../x.h"\n',
}
BARE_INCLUDES = {
    "quoted": '#include "common.h"\n',
    "angle": "#include <common.h>\n",
    "trailing-comment": '#include "foo.h" /* a note */\n',
    "spaced": '  #  include  <foo_2.h>\n',
}


@pytest.mark.parametrize("name", sorted(PATH_INCLUDES))
@pytest.mark.parametrize("rel", [UNIT, "include/new.h"])
def test_matching_denies_a_path_include(repo, name, rel):
    path = _unit(repo, rel=rel)
    decision = matching(in_repo(write(native(path), SCAFFOLD + PATH_INCLUDES[name]), repo))
    assert decision.deny, name
    assert "#include" in decision.reason, decision.reason
    assert always(write(native(path), SCAFFOLD + PATH_INCLUDES[name])).deny, name


INCLUDE_PREFIX = ("reverseapoc hooks: an #include names only a bare header name (CR-02, "
                  "configure's D-12 rule): ")  # fmt: skip
# Fix round 2 ruling: <name.h> also resolves in Watcom's own H directory, and game code may need
# toolchain headers (conio.h, i86.h), so the wording names both places and restricts nothing.
INCLUDE_WORDING = ('a bare header name: "name.h" from include/, or <name.h> from include/ or '
                   "the compiler's own headers")  # fmt: skip


@pytest.mark.parametrize("layer", ["matching", "always"])
def test_an_include_denial_has_its_own_prefix(repo, layer):
    """A path include is not inline asm or a #pragma, so its denial says what rule it broke."""
    payload = in_repo(write(native(_unit(repo)), SCAFFOLD + PATH_INCLUDES["quoted-path"]), repo)
    decision = matching(payload) if layer == "matching" else always(payload)
    assert decision.deny
    assert decision.reason.startswith(INCLUDE_PREFIX), decision.reason
    assert INCLUDE_WORDING in decision.reason, decision.reason
    assert "'\"sub/x.h\"'" in decision.reason
    assert "inline asm" not in decision.reason and "#pragma" not in decision.reason
    asm = in_repo(write(native(_unit(repo)), SCAFFOLD + "#pragma once\n"), repo)
    if layer == "matching":
        assert "no inline asm and no #pragma of any kind" in matching(asm).reason


@pytest.mark.parametrize("name", sorted(BARE_INCLUDES))
@pytest.mark.parametrize("rel", [UNIT, "include/new.h"])
def test_matching_allows_a_bare_header_include(repo, name, rel):
    path = _unit(repo, rel=rel)
    assert not matching(in_repo(write(native(path), SCAFFOLD + BARE_INCLUDES[name]), repo)).deny
    assert not always(write(native(path), SCAFFOLD + BARE_INCLUDES[name])).deny


def test_include_words_outside_a_directive_are_allowed(repo):
    path = _unit(repo)
    for text in ['/* #include "../x.h" */\n', 'char *s = "#include <../x.h>";\n',
                 'int include_count;\n']:  # fmt: skip
        assert not matching(in_repo(write(native(path), SCAFFOLD + text), repo)).deny, text


def test_an_edit_that_introduces_a_path_include_is_denied(repo):
    unit = _unit(repo)
    payload = in_repo(edit(native(unit), '#include "common.h"', NOTES_INCLUDE.rstrip("\n")), repo)
    decision = matching(payload)
    assert decision.deny and "#include" in decision.reason
    assert always(edit(native(unit), '#include "common.h"', NOTES_INCLUDE.rstrip("\n"))).deny
    # completing a path out of a bare name is caught on the post-edit text
    assert matching(in_repo(edit(native(unit), '"common.h"', '"../common.h"'), repo)).deny


# --- 07-04: per-session views (D-24, P6), owner-only cflags (D-27 P3), naming state (D-19) -----

VIEW_CLAIM = "ufo2p/u_000a34f0"
ATTEMPT = ("build", "driver", "r", "ufo2p", "func_000A3980", "attempt-1")


def _attempt(repo: Path) -> Path:
    return repo.joinpath(*ATTEMPT)


def _view_path(repo: Path, claim: str = VIEW_CLAIM) -> Path:
    exe, unit = claim.split("/")
    return _attempt(repo) / "view" / "src" / exe / f"{unit}.c"


def _view_unit(repo: Path, claim: str = VIEW_CLAIM, text: str = SCAFFOLD) -> Path:
    path = _view_path(repo, claim)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def view_env(repo: Path, *, unit_file: Path | None = None, kind: str | None = None) -> dict:
    """A view-mode session's env (D-24): claim, private unit file, notes and proposals."""
    attempt = _attempt(repo)
    env = {
        "REVERSEAPOC_CLAIM": VIEW_CLAIM,
        "REVERSEAPOC_UNIT_FILE": native(unit_file or _view_path(repo)),
        "REVERSEAPOC_ATTEMPT_NOTES": native(attempt / "notes.md"),
        "REVERSEAPOC_PROPOSALS": native(attempt / "proposals.jsonl"),
    }
    if kind is not None:
        env["REVERSEAPOC_SESSION_KIND"] = kind
    return env


def test_view_unit_is_writable(repo):
    unit = _view_unit(repo)
    env = view_env(repo)
    for form in [native(unit), unit.as_posix()]:
        assert not always(write(form, SCAFFOLD), env).deny, form
        assert not matching(in_repo(write(form, SCAFFOLD), repo), env).deny, form
    change = edit(native(unit), "INCLUDE_ASM(func_00010010);", "int x;")
    assert not always(change, env).deny
    assert not matching(in_repo(change, repo), env).deny
    notes = _attempt(repo) / "notes.md"
    assert not matching(in_repo(write(native(notes), "# notes\n"), repo), env).deny


def test_view_mode_denies_src_and_others(repo):
    _view_unit(repo)
    env = view_env(repo)
    others = [_unit(repo), _view_path(repo, "ufo2p/u_other"),
              _attempt(repo) / "view" / "include" / "x.h", repo / "include" / "x.h",
              repo / "src" / "ufo2p" / "u_other.c", repo / "tools" / "x.py",
              _attempt(repo) / "x.md"]  # fmt: skip
    for target in others:
        assert matching(in_repo(write(native(target), SCAFFOLD), repo), env).deny, target


def test_view_unit_is_scanned(repo):
    unit = _view_unit(repo)
    env = view_env(repo)
    asm = edit(native(unit), "INCLUDE_ASM(func_00010010);", "void f(void) { __asm { int 3 } }")
    decision = always(asm, env)
    assert decision.deny and "no inline asm" in decision.reason, decision.reason
    assert matching(in_repo(asm, repo), env).deny
    pragma = edit(native(unit), "INCLUDE_ASM(func_00010010);", "#pragma once")
    decision = matching(in_repo(pragma, repo), env)
    assert decision.deny and "#pragma of any kind" in decision.reason, decision.reason
    assert always(write(native(unit), SCAFFOLD + "_asm int 3\n"), env).deny


def test_proposals_file_is_writable(repo):
    env = view_env(repo)
    proposals = _attempt(repo) / "proposals.jsonl"
    line = '{"kind": "rename"}\n'
    assert not always(write(native(proposals), line), env).deny
    assert not matching(in_repo(write(native(proposals), line), repo), env).deny
    for other in [_attempt(repo) / "proposal.jsonl", _attempt(repo) / "other.jsonl",
                  _attempt(repo).parent / "attempt-2" / "proposals.jsonl"]:  # fmt: skip
        assert always(write(native(other), line), env).deny, other
        assert matching(in_repo(write(native(other), line), repo), env).deny, other
