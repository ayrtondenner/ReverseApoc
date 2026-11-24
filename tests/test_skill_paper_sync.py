"""The paper-sync project skill (.claude/skills/paper-sync/, todo paper-sync-skill): it is found by
when to use it, it ships the lint scripts its steps run, its steps keep the order that makes a
pass safe (backup before mirror, facts before prose, lint before sync, one compile), and
docs/tools.md lists it."""

from __future__ import annotations

import re

from conftest import REPO_ROOT

SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "paper-sync"
SKILL = SKILL_DIR / "SKILL.md"


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_the_frontmatter_names_the_skill_by_when_to_use_it():
    text = _text()
    assert text.startswith("---\nname: paper-sync\ndescription: Use when ")
    description = text.split("\n", 3)[2]
    assert len(description) <= 1024
    assert "6afce29e14bd43436c220d22" in description


def test_the_lint_scripts_it_runs_ship_with_it():
    text = _text()
    for script in ("sanity.py", "scan.py"):
        assert (SKILL_DIR / script).is_file()
        assert script in text


def test_the_steps_run_in_the_safe_order():
    steps = re.findall(r"^\d+\. \*\*(\w+)", _text(), re.MULTILINE)
    assert steps == ["Backup", "Mirror", "Facts", "Check", "Edit", "Lint", "Sync", "Compile"]


def test_a_pass_compiles_once_and_judges_by_built_cleanly():
    text = _text()
    assert "summary.builtCleanly" in text
    assert "never mirror" in text
    assert "overwrite: true" in text  # named only to forbid it over an earlier backup


def test_docs_tools_lists_the_skill():
    tools = (REPO_ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
    assert "paper-sync" in tools


def test_the_precondition_takes_ended_stopped_and_killed_runs():
    section = _text().split("## Before you start", 1)[1].split("## The pass", 1)[0]
    before = " ".join(section.split())
    for phrase in ("ENDED", "STOPPED", "killed", "attempt records", "still going"):
        assert phrase in before
