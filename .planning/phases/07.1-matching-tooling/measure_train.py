"""Phase 7.1 YAGNI measure: one plan train's numbers, for 07.1-YAGNI-MEASURE.md and -RESULTS.md.

    python measure_train.py SESSION FROM TO BASE HEAD

SESSION is a Claude Code session id; FROM and TO are the train's UTC window (ISO, as transcripts
stamp it); BASE and HEAD are commits (plan_head_before, then the last commit of the train, review
fixes included). Run from the repo root. BASE equal to HEAD measures tokens only.

A main-session message counts when its timestamp is in the window, a subagent by its first
message. Lines repeat one API message per content block, so usage is taken once per message id.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT = Path.home() / ".claude/projects/c--Users-Ayrton-Documents-Gitprojects-ReverseApoc"
WEIGHTS = {  # the owner's weights, relative to one input token
    "input_tokens": 1.0,
    "cache_read_input_tokens": 0.10,
    "cache_creation_input_tokens": 1.25,
    "output_tokens": 5.0,
}
INPUT_USD_PER_MTOK = {"claude-opus-5-5": 4.00}  # claude-api skill table, cached 2026-10-06
SYNTHETIC = "<synthetic>"  # a harness message; it has no real usage


def messages(path: Path) -> dict[str, tuple[str, str, dict]]:
    """message id -> (timestamp, model, usage), the last record of each id."""
    found = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if '"usage"' not in line:
            continue
        record = json.loads(line)
        message = record.get("message") or {}
        if message.get("id") and message.get("usage") and message.get("model") != SYNTHETIC:
            found[message["id"]] = (record.get("timestamp", ""), message["model"], message["usage"])
    return found


def effective(usage: dict) -> float:
    return sum(weight * (usage.get(key) or 0) for key, weight in WEIGHTS.items())


def train_messages(session: str, start: str, end: str) -> list[tuple[str, str, dict]]:
    main = messages(PROJECT / f"{session}.jsonl")
    picked = [m for m in main.values() if start <= m[0] <= end]
    for path in sorted((PROJECT / session / "subagents").glob("*.jsonl")):
        agent = messages(path)
        if agent and start <= min(m[0] for m in agent.values()) <= end:
            picked += agent.values()
    return picked


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def code_counts(base: str, head: str) -> tuple[int, int]:
    """Lines added under tools/ and test functions added under tests/."""
    numstat = git("diff", "--numstat", base, head, "--", "tools")
    lines = sum(int(row.split("\t")[0]) for row in numstat.splitlines() if row[0].isdigit())
    tests = re.findall(r"^\+\s*(?:async )?def test_", git("diff", base, head, "--", "tests"), re.M)
    return lines, len(tests)


def main() -> None:
    session, start, end, base, head = sys.argv[1:6]
    picked = train_messages(session, start, end)
    tokens = sum(effective(usage) for _, _, usage in picked)
    usd = sum(effective(usage) * INPUT_USD_PER_MTOK[model] / 1e6 for _, model, usage in picked)
    lines, tests = code_counts(base, head)
    print(f"L={lines} T={tests} E={round(tokens)} USD={usd:.2f} messages={len(picked)}")


if __name__ == "__main__":
    main()
