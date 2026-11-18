"""Third-party skills kept as installed under .claude/skills/ (docs/tools.md "Skill installation
decisions"): each is its upstream's bytes, with the source, commit and SKILL.md sha256 recorded."""

import hashlib
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_MD = REPO_ROOT / "docs" / "tools.md"
STOP_SLOP = REPO_ROOT / ".claude" / "skills" / "stop-slop"


def _recorded_sha256(skill: str) -> str:
    """The SKILL.md sha256 that docs/tools.md records on `skill`'s installation-decision line."""
    lines = [line for line in TOOLS_MD.read_text(encoding="utf-8").splitlines()
             if line.startswith(tuple(f"{n}. **{skill}**" for n in range(1, 20)))]  # fmt: skip
    assert len(lines) == 1, f"one installation-decision line for {skill} in docs/tools.md"
    found = re.search(r"`SKILL\.md` sha256 `([0-9a-f]{64})`", lines[0])
    assert found, f"{skill}'s line records its SKILL.md sha256"
    return found.group(1)


def test_stop_slop_is_the_recorded_upstream():
    """stop-slop (hardikpandya/stop-slop, MIT; the paper's prose, owner 2026-11-17) is vendored
    byte for byte: its SKILL.md hashes to the sha256 docs/tools.md records, and its licence is
    MIT."""
    digest = hashlib.sha256((STOP_SLOP / "SKILL.md").read_bytes()).hexdigest()
    assert digest == _recorded_sha256("stop-slop")
    assert "MIT" in (STOP_SLOP / "LICENSE").read_text(encoding="utf-8")
