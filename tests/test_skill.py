"""The watcom-decomp project skill (.claude/skills/watcom-decomp/SKILL.md, AGT-09, D-19).

The skill rides in the system prompt of every matching session, so it must stay short and every
path, verb and command it names must exist: a stale name costs the agent a turn. Commands are
checked against hooks.ATTEMPT_FORMS (ruling F27), the only Bash a matching session may run."""

from __future__ import annotations

import re

from conftest import REPO_ROOT
from reverseapoc import hooks
from reverseapoc.cli import build_parser

SKILL = REPO_ROOT / ".claude" / "skills" / "watcom-decomp" / "SKILL.md"
MAX_LINES = 300  # D-19
SECTIONS = (  # D-19's nine sections, in its order
    "Calling convention and linker names",
    "Flags",
    "C89 and the lint",
    "Pragmas",
    "Relocation rules",
    "Strings, statics and jump tables",
    "Replacing INCLUDE_ASM",
    "The attempt wrapper",
    "When to give up",
)
PATH_PREFIXES = ("docs/", "include/", "config/", "src/", ".claude/", "tools/", "tests/")
_SPAN = re.compile(r"`([^`\n]+)`")
_PLACEHOLDER = re.compile(r"<[^<>]+>|NNNN")
_VERB = re.compile(r"\breverseapoc ([a-z][a-z-]*)")
_PREFIX = " ".join(hooks.ATTEMPT_PREFIX)


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict[str, str]:
    assert text.startswith("---\n"), "SKILL.md starts with YAML frontmatter"
    block = text[4 : text.index("\n---\n", 4)]
    fields = {}
    for line in block.splitlines():
        key, sep, value = line.partition(":")
        if sep and not line.startswith(" "):
            fields[key.strip()] = value.strip()
    return fields


def _headings(text: str) -> list[str]:
    """The `## ` headings outside fenced blocks."""
    headings, fenced = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("## "):
            headings.append(line[3:].strip())
    return headings


def _spans(text: str) -> list[str]:
    return [span.strip() for span in _SPAN.findall(text)]


def test_skill_is_short_and_shaped():
    text = _text()
    assert len(text.splitlines()) <= MAX_LINES
    fields = _frontmatter(text)
    assert fields["name"] == "watcom-decomp"
    assert fields["description"].startswith("Use when")
    assert tuple(_headings(text)) == SECTIONS


def _repo_path(span: str) -> str | None:
    """The repo-relative path a backticked span names, without an anchor, a `:L12` line suffix
    or trailing punctuation; None when the span is not a path under PATH_PREFIXES."""
    if not span.startswith(PATH_PREFIXES) or " " in span:
        return None
    path = re.split(r"[#:]", span, maxsplit=1)[0]
    return path.rstrip(".,;)")


def test_skill_paths_exist():
    paths = [path for span in _spans(_text()) if (path := _repo_path(span))]
    assert paths, "the skill links to docs for depth (D-19)"
    for path in paths:
        pattern = _PLACEHOLDER.sub("*", path)
        assert list(REPO_ROOT.glob(pattern)), f"{path} names nothing in the repository"


def _verbs() -> set[str]:
    sub = next(a for a in build_parser()._actions if a.dest == "command")
    return set(sub.choices)


def test_skill_verbs_exist():
    found = set(_VERB.findall(_text()))
    assert "attempt" in found
    assert found <= _verbs(), sorted(found - _verbs())


def _commands(text: str) -> list[list[str]]:
    """The argv after ATTEMPT_PREFIX of every backticked span that starts `uv run`."""
    commands = []
    for span in _spans(text):
        if not span.startswith("uv run"):
            continue
        assert span.startswith(_PREFIX + " "), f"{span!r} is not an attempt wrapper command"
        commands.append(span[len(_PREFIX) + 1 :].split())
    return commands


def test_skill_commands_are_the_wrapper_forms():
    commands = _commands(_text())
    for argv in commands:
        literal = tuple(argv) in hooks.ATTEMPT_FORMS  # `asm <NAME>` is quoted literally (F27)
        assert literal or hooks.attempt_form_matches(argv), argv
    quoted = {tuple(argv) for argv in commands}
    assert set(hooks.ATTEMPT_FORMS) <= quoted, "every wrapper form is quoted"


def test_skill_settles_the_baseline_facts():
    """What the RED baseline agents had to guess, each stated once (writing-skills RED)."""
    text = _text()
    assert "600000" in text  # ruling F33: the sweep runs with the Bash tool's longest timeout
    assert "run_in_background" in text  # security finding 1: one check at a time
    assert "checks/NNNN.json" in text and "checks/NNNN.c" in text  # where the evidence is
    assert "notes.md" in text
    for code in ("0", "1", "2"):
        assert f"`{code}`" in text  # check's exit codes
