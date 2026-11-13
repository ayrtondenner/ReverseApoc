"""The drive-budget project skill (.claude/skills/drive-budget/SKILL.md, todo
budget-runs-and-contributors): every arm it maps a request to has a quota.toml entry, and its
example command is one the drive verb parses, so a stale name never reaches a user."""

from __future__ import annotations

import re
import shlex

from conftest import REPO_ROOT
from reverseapoc import quota
from reverseapoc.cli import build_parser

SKILL = REPO_ROOT / ".claude" / "skills" / "drive-budget" / "SKILL.md"
_ROW_ARM = re.compile(r"^\|[^|]+\| `([^`]+)`(?: / `([^`]+)`)? \|", re.MULTILINE)


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_the_frontmatter_names_the_skill_by_when_to_use_it():
    text = _text()
    assert text.startswith("---\nname: drive-budget\ndescription: Use when ")


def test_every_mapped_arm_has_a_quota_entry():
    mapping = _text().split("## Map the request", 1)[1].split("\n## ", 1)[0]
    arms = [arm for row in _ROW_ARM.findall(mapping) for arm in row if arm]
    assert len(arms) >= 6, arms
    table = quota.load_quota()
    assert [arm for arm in arms if arm not in table] == []


def test_the_example_command_parses():
    block = _text().split("```\n", 2)[1]
    argv = shlex.split(block.replace("\\\n", " "))
    assert argv[:3] == ["uv", "run", "reverseapoc"]
    args = build_parser().parse_args(argv[3:])
    assert args.dry_run
    assert [(name, str(budget)) for name, budget in args.arm_budget] == [
        ("claude-haiku-5-5", "5%week"), ("gpt-6.1-terra", "100%5h"), ("deepseek-flash", "$30")]
    table = quota.load_quota()
    total = sum(quota.size(name, budget, table, max_sessions=None).sessions
                for name, budget in args.arm_budget)  # fmt: skip
    assert args.max_sessions == total == 340
