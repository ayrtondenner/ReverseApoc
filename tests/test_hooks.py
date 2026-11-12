"""The guardrail hooks (tools/reverseapoc/hooks.py, AGT-05, D-15..D-18, D-44..D-46, DI-07).

`decide` gets synthetic PreToolUse payloads for files in a scratch repository (a tmp directory
holding `.git`); the entry point runs once for real in a subprocess. A path test that needs a
platform's own path form picks it by sys.platform inside one test (rulings R-A)."""

from __future__ import annotations

import codecs
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
                "matcher": ALWAYS_TOOLS,
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
    ["asm.md", "buildx/x", "orig_notes.md", "tools/reverseapoc/asm.py", "config/cflags.txt.bak",
     "config/cflags-proposals.toml.bak", "configure.py", "tests/test_x.py", "docs/x.md",
     ".planning/x.md", "config/targets.toml.bak", "src/README.md"],
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
    """The matching layer; with no `env`, the view-mode session env of the payload's checkout
    (07-13: a session without the driver's REVERSEAPOC_UNIT_FILE writes nothing), or the bare
    claim when the payload names no cwd."""
    if env is None:
        env = view_env(Path(payload["cwd"])) if payload.get("cwd") else CLAIM
    return hooks.decide(payload, layer="matching", env=env, tracked=tracked)


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
    """07-13 (D-24): the claimed unit a session may write is its private view unit; the shared
    src/<exe>/<unit>.c is denied like every other file."""
    unit = _view_unit(repo)
    assert not matching(in_repo(write(native(unit), SCAFFOLD), repo)).deny
    assert not matching(in_repo(write(unit.as_posix(), SCAFFOLD), repo)).deny
    assert not matching(in_repo(edit(native(unit), "INCLUDE_ASM(func_00010010);", ""), repo)).deny
    marker = "INCLUDE_ASM(func_00010000);"
    assert not matching(in_repo(multi_edit(native(unit), (marker, "int x;")), repo)).deny
    for rel in [UNIT, "include/foo.h", "src/ufo2p/u_other.c", "src/tacp/u_000a34f0.c",
                "config/ufo2p/status.csv",
                "decomphub.progress.json", "progress/attempts.jsonl", "tools/x.py", "tests/x.py",
                "configure.py", "config/cflags.txt", ".claude/x", ".github/x", "src/ufo2p/x.h",
                "docs/x.md", ".planning/x.md", "src/ufo2p/u_000a34f0.c.bak"]:  # fmt: skip
        target = repo.joinpath(*rel.split("/"))
        assert matching(in_repo(write(native(target)), repo)).deny, rel
    outside = repo.parent / "elsewhere" / "src" / "ufo2p" / "u_000a34f0.c"
    assert matching(in_repo(write(native(outside), SCAFFOLD), repo)).deny


def test_matching_include_rules(repo):
    """D-19 (07-13 removed the Phase 6 header allowance): no include/ write, new or not."""
    for name in ["foo.h", "common.h", "watcom_compat.h", "COMMON.H", "sub/x.h", "x.c"]:
        target = repo / "include" / name
        assert matching(in_repo(write(native(target), "int foo(void);\n"), repo)).deny, name


def test_matching_allows_the_attempt_notes(repo):
    notes = _attempt(repo) / "notes.md"
    assert not matching(in_repo(write(native(notes), "# notes\n"), repo)).deny
    assert matching(in_repo(write(native(notes.with_name("x.md"))), repo)).deny


def test_matching_denies_every_pragma_aux(repo):
    unit = _view_unit(repo)
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
    unit = _view_unit(repo)
    decision = matching(in_repo(write(native(unit), SCAFFOLD + text), repo))
    assert decision.deny
    assert "#pragma of any kind" in decision.reason
    header = repo / "include" / "foo.h"
    assert matching(in_repo(write(native(header), text), repo)).deny
    assert not always(write(native(unit), SCAFFOLD + text), view_env(repo)).deny
    assert not always(write(native(_unit(repo)), SCAFFOLD + text)).deny


def test_matching_allows_pragma_words_outside_code(repo):
    unit = _view_unit(repo)
    for text in ["/* #pragma off (check_stack) */\n", 'char *s = "#pragma once";\n',
                 "int pragma_count;\n", "/* %:pragma once */\n",
                 'char *t = "%:pragma once";\n']:  # fmt: skip
        assert not matching(in_repo(write(native(unit), SCAFFOLD + text), repo)).deny, text


PREPROCESSOR_OPERATORS = [  # 07-19 fix round 1 S1: pasting or stringizing a banned token
    "#define P(a, b) a##b\nP(__a, sm) int 3\n",
    "#define P(a, b) a ## b\n",
    "#define P(a, b) a %:%: b\n",
    "%:define P(a, b) a %:%: b\n",
    "??=define P(a, b) a ??=??= b\n",
    "#define P(a, b) a #\\\n# b\n",
    "#define S(x) #x\n",
    "#define S(x) %:x\n",
]


@pytest.mark.parametrize("text", PREPROCESSOR_OPERATORS)
def test_matching_denies_preprocessor_operators(repo, text):
    """The token scan reads source text, so `__a##sm` would rebuild `__asm` after it; the
    matching layer refuses `#`/`##` (and `%:`/`%:%:`) operators. The always layer keeps
    accepting them: include/common.h's INCLUDE_ASM uses `##` (F16)."""
    unit = _view_unit(repo)
    decision = matching(in_repo(write(native(unit), SCAFFOLD + text), repo))
    assert decision.deny
    assert "preprocessor operator" in decision.reason
    assert not always(write(native(unit), SCAFFOLD + text), view_env(repo)).deny
    assert not always(write(native(_unit(repo)), SCAFFOLD + text)).deny


def test_matching_allows_hashes_outside_code(repo):
    unit = _view_unit(repo)
    for text in ['char *s = "a##b";\n', "/* a ## b, #x, %:%: */\n", "char c = '#';\n",
                 "  #  define VOICES 8\n", "%:define VOICES 8\n"]:  # fmt: skip
        assert not matching(in_repo(write(native(unit), SCAFFOLD + text), repo)).deny, text


MSVC_STYLE = {  # 07-19 fix round 2 S3: the other spellings of a pragma and of emitted bytes
    "pragma": ("__pragma(pack(1))\nint x;\n", "__pragma"),
    "emit": ("void f(void) { __emit 0x90; }\n", "__emit"),
}  # fmt: skip


@pytest.mark.parametrize(("text", "token"), MSVC_STYLE.values(), ids=MSVC_STYLE.keys())
def test_matching_denies_pragma_and_emit_keywords(repo, text, token):
    unit = _view_unit(repo)
    decision = matching(in_repo(write(native(unit), SCAFFOLD + text), repo))
    assert decision.deny
    assert token in decision.reason
    assert not always(write(native(_unit(repo)), SCAFFOLD + text)).deny


def test_matching_allows_pragma_and_emit_words_outside_code(repo):
    unit = _view_unit(repo)
    for text in ["/* __pragma __emit */\n", 'char *s = "__emit";\n', "int emit_count;\n",
                 "int my__pragma;\n"]:  # fmt: skip
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
    """Outside a harness worktree the always layer has no opinion on Bash, background or not
    (M14 is matching-only)."""
    assert not always(_background("ls", repo, True)).deny


def test_attempt_forms_are_the_shared_constants():
    assert hooks.ATTEMPT_PREFIX == ("uv", "run", "--frozen", "reverseapoc", "attempt")
    assert hooks.ATTEMPT_FORMS == (
        ("check",), ("check", "--sweep"), ("asm",), ("asm", "<NAME>"), ("context",),
    )  # fmt: skip
    # 07.2-02, 07.2-03 (D-26): the verbs only a matching session runs; readability keeps the five
    assert hooks.MATCHING_FORMS == (
        ("check",), ("check", "--sweep"), ("asm",), ("asm", "<NAME>"), ("context",),
        ("giveup",), ("plan",),
    )  # fmt: skip
    assert hooks.forms_for("matching") == hooks.MATCHING_FORMS
    assert hooks.forms_for("readability") == hooks.ATTEMPT_FORMS
    assert not hooks.attempt_form_matches(("giveup",))
    assert hooks.attempt_form_matches(("giveup",), hooks.MATCHING_FORMS)
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
     f"FOO=1 {WRAPPER} check", f"{WRAPPER} asm fé", f"{WRAPPER} check\r", f"{WRAPPER}", "",
     f"{WRAPPER} asm {{func_00010000,func_00010010}}", "cat src/{a,b}.c",
     f"{WRAPPER} {{check,context}}"],
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
    claim = "ufo2p/u_000a34f0"
    base = "build/driver/r/ufo2p/func_000A3980/attempt-1"
    notes, proposals = f"{base}/notes.md", f"{base}/proposals.jsonl"
    unit_file = f"{base}/view/src/ufo2p/u_000a34f0.c"

    def allowed(rel: str, tracked: bool = False) -> bool:
        return hooks.matching_write_allowed(
            rel, claim=claim, notes=notes, tracked=lambda _: tracked, unit_file=unit_file,
            proposals=proposals,
        )  # fmt: skip

    assert allowed(unit_file)
    assert allowed(notes)
    assert allowed(proposals)
    for rel in ["src/ufo2p/u_000a34f0.c", "include/new.h", "include/common.h",
                "include/watcom_compat.h", "src/ufo2p/u_other.c", "config/ufo2p/status.csv",
                "build/driver/r/x/notes.md", "tools/x.py"]:  # fmt: skip
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
    assert new.returncode == 0, new.stderr
    assert b'"deny"' in new.stdout and b"REVERSEAPOC_UNIT_FILE" in new.stdout  # 07-13: no legacy
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
    (project_entry,) = _hook_entries(project)
    # 261109-gzy: the project matcher adds Bash and PowerShell; the driver's copy keeps the edit
    # matcher, since its matching layer handles Bash and refuses PowerShell.
    assert project_entry == {"matcher": ALWAYS_TOOLS, "hooks": [ALWAYS_HANDLER]}
    (matching_entry,) = [e for e in entries if e["hooks"] != [ALWAYS_HANDLER]]
    assert [e for e in entries if e != matching_entry] == [
        {"matcher": EDIT_TOOLS, "hooks": [ALWAYS_HANDLER]}
    ]
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


def _glob_decisions(repo: Path, pattern: str) -> list[hooks.Decision]:
    """The matching layer on `pattern` as a Glob pattern and as a Grep glob."""
    return [matching(tool("Glob", repo, pattern=pattern)),
            matching(tool("Grep", repo, pattern="x", glob=pattern))]  # fmt: skip


@pytest.mark.parametrize("pattern", ["src/**/*.{c,h}", "{src,include}/**/*.h",
                                     "src/{ufo2p,tacp}/*.c", "{a,b}{c,d}.txt",
                                     "src/**/{x,y,z}.c"])  # fmt: skip
def test_matching_accepts_plain_brace_globs(repo, pattern):
    """261109-gzw: plain {a,b} alternatives, each expansion inside the repo and no .env."""
    assert not any(decision.deny for decision in _glob_decisions(repo, pattern))


_ENV = ("names a .env file",)
_LEAVES = ("can leave the repository", "not plain {a,b} alternatives")
_NOT_PLAIN = ("not plain {a,b} alternatives",)


@pytest.mark.parametrize(("pattern", "reasons"), [
    ("{.env,x}", _ENV), (".e{n,x}v", _ENV), ("src/{a,.ENV}", _ENV),
    ("{/etc,src}/*", _LEAVES), ("{~,src}/x", _LEAVES), ("{C:,src}/x", _LEAVES),
    ("{..,src}/x", _LEAVES), ("{src,a/../..}/x", _LEAVES),
    ("{a..c}", _NOT_PLAIN), ("{-..0}x", _NOT_PLAIN), ("{a,{b,c}}", _NOT_PLAIN),
    ("{a}", _NOT_PLAIN), ("{a,}", _NOT_PLAIN), ("{}", _NOT_PLAIN), ("{a,b", _NOT_PLAIN),
    ("a}b", _NOT_PLAIN), ("\\{a,b}", _NOT_PLAIN), ("src\\{a,b}", _NOT_PLAIN),
    ("{a,b}" * 7, _NOT_PLAIN),  # 128 expansions, over the cap of 64
])  # fmt: skip
def test_matching_refuses_unsafe_brace_globs(repo, pattern, reasons):
    """Every brace shape outside one level of plain alternatives, and every expansion that
    leaves the repository or names a .env file, is refused."""
    for decision in _glob_decisions(repo, pattern):
        assert decision.deny
        assert any(reason in decision.reason for reason in reasons), decision.reason


@pytest.mark.parametrize("pattern", [".[e]nv", "*[!a].c", "a]b", "{a,b}[c]"])
def test_matching_refuses_class_globs(repo, pattern):
    """M2: a character class could spell .env, so it is refused rather than judged."""
    for decision in _glob_decisions(repo, pattern):
        assert decision.deny and "character class" in decision.reason


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


# --- 261109-gzy: a worktree's shell command never spells the main checkout's absolute path ----

ALWAYS_TOOLS = EDIT_TOOLS + "|Bash|PowerShell"
SHELL_TOOLS = ("Bash", "PowerShell")
RELATIVE_WATCOM = "../../../third_party/watcom"
SPELLS_MAIN = "spells the main checkout's absolute path"
PLAN_DIR = ".planning/quick/261109-gzy-x"
RELATIVE_COMMANDS = [  # the batch briefs' sanctioned relative read-only uses (R10)
    f"REVERSEAPOC_WATCOM_DIR={RELATIVE_WATCOM} uv run pytest -q",
    f'mkdir -p "{PLAN_DIR}" && cp "../../../{PLAN_DIR}/PLAN.md" "{PLAN_DIR}/PLAN.md"',
    "cat ../../../.planning/quick-batches/261109-gzs/RULINGS.md",
    f"$env:REVERSEAPOC_WATCOM_DIR = '{RELATIVE_WATCOM}'",
]


@pytest.fixture
def worktree(repo: Path) -> Path:
    """A harness worktree of the scratch checkout: repo/.claude/worktrees/agent-x, `.git` file."""
    root = repo / ".claude" / "worktrees" / "agent-x"
    root.mkdir(parents=True)
    (root / ".git").write_text("gitdir: ../../../.git/worktrees/agent-x\n", encoding="utf-8")
    return root


def shell(name: str, command: str, cwd: Path) -> dict:
    """A Bash or PowerShell payload."""
    return tool(name, cwd, command=command, description="x")


def watcom_command(name: str, raw: str) -> str:
    """The Watcom path set the way each shell spells it."""
    if name == "Bash":
        return f"REVERSEAPOC_WATCOM_DIR={raw} uv run pytest -q"
    return f"$env:REVERSEAPOC_WATCOM_DIR = '{raw}'; uv run pytest -q"


def main_watcom(repo: Path) -> str:
    return native(repo / "third_party" / "watcom")


@pytest.mark.parametrize("name", SHELL_TOOLS)
@pytest.mark.parametrize("form", PATH_FORMS)
def test_worktree_command_spelling_the_main_checkout_is_denied(repo, worktree, name, form):
    """R6: every drive, slash, device and case spelling of the main checkout is denied; only
    the relative one passes."""
    raw = path_form(form, repo / "third_party" / "watcom", worktree)
    decision = always(shell(name, watcom_command(name, raw), worktree))
    if form == "relative":
        assert not decision.deny, raw
        return
    assert decision.deny and SPELLS_MAIN in decision.reason, (form, raw)
    text = main_watcom(repo)
    for variant in (text.upper(), text.swapcase(), text.replace("\\", "\\\\")):
        assert always(shell(name, watcom_command(name, variant), worktree)).deny, variant


@pytest.mark.parametrize("name", SHELL_TOOLS)
def test_worktree_command_allows_its_own_worktree(repo, worktree, name):
    """R7: the worktree's own absolute path, in any form, is not the main checkout's."""
    script = worktree / "tools" / "x.py"
    commands = [f'cd "{native(worktree)}" && uv run pytest -q', f"uv run python {native(script)}",
                f"uv run python {script.as_posix()}"]  # fmt: skip
    if WINDOWS:
        posix = worktree.as_posix()
        commands.append(f"cd /{posix[0].lower()}{posix[2:]} && uv run pytest -q")
    for command in commands:
        assert not always(shell(name, command, worktree)).deny, command
    below = worktree / "tools"
    below.mkdir()
    assert always(shell(name, watcom_command(name, main_watcom(repo)), below)).deny


@pytest.mark.parametrize("name", SHELL_TOOLS)
@pytest.mark.parametrize("other", ["agent-y", "agent-x2", "agent-x.bak", ""])
def test_worktree_command_denies_other_worktrees(repo, worktree, name, other):
    """R8: another worktree, or the worktrees directory itself, is the main checkout's path."""
    target = repo / ".claude" / "worktrees" / other
    decision = always(shell(name, f'ls "{native(target)}"', worktree))
    assert decision.deny and SPELLS_MAIN in decision.reason, target


@pytest.mark.parametrize("name", SHELL_TOOLS)
@pytest.mark.parametrize("sibling", ["repo-old", "repo2", "repo_x"])
def test_worktree_command_allows_sibling_names(tmp_path, worktree, name, sibling):
    """R9: a directory beside the checkout whose name only starts with the checkout's."""
    raw = native(tmp_path / sibling / "third_party" / "watcom")
    assert not always(shell(name, watcom_command(name, raw), worktree)).deny, raw


@pytest.mark.parametrize("name", SHELL_TOOLS)
@pytest.mark.parametrize("command", RELATIVE_COMMANDS)
def test_worktree_command_allows_the_relative_forms(worktree, name, command):
    """R10: the briefs' relative `../../../` uses stay allowed (the hook resolves no `..`)."""
    assert not always(shell(name, command, worktree)).deny


@pytest.mark.parametrize("name", SHELL_TOOLS)
def test_worktree_command_main_session_has_no_opinion(tmp_path, repo, name):
    """R4: outside a worktree (the main session, a driver session, anywhere else) a shell call
    gets no opinion, decided before its tool_input is read."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (repo / "tools").mkdir()
    command = watcom_command(name, main_watcom(repo))
    for cwd in (repo, repo / "tools", elsewhere):
        assert not always(shell(name, command, cwd)).deny, cwd
    for tool_input in (None, "x", {"command": 3}):
        assert not always({**shell(name, "ls", repo), "tool_input": tool_input}).deny


@pytest.mark.parametrize("name", SHELL_TOOLS)
def test_worktree_command_fails_closed(worktree, name):
    """R3: a cwd that cannot be placed; R5: a worktree payload with no command string."""
    payload = shell(name, "ls", worktree)
    cwds = [3, "", "x", *(["\\\\.\\pipe\\x"] if WINDOWS else [])]
    for cwd in cwds:
        with pytest.raises(hooks.HookError):
            always({**payload, "cwd": cwd})
    with pytest.raises(hooks.HookError):
        always({key: value for key, value in payload.items() if key != "cwd"})
    for tool_input in (None, {}, {"command": 3}):
        with pytest.raises(hooks.HookError):
            always({**payload, "tool_input": tool_input})


@pytest.mark.parametrize("name", SHELL_TOOLS)
def test_worktree_command_reason(repo, worktree, name):
    decision = always(shell(name, f'cd "{native(repo)}"', worktree))
    assert decision.reason.startswith("reverseapoc hooks: ")
    for part in (name, "agent-x", SPELLS_MAIN, RELATIVE_WATCOM, "261109-gzy"):
        assert part in decision.reason, part


def test_worktree_command_matching_layer_unchanged(repo, worktree):
    """R16: the matching layer's Bash rule (D-44) decides before the always layer could."""
    for form in hooks.ATTEMPT_FORMS:
        args = " ".join("func_000A3980" if a == hooks.ATTEMPT_NAME_SLOT else a for a in form)
        assert not always(bash(f"{WRAPPER} {args}", repo)).deny, form
    decision = matching(bash(f'cd "{native(repo)}"', worktree))
    assert decision.deny and "runs only the attempt wrapper" in decision.reason
    assert SPELLS_MAIN not in decision.reason
    assert not matching(bash(f"{WRAPPER} check", repo)).deny


def test_worktree_command_entry_point_end_to_end(repo, worktree):
    def run(payload: dict) -> subprocess.CompletedProcess[bytes]:
        return _run_entry(json.dumps(payload).encode("utf-8"))

    denied = run(bash(watcom_command("Bash", main_watcom(repo)), worktree))
    assert denied.returncode == 0, denied.stderr
    specific = json.loads(denied.stdout)["hookSpecificOutput"]
    assert specific["permissionDecision"] == "deny"
    assert SPELLS_MAIN in specific["permissionDecisionReason"]
    relative = run(bash(watcom_command("Bash", RELATIVE_WATCOM), worktree))
    assert (relative.returncode, relative.stdout) == (0, b""), relative.stderr
    main = run(bash(watcom_command("Bash", main_watcom(repo)), repo))
    assert (main.returncode, main.stdout) == (0, b""), main.stderr
    no_cwd = {k: v for k, v in bash("ls", worktree).items() if k != "cwd"}
    assert run(no_cwd).returncode == 2


# R11-R14: the script files a worktree command names are read too (the 261107-qk9 incident).
SCRIPT_FORMS = {
    "python": ("Bash", "uv run python {w}", "x.py"),
    "bash": ("Bash", "bash {w}", "x.sh"),
    "node": ("Bash", "node {w}", "x.mjs"),
    "powershell": ("PowerShell", "& {w}", "x.ps1"),
}


def script_denial(decision: hooks.Decision, word: str, name: str = "Bash") -> bool:
    return decision.deny and f"the script {word} that a {name} command" in decision.reason


def ps_word(file: str) -> str:
    """A PowerShell call names a script in the worktree with a leading .\\ (./ on POSIX)."""
    return (".\\" if WINDOWS else "./") + file


def refuse_open(monkeypatch, script: Path) -> None:
    """Path.open raises PermissionError for `script` only and delegates every other path."""
    real_open = Path.open

    def guarded(self, *args, **kwargs):
        if Path(self) == script:
            raise PermissionError(13, "refused by the test", str(self))
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)


@pytest.mark.parametrize(("name", "template", "file"), SCRIPT_FORMS.values(),
                         ids=SCRIPT_FORMS.keys())  # fmt: skip
def test_worktree_command_reads_the_scripts_it_runs(repo, worktree, name, template, file):
    """R11, R12: the script a command runs is denied when it spells the main checkout, by its
    relative name or by its absolute path inside the worktree."""
    script = worktree / file
    word = ps_word(file) if name == "PowerShell" else file
    for named, written in ((word, word), (native(script), f'"{native(script)}"')):
        command = template.format(w=written)
        script.write_text(f'WATCOM = "{main_watcom(repo)}"\n', encoding="utf-8")
        decision = always(shell(name, command, worktree))
        assert script_denial(decision, named, name) and SPELLS_MAIN in decision.reason, command
        script.write_text(f'WATCOM = "{RELATIVE_WATCOM}"\n', encoding="utf-8")
        assert not always(shell(name, command, worktree)).deny, command


def test_worktree_command_reads_scripts_outside_the_checkout(tmp_path, repo, worktree):
    """R11: a script in the scratchpad or temp, named by its absolute path, is read too."""
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    script = scratch / "x.py"
    script.write_text(f'WATCOM = "{main_watcom(repo)}"\n', encoding="utf-8")
    decision = always(shell("Bash", f'uv run python "{native(script)}"', worktree))
    assert script_denial(decision, native(script))


def test_worktree_command_reads_escaped_and_utf16_scripts(repo, worktree):
    """R11: a string literal's doubled backslashes, and UTF-16 text with a BOM."""
    script = worktree / "x.py"
    escaped = main_watcom(repo).replace("\\", "\\\\")
    script.write_text(f'WATCOM = "{escaped}"\n', encoding="utf-8")
    assert script_denial(always(shell("Bash", "uv run python x.py", worktree)), "x.py")
    script.write_bytes(f'WATCOM = "{main_watcom(repo)}"\n'.encode("utf-16"))
    assert script_denial(always(shell("Bash", "uv run python x.py", worktree)), "x.py")


def test_worktree_command_skips_missing_scripts(worktree):
    """R12: a script not written yet, or a directory with a script suffix, says nothing."""
    (worktree / "d.py").mkdir()
    for command in ("uv run python not_yet.py", "uv run python d.py"):
        assert not always(shell("Bash", command, worktree)).deny, command


def test_worktree_command_refuses_a_script_over_the_cap(worktree, monkeypatch):
    """R13: a script over _SCRIPT_CAP bytes cannot be scanned, so it is denied."""
    monkeypatch.setattr(hooks, "_SCRIPT_CAP", 64)
    script = worktree / "x.py"
    script.write_bytes(b"#" * 65)
    decision = always(shell("Bash", "uv run python x.py", worktree))
    assert script_denial(decision, "x.py") and "cannot be scanned" in decision.reason
    script.write_bytes(b"#" * 64)
    assert not always(shell("Bash", "uv run python x.py", worktree)).deny


def test_worktree_command_fails_closed_on_unreadable_scripts(worktree, monkeypatch):
    """R14: a script that exists but cannot be read or decoded, or cannot be placed, blocks."""
    script = worktree / "x.py"
    script.write_text("x = 1\n", encoding="utf-8")
    refuse_open(monkeypatch, script)
    with pytest.raises(hooks.HookError, match="cannot be read"):
        always(shell("Bash", "uv run python x.py", worktree))
    monkeypatch.undo()
    shell_script = worktree / "x.sh"
    shell_script.write_bytes(codecs.BOM_UTF16_LE + b"abc")
    with pytest.raises(hooks.HookError, match="cannot be read"):
        always(shell("Bash", "bash x.sh", worktree))
    if WINDOWS:
        with pytest.raises(hooks.HookError):
            always(shell("Bash", "uv run python Q:x.py", worktree))


def test_worktree_command_main_session_reads_no_script(repo, monkeypatch):
    """R4: outside a worktree no script is read at all."""
    script = repo / "x.py"
    script.write_text(f'WATCOM = "{main_watcom(repo)}"\n', encoding="utf-8")
    assert not always(shell("Bash", "uv run python x.py", repo)).deny
    refuse_open(monkeypatch, script)
    assert not always(shell("Bash", "uv run python x.py", repo)).deny


def test_worktree_command_entry_point_reads_scripts(repo, worktree):
    (worktree / "x.py").write_text(f'WATCOM = "{main_watcom(repo)}"\n', encoding="utf-8")
    done = _run_entry(json.dumps(bash("uv run python x.py", worktree)).encode("utf-8"))
    assert done.returncode == 0, done.stderr
    reason = json.loads(done.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "the script x.py that a Bash command" in reason and SPELLS_MAIN in reason


# Security review of 261109-gzy (coordinator ruling): expansion, encodings, written scripts.


def test_worktree_command_reads_every_tool_script():
    """No script under tools/ or tests/, nor configure.py, is locked out from a worktree: each
    reads as one text that does not spell a main checkout (hooks.py itself included)."""
    pairs = [(native(REPO_ROOT.parent / "zz-no-such-main"), "agent-x")]
    scripts = [*REPO_ROOT.glob("tools/**/*.py"), *REPO_ROOT.glob("tests/**/*.py"),
               REPO_ROOT / "configure.py"]  # fmt: skip
    assert REPO_ROOT / "tools" / "reverseapoc" / "hooks.py" in scripts
    for script in scripts:
        path = hooks.canonical(native(script))
        assert hooks._script_denial(script.name, path, "Bash", pairs) == "", script


@pytest.mark.parametrize(("name", "command"), [
    ("Bash", "uv run python $HOME/x.py"), ("Bash", 'uv run python "${TMP}/x.py"'),
    ("Bash", "uv run python ~/x.py"), ("Bash", "bash `pwd`/x.sh"),
    ("Bash", "node tests/*.mjs"), ("Bash", "uv run python %TEMP%/x.py"),
    ("Bash", "X=$PWD/x.py uv run pytest -q"),
    ("PowerShell", "& $env:TEMP\\x.ps1"), ("PowerShell", '& "$PWD\\x.ps1"'),
    ("PowerShell", "& ~\\x.ps1"), ("PowerShell", "& .\\my` dir\\x.ps1"),
])  # fmt: skip
def test_worktree_command_denies_scripts_named_through_expansion(worktree, name, command):
    """Ruling 1: a script word the shell would expand cannot be read as written, so it is
    denied rather than skipped."""
    decision = always(shell(name, command, worktree))
    assert decision.deny and "needs shell expansion" in decision.reason, command


def test_worktree_command_resolves_quotes_and_escapes_literally(repo, worktree):
    """Ruling 1: Bash quotes and backslash escapes, and PowerShell quotes, resolve to a literal
    path, which is read."""
    folder = worktree / "my dir"
    folder.mkdir()
    for file in ("x.py", "x.ps1"):
        (folder / file).write_text(f'WATCOM = "{main_watcom(repo)}"\n', encoding="utf-8")
    cases = [("Bash", 'uv run python "my dir/x.py"', "my dir/x.py"),
             ("Bash", "uv run python my\\ dir/x.py", "my dir/x.py"),
             ("Bash", "uv run python 'my dir'/x.py", "my dir/x.py"),
             ("PowerShell", f"& '{ps_word('my dir/x.ps1')}'", ps_word("my dir/x.ps1")),
             ("PowerShell", f'& "{ps_word("my dir/x.ps1")}"', ps_word("my dir/x.ps1"))]  # fmt: skip
    for name, command, word in cases:
        assert script_denial(always(shell(name, command, worktree)), word, name), command


def test_worktree_command_bash_split_fails_closed(worktree):
    """Ruling 1: a Bash command that cannot be split blocks; a here-document body with an
    apostrophe is data, not words."""
    with pytest.raises(hooks.HookError, match="cannot be split"):
        always(shell("Bash", 'uv run python "x.py', worktree))
    heredoc = "cat > notes.txt <<'EOF'\ndon't\nEOF\nls"
    assert not always(shell("Bash", heredoc, worktree)).deny


@pytest.mark.parametrize("file", ["x.sh", "x.ps1"])
def test_worktree_command_decodes_utf32_and_refuses_mixed_text(repo, worktree, file):
    """Ruling 2: UTF-32 after its BOM (checked before UTF-16); a NUL, UTF-16 without a BOM or a
    BOM inside the text is not one text, so it is denied; a leading UTF-8 BOM is dropped."""
    script = worktree / file
    word = file if file == "x.sh" else ps_word(file)
    name, command = ("Bash", f"bash {word}") if file == "x.sh" else ("PowerShell", f"& {word}")
    text = f'WATCOM = "{main_watcom(repo)}"\n'
    script.write_bytes(text.encode("utf-32"))
    decision = always(shell(name, command, worktree))
    assert script_denial(decision, word, name) and SPELLS_MAIN in decision.reason
    for data in (b"a\0b\n", "x\n".encode("utf-16-le"), "a\ufeffb\n".encode("utf-8")):
        script.write_bytes(data)
        decision = always(shell(name, command, worktree))
        assert script_denial(decision, word, name) and "not one text" in decision.reason, data
    script.write_bytes(f"\ufeffWATCOM = '{RELATIVE_WATCOM}'\n".encode())
    assert not always(shell(name, command, worktree)).deny


def test_worktree_command_reads_python_in_its_source_encoding(repo, worktree):
    """Ruling 3: a .py file is decoded as Python decodes it (its coding cookie), and one whose
    encoding Python cannot detect is denied."""
    script = worktree / "x.py"
    # Backslashes on every platform: UTF-7 escapes "\" but writes "/" and letters as-is,
    # so only the backslash form makes a UTF-8 reading miss the path on Linux too
    # (the hook folds "\" to "/").
    backslashed = main_watcom(repo).replace("/", chr(92))
    body = f'WATCOM = "{backslashed}"\n'.encode("utf-7")
    needle = hooks._needle(hooks.canonical(native(repo)))
    assert needle not in hooks._normalised(body.decode("utf-8"))  # UTF-8 would miss it
    script.write_bytes(b"# coding: utf-7\n" + body)
    decision = always(shell("Bash", "uv run python x.py", worktree))
    assert script_denial(decision, "x.py") and SPELLS_MAIN in decision.reason
    script.write_bytes(b"# coding: no-such-codec\nx = 1\n")
    decision = always(shell("Bash", "uv run python x.py", worktree))
    assert script_denial(decision, "x.py") and "no source encoding" in decision.reason


WRITTEN_AND_RUN = [
    ("Bash", 'echo "$X" > x.py && uv run python x.py'), ("Bash", "curl -s u >> x.sh; bash x.sh"),
    ("Bash", "cp ../y.py x.py && uv run python ./x.py"),
    ("Bash", "printf x | tee x.mjs\nnode x.mjs"),
    ("PowerShell", "Set-Content x.ps1 $v; & {w}"),
    ("PowerShell", "$v | Out-File -FilePath x.ps1; & {w}"), ("PowerShell", "$v > x.ps1; & {w}"),
]  # fmt: skip


@pytest.mark.parametrize(("name", "command"), WRITTEN_AND_RUN)
@pytest.mark.parametrize("exists", [False, True])
def test_worktree_command_denies_a_script_it_writes_and_runs(worktree, name, command, exists):
    """Ruling 4: a script the same command writes (a redirection, tee, cp, Out-File...) and
    names again would run unscanned, whether or not an older copy exists."""
    command = command.format(w=ps_word("x.ps1"))
    if exists:
        for file in ("x.py", "x.sh", "x.mjs", "x.ps1"):
            (worktree / file).write_text(f"W = '{RELATIVE_WATCOM}'\n", encoding="utf-8")
    decision = always(shell(name, command, worktree))
    assert decision.deny and "the same command writes it" in decision.reason, command


@pytest.mark.parametrize("command", ["uv run python x.py > out.txt", "cp a.py b.py",
                                     "tee x.sh < /dev/null"])  # fmt: skip
def test_worktree_command_allows_a_write_it_does_not_run(worktree, command):
    """Ruling 4: a missing script that is only written, or only run, still gets no opinion."""
    assert not always(shell("Bash", command, worktree)).deny, command


# Second security review of 261109-gzy (coordinator ruling 2): fail closed, no parser cleverness.


@pytest.mark.parametrize(("name", "command"), [
    ("Bash", "cat > notes.txt <<'EOF'\n{main}\nEOF"), ("Bash", "ls # {main}"),
    ("Bash", 'uv run python -c "print(\'{main}\')"'), ("Bash", "echo '{main}'\"x\""),
    ("PowerShell", "@'\n{main}\n'@ | Out-File notes.txt"), ("PowerShell", "<# {main} #> ls"),
])  # fmt: skip
def test_worktree_command_raw_text_check_is_independent(repo, worktree, name, command):
    """Ruling 2 item 1: the whole command text is scanned as written, before any tokenizing,
    so a heredoc body, a comment or a -c string still denies; so does a script's whole text."""
    decision = always(shell(name, command.format(main=main_watcom(repo)), worktree))
    assert decision.deny and f"a {name} command from the harness worktree" in decision.reason
    (worktree / "x.sh").write_text(f"# {main_watcom(repo)}\necho ok\n", encoding="utf-8")
    assert script_denial(always(shell("Bash", "bash x.sh", worktree)), "x.sh")


def test_worktree_command_bash_has_no_comments(worktree):
    """Ruling 2 item 2: `#` starts no comment for the split, so nothing after it is skipped,
    and an apostrophe after it breaks the split, which blocks."""
    decision = always(shell("Bash", "echo ok # && bash $HOME/x.sh", worktree))
    assert decision.deny and "needs shell expansion" in decision.reason
    with pytest.raises(hooks.HookError, match="cannot be split"):
        always(shell("Bash", "ls # it's", worktree))


INDIRECTION = [
    ("Bash", "cat > x.py <<'EOF'\nprint(1)\nEOF"), ("Bash", "bash <<EOF\nbash x.sh\nEOF"),
    ("Bash", "uv run python <<< 'import x' x.py"), ("Bash", "cd tools && uv run python x.py"),
    ("Bash", "pushd tools; bash x.sh"), ("Bash", "bash -c 'node x.mjs'"),
    ("Bash", 'eval "uv run python x.py"'), ("Bash", "uv run python \\\n  x.py"),
    ("PowerShell", "Set-Location tools; & ./x.ps1"), ("PowerShell", "Push-Location t; & ./x.ps1"),
    ("PowerShell", "pwsh -Command ./x.ps1"), ("PowerShell", "pwsh -EncodedCommand AAAA x.ps1"),
    ("PowerShell", "Invoke-Expression './x.ps1'"), ("PowerShell", "iex './x.ps1'"),
]  # fmt: skip


@pytest.mark.parametrize(("name", "command"), INDIRECTION)
def test_worktree_command_denies_scripts_beside_indirection(worktree, name, command):
    """Ruling 2 item 3: a command that names a script and also holds a heredoc marker, a
    directory change, inline code or eval, or a backslash-newline is denied: the hook cannot
    tell which file runs."""
    decision = always(shell(name, command, worktree))
    assert decision.deny and "cannot tell which file runs" in decision.reason, command


@pytest.mark.parametrize(("name", "command"), [
    ("Bash", "uv run python x.py > build/log.txt"), ("Bash", "bash x.sh >> /tmp/x/log.txt 2>&1"),
    ("PowerShell", "& ./x.ps1 > build/log.txt"), ("Bash", "cd tools && ls"),
    ("Bash", "cat > notes.txt <<'EOF'\nx\nEOF"),
])  # fmt: skip
def test_worktree_command_allows_plain_output_redirection(worktree, name, command):
    """Ruling 2 item 3: a script's stdout redirected to a file stays allowed, and a heredoc or a
    cd with no script named says nothing."""
    # 261112-fdw: `bash x.sh` needs x.sh in the cwd (else bash searches PATH for it).
    (worktree / "x.sh").write_text(f"W = '{RELATIVE_WATCOM}'\n", encoding="utf-8")
    assert not always(shell(name, command, worktree)).deny, command


def test_worktree_command_expansion_covers_braces_and_continuations(worktree):
    """Ruling 2 item 4: a brace or a backslash-newline in a script word is an expansion."""
    for word in ("x{1,2}.sh", "x\\\n.sh"):
        assert hooks._EXPANSION.search(word), word
    decision = always(shell("Bash", "bash x{1,2}.sh", worktree))
    assert decision.deny and "needs shell expansion" in decision.reason


# --- 261112-fdw: a script-naming worktree call passes only when every command has a listed shape

CANNOT_TELL = "cannot tell which file runs"
GSD_TOOLS = ".claude/gsd-core/bin/gsd-tools.cjs"
CLEAN_FILES = ("x.py", "a.py", "x.sh", "a.sh", "x.mjs", "x.ps1", "a.ps1", "tools/x.py",
               "tests/test_hooks.py", "tools/reverseapoc/hooks.py")  # fmt: skip


def clean_scripts(worktree: Path) -> None:
    """Clean scripts at every name the allowlist cases use, so their reads really happen."""
    for file in CLEAN_FILES:
        path = worktree / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"W = '{RELATIVE_WATCOM}'\n", encoding="utf-8")


ALLOWLIST_DENIED = [
    ("Bash", "node -e \"require('./x.js')\""), ("Bash", "node --eval \"require('./x.js')\""),
    ("Bash", "uv run --directory tools python x.py"),
    ("Bash", "uv run --project tools python x.py"),
    ("Bash", "env -C tools bash x.sh"), ("Bash", 'env -"C" tools bash x.sh'),
    ("Bash", "git -C tools add x.py"), ("Bash", 'c""d tools && uv run python x.py'),
    ("Bash", "'cd' tools && bash x.sh"), ("Bash", "\\cd tools; bash x.sh"),
    ("Bash", 'e\\val "bash x.sh"'), ("Bash", "bash -\"c\" 'node x.mjs'"),
    ("Bash", "PATH=. git add x.py"), ("Bash", "./git add x.py"), ("Bash", "bash a=b.sh"),
    ("Bash", "cat x.py | bash"), ("Bash", "bash not_yet.sh"), ("Bash", "x.sh"),
    ("Bash", '>log c""d tools; bash x.sh'),
    ("PowerShell", "sl tools; & ./x.ps1"), ("PowerShell", "chdir tools; & ./x.ps1"),
    ("PowerShell", "pwsh -e AAAA x.ps1"), ("PowerShell", "pwsh -ec AAAA x.ps1"),
    ("PowerShell", "pwsh -enc AAAA x.ps1"),
    ("PowerShell", "pwsh -WorkingDirectory tools -File x.ps1"),
    ("PowerShell", "Start-Process pwsh -WorkingDirectory tools -ArgumentList x.ps1"),
    ("PowerShell", "& 'cd' tools; & ./x.ps1"), ("PowerShell", "c`d tools; & ./x.ps1"),
    ("PowerShell", "Set-Loc`ation tools; & ./x.ps1"), ("PowerShell", "i`ex './x.ps1'"),
    ("PowerShell", "& x.ps1"), ("PowerShell", "$env:PATH = '.'; git add x.py"),
]  # fmt: skip


@pytest.mark.parametrize(("name", "command"), ALLOWLIST_DENIED)
def test_worktree_command_allowlist_denies_unlisted_commands(worktree, name, command):
    """261112-fdw: a directory change, inline code, a working-directory flag, a quoted or escaped
    keyword, a steering variable, a path-qualified program, a bare script name or a bash with no
    readable script is outside the allowlist, so the hook cannot tell which file runs."""
    clean_scripts(worktree)
    decision = always(shell(name, command, worktree))
    assert decision.deny and CANNOT_TELL in decision.reason, command


# This plan's three verify lines, verbatim but for Task 3's grep word (so this file never holds it).
TODO_DONE = ".planning/todos/completed/worktree-hook-residual-bypasses.md"
TWO_FILES = "tools/reverseapoc/hooks.py tests/test_hooks.py"
VERIFY_LINES = [
    f"uv run pytest -q tests/test_hooks.py -k worktree_command && uv run ruff check {TWO_FILES} && "
    "test \"$(grep -v '^\\s*#' tools/reverseapoc/hooks.py | grep -ciE 'push[d]|set-locatio[n]')\""
    " = 0 && grep -q '261112-fdw' tools/reverseapoc/hooks.py",
    f"uv run pytest -q tests/test_hooks.py -k worktree_command && uv run ruff check {TWO_FILES} && "
    "test \"$(grep 'def test_worktree_command' tests/test_hooks.py | wc -l)\" -ge 40",
    f"grep -q '261112-fdw' docs/workflow.md && test -f {TODO_DONE} && "
    "test ! -e .planning/todos/pending/worktree-hook-residual-bypasses.md && "
    f"grep -q '^## Result' {TODO_DONE} && ! git grep -q -i zz-no-such-word -- {TWO_FILES} "
    'docs/workflow.md && git diff --exit-code "$(git merge-base HEAD main)" -- '
    ".claude/settings.json config/driver/claude-settings.json && uv run ruff check .",
]
ORDINARY = [
    ("Bash", "uv run python x.py"), ("Bash", "uv run --frozen python x.py"),
    ("Bash", "python x.py"), ("Bash", "bash x.sh"), ("Bash", "node x.mjs"), ("Bash", "./x.sh"),
    ("Bash", "uv run pytest -q tests/test_hooks.py -k worktree"),
    ("Bash", f"REVERSEAPOC_WATCOM_DIR={RELATIVE_WATCOM} uv run pytest -q tests/test_hooks.py"),
    ("Bash", f"REVERSEAPOC_WATCOM_DIR={RELATIVE_WATCOM} uv run python x.py"),
    ("Bash", f"uv run ruff check {TWO_FILES}"),
    ("Bash", f'git add {TWO_FILES} && git commit -m "fix: hooks.py"'),
    ("Bash", "git diff tools/reverseapoc/hooks.py"),
    ("Bash", "git log --oneline -- tools/reverseapoc/hooks.py"),
    ("Bash", "cat tools/x.py | head -20"), ("Bash", "wc -l tools/x.py"),
    ("Bash", "grep -n def tools/x.py"),
    ("Bash", "uv run pytest -q tests/test_hooks.py 2>&1 | tail -5"),
    ("Bash", "mkdir -p .planning/quick/q && "
             "cp ../../../.planning/quick/q/x.py .planning/quick/q/x.py"),
    ("Bash", "cat ../../../tools/reverseapoc/hooks.py"),
    ("PowerShell", "& ./x.ps1"), ("PowerShell", "& ./x.ps1 > build/log.txt"),
    ("PowerShell", "uv run python x.py"),
    ("PowerShell", "uv run pytest -q " + ("tests\\" if WINDOWS else "tests/") + "test_hooks.py"),
    ("PowerShell", f"$env:REVERSEAPOC_WATCOM_DIR = '{RELATIVE_WATCOM}'; "
                   "uv run pytest -q tests/test_hooks.py"),
    ("PowerShell", 'git add tools/reverseapoc/hooks.py; git commit -m "fix hooks.py"'),
    ("PowerShell", "Get-Content tools/x.py | Select-Object -First 20"),
    ("PowerShell", "uv run pytest -q tests/test_hooks.py | Select-String passed"),
    ("Bash", 'test "$(grep -c X tools/reverseapoc/hooks.py)" -ge 1'),
    ("Bash", "git merge-base HEAD main"),
    ("Bash", "git merge-base HEAD main && git diff --stat HEAD -- tools/reverseapoc/hooks.py"),
    ("Bash", "git grep -n foo -- tools/x.py"),
    ("Bash", "git rev-parse --show-toplevel && git ls-files tools/reverseapoc/hooks.py"),
    ("Bash", "git branch --show-current && git add x.py"),
    ("Bash", "git branch --list 'worktree-*' && git add x.py"),
    ("Bash", "git worktree list && git add x.py"), ("Bash", "git stash list && git add x.py"),
    ("Bash", "git show-ref --heads && git check-ignore x.py"),
    ("Bash", "git diff --stat tools/x.py || true"),
    ("Bash", "git diff --no-ext-diff x.py"), ("Bash", "git log --no-textconv -p -- x.py"),
    ("Bash", "uv run reverseapoc causes --json build/driver/r"),
    ("Bash", "uv run reverseapoc causes --json build/driver/r && "
             "git diff tools/reverseapoc/causes.py"),
    ("Bash", f"node {GSD_TOOLS} query frontmatter.get .planning/quick/x/y-PLAN.md"),
    ("Bash", f"INIT=$(node {GSD_TOOLS} query init.quick)"),
    ("Bash", "X=1; uv run python x.py"),
    ("Bash", "TMPDIR=build/tmp uv run pytest -q tests/test_hooks.py"),
    ("Bash", 'N=$(grep -c def tools/x.py); test "$N" -ge 1'),
    ("Bash", "test -f tools/x.py && [ -f x.sh ]"), ("Bash", "diff tools/x.py x.py"),
    ("Bash", "find tools -name x.py"), ("Bash", "grep -n def tools/x.py | sort"),
    ("Bash", "sed -n 1,80p tools/x.py"), ("Bash", "sed -n '1,20p;40,60p' tools/x.py"),
    *(("Bash", line) for line in VERIFY_LINES),
]  # fmt: skip


@pytest.mark.parametrize(("name", "command"), ORDINARY)
def test_worktree_command_allowlist_allows_ordinary_commands(worktree, name, command):
    """261112-fdw, RULINGS fdw: ordinary worktree commands, the sanctioned relative forms, the
    real GSD shapes and this plan's verify lines keep no opinion; their scripts are read."""
    clean_scripts(worktree)
    assert not always(shell(name, command, worktree)).deny, command


FIND_REFUSED = ["-exec bash {} +", "-execdir bash {} +", "-ok rm {} +", "-okdir rm {} +",
                "-delete", "-fls out.txt", "-fprint out.txt", "-fprint0 out.txt",
                "-fprintf out.txt %p"]  # fmt: skip
READ_ONLY_DENIED = [
    "git branch -D x && git add x.py", "git branch -d x && git add x.py",
    "git branch -m a b && git add x.py", "git branch -f x && git add x.py",
    "git branch topic && git add x.py", "git worktree add ../w && git add x.py",
    "git stash && git add x.py", "git grep -Obash foo -- x.py",
    "git grep --open-files-in-pager=vim foo -- x.py", "git grep --op foo -- x.py",
    "git --git-dir=../../../.git log -- x.py", "git --work-tree=tools add x.py",
    "git -c core.pager=less log -- x.py",
    # coordinator amendment (iteration 2): free subcommands refuse --output, --ext-diff, --textconv
    "git diff --output=out.txt x.py", "git diff --output out.txt x.py",
    "git log --outp=out.txt -- x.py", "git diff --ext-diff x.py", "git log -p --ext-diff -- x.py",
    "git show --textconv HEAD -- x.py", "git grep --textconv foo -- x.py",
    *(f"find tools -name x.py {flag}" for flag in FIND_REFUSED),
    "sort --compress-program=./y x.py", "sort --comp=./y x.py",
    "sed -i 1d x.py", "sed --in-place 1d x.py", "sed -n 1,80p x.py -i",
    "sed -n '1e bash y.sh' x.py", "sed -n '1w out.txt' x.py", "sed -n '1r y.sh' x.py",
    "sed -n '/def/p' x.py", "sed 1,80p x.py", "sed -e 1p x.py",
    "awk '{print}' x.py",
    f'GSD_TOOLS={GSD_TOOLS}; node "$GSD_TOOLS" query init.quick',
    "HOME=. git log -- x.py", "Path=. git add x.py", "GIT_EXTERNAL_DIFF=./y git diff x.py",
    "EDITOR=./y git commit x.py", "UV_PYTHON=./y uv run python x.py",
    "NODE_OPTIONS=--require=./y node x.mjs", "PYTHONPATH=y uv run pytest tests/test_hooks.py",
    "PYTEST_ADDOPTS=-py uv run pytest tests/test_hooks.py", "BASH_ENV=./y bash x.sh",
    "SHELLOPTS=xtrace bash x.sh", "BASHOPTS=extdebug bash x.sh", "PS4=x bash x.sh",
]  # fmt: skip


@pytest.mark.parametrize("command", READ_ONLY_DENIED)
def test_worktree_command_allowlist_refuses_dangerous_flags(worktree, command):
    """261112-fdw, coordinator ruling: each widened read-only command fails closed on the flags
    that run a program or write, a variable script word is not a plain path, and an assignment
    to a variable that steers a listed program is refused."""
    clean_scripts(worktree)
    decision = always(shell("Bash", command, worktree))
    assert decision.deny and CANNOT_TELL in decision.reason, command


@pytest.mark.parametrize(("name", "command", "word"), [
    ("PowerShell", "sl tools; & ./x.ps1", "sl"), ("Bash", 'c""d tools && uv run python x.py', "cd"),
])  # fmt: skip
def test_worktree_command_allowlist_reason(worktree, name, command, word):
    decision = always(shell(name, command, worktree))
    assert decision.reason.startswith("reverseapoc hooks: ")
    for part in (name, "agent-x", word, "261112-fdw", CANNOT_TELL):
        assert part in decision.reason, part


def test_worktree_command_allowlist_entry_point(worktree):
    def run(payload: dict) -> subprocess.CompletedProcess[bytes]:
        return _run_entry(json.dumps(payload).encode("utf-8"))

    denied = run(shell("PowerShell", "sl tools; & ./x.ps1", worktree))
    assert denied.returncode == 0, denied.stderr
    assert json.loads(denied.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    clean_scripts(worktree)
    allowed = run(shell("Bash", "bash x.sh", worktree))
    assert (allowed.returncode, allowed.stdout) == (0, b""), allowed.stderr


SUBSTITUTIONS = [
    ("Bash", 'echo "$(uv run --directory tools python y.py)"', CANNOT_TELL),
    ("Bash", "echo \"$(bash -c 'node x.mjs')\"", CANNOT_TELL),
    ("Bash", 'echo "`uv run --project tools python y.py`"', CANNOT_TELL),
    ("Bash", 'X="$(uv run --directory tools python y.py)"; git add x.py', CANNOT_TELL),
    ("Bash", 'echo "$(echo "$(uv run --directory t python y.py)")"', CANNOT_TELL),
    ("Bash", "cat x.py <(node --eval 1)", CANNOT_TELL),
    ("PowerShell", 'git commit -m "$(sl tools)"; & ./x.ps1', CANNOT_TELL),
    ("PowerShell", 'echo "$(& ./a.ps1)"; & ./x.ps1', CANNOT_TELL),
    ("Bash", 'echo x > y.py; X="$(uv run python y.py)"', "the same command writes it"),
    ("Bash", 'git diff --exit-code "$(git merge-base HEAD main)" -- tools/x.py', None),
    ("Bash", 'test "$(grep -c X tools/reverseapoc/hooks.py)" -ge 1', None),
    ("Bash", 'echo "$(git rev-parse HEAD)" x.py', None),
    ("Bash", "git commit -m 'literal $(cd tools) in hooks.py docs'", None),
    ("PowerShell", 'git commit -m "fix $(git rev-parse --short HEAD) in hooks.py docs"', None),
]  # fmt: skip


@pytest.mark.parametrize(("name", "command", "expected"), SUBSTITUTIONS)
def test_worktree_command_judges_substitutions(worktree, name, command, expected):
    """261112-fdw A10: each command substitution, quoted or nested, and each PowerShell
    subexpression is held to the allowlist, and its script words are read with the call's (a
    write and a run across the boundary are caught); a single-quoted one is literal."""
    clean_scripts(worktree)
    decision = always(shell(name, command, worktree))
    if expected is None:
        assert not decision.deny, command
        return
    assert decision.deny and expected in decision.reason, command


def test_worktree_command_unterminated_substitution_fails_closed(worktree):
    """261112-fdw A9: an unterminated substitution blocks (the shell would refuse it anyway)."""
    for name, command in (("Bash", 'echo "$(uv run python x.py"'),
                          ("PowerShell", 'git commit -m "$(git status x.py"')):  # fmt: skip
        with pytest.raises(hooks.HookError, match="unterminated"):
            always(shell(name, command, worktree))


@pytest.mark.parametrize("command", ["& ./x.p`s1", '& "./x.p`u{73}1"', "uv run python x.p`y"])
def test_worktree_command_finds_backtick_hidden_scripts(worktree, command):
    """261112-fdw A2: a PowerShell backtick escape no longer hides a script suffix; the word
    still needs the escape, so it cannot be read as written."""
    clean_scripts(worktree)
    decision = always(shell("PowerShell", command, worktree))
    assert decision.deny and "needs shell expansion" in decision.reason, command

QUOTING_DENIED = [
    ("Bash", "bash x.sh $'a'"),          # names a script and contains $'...'
    ("Bash", "bash x.sh # a note"),      # names a script and has a word starting with #
    ("Bash", 'echo "$(echo $\'a\')"; bash x.sh'),  # $'...' inside a substitution
    ("PowerShell", "& ./x.ps1 {#}"),     # any unquoted #, not only at a word start
]
QUOTING_ALLOWED = [
    ("Bash", 'git commit -m "fix #12 in hooks.py"'),   # '#' inside quotes is not a comment
    ("Bash", "echo $'a'"),                             # names no script: unchanged
]


def test_worktree_command_refuses_ansi_c_quotes_and_comments(worktree):
    """261112-fdw review finding 1: a script-naming call with $'...' or a word-initial #
    is denied (fail closed); quoted '#' and calls that name no script are unchanged."""
    clean_scripts(worktree)
    for name, command in QUOTING_DENIED:
        decision = always(shell(name, command, worktree))
        assert decision.deny and CANNOT_TELL in decision.reason, command
    for name, command in QUOTING_ALLOWED:
        assert not always(shell(name, command, worktree)).deny, command



def test_worktree_command_reads_powershell_quotes_as_powershell_does(repo, worktree):
    """261112-fdw A2: a single-quoted backtick stays literal, an escaped verb is the verb
    PowerShell runs, and curly quotes are the quotes PowerShell takes them for."""
    clean_scripts(worktree)
    for name in SHELL_TOOLS:
        assert not always(shell(name, "git commit -m 'fix `hooks.py`'", worktree)).deny, name
    assert not always(shell("PowerShell", "g`it add x.py", worktree)).deny
    (worktree / "x.ps1").write_text(f'WATCOM = "{main_watcom(repo)}"\n', encoding="utf-8")
    decision = always(shell("PowerShell", "& ./x.p\u2018\u2019s1", worktree))
    assert decision.deny and SPELLS_MAIN in decision.reason


RUNSPACE_DENIED = ["& ./a.ps1; & ./x.ps1", "& ./a.ps1; uv run pytest -q tests/test_hooks.py",
                   "& ./a.ps1 | & ./x.ps1", "./a.ps1; git add x.py",
                   '& ./a.ps1; git commit -m "$(git status)"']  # fmt: skip
RUNSPACE_ALLOWED = [("PowerShell", "& ./a.ps1; git status"),
                    ("PowerShell", "uv run python a.py; uv run python x.py"),
                    ("Bash", "bash a.sh; bash x.sh"), ("Bash", "./a.sh; ./x.sh")]  # fmt: skip


def test_worktree_command_powershell_script_run_ends_the_call(worktree):
    """261112-fdw A8: a .ps1 runs in the caller's runspace and can move its location, so no
    script word may follow a direct script run; interpreter runs are child processes."""
    clean_scripts(worktree)
    for command in RUNSPACE_DENIED:
        decision = always(shell("PowerShell", command, worktree))
        assert decision.deny and CANNOT_TELL in decision.reason, command
        assert "261112-fdw" in decision.reason, command
    for name, command in RUNSPACE_ALLOWED:
        assert not always(shell(name, command, worktree)).deny, command


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
    view = _view_unit(repo)
    decision = matching(in_repo(write(native(view), SCAFFOLD + PATH_INCLUDES[name]), repo))
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
    unit = _view_unit(repo) if layer == "matching" else _unit(repo)
    payload = in_repo(write(native(unit), SCAFFOLD + PATH_INCLUDES["quoted-path"]), repo)
    decision = matching(payload) if layer == "matching" else always(payload)
    assert decision.deny
    assert decision.reason.startswith(INCLUDE_PREFIX), decision.reason
    assert INCLUDE_WORDING in decision.reason, decision.reason
    assert "'\"sub/x.h\"'" in decision.reason
    assert "inline asm" not in decision.reason and "#pragma" not in decision.reason
    asm = in_repo(write(native(unit), SCAFFOLD + "#pragma once\n"), repo)
    if layer == "matching":
        assert "no inline asm and no #pragma of any kind" in matching(asm).reason


@pytest.mark.parametrize("name", sorted(BARE_INCLUDES))
@pytest.mark.parametrize("rel", [UNIT, "include/new.h"])
def test_matching_allows_a_bare_header_include(repo, name, rel):
    path = _unit(repo, rel=rel)
    view = _view_unit(repo)
    assert not matching(in_repo(write(native(view), SCAFFOLD + BARE_INCLUDES[name]), repo)).deny
    assert not always(write(native(path), SCAFFOLD + BARE_INCLUDES[name])).deny


def test_include_words_outside_a_directive_are_allowed(repo):
    path = _view_unit(repo)
    for text in ['/* #include "../x.h" */\n', 'char *s = "#include <../x.h>";\n',
                 'int include_count;\n']:  # fmt: skip
        assert not matching(in_repo(write(native(path), SCAFFOLD + text), repo)).deny, text


def test_an_edit_that_introduces_a_path_include_is_denied(repo):
    unit, view = _unit(repo), _view_unit(repo)
    payload = in_repo(edit(native(view), '#include "common.h"', NOTES_INCLUDE.rstrip("\n")), repo)
    decision = matching(payload)
    assert decision.deny and "#include" in decision.reason
    assert always(edit(native(unit), '#include "common.h"', NOTES_INCLUDE.rstrip("\n"))).deny
    # completing a path out of a bare name is caught on the post-edit text
    completed = matching(in_repo(edit(native(view), '"common.h"', '"../common.h"'), repo))
    assert completed.deny and "#include" in completed.reason


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


def _every_edit_tool(path: str) -> list[dict]:
    notebook = {"tool_name": "NotebookEdit",
                "tool_input": {"notebook_path": path, "new_source": "x"}}  # fmt: skip
    return [write(path), edit(path, "a", "b"), multi_edit(path, ("a", "b")), notebook]


def _owner_only(repo: Path, rel: str) -> None:
    """D-27 P3: every edit tool is denied the owner-only cflags file `rel` with no env at all,
    naming D-12 and the owner's own verbs, in every path form."""
    for form in _forms(repo, rel):
        for payload in _every_edit_tool(form):
            decision = always(payload)
            assert decision.deny, (form, payload["tool_name"])
            assert "D-12" in decision.reason, decision.reason
            assert "reverseapoc flags" in decision.reason, decision.reason


def test_always_layer_protects_cflags(repo):
    _owner_only(repo, "config/cflags.txt")
    reason = always(write(native(repo / "config" / "cflags.txt"))).reason
    assert "flags approve" in reason and "flags default" in reason, reason


def test_always_layer_protects_the_proposal_queue(repo):
    _owner_only(repo, "config/cflags-proposals.toml")


@pytest.mark.parametrize("exe", ["ufo2p", "tacp"])
def test_view_mode_denies_symbols_csv_with_d19_reason(repo, exe):
    _view_unit(repo)
    symbols = repo / "config" / exe / "symbols.csv"
    decision = matching(in_repo(write(native(symbols), "x\n"), repo), view_env(repo))
    assert decision.deny
    assert "D-19" in decision.reason and "proposals.jsonl" in decision.reason, decision.reason


@pytest.mark.parametrize("name", ["fx.h", "common.h", "sub/x.h"])
def test_view_mode_denies_headers_with_d19_reason(repo, name):
    _view_unit(repo)
    header = repo / "include" / name
    decision = matching(in_repo(write(native(header), "int fx;\n"), repo), view_env(repo))
    assert decision.deny
    assert "D-19" in decision.reason, decision.reason
    other = matching(in_repo(write(native(repo / "tools" / "x.py")), repo), view_env(repo))
    assert other.deny and "D-24" in other.reason and "D-19" not in other.reason, other.reason


LEGACY_REASON = "a session needs the driver's REVERSEAPOC_UNIT_FILE (D-24)"


def test_claim_without_unit_file_writes_nothing(repo):
    """07-13 (T-07-39): the Phase 6 single-session allowlist is gone. With a claim, notes and
    proposals but no REVERSEAPOC_UNIT_FILE, every write is denied naming D-24: the shared unit,
    a new header, notes.md, proposals.jsonl and a view-shaped unit alike."""
    notes = _attempt(repo) / "notes.md"
    proposals = _attempt(repo) / "proposals.jsonl"
    env = {**CLAIM, "REVERSEAPOC_ATTEMPT_NOTES": native(notes),
           "REVERSEAPOC_PROPOSALS": native(proposals)}  # fmt: skip
    targets = [_unit(repo), repo / "include" / "fx.h", notes, proposals,
               repo / "config" / "ufo2p" / "symbols.csv"]  # fmt: skip
    for target in targets:
        decision = matching(in_repo(write(native(target), SCAFFOLD), repo), env)
        assert decision.deny, target
        assert LEGACY_REASON in decision.reason, decision.reason
    # a view-shaped unit is build output to a session the driver gave no unit file
    view = matching(in_repo(write(native(_view_unit(repo)), SCAFFOLD), repo), env)
    assert view.deny and "build/ is protected" in view.reason, view.reason
    claim = "ufo2p/u_000a34f0"
    for rel in [UNIT, "include/new.h", "build/driver/r/proposals.jsonl"]:
        assert not hooks.matching_write_allowed(
            rel, claim=claim, notes=None, tracked=lambda _: False,
            proposals="build/driver/r/proposals.jsonl",
        ), rel  # fmt: skip
    assert matching(bash(f"{WRAPPER} check", repo), env).deny is False  # Bash keeps its rules


def test_legacy_header_allowance_gone(repo):
    """The old F5 case: a new include/x.h with only CLAIM and NOTES set is denied."""
    notes = _attempt(repo) / "notes.md"
    env = {**CLAIM, "REVERSEAPOC_ATTEMPT_NOTES": native(notes)}
    decision = matching(in_repo(write(native(repo / "include" / "x.h"), "int x;\n"), repo), env)
    assert decision.deny and LEGACY_REASON in decision.reason, decision.reason
    assert not hooks.matching_write_allowed("include/x.h", claim="ufo2p/u_000a34f0",
                                            notes=None, tracked=lambda _: False)  # fmt: skip


def test_session_env_names():
    assert hooks.UNIT_FILE_ENV == "REVERSEAPOC_UNIT_FILE"
    assert hooks.PROPOSALS_ENV == "REVERSEAPOC_PROPOSALS"
    assert hooks.SESSION_KIND_ENV == "REVERSEAPOC_SESSION_KIND"
    assert hooks.SESSION_KINDS == ("matching", "readability")


def test_readability_kind_same_allowlist(repo):
    """D-17/D-18: a readability session gets the view-mode allowlist unchanged, and only in view
    mode (the legacy allowlist would let it write include/, which is naming state, D-19)."""
    unit = _view_unit(repo)
    env = view_env(repo, kind="readability")
    allowed = [unit, _attempt(repo) / "notes.md", _attempt(repo) / "proposals.jsonl"]
    for target in allowed:
        assert not matching(in_repo(write(native(target), SCAFFOLD), repo), env).deny, target
    denied = [_unit(repo), repo / "include" / "fx.h", repo / "config" / "ufo2p" / "symbols.csv",
              repo / "tools" / "x.py", _view_path(repo, "ufo2p/u_other")]  # fmt: skip
    for target in denied:
        assert matching(in_repo(write(native(target), SCAFFOLD), repo), env).deny, target
    legacy = {**CLAIM, "REVERSEAPOC_SESSION_KIND": "readability"}
    for target in [_unit(repo), repo / "include" / "fx.h"]:
        decision = matching(in_repo(write(native(target), SCAFFOLD), repo), legacy)
        assert decision.deny and "REVERSEAPOC_UNIT_FILE" in decision.reason, decision.reason


# ---- 07.2-02 (999.5, D-04, D-26): giveup.json and the matching-only `attempt giveup` ----

GIVEUP_JSON = '{"category": "other", "tried": "a", "still_differs": "b", "suspected_cause": "c"}'


def test_bash_allows_giveup_only_in_a_matching_session(repo):
    command = f"{WRAPPER} giveup"
    assert hooks.bash_allowed(command, kind="matching")
    assert hooks.bash_allowed(command)  # absent kind: a matching run
    assert not hooks.bash_allowed(command, kind="readability")
    assert not hooks.bash_allowed(f"{WRAPPER} giveup x", kind="matching")
    _view_unit(repo)
    assert not matching(bash(command, repo, None)).deny
    decision = matching(bash(command, repo, None), view_env(repo, kind="readability"))
    assert decision.deny and "giveup" not in decision.reason, decision.reason
    assert f"{WRAPPER} context" in decision.reason


def test_bash_chars_unchanged():
    """T-07.2-04: the injection boundary is not loosened for the new form."""
    assert hooks._BASH_CHARS.pattern == r"[A-Za-z0-9_ -]+"


def test_matching_allows_the_giveup_json_beside_the_notes(repo):
    """D-26: a matching session may write giveup.json beside its notes.md, a readability
    session may not, and a giveup.json anywhere else under build/driver/ is denied."""
    _view_unit(repo)
    giveup = _attempt(repo) / "giveup.json"
    assert hooks.GIVEUP_NAME == "giveup.json"
    assert not matching(in_repo(write(native(giveup), GIVEUP_JSON), repo)).deny
    upper = repo / giveup.relative_to(repo).as_posix().upper()
    assert not matching(in_repo(write(native(upper), GIVEUP_JSON), repo)).deny
    readability = view_env(repo, kind="readability")
    assert matching(in_repo(write(native(giveup), GIVEUP_JSON), repo), readability).deny
    elsewhere = [_attempt(repo).parent / "attempt-2" / "giveup.json",
                 _attempt(repo) / "view" / "giveup.json",
                 repo / "build" / "driver" / "giveup.json",
                 _attempt(repo) / "giveup.json.bak"]  # fmt: skip
    for target in elsewhere:
        assert matching(in_repo(write(native(target), GIVEUP_JSON), repo)).deny, target


def test_always_exempts_only_the_notes_sibling_giveup(repo):
    notes = repo / "build" / "driver" / "run1" / "ufo2p" / "func_000A3980" / "a-1" / "notes.md"
    env = {"REVERSEAPOC_ATTEMPT_NOTES": native(notes)}
    giveup = notes.with_name("giveup.json")
    assert not always(write(native(giveup)), env).deny
    assert always(write(native(giveup)), {}).deny
    assert always(write(native(notes.parent.parent / "giveup.json")), env).deny
    assert always(write(native(notes.with_name("giveup.jsonl"))), env).deny


def test_matching_write_allowed_takes_the_session_kind():
    claim = "ufo2p/u_000a34f0"
    base = "build/driver/r/ufo2p/func_000A3980/attempt-1"
    paths = {"notes": f"{base}/notes.md", "unit_file": f"{base}/view/src/ufo2p/u_000a34f0.c",
             "proposals": f"{base}/proposals.jsonl"}  # fmt: skip

    def allowed(rel: str, **kind) -> bool:
        return hooks.matching_write_allowed(rel, claim=claim, tracked=lambda _: False,
                                            **paths, **kind)  # fmt: skip

    assert allowed(f"{base}/giveup.json")
    assert allowed(f"{base}/GIVEUP.JSON")
    assert allowed(f"{base}/giveup.json", kind="matching")
    assert not allowed(f"{base}/giveup.json", kind="readability")
    assert allowed(f"{base}/notes.md", kind="readability")
    assert not allowed("build/driver/r/ufo2p/func_000A3980/giveup.json")
    assert not allowed(f"{base}/view/giveup.json")


# ---- 07.2-03 (999.6, D-01, D-26): plan.json and check-note.json beside the notes ----

SESSION_JSON = '{"change": "a", "why": "b", "expect": "c"}'


def test_bash_allows_plan_only_in_a_matching_session(repo):
    command = f"{WRAPPER} plan"
    assert hooks.bash_allowed(command, kind="matching")
    assert hooks.bash_allowed(command)  # absent kind: a matching run
    assert not hooks.bash_allowed(command, kind="readability")
    assert not hooks.bash_allowed(f"{WRAPPER} plan x", kind="matching")  # it takes no argument
    _view_unit(repo)
    assert not matching(bash(command, repo, None)).deny
    assert matching(bash(command, repo, None), view_env(repo, kind="readability")).deny


def test_session_file_names():
    assert (hooks.PLAN_NAME, hooks.CHECK_NOTE_NAME) == ("plan.json", "check-note.json")
    assert hooks.SESSION_FILE_NAMES == ("giveup.json", "plan.json", "check-note.json")


@pytest.mark.parametrize("name", ["plan.json", "check-note.json"])
def test_matching_allows_the_plan_and_note_beside_the_notes(repo, name):
    """D-26: a matching session may write plan.json and check-note.json beside its notes.md, a
    readability session may not, and either name anywhere else under build/driver/ is denied."""
    _view_unit(repo)
    target = _attempt(repo) / name
    assert not matching(in_repo(write(native(target), SESSION_JSON), repo)).deny
    upper = repo / target.relative_to(repo).as_posix().upper()
    assert not matching(in_repo(write(native(upper), SESSION_JSON), repo)).deny
    readability = view_env(repo, kind="readability")
    assert matching(in_repo(write(native(target), SESSION_JSON), repo), readability).deny
    elsewhere = [_attempt(repo).parent / "attempt-2" / name, _attempt(repo) / "view" / name,
                 _attempt(repo) / "checks" / name, repo / "build" / "driver" / name,
                 _attempt(repo) / f"{name}.bak"]  # fmt: skip
    for path in elsewhere:
        assert matching(in_repo(write(native(path), SESSION_JSON), repo)).deny, path


@pytest.mark.parametrize("name", ["plan.json", "check-note.json"])
def test_always_exempts_only_the_notes_sibling_plan_and_note(repo, name):
    notes = repo / "build" / "driver" / "run1" / "ufo2p" / "func_000A3980" / "a-1" / "notes.md"
    env = {"REVERSEAPOC_ATTEMPT_NOTES": native(notes)}
    assert not always(write(native(notes.with_name(name))), env).deny
    assert always(write(native(notes.with_name(name))), {}).deny
    assert always(write(native(notes.parent.parent / name)), env).deny
    assert always(write(native(notes.parent / "checks" / name)), env).deny


@pytest.mark.parametrize("name", ["plan.json", "check-note.json"])
def test_matching_write_allowed_admits_the_plan_and_note(name):
    claim = "ufo2p/u_000a34f0"
    base = "build/driver/r/ufo2p/func_000A3980/attempt-1"
    paths = {"notes": f"{base}/notes.md", "unit_file": f"{base}/view/src/ufo2p/u_000a34f0.c",
             "proposals": f"{base}/proposals.jsonl"}  # fmt: skip

    def allowed(rel: str, **kind) -> bool:
        return hooks.matching_write_allowed(rel, claim=claim, tracked=lambda _: False,
                                            **paths, **kind)  # fmt: skip

    assert allowed(f"{base}/{name}")
    assert allowed(f"{base}/{name.upper()}")
    assert not allowed(f"{base}/{name}", kind="readability")
    assert not allowed(f"build/driver/r/ufo2p/func_000A3980/{name}")
    assert not allowed(f"{base}/checks/0001.note.json")


@pytest.mark.parametrize("kind", ["other", "", "Matching", "readability "])
def test_unknown_kind_denies_writes(repo, kind):
    unit = _view_unit(repo)
    notes = _attempt(repo) / "notes.md"
    legacy = {**CLAIM, "REVERSEAPOC_ATTEMPT_NOTES": native(notes),
              "REVERSEAPOC_SESSION_KIND": kind}  # fmt: skip
    # each env's own allowlist, which an unknown kind closes
    proposals = _attempt(repo) / "proposals.jsonl"
    for env, targets in [(view_env(repo, kind=kind), [unit, notes, proposals]),
                         (legacy, [notes, _unit(repo), repo / "include" / "fx.h"])]:  # fmt: skip
        for target in targets:
            decision = matching(in_repo(write(native(target), SCAFFOLD), repo), env)
            assert decision.deny, (env, target)
            assert "matching" in decision.reason and "readability" in decision.reason


@pytest.mark.parametrize("claim", ["ufo2p/u_other", "tacp/u_000a34f0"])
def test_unit_file_for_another_unit_is_not_exempt(repo, claim):
    """T-07-12: a unit file env naming another unit than the claim stays under build/'s
    protection, in both layers."""
    other = _view_unit(repo, claim)
    env = view_env(repo, unit_file=other)
    decision = always(write(native(other), SCAFFOLD), env)
    assert decision.deny and "build/" in decision.reason, decision.reason
    assert matching(in_repo(write(native(other), SCAFFOLD), repo), env).deny


@pytest.mark.parametrize(
    "parts",
    [("build", "other", "view", "src", "ufo2p", "u_000a34f0.c"),
     ("build", "view", "src", "ufo2p", "u_000a34f0.c"),
     ("build", "driver", "view", "src", "ufo2p", "u_000a34f0.c"),
     ("build", "driver", "r", "src", "ufo2p", "u_000a34f0.c"),
     ("build", "driver", "r", "view", "ufo2p", "u_000a34f0.c"),
     ("build", "driver", "r", "view", "src", "ufo2p", "u_000a34f0.h"),
     ("view", "src", "ufo2p", "u_000a34f0.c")],
)  # fmt: skip
def test_unit_file_outside_build_driver_is_not_exempt(repo, parts):
    path = repo.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(SCAFFOLD.encode("utf-8"))
    env = view_env(repo, unit_file=path)
    assert matching(in_repo(write(native(path), SCAFFOLD), repo), env).deny
    if parts[0] == "build":
        assert always(write(native(path), SCAFFOLD), env).deny
    proposals = repo / "build" / "other" / "proposals.jsonl"
    env = {**view_env(repo), "REVERSEAPOC_PROPOSALS": native(proposals)}
    assert always(write(native(proposals), "{}\n"), env).deny


def test_session_paths_need_every_build_form_to_fit(repo):
    """Only the exact shapes count: a unit file whose form against one checkout fits but whose
    form against an enclosing checkout lies elsewhere under build/ is not a session path."""
    env = view_env(repo)
    found = hooks._session_paths(env, "")
    assert native(_view_path(repo)).replace("\\", "/").casefold() in found
    assert (_attempt(repo) / "proposals.jsonl").as_posix().casefold() in found
    inner = repo / "build" / "inner"
    (inner / ".git").mkdir(parents=True)
    nested = inner.joinpath(*ATTEMPT, "view", "src", "ufo2p", "u_000a34f0.c")
    assert hooks._session_paths({**env, "REVERSEAPOC_UNIT_FILE": native(nested),
                                 "REVERSEAPOC_PROPOSALS": ""}, "") == frozenset()  # fmt: skip
    assert hooks._session_paths({"REVERSEAPOC_PROPOSALS": native(nested)}, "") == frozenset()


def _unusable_unit_file(repo: Path, form: str) -> str:
    """A REVERSEAPOC_UNIT_FILE value the matching layer cannot place as one path in the
    checkout, so `_session_relative` gives None."""
    view = _view_unit(repo)
    if form == "outside":
        return native(repo.parent / "elsewhere" / view.relative_to(repo))
    if form == "home":
        return "~/" + view.relative_to(repo).as_posix()
    if form == "nul":
        return native(view) + "\0"
    link = repo / "link.c"
    target = view if form == "symlink-inside" else repo.parent / "elsewhere.c"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation needs privileges on this host")
    return native(link)


@pytest.mark.parametrize("form", ["outside", "home", "nul", "symlink-inside", "symlink-outside"])
def test_unusable_unit_file_denies_every_write(repo, form):
    """Fix round 1: a set but unusable REVERSEAPOC_UNIT_FILE denies every write; it never falls
    back to the legacy allowlist (src/<exe>/<unit>.c, a new include/*.h, notes.md)."""
    env = view_env(repo)
    env["REVERSEAPOC_UNIT_FILE"] = _unusable_unit_file(repo, form)
    for target in [_unit(repo), repo / "include" / "fx.h", _attempt(repo) / "notes.md"]:
        decision = matching(in_repo(write(native(target), SCAFFOLD), repo), env)
        assert decision.deny, (form, target)
        assert "REVERSEAPOC_UNIT_FILE" in decision.reason, decision.reason
    for target in [_view_path(repo), _attempt(repo) / "proposals.jsonl"]:
        assert matching(in_repo(write(native(target), SCAFFOLD), repo), env).deny, (form, target)


def test_unit_file_with_two_forms_denies_every_write(repo, monkeypatch):
    """The symlink case without symlink privileges: the host resolves the env path (an alias,
    an 8.3 name) to another file in the checkout, so it has two forms and names no single path."""
    view = _view_unit(repo)
    alias = repo / "alias.c"
    real = os.path.realpath

    def aliased(path, **kwargs):
        return str(view) if Path(path) == alias else real(path, **kwargs)

    monkeypatch.setattr(os.path, "realpath", aliased)
    env = {**view_env(repo), "REVERSEAPOC_UNIT_FILE": native(alias)}
    for target in [_unit(repo), repo / "include" / "fx.h", _attempt(repo) / "notes.md", view]:
        decision = matching(in_repo(write(native(target), SCAFFOLD), repo), env)
        assert decision.deny, target
    reason = matching(in_repo(write(native(_unit(repo)), SCAFFOLD), repo), env).reason
    assert "REVERSEAPOC_UNIT_FILE" in reason, reason


def test_wrong_shape_unit_file_keeps_the_view_allowlist(repo):
    """A unit file under build/ at the wrong shape is placeable, so the session stays in view
    mode: it never gains the legacy src/ and include/ allowlist, and the file is not writable."""
    wrong = repo / "build" / "other" / "view" / "src" / "ufo2p" / "u_000a34f0.c"
    env = view_env(repo, unit_file=wrong)
    for target in [_unit(repo), repo / "include" / "fx.h", wrong, _view_path(repo)]:
        assert matching(in_repo(write(native(target), SCAFFOLD), repo), env).deny, target


@pytest.mark.parametrize("name", sorted(PATH_INCLUDES))
def test_view_unit_include_rule(repo, name):
    unit = _view_unit(repo)
    env = view_env(repo)
    text = SCAFFOLD + PATH_INCLUDES[name]
    for decision in [always(write(native(unit), text), env),
                     matching(in_repo(write(native(unit), text), repo), env)]:  # fmt: skip
        assert decision.deny, name
        assert decision.reason.startswith(INCLUDE_PREFIX), decision.reason
    bare = SCAFFOLD + BARE_INCLUDES["quoted"]
    assert not matching(in_repo(write(native(unit), bare), repo), env).deny


# --- 07.2-12 (D-10): an egress session reads neither orig/ nor third_party/ -------------------


def _egress_reads(repo: Path) -> list[dict]:
    """Read, Glob and Grep of the game files and the compiler, by path and by pattern."""
    return [
        tool("Read", repo, file_path=native(repo / "orig" / "UFO2P.EXE")),
        tool("Read", repo, file_path=native(repo / "ORIG" / "tacp.exe")),  # NTFS: any case
        tool("Glob", repo, pattern="*", path=native(repo / "orig")),
        tool("Glob", repo, pattern="orig/**"),
        tool("Glob", repo, pattern="{src,third_party}/**/*.h"),
        tool("Grep", repo, pattern="x", path=native(repo / "third_party" / "watcom")),
        tool("Grep", repo, pattern="x", glob="third_party/**"),
        tool("Grep", repo, pattern="x", path=native(repo / "orig") + os.sep),
    ]


def test_egress_session_cannot_read_orig(repo):
    """With REVERSEAPOC_EGRESS=1 (a session of a non-Anthropic arm), every read of orig/ or
    third_party/ is denied naming D-10; without it the same reads behave as today, and other
    reads of the egress session do too."""
    egress = {**view_env(repo), hooks.EGRESS_ENV: "1"}
    assert hooks.EGRESS_ENV == "REVERSEAPOC_EGRESS"
    for payload in _egress_reads(repo):
        decision = matching(payload, egress)
        assert decision.deny and "D-10" in decision.reason, payload["tool_input"]
        assert not matching(payload).deny, payload["tool_input"]
    for payload in (tool("Read", repo, file_path=native(repo / "src" / "ufo2p" / "x.c")),
                    tool("Grep", repo, pattern="x", path=native(repo / "include")),
                    tool("Glob", repo, pattern="src/**/*.c")):  # fmt: skip
        assert not matching(payload, egress).deny, payload["tool_input"]


def _egress_bypasses(repo: Path) -> list[dict]:
    """Security review of 07.2-12 (HIGH, MEDIUM): spellings the first egress rule let through.
    Paths through another root form (a worktree's checkout under .claude/worktrees/, an
    ancestor holding a planted .git), and wildcard patterns or recursive searches that reach
    orig/ or third_party/ without naming either literally. gitignore is never relied on."""
    worktree = repo / ".claude" / "worktrees" / "agent-x"
    (worktree / ".git").parent.mkdir(parents=True, exist_ok=True)
    (worktree / ".git").write_text("gitdir: ../../../.git/worktrees/agent-x\n", encoding="utf-8")
    nested = repo / "src" / "nested"
    (nested / ".git").mkdir(parents=True, exist_ok=True)
    return [
        tool("Read", repo, file_path=native(worktree / "orig" / "UFO2P.EXE")),
        tool("Read", repo, file_path=native(nested / "orig" / "UFO2P.EXE")),
        tool("Grep", repo, pattern="x", path=native(worktree / "third_party" / "watcom")),
        tool("Glob", repo, pattern="o*ig/**"),
        tool("Glob", repo, pattern="or?g/*"),
        tool("Glob", repo, pattern="third_*/**"),
        tool("Glob", repo, pattern="{src,thi*}/**"),
        tool("Glob", repo, pattern="*"),
        tool("Glob", repo, pattern="**/*.EXE"),
        tool("Glob", repo, pattern="*/UFO2P.EXE"),
        tool("Glob", repo, pattern="*.EXE"),  # may match at any depth, as a ripgrep glob does
        tool("Glob", repo, pattern="worktrees/*/orig/*", path=native(repo / ".claude")),
        tool("Glob", repo, pattern=".claude/**/UFO2P.EXE"),
        tool("Glob", repo, pattern="*", path=native(worktree)),
        tool("Grep", repo, pattern="x"),  # the whole checkout, orig/ included
        tool("Grep", repo, pattern="x", glob="*.EXE"),  # a basename glob at any depth
        tool("Grep", repo, pattern="x", path=native(repo / ".claude")),
        tool("Grep", repo, pattern="x", path=native(worktree)),
    ]


def test_egress_session_cannot_read_orig_through_any_form(repo):
    egress = {**view_env(repo), hooks.EGRESS_ENV: "1"}
    passed = [payload["tool_input"] for payload in _egress_bypasses(repo)
              if not matching(payload, egress).deny]  # fmt: skip
    assert passed == []


@pytest.mark.parametrize("pattern", ["@(orig)/*", "+(o)rig/**", "!(src)/**", "!src/**",
                                     "orig|src/*", "third@(_party)/**",
                                     ".claude/@(worktrees)/x/*", "*(x)/UFO2P.EXE"])  # fmt: skip
def test_egress_patterns_fail_closed_on_other_glob_syntax(repo, pattern):
    """Security review (MEDIUM): fnmatch does not model extglob, alternation or negation, so a
    pattern segment holding anything but [A-Za-z0-9._-] and the plain wildcards * and ? is
    judged as one that can match any run of segments."""
    egress = {**view_env(repo), hooks.EGRESS_ENV: "1"}
    assert matching(tool("Glob", repo, pattern=pattern), egress).deny, pattern
    assert not matching(tool("Glob", repo, pattern=pattern)).deny, pattern  # as today
    scoped = tool("Glob", repo, pattern="src/@(ufo2p)/*.c")  # below src/: cannot reach either
    assert not matching(scoped, egress).deny


def test_egress_session_keeps_scoped_searches(repo):
    """What an egress session still may do: read and search below src/, include/ and its own
    attempt directory, with globs that stay there."""
    egress = {**view_env(repo), hooks.EGRESS_ENV: "1"}
    for payload in (tool("Glob", repo, pattern="src/ufo2p/*.c"),
                    tool("Glob", repo, pattern="*.h", path=native(repo / "include")),
                    tool("Glob", repo, pattern="src/**/*.c"),
                    tool("Grep", repo, pattern="x", path=native(repo / "src"), glob="*.c"),
                    tool("Read", repo,
                         file_path=native(repo / "docs" / "matching.md"))):  # fmt: skip
        assert not matching(payload, egress).deny, payload["tool_input"]
