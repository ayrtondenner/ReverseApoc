---
title: Refuse writes and test runs under the checkout while a drive holds its lock
created: 2026-11-17
area: hooks
files: tools/reverseapoc/hooks.py, tools/reverseapoc/locks.py
source: run 20261116-copilot3 (the coordinator's own breach of the CLAUDE.md drive rule)
---

# Nothing stops a coordinator from writing under the checkout during a drive

CLAUDE.md says nothing may write under the checkout while `reverseapoc drive` runs. On
2026-11-16 the coordinator edited `tools/reverseapoc/driver.py` and `tests/test_copilot.py` and
ran pytest in the checkout during run 20261116-copilot3. The audit caught it only afterwards:
it restored the edits, quarantined the bytecode and stopped the night, and the in-flight
sessions of every arm were lost.

**Do (test first):** a project PreToolUse hook (the existing `tools/reverseapoc/hooks.py`
pattern, wired in `.claude/settings.json`) that, while the drive lock exists and its process is
alive, refuses Edit/Write under the checkout and Bash commands that write there or run pytest,
uv sync or the CLI from it, naming the scratchpad-clone route instead. Reads stay allowed, and
the drive's own sessions are not affected (they run with their own settings). A stale lock
(no live process) does not block.

**Done when:** with a fake live lock, an Edit under `tools/` and `uv run pytest` in the checkout
are refused with that message, and both are allowed again once the lock is gone.

## Resolution (2026-11-18)

Done in batch 2026-11-18 (U9, merge 82719c21): the always hook refuses checkout writes and test runs under a live drive lock, default deny, after a security review.
